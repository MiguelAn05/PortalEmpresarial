"""
Refleja las tareas del Master Planner en el calendario de Outlook.

Va en una sola dirección: portal → Outlook. Lo que se hace en el portal se
ve en el calendario (y por lo tanto en Teams), pero editar el evento en
Outlook no cambia la tarea. Es a propósito: un evento de Outlook no tiene
proyecto, ni área, ni avance, así que no hay forma de traducir de vuelta
la mayoría de lo que importa.

Una tarea genera evento solo si tiene responsable y fecha. Sin responsable
no hay calendario donde ponerlo; sin fecha no hay dónde ubicarlo.
"""
import logging
from datetime import timedelta

from sqlalchemy.orm import Session

from app.core import graph
from app.core.config import settings
from app.models.master_planner import Tarea
from app.models.user import User

logger = logging.getLogger(__name__)

CATEGORIA = "Master Planner"


def _formato_graph(dt) -> str:
    """Graph espera la fecha sin zona; la zona va aparte, en timeZone."""
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def _cuerpo_html(tarea: Tarea, proyecto_nombre: str | None) -> str:
    partes = []
    if proyecto_nombre:
        partes.append(f"<p><b>Proyecto:</b> {proyecto_nombre}</p>")
    if tarea.descripcion:
        partes.append(f"<p>{tarea.descripcion}</p>")
    partes.append(
        f'<p><a href="{settings.FRONTEND_URL}/master-planner/tareas/{tarea.id}">'
        f"Abrir la tarea en el portal</a></p>"
    )
    partes.append(
        "<p style='color:#6B7EA8;font-size:12px'>"
        "Este evento lo crea el Portal Empresarial. Si lo mueves aquí, el "
        "portal no se entera: cambia la fecha en la tarea."
        "</p>"
    )
    return "".join(partes)


def construir_evento(tarea: Tarea, proyecto_nombre: str | None = None) -> dict | None:
    """
    Traduce la tarea al formato de evento de Graph.

    Con fecha de inicio y fin, va como bloque de horas. Si solo hay una de
    las dos, va como evento de día completo: es más honesto que inventarse
    una hora que nadie definió.

    Devuelve None si la tarea no da para un evento.
    """
    inicio = tarea.fecha_inicio
    fin = tarea.fecha_fin
    if not inicio and not fin:
        return None

    if inicio and fin:
        todo_el_dia = False
        # Un fin anterior al inicio dejaría un evento inválido en Graph.
        if fin <= inicio:
            fin = inicio + timedelta(hours=1)
        arranque, cierre = inicio, fin
    else:
        # Día completo: Graph pide medianoche a medianoche, y el cierre es
        # el día SIGUIENTE (si no, el evento no se ve o dura cero).
        todo_el_dia = True
        dia = (inicio or fin).replace(hour=0, minute=0, second=0, microsecond=0)
        arranque, cierre = dia, dia + timedelta(days=1)

    return {
        "subject": tarea.titulo,
        "body": {"contentType": "HTML", "content": _cuerpo_html(tarea, proyecto_nombre)},
        "start": {"dateTime": _formato_graph(arranque), "timeZone": settings.MS_ZONA_HORARIA},
        "end": {"dateTime": _formato_graph(cierre), "timeZone": settings.MS_ZONA_HORARIA},
        "isAllDay": todo_el_dia,
        "categories": [CATEGORIA],
    }


def _email_responsable(db: Session, tarea: Tarea) -> str | None:
    if not tarea.asignado_a:
        return None
    usuario = db.get(User, tarea.asignado_a)
    return usuario.email if usuario else None


def sincronizar_tarea(db: Session, tarea: Tarea, proyecto_nombre: str | None = None) -> None:
    """
    Crea, mueve o borra el evento de la tarea según cómo esté ahora.

    Se llama después de guardar. Nunca levanta excepciones: si Outlook
    falla, la tarea ya quedó guardada y eso es lo que importa.
    """
    if not graph.graph_configurado():
        return

    try:
        email = _email_responsable(db, tarea)
        evento = construir_evento(tarea, proyecto_nombre) if email else None

        # Se quedó sin responsable o sin fechas: el evento ya no aplica.
        if evento is None:
            if tarea.outlook_evento_id and email:
                graph.borrar_evento(email, tarea.outlook_evento_id)
            if tarea.outlook_evento_id:
                tarea.outlook_evento_id = None
                db.commit()
            return

        if tarea.outlook_evento_id:
            if graph.actualizar_evento(email, tarea.outlook_evento_id, evento):
                return
            # El evento se borró a mano en Outlook: se crea de nuevo en vez
            # de dejar la tarea sin nada en el calendario.
            tarea.outlook_evento_id = None

        evento_id = graph.crear_evento(email, evento)
        if evento_id:
            tarea.outlook_evento_id = evento_id
            db.commit()

    except Exception:
        logger.exception(
            "No se pudo sincronizar la tarea %s con Outlook. La tarea quedó "
            "guardada; solo falta el evento en el calendario.", tarea.id,
        )


def borrar_evento_en_calendario_de(db: Session, usuario_id: int, evento_id: str) -> None:
    """
    Quita un evento del calendario de un usuario concreto.

    Hace falta cuando una tarea cambia de responsable: el evento vive en la
    agenda del anterior, y si no se borra ahí le queda para siempre un
    compromiso que ya no es suyo.
    """
    if not graph.graph_configurado():
        return
    try:
        usuario = db.get(User, usuario_id)
        if usuario:
            graph.borrar_evento(usuario.email, evento_id)
    except Exception:
        logger.exception(
            "No se pudo quitar el evento %s del calendario del usuario %s.",
            evento_id, usuario_id,
        )


def borrar_evento_de_tarea(db: Session, tarea: Tarea) -> None:
    """Quita el evento del calendario. Se llama ANTES de borrar la tarea."""
    if not graph.graph_configurado() or not tarea.outlook_evento_id:
        return
    try:
        email = _email_responsable(db, tarea)
        if email:
            graph.borrar_evento(email, tarea.outlook_evento_id)
    except Exception:
        logger.exception(
            "No se pudo borrar en Outlook el evento de la tarea %s; "
            "puede quedar un evento huérfano en el calendario.", tarea.id,
        )
