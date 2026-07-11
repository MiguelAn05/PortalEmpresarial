"""
Notificaciones de PQRS.

Punto único donde se decide QUÉ se notifica y A QUIÉN, tanto para el
cliente (correo externo) como para los usuarios internos (por área/rol).
Los routers solo llaman a estas funciones en el momento en que ocurre
el evento — no arman payloads de n8n directamente.

Para agregar una notificación nueva en el futuro (ej. "PQRS vencida"):
  1. Crear una función nueva aquí, siguiendo el mismo patrón.
  2. Llamarla desde el router en el punto donde ocurre el evento.
  3. Armar el flujo correspondiente en n8n (mismo webhook, nuevo path).
No hace falta tocar nada más.

Eventos que disparamos hoy (nombres = path del webhook en n8n):
  - pqrs-creada-cliente     -> confirmación de radicación al cliente
  - pqrs-cerrada            -> aviso de cierre al cliente (+ encuesta)
  - pqrs-notificacion-area  -> aviso a los usuarios de un área
                                (motivo: "creacion" | "reasignacion")
"""
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User
from app.modules.pqrs.service import disparar_webhook_n8n


def _correos_por_area(db: Session, tenant_id: int, area: str) -> list[str]:
    """Correos de los usuarios activos del tenant que pertenecen a esa área."""
    if not area:
        return []

    area_norm = area.strip().lower()
    usuarios = (
        db.query(User)
        .filter(User.tenant_id == tenant_id, User.activo == True)  # noqa: E712
        .all()
    )
    return [
        u.email for u in usuarios
        if u.area and u.area.strip().lower() == area_norm and u.email
    ]


# ── Notificaciones al cliente (externas) ────────────────────────────

def notificar_cliente_creacion(solicitud) -> None:
    """Confirmación al cliente de que su PQRS fue radicada."""
    if not solicitud.cliente_email:
        return
    disparar_webhook_n8n("pqrs-creada-cliente", {
        "pqrs_id": solicitud.id,
        "codigo_seguimiento": solicitud.codigo_seguimiento,
        "cliente_nombre": solicitud.cliente_nombre,
        "cliente_email": solicitud.cliente_email,
        "tipo": solicitud.tipo,
        "link_seguimiento": f"{settings.FRONTEND_URL}/seguimiento",
    })


def notificar_cliente_cierre(solicitud) -> None:
    """Aviso al cliente de que su PQRS fue cerrada (con link a la encuesta)."""
    if not solicitud.cliente_email:
        return
    disparar_webhook_n8n("pqrs-cerrada", {
        "pqrs_id": solicitud.id,
        "codigo_seguimiento": solicitud.codigo_seguimiento,
        "cliente_nombre": solicitud.cliente_nombre,
        "cliente_email": solicitud.cliente_email,
        "tipo": solicitud.tipo,
        "area_responsable": solicitud.area_responsable,
        "link_seguimiento": f"{settings.FRONTEND_URL}/seguimiento",
    })


# ── Notificaciones internas (por área) ───────────────────────────────

def notificar_area(db: Session, tenant_id: int, solicitud, area: str, motivo: str) -> None:
    """
    Avisa únicamente a los usuarios pertenecientes a `area` — nunca a
    todo el sistema ni a otras áreas.

    motivo: "creacion"     -> se acaba de radicar y quedó asignada a esta área
            "reasignacion" -> se movió de otra área a esta
    """
    if not area:
        return

    destinatarios = _correos_por_area(db, tenant_id, area)
    if not destinatarios:
        return  # nadie configurado en esa área todavía — nada que enviar

    disparar_webhook_n8n("pqrs-notificacion-area", {
        "pqrs_id": solicitud.id,
        "codigo_seguimiento": solicitud.codigo_seguimiento,
        "radicado_calidad": solicitud.radicado_calidad,  # solo va lleno si area == Calidad
        "area": area,
        "motivo": motivo,
        "tipo": solicitud.tipo,
        "cliente_nombre": solicitud.cliente_nombre,
        "descripcion": (solicitud.descripcion or "")[:280],
        "destinatarios": destinatarios,
        "link_portal": f"{settings.FRONTEND_URL}/pqrs/{solicitud.id}",
    })
