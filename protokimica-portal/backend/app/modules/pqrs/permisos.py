"""
Quién puede cerrar y reclasificar una PQRS.

Cerrar una PQRS y decidir si al final fue una petición, una queja o un
reclamo es responsabilidad de Servicio al cliente: el tipo que elige el
cliente al radicar suele estar mal, y esa clasificación es la que alimenta
los indicadores y los reportes a Calidad.

Se resuelve por ÁREA y no por rol porque "Servicio al cliente" ya existe
como área y así se administra desde Admin › Usuarios cambiando el área de la
persona, sin un rol paralelo que pueda contradecirla.
"""
from fastapi import Depends, HTTPException, status
from sqlalchemy import and_, not_, or_
from sqlalchemy.orm import Query, Session

from app.core import canales
from app.core.areas import AREAS
from app.core.deps import get_current_user
from app.models.pqrs import PQRSSolicitud
from app.models.user import User

# Se toma de la lista de areas y no se escribe a mano: si alguien cambia
# como se escribe el area, esto tiene que moverse con ella o el cierre de
# PQRS deja de funcionar en silencio.
AREA_SERVICIO_CLIENTE = "Servicio al Cliente"
assert AREA_SERVICIO_CLIENTE in AREAS, (
    f"'{AREA_SERVICIO_CLIENTE}' ya no esta en app/core/areas.py. "
    "Actualiza esta constante o nadie podra cerrar PQRS."
)


def es_servicio_al_cliente(usuario: User) -> bool:
    """Admin siempre puede: es el rol que destraba cuando algo se atasca."""
    return usuario.rol == "admin" or usuario.area == AREA_SERVICIO_CLIENTE


def solo_servicio_al_cliente(current_user: User = Depends(get_current_user)) -> User:
    """
    Dependencia para los endpoints que solo puede usar Servicio al cliente.
    El mensaje dice a quién pedirle el favor, no solo que no se puede.
    """
    if not es_servicio_al_cliente(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Solo el área de Servicio al Cliente puede hacer esto. "
                "Si la PQRS ya está resuelta, pídele a Servicio al Cliente que la cierre."
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
    return es_servicio_al_cliente(usuario)


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

AREA_PUNTOS_DE_VENTA = "Puntos de Venta"
assert AREA_PUNTOS_DE_VENTA in AREAS, (
    f"'{AREA_PUNTOS_DE_VENTA}' ya no esta en app/core/areas.py. Actualiza "
    "esta constante o los puntos de venta volverian a ver todas las PQRS."
)


def puntos_visibles(usuario: User) -> list[str] | None:
    """
    Los canales de punto de venta a los que está acotada esta persona, o
    `None` si no tiene límite.

    `admin` y `gerencia` nunca tienen límite, aunque alguien les haya puesto
    el área: gerencia ve todas las áreas por definición, y admin es quien
    destraba.
    """
    if usuario.rol in ("admin", "gerencia") or usuario.area != AREA_PUNTOS_DE_VENTA:
        return None
    canal = canales.canal_por_codigo(usuario.punto_venta)
    if canal in canales.puntos_de_venta():
        return [canal]
    return canales.puntos_de_venta()


def _radicado_con_prefijo(prefijo: str):
    """
    El código empieza por `prefijo` y sigue con el número.

    LIKE no distingue «PVC» de «PVCR»: `PVCR0001` también empieza por `PVC`.
    Así que se excluyen explícitamente los prefijos más largos que arrancan
    igual; el resto del código son dígitos, no hay otra forma de confundirse.
    """
    columna = PQRSSolicitud.codigo_seguimiento
    condiciones = [columna.like(f"{prefijo}%")]
    for otro in canales.PREFIJOS_POR_CANAL.values():
        if otro != prefijo and otro.startswith(prefijo):
            condiciones.append(not_(columna.like(f"{otro}%")))
    return and_(*condiciones)


def filtrar_visibles(query: Query, usuario: User) -> Query:
    """Acota una consulta de `PQRSSolicitud` a lo que esta persona puede ver."""
    puntos = puntos_visibles(usuario)
    if puntos is None:
        return query

    condiciones = []
    for canal in puntos:
        condiciones.append(PQRSSolicitud.canal_atencion == canal)
        condiciones.append(_radicado_con_prefijo(canales.prefijo_de(canal)))
    condiciones.append(PQRSSolicitud.asignado_a == usuario.id)
    # El coordinador ve además lo que Servicio al Cliente le pasó al área,
    # aunque haya entrado por otro canal. A una sede no: no hay forma de
    # saber a cuál de las seis le tocaba.
    if len(puntos) > 1:
        condiciones.append(PQRSSolicitud.area_responsable == AREA_PUNTOS_DE_VENTA)
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
