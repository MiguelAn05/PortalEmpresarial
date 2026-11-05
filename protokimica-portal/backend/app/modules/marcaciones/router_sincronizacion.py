"""
La entrada de las marcaciones: la usa el script del servidor de ZKBio.

No usa una cuenta de usuario del portal: va con una clave propia
(`CLAVE_MARCACIONES`). Un proceso automático no debería tener las credenciales
de una persona — el día que cambie su contraseña o se vaya de la empresa, la
sincronización se cae sin que nadie sepa por qué. Esa clave solo sirve para
enviar marcaciones y malla: no abre sesión ni lee nada.

El portal nunca se conecta al reloj. Es el script quien empuja, así que no
existe ninguna credencial ni ruta desde el portal —expuesto a internet— hacia
el servidor de ZKBio.
"""
import hmac

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.modulos import contratados_de
from app.core.tenant_publico import tenant_publico
from app.models.tenant import Tenant
from app.modules.marcaciones import constants as C
from app.modules.marcaciones import service
from app.modules.marcaciones.schemas import SincronizacionIn

router = APIRouter(prefix="/marcaciones", tags=["Marcaciones"])


def _verificar_clave(clave: str | None) -> None:
    """Se compara con `compare_digest`: el tiempo de respuesta no delata cuántos caracteres acertó quien lo intente."""
    esperada = settings.CLAVE_MARCACIONES
    if not esperada:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="La sincronización de marcaciones no está configurada. Falta CLAVE_MARCACIONES en el .env del servidor.",
        )
    if not clave or not hmac.compare_digest(clave, esperada):
        raise HTTPException(status_code=403, detail="Clave de sincronización inválida.")


def _empresa_con_marcaciones(db: Session) -> Tenant:
    # Cuando el portal sirva a más de una empresa, el tenant tendrá que salir
    # de la propia clave (ver `core/tenant_publico.py`).
    tenant = tenant_publico(db)
    if "marcaciones" not in contratados_de(tenant):
        raise HTTPException(status_code=403, detail="La empresa no tiene contratado el módulo de Marcaciones.")
    return tenant


def _rechazar(db: Session, tenant_id: int, error: HTTPException):
    """Deja constancia del intento fallido y lo devuelve tal cual al script."""
    db.rollback()
    service.registrar(db, tenant_id, error=str(error.detail))
    db.commit()
    raise error


@router.post("/sincronizar")
def sincronizar(
    payload: SincronizacionIn,
    x_clave_marcaciones: str | None = Header(None),
    db: Session = Depends(get_db),
):
    """
    Aplica un envío del reloj: marcaciones nuevas (sin duplicar) y, si vienen,
    la malla de turnos, los festivos y las excepciones.

    Un lote vacío se rechaza: un error en la lectura de ZKBio no debe parecer
    «hoy nadie marcó», ni una malla vacía dejar a todos desactivados.
    """
    _verificar_clave(x_clave_marcaciones)
    tenant = _empresa_con_marcaciones(db)

    if payload.empleados is not None and not payload.empleados:
        _rechazar(db, tenant.id, HTTPException(status_code=400, detail=(
            "La malla llegó vacía. No se aplica: dejaría a todos desactivados.")))
    if payload.festivos is not None and not payload.festivos:
        _rechazar(db, tenant.id, HTTPException(status_code=400, detail=(
            "La lista de festivos llegó vacía. No se aplica: se borrarían todos.")))
    if not any([payload.empleados, payload.marcaciones, payload.festivos, payload.excepciones is not None]):
        _rechazar(db, tenant.id, HTTPException(status_code=400, detail=(
            "El envío llegó vacío. No se aplica: un error en la lectura de ZKBio no debe verse como «nadie marcó».")))
    if len(payload.marcaciones or []) > C.MAX_MARCACIONES_POR_ENVIO:
        _rechazar(db, tenant.id, HTTPException(status_code=413, detail=(
            f"El envío trae más de {C.MAX_MARCACIONES_POR_ENVIO} marcaciones. Mándalas por tramos de días.")))

    try:
        resumen = service.sincronizar(db, tenant.id, payload.model_dump())
    except Exception as exc:  # noqa: BLE001 — se registra y se re-lanza: el script debe ver el fallo
        db.rollback()
        service.registrar(db, tenant.id, error=f"{type(exc).__name__}: {exc}"[:500])
        db.commit()
        raise
    service.registrar(db, tenant.id, resumen=resumen)
    db.commit()
    return resumen
