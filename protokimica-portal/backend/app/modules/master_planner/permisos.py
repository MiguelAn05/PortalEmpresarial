"""
Quién ve qué en Master Planner.

Regla: cada quien ve los proyectos de su área. Como hay proyectos que
involucran a varias áreas y gente a la que le asignan trabajo fuera de la
suya, la visibilidad se amplía por cuatro caminos:

  1. el proyecto es de tu área (responsable o participante),
  2. eres el líder del proyecto,
  3. tienes una tarea asignada dentro del proyecto,
  4. el proyecto no tiene área definida.

El punto 4 es deliberado: un proyecto sin clasificar no debe desaparecer
de la vista de nadie: si lo ocultáramos, se perdería sin que nadie note
que existe. Al quedar visible, además, empuja a que le pongan área.

`admin` y `gerencia` ven todo sin filtro.
"""
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.deps import ROLES_VISION_TOTAL
from app.models.master_planner import Proyecto, ProyectoArea, Tarea
from app.models.user import User


def ve_todo(usuario: User) -> bool:
    return usuario.rol in ROLES_VISION_TOTAL


def condicion_proyectos_visibles(usuario: User):
    """
    Condición SQLAlchemy para filtrar proyectos, o None si el usuario ve
    todo (en cuyo caso no hay que filtrar nada).
    """
    if ve_todo(usuario):
        return None

    caminos = [
        Proyecto.lider_id == usuario.id,
        Proyecto.id.in_(
            select(Tarea.proyecto_id).where(Tarea.asignado_a == usuario.id)
        ),
        Proyecto.area.is_(None),
    ]
    if usuario.area:
        caminos.append(Proyecto.area == usuario.area)
        caminos.append(
            Proyecto.id.in_(
                select(ProyectoArea.proyecto_id).where(ProyectoArea.area == usuario.area)
            )
        )
    return or_(*caminos)


def aplicar_filtro_proyectos(query, usuario: User):
    """Añade el filtro de visibilidad a una consulta que ya involucra Proyecto."""
    condicion = condicion_proyectos_visibles(usuario)
    return query if condicion is None else query.filter(condicion)


def puede_ver_proyecto(db: Session, proyecto: Proyecto, usuario: User) -> bool:
    """
    Comprueba la visibilidad de un proyecto concreto. Se usa en los
    endpoints de detalle, donde no hay una consulta a la que encadenar
    el filtro.
    """
    if ve_todo(usuario):
        return True
    if proyecto.lider_id == usuario.id or proyecto.area is None:
        return True
    if usuario.area and (
        proyecto.area == usuario.area or usuario.area in proyecto.areas_participantes
    ):
        return True
    tiene_tarea = db.query(
        select(Tarea.id)
        .where(Tarea.proyecto_id == proyecto.id, Tarea.asignado_a == usuario.id)
        .exists()
    ).scalar()
    return bool(tiene_tarea)


def puede_ver_presupuesto(proyecto: Proyecto, usuario: User) -> bool:
    """
    El presupuesto es información sensible: solo lo ve quien pertenece al
    proyecto por área o lo lidera. Alguien de otra área con una tarea
    asignada puede trabajar en el proyecto sin ver cuánta plata mueve.
    """
    if ve_todo(usuario):
        return True
    if proyecto.lider_id == usuario.id or proyecto.area is None:
        return True
    return bool(usuario.area) and (
        proyecto.area == usuario.area or usuario.area in proyecto.areas_participantes
    )
