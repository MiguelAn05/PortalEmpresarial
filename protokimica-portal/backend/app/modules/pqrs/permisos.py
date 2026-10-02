"""
Quién puede cerrar y reclasificar una PQRS.

Cerrar una PQRS y decidir si al final fue una petición, una queja o un
reclamo es responsabilidad de quien atiende el servicio al cliente: el tipo
que elige el cliente al radicar suele estar mal, y esa clasificación es la
que alimenta los indicadores y los reportes a Calidad.

**Lo decide la capacidad `pqrs.cerrar`, no el nombre de un área.** En
Protokimica la tiene el área «Servicio al Cliente» (ver
`core/capacidades.SEMILLA_INICIAL`), pero en otra empresa ese equipo se llama
distinto, y se configura en Administración › Capacidades sin tocar código.
Antes era una constante, `AREA_SERVICIO_CLIENTE`.
"""
from fastapi import Depends, HTTPException, status
from sqlalchemy import and_, not_, or_
from sqlalchemy.orm import Query, Session

from app.core import canales
from app.core import capacidades
from app.core import areas
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.pqrs import PQRSSolicitud
from app.models.user import User

CAPACIDAD_GESTION = "pqrs.cerrar"


def puede_gestionar_pqrs(usuario: User) -> bool:
    """Admin siempre puede: es el rol que destraba cuando algo se atasca."""
    return capacidades.del_usuario(usuario, CAPACIDAD_GESTION)


def solo_gestion_pqrs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """
    Dependencia para cerrar, reclasificar y repartir. El mensaje dice a
    quién pedirle el favor —sale de quién tiene la capacidad hoy—, no solo
    que no se puede.
    """
    if not puede_gestionar_pqrs(current_user):
        quien = capacidades.quienes_lo_hacen(db, current_user.tenant_id, CAPACIDAD_GESTION)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Esto lo hace {quien}. "
                f"Si la PQRS ya está resuelta, pídele a {quien} que la cierre."
            ),
        )
    return current_user


def puede_cambiar_area(usuario: User) -> bool:
    """
    Quién reparte el trabajo: Servicio al cliente, más admin.

    El área no es una etiqueta. Decide a quién le llega el aviso, en la
    bandeja de quién aparece el caso y contra quién corre el plazo. Si
    cualquiera pudiera moverla, un caso incómodo cambiaría de dueño sin que
    nadie lo hubiera decidido, y el reparto se quedaría sin responsable.

    La excepción la pone el flujo, no una persona: al pedir una autorización
    la PQRS pasa sola al área autorizadora, y al responderla vuelve sola.
    Eso no es reasignar a mano — es el caso siguiendo su curso.
    """
    return puede_gestionar_pqrs(usuario)


# ── Qué PQRS ve cada quien ─────────────────────────────────────────────
#
# Todo el portal ve todas las PQRS, MENOS el área «Puntos de Venta». A una
# sede le interesan las de su mostrador: las de las otras cinco y las de
# Venta institucional son ruido que tiene que saltarse para encontrar lo suyo.
#
# **Por qué por punto y no solo por área.** Solo con el área, Guayabal vería
# también las de Belén y tendría que filtrar cada vez que entra — y el
# filtro que hay que acordarse de poner es el que un día no se pone. Por eso
# cada usuario lleva su `punto_venta` (el prefijo), y el área queda como el
# caso del coordinador: alguien de «Puntos de Venta» SIN punto asignado ve
# los seis puntos, que es lo que necesita quien responde por todos.
#
# **Se reconoce por el canal Y por el prefijo del radicado.** Los dos salen
# del mismo dato al radicar; mirar ambos cubre una PQRS vieja a la que le
# falte uno de los dos.
#
# Lo que alguien le ASIGNA a una persona lo ve siempre, sea del punto que
# sea: si no, un caso asignado desaparecería de la bandeja de quien tiene que
# resolverlo.
#
# Fuera de su alcance, la PQRS responde 404 y no 403 — igual que Master
# Planner: no se confirma que exista algo que no te toca.

# El área de las sedes es la que tiene la marca `es_de_sedes` en
# Administración › Áreas (`areas.area_de_sedes`); antes era la constante
# `AREA_PUNTOS_DE_VENTA`. Las sedes son los canales de tipo `sede`.


def puntos_visibles(db: Session, usuario: User) -> list[str] | None:
    """
    Los canales de punto de venta a los que está acotada esta persona, o
    `None` si no tiene límite.

    `admin` y `gerencia` nunca tienen límite, aunque alguien les haya puesto
    el área: gerencia ve todas las áreas por definición, y admin es quien
    destraba.
    """
    if usuario.rol in ("admin", "gerencia"):
        return None
    if not usuario.area or usuario.area != areas.area_de_sedes(db, usuario.tenant_id):
        return None
    # Una sede desactivada sigue contando: quien estaba en ella sigue viendo
    # sus PQRS, que no dejaron de existir.
    sedes = canales.puntos_de_venta(db, usuario.tenant_id, incluir_inactivos=True)
    canal = canales.canal_por_codigo(db, usuario.tenant_id, usuario.punto_venta, solo_activos=False)
    if canal and canal.nombre in sedes:
        return [canal.nombre]
    return sedes


def _radicado_con_prefijo(prefijo: str, todos: list[str]):
    """
    El código empieza por `prefijo` y sigue con el número.

    LIKE no distingue «PVC» de «PVCR»: `PVCR0001` también empieza por `PVC`.
    Así que se excluyen explícitamente los prefijos más largos que arrancan
    igual; el resto del código son dígitos, no hay otra forma de confundirse.
    """
    columna = PQRSSolicitud.codigo_seguimiento
    condiciones = [columna.like(f"{prefijo}%")]
    for otro in todos:
        if otro != prefijo and otro.startswith(prefijo):
            condiciones.append(not_(columna.like(f"{otro}%")))
    return and_(*condiciones)


def filtrar_visibles(query: Query, usuario: User) -> Query:
    """Acota una consulta de `PQRSSolicitud` a lo que esta persona puede ver."""
    db = query.session
    puntos = puntos_visibles(db, usuario)
    if puntos is None:
        return query

    todos = canales.prefijos(db, usuario.tenant_id)
    condiciones = []
    for canal in puntos:
        condiciones.append(PQRSSolicitud.canal_atencion == canal)
        prefijo = canales.prefijo_de(db, usuario.tenant_id, canal)
        if prefijo:
            condiciones.append(_radicado_con_prefijo(prefijo, todos))
    condiciones.append(PQRSSolicitud.asignado_a == usuario.id)
    # El coordinador ve además lo que Servicio al Cliente le pasó al área,
    # aunque haya entrado por otro canal. A una sede no: no hay forma de
    # saber a cuál de las seis le tocaba.
    if len(puntos) > 1:
        condiciones.append(PQRSSolicitud.area_responsable == usuario.area)
    return query.filter(or_(*condiciones))


def obtener_visible(db: Session, tenant_id: int, pqrs_id: int, usuario: User) -> PQRSSolicitud:
    """
    La PQRS, si existe Y esta persona la puede ver. Si no, 404.

    Todo endpoint que reciba un `pqrs_id` pasa por aquí. La lista filtrada
    no basta: esconderla de la lista no impide escribir el número en la URL.
    """
    query = db.query(PQRSSolicitud).filter(
        PQRSSolicitud.id == pqrs_id, PQRSSolicitud.tenant_id == tenant_id,
    )
    solicitud = filtrar_visibles(query, usuario).first()
    if not solicitud:
        raise HTTPException(status_code=404, detail="PQRS no encontrada.")
    return solicitud
