"""
Qué pasa después de marcar una PQRS "resuelto".

Antes "resuelto" era casi lo mismo que "cerrado": una vez ahí, alguien tenía
que entrar y cambiarle el estado a mano, y el cliente nunca se enteraba de
qué se le había solucionado — solo le llegaba la encuesta al cerrar.

Ahora el cliente recibe la solución por correo (`avisos_resuelta`, en
`notificaciones.py`) y tiene dos formas de responder:

  1. Un clic en el correo — `confirmar_solucion()` o `rechazar_solucion()`,
     públicas, sin sesión: es SU caso, no hace falta que tenga cuenta en
     el portal.
  2. No responder. Pasados `DIAS_ESPERA_CLIENTE` días hábiles desde que
     entró a "resuelto", `cerrar_vencidas()` la cierra sola.

**Esto no es un sexto estado.** Sigue siendo "resuelto", con una fecha
(`fecha_resuelto`) de la que sale el plazo. Meter un estado nuevo habría
obligado a tocar cada semáforo, filtro e indicador que ya conoce los cinco
estados actuales, para algo que se resuelve con una columna.

**El plazo legal de respuesta (Ley 1480 de 2011, los días hábiles que ya
calcula `fecha_limite_sla`) se cumple al llegar a "resuelto" con una
solución real — no al cerrar.** Los `DIAS_ESPERA_CLIENTE` son una política
de calidad de la empresa, no un trámite legal, y por eso el correo nunca
dice que el silencio del cliente tenga una consecuencia jurídica: dice que
así se cierra el caso en el portal, y que puede reabrirlo cuando quiera.
"""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.dias_habiles import limite_en_habiles
from app.models.pqrs import PQRSEncuesta, PQRSSeguimiento, PQRSSolicitud
from app.modules.pqrs.notificaciones import (
    Aviso, DIAS_ESPERA_CLIENTE, avisos_cierre, avisos_cliente_rechazo,
)


def plazo_confirmacion(fecha_resuelto: datetime) -> datetime:
    """La fecha y hora en que una PQRS resuelta se cierra sola si nadie contesta."""
    return limite_en_habiles(fecha_resuelto, DIAS_ESPERA_CLIENTE)


def _cerrar(db: Session, solicitud: PQRSSolicitud, comentario: str) -> None:
    """Lo que comparten las tres formas de cerrar: la propia, la del cliente y la automática."""
    solicitud.estado = "cerrado"
    solicitud.fecha_cierre = datetime.now(timezone.utc)
    if not solicitud.encuesta:
        db.add(PQRSEncuesta(pqrs_id=solicitud.id))
    db.add(PQRSSeguimiento(
        pqrs_id=solicitud.id,
        usuario_id=None,  # sin actor humano: lo dispara el cliente o el reloj
        tipo_evento="cambio_estado",
        comentario=comentario,
        estado_nuevo="cerrado",
    ))


def confirmar_solucion(db: Session, solicitud: PQRSSolicitud) -> list[Aviso]:
    """El cliente dice que sí quedó bien: cierra al instante."""
    _cerrar(db, solicitud, "El cliente confirmó que la solución fue satisfactoria.")
    db.commit()
    db.refresh(solicitud)
    return avisos_cierre(solicitud, motivo_cierre="cliente_confirmo")


def rechazar_solucion(db: Session, solicitud: PQRSSolicitud,
                      comentario_cliente: str) -> list[Aviso]:
    """
    El cliente dice que NO quedó bien: reabre a "en proceso" con su
    comentario, y se acabó el plazo de espera — `fecha_resuelto` se borra
    para que el trabajo de cierre automático no la toque mientras se está
    retomando.
    """
    solicitud.estado = "en_proceso"
    solicitud.fecha_resuelto = None
    db.add(PQRSSeguimiento(
        pqrs_id=solicitud.id,
        usuario_id=None,
        tipo_evento="cambio_estado",
        comentario=(
            f"El cliente indicó que la solución no fue suficiente: "
            f"«{comentario_cliente.strip()}»"
        ),
        estado_nuevo="en_proceso",
    ))
    db.commit()
    db.refresh(solicitud)
    return avisos_cliente_rechazo(db, solicitud.tenant_id, solicitud, comentario_cliente)


def cerrar_vencidas(db: Session, tenant_id: int) -> list[tuple[PQRSSolicitud, list[Aviso]]]:
    """
    Cierra las PQRS "resuelto" cuyo plazo de confirmación ya venció.

    Lo llama una automatización una vez al día (ver `n8n/pqrs-cerrar-vencidas.json`),
    igual que ya se hace con el recordatorio de PQRS por vencer. Devuelve,
    por cada una que cerró, la solicitud y sus avisos — el router es quien
    los manda, después de responder.
    """
    ahora = datetime.now(timezone.utc)
    candidatas = (
        db.query(PQRSSolicitud)
        .filter(
            PQRSSolicitud.tenant_id == tenant_id,
            PQRSSolicitud.estado == "resuelto",
            PQRSSolicitud.fecha_resuelto.isnot(None),
        )
        .all()
    )

    cerradas = []
    for solicitud in candidatas:
        if ahora < plazo_confirmacion(solicitud.fecha_resuelto):
            continue
        _cerrar(
            db, solicitud,
            f"Cerrada automáticamente: el cliente no respondió en "
            f"{DIAS_ESPERA_CLIENTE} días hábiles.",
        )
        db.commit()
        db.refresh(solicitud)
        cerradas.append((solicitud, avisos_cierre(solicitud, motivo_cierre="automatico")))

    return cerradas
