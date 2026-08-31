"""
Catálogo de productos: la entrada que usa el ERP y la búsqueda pública.

La sincronización NO usa una cuenta de usuario del portal: va con una clave
propia (CLAVE_SINCRONIZACION). Un proceso automático no debería tener las
credenciales de una persona — el día que esa persona cambie su contraseña o
se vaya de la empresa, la sincronización se cae sin que nadie sepa por qué.

Esa clave solo sirve para reemplazar el catálogo. No abre sesión, no lee
PQRS y no da acceso a nada más.
"""
import hmac

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_tenant_id, get_current_user
from app.models.tenant import Tenant
from app.models.user import User
from app.modules.catalogo import service

router = APIRouter(prefix="/catalogo", tags=["Catálogo de productos"])


class ProductoIn(BaseModel):
    codigo: str
    nombre: str
    presentacion: str | None = None


class SincronizacionIn(BaseModel):
    productos: list[ProductoIn]


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

    # TODO: `slug == "protokimica"` sigue quemado, como en el resto de lo
    # público. Cuando el portal sirva a más de una empresa, el tenant tendrá
    # que salir de la propia clave de sincronización.
    tenant = db.query(Tenant).filter(Tenant.slug == "protokimica").first()
    if not tenant:
        raise HTTPException(status_code=500, detail="Error de configuración.")

    if not payload.productos:
        raise HTTPException(
            status_code=400,
            detail=(
                "El lote llegó vacío. No se aplica: un error en la consulta del "
                "ERP dejaría el buscador sin ningún producto."
            ),
        )

    return service.sincronizar(
        db, tenant.id, [p.model_dump() for p in payload.productos],
    )


@router.get("/productos")
def buscar_productos(
    q: str = "",
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(get_current_user),
):
    """Buscador para el formulario interno de PQRS."""
    return service.buscar(db, tenant_id, q)
