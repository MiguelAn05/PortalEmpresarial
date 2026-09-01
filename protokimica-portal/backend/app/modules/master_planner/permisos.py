"""
Quién ve qué en Master Planner.

**Regla: ves aquello en lo que participas. Un líder ve además lo de su
gente.**

Para cualquiera (agente, lectura) hay dos caminos:

  1. eres el líder del proyecto,
  2. tienes una tarea asignada dentro del proyecto.

Un **líder de área** suma un tercero: los proyectos de su equipo. Cuenta como
tal si el proyecto es de su área, o si alguien de su área lo lidera o tiene
trabajo adentro — aunque el proyecto sea de otra área. Es el caso de a quien
no es jefe pero le encargan liderar un proyecto: su jefe tiene que poder
mirarlo, o el área se queda sin quien responda por él.

Antes bastaba con ser del área para ver un proyecto, sin importar el rol. Eso
llenaba la pantalla a los agentes con veinte proyectos ajenos entre los que
buscar el suyo. La diferencia ahora es el rol: el que ejecuta ve lo suyo, el
que responde por un área ve lo de su gente.

El precio de esta regla es que **un proyecto sin líder y sin tareas no lo
ve nadie**. Por eso al crear un proyecto sin líder se pone a quien lo creó:
si no, desaparecería apenas se guarda (ver el router de proyectos).

`admin` y `gerencia` ven todo sin filtro, y también Administración y
Tesorería: aprueban y desembolsan la plata de TODOS los proyectos.
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


def _equipo_de(usuario: User):
    """
    Los usuarios del área de esta persona — sin los administradores.

    Un `admin` suele tener un área asignada (la suya de verdad), pero crea
    proyectos para TODA la empresa. Contarlo como parte del equipo haría que
    el jefe de esa área viera el portal entero, que es justo lo contrario de
    lo que se busca.
    """
    return select(User.id).where(
        User.tenant_id == usuario.tenant_id,
        User.area == usuario.area,
        User.rol != "admin",
    )


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

    # Participar es personal: lo lideras o te asignaron trabajo adentro.
    caminos = [
        Proyecto.lider_id == usuario.id,
        Proyecto.id.in_(
            select(Tarea.proyecto_id).where(Tarea.asignado_a == usuario.id)
        ),
    ]

    # Un líder responde por su área: ve también lo de su gente. Sin esto, a
    # quien le encargan liderar un proyecto sin ser jefe queda solo, porque
    # su jefe no podría ni abrirlo.
    if usuario.rol == "lider" and usuario.area:
        equipo = _equipo_de(usuario)
        # `condicion_area` y no `Proyecto.area == …`: cuenta también los
        # proyectos donde su área es PARTICIPANTE. Mirar solo la responsable
        # le escondía al líder de Mercadeo un proyecto de TICS en el que su
        # equipo trabaja — es el mismo defecto que ya había mordido en el
        # filtro por área, que aquí no se había corregido.
        caminos.append(condicion_area(usuario.area))
        caminos.append(Proyecto.lider_id.in_(equipo))
        caminos.append(
            Proyecto.id.in_(
                select(Tarea.proyecto_id).where(Tarea.asignado_a.in_(equipo))
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
    if proyecto.lider_id == usuario.id:
        return True

    es_jefe_del_area = usuario.rol == "lider" and usuario.area
    # Responsable o participante: la misma regla que la lista, o el proyecto
    # se vería en el listado y respondería 404 al abrirlo.
    if es_jefe_del_area and usuario.area in proyecto.areas_involucradas:
        return True

    tiene_tarea = db.query(
        select(Tarea.id)
        .where(Tarea.proyecto_id == proyecto.id, Tarea.asignado_a == usuario.id)
        .exists()
    ).scalar()
    if tiene_tarea:
        return True

    # ¿Alguien de su equipo participa? Es la misma pregunta de la lista, para
    # un solo proyecto.
    if es_jefe_del_area:
        equipo = _equipo_de(usuario)
        if proyecto.lider_id is not None:
            lider_es_suyo = db.query(
                select(User.id)
                .where(User.id == proyecto.lider_id,
                       User.area == usuario.area,
                       User.rol != "admin")
                .exists()
            ).scalar()
            if lider_es_suyo:
                return True
        return bool(db.query(
            select(Tarea.id)
            .where(Tarea.proyecto_id == proyecto.id, Tarea.asignado_a.in_(equipo))
            .exists()
        ).scalar())

    return False


def puede_ver_presupuesto(proyecto: Proyecto, usuario: User) -> bool:
    """
    El presupuesto es información sensible: solo lo ve quien lidera el
    proyecto. Alguien con una tarea asignada puede trabajar en el proyecto
    sin ver cuánta plata mueve.

    Administración y Tesorería son la excepción: aprueban y desembolsan la
    plata de TODOS los proyectos, así que sin acceso transversal no podrían
    hacer su trabajo.
    """
    if ve_todo(usuario):
        return True
    if puede_aprobar_pagos(usuario) or puede_registrar_pagos(usuario):
        return True
    if proyecto.lider_id == usuario.id:
        return True
    # El líder del área responsable: el presupuesto se le carga a su área, así
    # que responde por él aunque el proyecto lo lidere alguien de su equipo.
    # Tener una tarea adentro sigue sin dar acceso a la plata.
    return usuario.rol == "lider" and bool(usuario.area) and proyecto.area == usuario.area


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


def condicion_area(area: str):
    """
    Proyectos que le pertenecen a un área: los que lidera Y aquellos en los
    que participa.

    Es lo que espera quien filtra: si Mercadeo entró a un proyecto de TICS,
    al filtrar por Mercadeo ese proyecto tiene que salir. Mirar solo
    `Proyecto.area` lo escondía, y la gente de Mercadeo veía el proyecto en
    la lista general pero lo perdía apenas filtraba por su propia área.

    OJO: esto es para FILTRAR, no para atribuir. El presupuesto se le sigue
    cargando solo al área responsable (ver `resumen.py`); si se repartiera
    entre las participantes, un proyecto de 10 millones con tres áreas
    sumaría 30 en los totales por área.
    """
    return or_(
        Proyecto.area == area,
        Proyecto.id.in_(
            select(ProyectoArea.proyecto_id).where(ProyectoArea.area == area)
        ),
    )
