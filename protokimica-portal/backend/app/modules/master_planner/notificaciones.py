"""
Avisos del Master Planner hacia n8n.

Mismo criterio que `pqrs/notificaciones.py`: el payload sale de aquí con
TODO lo que hace falta para escribir el correo — sobre todo el correo del
destinatario. Mandar el id del usuario obligaría a n8n a autenticarse contra
el portal para resolver algo que aquí ya se tiene a la mano.

Nada de esto puede tumbar la operación: `disparar_webhook_n8n` no lanza
excepciones y se llama después de guardar.
"""
from app.core.config import settings
from app.models.user import User
from app.modules.pqrs.service import disparar_webhook_n8n


def _link_tarea(tarea_id: int) -> str:
    return f"{settings.FRONTEND_URL}/master-planner/tareas/{tarea_id}"


def _link_proyecto(proyecto_id: int) -> str:
    return f"{settings.FRONTEND_URL}/master-planner/proyectos/{proyecto_id}"


def avisar_tarea_asignada(db, tarea, proyecto_nombre: str) -> None:
    """
    Avisa a quien le acaban de asignar una tarea.

    Sin destinatario no hay aviso: una tarea sin responsable, o con un
    usuario sin correo, no tiene a quién notificar y no es un error.
    """
    if not tarea.asignado_a:
        return

    usuario = db.get(User, tarea.asignado_a)
    if not usuario or not usuario.email:
        return

    disparar_webhook_n8n("mp-tarea-asignada", {
        "tarea_id": tarea.id,
        "titulo": tarea.titulo,
        "descripcion": (tarea.descripcion or "")[:280],
        "proyecto": proyecto_nombre,
        "prioridad": tarea.prioridad,
        "fecha_fin": tarea.fecha_fin.isoformat() if tarea.fecha_fin else None,
        "destinatario": usuario.email,
        "destinatario_nombre": usuario.nombre,
        "link_portal": _link_tarea(tarea.id),
    })


def avisar_proyecto_creado(db, proyecto) -> None:
    """Avisa al líder del proyecto que quedó a su cargo."""
    if not proyecto.lider_id:
        return

    lider = db.get(User, proyecto.lider_id)
    if not lider or not lider.email:
        return

    disparar_webhook_n8n("mp-proyecto-creado", {
        "proyecto_id": proyecto.id,
        "nombre": proyecto.nombre,
        "objetivo": (proyecto.objetivo or "")[:280],
        "area": proyecto.area,
        "prioridad": proyecto.prioridad,
        "fecha_fin_estimada": (
            proyecto.fecha_fin_estimada.isoformat()
            if proyecto.fecha_fin_estimada else None
        ),
        "destinatario": lider.email,
        "destinatario_nombre": lider.nombre,
        "link_portal": _link_proyecto(proyecto.id),
    })


def avisar_proyecto_cerrado(db, proyecto, acta) -> None:
    """
    Avisa que un proyecto se finalizó o se canceló.

    Va con las cifras del acta, no con las actuales: es lo que se firmó.
    Los destinatarios los resuelve n8n (gerencia, Calidad), porque a quién
    le interesa esto es una decisión de negocio que cambia sin tocar código.
    """
    disparar_webhook_n8n("mp-proyecto-cerrado", {
        "proyecto_id": proyecto.id,
        "nombre": proyecto.nombre,
        "area": proyecto.area,
        "tipo": acta.tipo,                      # finalizado | cancelado
        "motivo": acta.motivo,
        "entregables": acta.entregables,
        "observaciones": acta.observaciones,
        "cerrado_por": acta.cerrado_por_nombre,
        "tareas_completadas": acta.tareas_completadas,
        "tareas_total": acta.tareas_total,
        "presupuesto_planeado": float(acta.presupuesto_planeado or 0),
        "presupuesto_pagado": float(acta.presupuesto_pagado or 0),
        "link_portal": _link_proyecto(proyecto.id),
    })
