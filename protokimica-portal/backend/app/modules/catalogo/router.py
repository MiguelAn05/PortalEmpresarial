"""
Catálogo de productos: la entrada que usa el ERP y la búsqueda pública.

La sincronización NO usa una cuenta de usuario del portal: va con una clave
propia (CLAVE_SINCRONIZACION). Un proceso automático no debería tener las
credenciales de una persona — el día que esa persona cambie su contraseña o
se vaya de la empresa, la sincronización se cae sin que nadie sepa por qué.

Esa clave solo sirve para reemplazar el catálogo y la lista de huellas de
clientes. No abre sesión, no lee PQRS y no da acceso a nada más.
"""
import hmac
from datetime import date

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.tenant_publico import tenant_publico
from app.core.modulos import contratado, contratados_de
from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_tenant_id, get_current_user, require_role
from app.models.tenant import Tenant
from app.models.user import User
from app.modules.catalogo import clientes, service

router = APIRouter(prefix="/catalogo", tags=["Catálogo de productos"])


# Los topes son los de las columnas de `cat_productos`: un valor más largo
# rechaza el lote entero con un 422 que dice cuál, en vez de reventar en el
# commit con un error de Postgres.
class ProductoIn(BaseModel):
    codigo: str = Field(max_length=60)
    nombre: str = Field(max_length=300)
    presentacion: str | None = Field(None, max_length=60)
    grupo: str | None = Field(None, max_length=60)
    fecha_ultima_venta: date | None = None


class SincronizacionIn(BaseModel):
    productos: list[ProductoIn]


class HuellasIn(BaseModel):
    # HMAC-SHA256 de cada NIT de cliente, en hexadecimal. Ver `clientes.py`.
    huellas: list[str]
    # La huella de `clientes.TEXTO_DE_CONTROL`: prueba que el script usa la
    # misma clave que el portal.
    control: str


def _verificar_clave(clave: str | None) -> None:
    """
    Valida la clave de sincronización.

    Se compara con `compare_digest` y no con `==` para que el tiempo de
    respuesta no delate cuántos caracteres acertó quien lo intente.
    """
    esperada = settings.CLAVE_SINCRONIZACION
    if not esperada:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "La sincronización del catálogo no está configurada. "
                "Falta CLAVE_SINCRONIZACION en el .env del servidor."
            ),
        )
    if not clave or not hmac.compare_digest(clave, esperada):
        raise HTTPException(status_code=403, detail="Clave de sincronización inválida.")


def _empresa_con_pqrs(db: Session) -> Tenant:
    # Cuando el portal sirva a más de una empresa, el tenant tendrá que salir
    # de la propia clave de sincronización (ver `core/tenant_publico.py`).
    tenant = tenant_publico(db)
    if "pqrs" not in contratados_de(tenant):
        raise HTTPException(
            status_code=403,
            detail="La empresa no tiene contratado PQRS, que es donde se usa el catálogo.",
        )
    return tenant


def _rechazar(db: Session, tenant_id: int, tipo: str, error: HTTPException):
    """Deja constancia del intento fallido y lo devuelve tal cual al script."""
    db.rollback()
    service.registrar(db, tenant_id, tipo, error=str(error.detail))
    db.commit()
    raise error


@router.post("/sincronizar")
def sincronizar_catalogo(
    payload: SincronizacionIn,
    x_clave_sincronizacion: str | None = Header(None),
    db: Session = Depends(get_db),
):
    """
    Reemplaza el catálogo con el lote que manda el ERP.

    Lo llama un proceso del lado de Oracle: el portal nunca se conecta a esa
    base. Así no existe ninguna credencial ni ruta desde el portal —que está
    expuesto a internet— hacia el servidor del ERP.
    """
    _verificar_clave(x_clave_sincronizacion)
    tenant = _empresa_con_pqrs(db)

    if not payload.productos:
        _rechazar(db, tenant.id, "productos", HTTPException(
            status_code=400,
            detail=(
                "El lote llegó vacío. No se aplica: un error en la consulta del "
                "ERP dejaría el buscador sin ningún producto."
            ),
        ))

    resumen = service.sincronizar(
        db, tenant.id, [p.model_dump() for p in payload.productos],
    )
    service.registrar(db, tenant.id, "productos", resumen=resumen)
    db.commit()
    return resumen


@router.post("/sincronizar-clientes")
def sincronizar_clientes(
    payload: HuellasIn,
    x_clave_sincronizacion: str | None = Header(None),
    db: Session = Depends(get_db),
):
    """
    Reemplaza la lista de huellas de clientes del ERP.

    Llegan huellas, no NIT: el script de MORFEO las calcula allá y los NIT no
    salen de la red interna. Ver `catalogo/clientes.py`.
    """
    _verificar_clave(x_clave_sincronizacion)
    tenant = _empresa_con_pqrs(db)

    if not payload.huellas:
        _rechazar(db, tenant.id, "clientes", HTTPException(
            status_code=400,
            detail=(
                "La lista de clientes llegó vacía. No se aplica: un error en la "
                "consulta del ERP dejaría a todos los clientes sin verificar."
            ),
        ))

    try:
        resumen = clientes.sincronizar(db, tenant.id, payload.huellas, payload.control)
    except HTTPException as error:
        _rechazar(db, tenant.id, "clientes", error)

    service.registrar(db, tenant.id, "clientes", resumen=resumen)
    db.commit()
    return resumen


@router.get(
    "/estado",
    dependencies=[Depends(contratado("pqrs")), Depends(require_role("admin"))],
)
def estado_sincronizacion(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """
    Cuándo mandó el ERP lo último y si salió bien.

    El script corre en otro servidor: si se cae, aquí es donde se nota.
    """
    return service.estado(db, tenant_id)


@router.get("/productos", dependencies=[Depends(contratado("pqrs"))])
def buscar_productos(
    q: str = "",
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(get_current_user),
):
    """Buscador para el formulario interno de PQRS."""
    return service.buscar(db, tenant_id, q)
