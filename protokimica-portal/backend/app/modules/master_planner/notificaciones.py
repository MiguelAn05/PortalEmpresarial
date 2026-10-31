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
from app.core.notificaciones import Aviso, disparar_webhook_n8n


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


# Un solo evento para todo lo que le pasa a un documento, como `nc-en-turno`
# en Notas crédito: el asunto y qué hacer los redacta el backend, así que un
# movimiento nuevo no obliga a construir, importar y activar otro flujo.
EVENTO_DOCUMENTO = "mp-documento"

# Los que se mandan como aviso armado (no como llamada suelta): la prueba de
# `test_flujos_n8n.py` exige que cada uno tenga su flujo en `backend/n8n/`.
EVENTOS = frozenset({EVENTO_DOCUMENTO})


def _correo(usuario) -> bool:
    return bool(usuario and usuario.activo and usuario.email)


def avisos_documento(db, tarea, version) -> list[Aviso]:
    """
    El aviso del movimiento que acaba de pasar, leído del estado en que quedó
    la versión:

    - **en revisión** → a quien le toca firmar;
    - **devuelta** → a quien la preparó, con el comentario y cuántas
      observaciones tiene;
    - **aprobada** → a quien la preparó, con el líder del proyecto en copia.

    Si quien la preparó no tiene a dónde llegarle, va al líder: un documento
    devuelto que nadie se entera de que volvió se queda quieto.
    """
    from app.modules.master_planner import revision

    # Una tarea sin proyecto no tiene líder: el aviso va solo a su gente.
    lider = tarea.proyecto.lider if tarea.proyecto else None
    autor = tarea.asignado if _correo(tarea.asignado) else (lider if _correo(lider) else None)
    ultimo = version.eventos[-1] if version.eventos else None
    base = {
        "tarea_id": tarea.id,
        "titulo": tarea.titulo,
        "proyecto": tarea.proyecto_nombre,
        "documento": version.nombre_original,
        "version": version.numero,
        "quien": ultimo.usuario_nombre if ultimo else None,
        "comentario": ((ultimo.comentario or "")[:500] if ultimo else ""),
        "fecha_fin": tarea.fecha_fin.isoformat() if tarea.fecha_fin else None,
        "link_portal": f"{settings.FRONTEND_URL}/master-planner/documento/{version.id}",
        "en_copia": [],
    }

    if version.estado == "en_revision":
        paso = revision.paso_en_turno(tarea, version)
        if not paso or not _correo(paso.revisor):
            return []
        return [(EVENTO_DOCUMENTO, {
            **base, "tipo": "turno", "paso": paso.nombre,
            "destinatario": paso.revisor.email, "destinatario_nombre": paso.revisor.nombre,
            "asunto": f"Documento para tu firma · {tarea.titulo}",
            "que_hacer": f"Te toca revisarlo y firmarlo como {paso.nombre}. Si hay algo que corregir, "
                         "márcalo en el documento y devuélvelo.",
        })]

    if version.estado == "devuelta":
        if not autor:
            return []
        pendientes = sum(1 for o in version.observaciones if not o.atendida)
        return [(EVENTO_DOCUMENTO, {
            **base, "tipo": "devuelto", "paso": ultimo.paso_nombre if ultimo else None,
            "observaciones": pendientes,
            "destinatario": autor.email, "destinatario_nombre": autor.nombre,
            "asunto": f"Te devolvieron el documento · {tarea.titulo}",
            "que_hacer": (f"Tiene {pendientes} observaciones. " if pendientes else "")
                         + "Corrígelo en tu archivo original y sube la versión nueva desde la tarea: "
                           "vuelve a empezar por la primera firma.",
        })]

    if version.estado == "aprobada":
        if not autor:
            return []
        copia = [lider.email] if _correo(lider) and lider.id != autor.id else []
        return [(EVENTO_DOCUMENTO, {
            **base, "tipo": "aprobado", "paso": ultimo.paso_nombre if ultimo else None,
            "destinatario": autor.email, "destinatario_nombre": autor.nombre, "en_copia": copia,
            "asunto": f"Documento aprobado · {tarea.titulo}",
            "que_hacer": "Pasó todas las firmas y la tarea quedó cumplida. No hace falta hacer nada más.",
        })]

    return []
