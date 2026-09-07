"""
Los correos de las notas crédito.

Sin esto la función no sirve: hoy el punto de venta manda un correo y alguien
de Contabilidad lo ve llegar. Si el portal solo guardara la solicitud en una
pantalla, nadie sabría que hay algo esperando — habríamos cambiado un correo
que funciona por un tablero que nadie mira.

Se apoya en la maquinaria de avisos de PQRS (`enviar_avisos`, los correos por
área y el envoltorio que impide que notificar tumbe la petición) porque es
exactamente la misma y duplicarla sería tener dos sitios donde arreglar el
próximo webhook con un salto de línea al final.
"""
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User
from app.modules.pqrs.notificaciones import (
    Aviso, _correos_por_area, _protegido,
)
from app.modules.notas_credito.permisos import AREA_AUTORIZADORA

# El nombre del evento ES el path del webhook en n8n. Una prueba compara esta
# lista contra los flujos de `backend/n8n/`: un path mal escrito no falla, n8n
# contesta 404 y el correo simplemente no llega.
EVENTO_SOLICITADA = "nc-solicitada"
EVENTO_RESPONDIDA = "nc-respondida"

EVENTOS = frozenset({EVENTO_SOLICITADA, EVENTO_RESPONDIDA})


def _base(solicitud) -> dict:
    """Lo que ambos correos necesitan decir de la solicitud."""
    return {
        "solicitud_id": solicitud.id,
        "codigo": solicitud.codigo,
        "punto_venta": solicitud.punto_venta,
        "factura_afectada": solicitud.factura_afectada,
        "factura_reemplaza": solicitud.factura_reemplaza,
        "producto": solicitud.producto_nombre or "",
        "valor": str(solicitud.valor) if solicitud.valor is not None else "",
        "motivo": solicitud.motivo_nombre or "",
        "observaciones": (solicitud.observaciones or "")[:280],
        # El soporte se ANUNCIA, no se enlaza: /uploads no pide sesión, así que
        # una URL en un correo se reenvía sola. El botón lleva al portal.
        "tiene_adjunto": bool(solicitud.adjunto),
        "link_portal": f"{settings.FRONTEND_URL}/notas-credito",
    }


def _aviso_solicitada(db: Session, tenant_id: int, solicitud, solicitante: str) -> list[Aviso]:
    """Le avisa a Contabilidad que hay una nota crédito esperando su firma."""
    destinatarios = _correos_por_area(db, tenant_id, AREA_AUTORIZADORA)
    if not destinatarios:
        return []
    return [(EVENTO_SOLICITADA, {
        **_base(solicitud),
        "solicitada_por": solicitante,
        "destinatarios": destinatarios,
    })]


def _aviso_respondida(db: Session, tenant_id: int, solicitud, decision: str,
                      respondida_por: str) -> list[Aviso]:
    """
    Le avisa a QUIEN la pidió, no al área.

    Es una persona concreta la que está esperando para atender a su cliente;
    mandarlo al área entera sería que el aviso le llegue a todo el almacén
    menos, en la práctica, a quien tiene que actuar.
    """
    solicitante = db.get(User, solicitud.solicitado_por)
    if not solicitante or not solicitante.email or not solicitante.activo:
        return []
    return [(EVENTO_RESPONDIDA, {
        **_base(solicitud),
        "decision": decision,
        "respondida_por": respondida_por,
        "numero_nc": solicitud.numero_nc or "",
        "comentario": (solicitud.comentario_respuesta or "")[:280],
        "destinatarios": [solicitante.email],
    })]


def avisos_solicitada(db: Session, tenant_id: int, solicitud, solicitante: str) -> list[Aviso]:
    return _protegido(_aviso_solicitada, db, tenant_id, solicitud, solicitante)


def avisos_respondida(db: Session, tenant_id: int, solicitud, decision: str,
                      respondida_por: str) -> list[Aviso]:
    return _protegido(_aviso_respondida, db, tenant_id, solicitud, decision, respondida_por)
