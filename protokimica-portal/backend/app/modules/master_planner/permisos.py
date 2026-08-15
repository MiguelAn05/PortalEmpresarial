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
from fastapi import Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.areas import AREAS as AREAS_EMPRESA
from app.core.deps import ROLES_VISION_TOTAL, get_current_user
from app.models.master_planner import Proyecto, ProyectoArea, Tarea
from app.models.user import User


# ── Aprobación y pago del presupuesto ─────────────────────────
# Dos manos distintas a propósito: quien autoriza el gasto no es quien lo
# desembolsa. Es el control básico que pide cualquier auditoría.
AREA_APRUEBA_PAGOS = "Administración"
AREA_REGISTRA_PAGOS = "Tesorería"

for _area in (AREA_APRUEBA_PAGOS, AREA_REGISTRA_PAGOS):
    assert _area in AREAS_EMPRESA, (
        f"'{_area}' ya no está en app/core/areas.py. Actualiza esta constante "
        "o nadie podrá aprobar ni registrar pagos."
    )


def puede_aprobar_pagos(usuario: User) -> bool:
    return usuario.rol == "admin" or usuario.area == AREA_APRUEBA_PAGOS


def puede_registrar_pagos(usuario: User) -> bool:
    return usuario.rol == "admin" or usuario.area == AREA_REGISTRA_PAGOS


def ve_todo(usuario: User) -> bool:
    """
    Quién ve todos los proyectos sin filtro de área.

    Además de admin y gerencia, entran Administración y Tesorería: aprueban y
    desembolsan la plata de TODOS los proyectos, así que un filtro por área
    les impediría hacer su trabajo. Ver el proyecto no les da permiso de
    editarlo — eso lo sigue decidiendo `solo_lectura_no`.
    """
    return (
        usuario.rol in ROLES_VISION_TOTAL
        or usuario.area in (AREA_APRUEBA_PAGOS, AREA_REGISTRA_PAGOS)
    )


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

    Administración y Tesorería son la excepción: aprueban y desembolsan la
    plata de TODOS los proyectos, así que sin acceso transversal no podrían
    hacer su trabajo.
    """
    if ve_todo(usuario):
        return True
    if puede_aprobar_pagos(usuario) or puede_registrar_pagos(usuario):
        return True
    if proyecto.lider_id == usuario.id or proyecto.area is None:
        return True
    return bool(usuario.area) and (
        proyecto.area == usuario.area or usuario.area in proyecto.areas_participantes
    )


def solo_aprueba_pagos(current_user: User = Depends(get_current_user)) -> User:
    if not puede_aprobar_pagos(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Solo el área de {AREA_APRUEBA_PAGOS} puede aprobar el pago de un "
                "ítem de presupuesto."
            ),
        )
    return current_user


def solo_registra_pagos(current_user: User = Depends(get_current_user)) -> User:
    if not puede_registrar_pagos(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Solo el área de {AREA_REGISTRA_PAGOS} puede registrar un pago. "
                f"Si el ítem ya está aprobado, pídele a {AREA_REGISTRA_PAGOS} que "
                "registre el desembolso."
            ),
        )
    return current_user


def puede_cerrar_proyecto(proyecto: Proyecto, usuario: User) -> bool:
    """
    Quién puede finalizar o cancelar un proyecto: su líder, y admin.

    Se decide por quién lidera y no solo por el rol, porque cerrar un
    proyecto es afirmar que se cumplió (o que se abandona), y eso le compete
    a quien responde por él. Un líder de otra área puede editar tareas donde
    participa, pero no dar por terminado un proyecto que no es suyo.
    """
    if usuario.rol == "admin":
        return True
    return proyecto.lider_id == usuario.id
