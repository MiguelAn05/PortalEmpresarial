"""
Quién hace qué con una solicitud de nota crédito.

**Primer módulo migrado a permisos por capacidad** (ver `core/capacidades.py`).
Antes esto era `usuario.rol == "admin" or usuario.area == "Contabilidad"`, y
la única forma de que otra área también tramitara notas crédito era
cambiarle el área a alguien — con lo que se le entregaba también todo lo
demás que Contabilidad decide en otros módulos. Ahora un administrador
otorga la capacidad desde Administración › Capacidades, a un área o a una
persona puntual, sin desplegar nada.

Contabilidad sigue teniendo las dos capacidades por defecto — eso lo dejó
sembrado la migración `d81f6a4c92e3`, no este archivo — así que para el caso
de todos los días nada cambió.

Autorizar (aprobar/rechazar) y registrar el número ya emitido son DOS
capacidades separadas (`notas_credito.autorizar` y `notas_credito.registrar`)
aunque hoy las tenga la misma gente: un administrador podría, por ejemplo,
darle a alguien solo el registro sin dejarlo aprobar montos. Antes una sola
función cubría las dos acciones, así que no había manera de separarlas.

Servicio al Cliente NO participa. Esto es un trámite entre el punto de venta
y quien tenga la capacidad; meterlos sería darles una bandeja más que
revisar sin que tengan nada que decidir en ella.
"""
from sqlalchemy.orm import Session

from app.core.capacidades import CAPACIDADES, quienes_tienen, tiene
from app.models.user import User

CAP_AUTORIZAR = "notas_credito.autorizar"
CAP_REGISTRAR = "notas_credito.registrar"

assert CAP_AUTORIZAR in CAPACIDADES and CAP_REGISTRAR in CAPACIDADES, (
    "Las capacidades de notas crédito ya no están en core/capacidades.py. "
    "Actualiza este módulo o nadie podrá autorizar ni registrar una nota "
    "crédito."
)


def puede_autorizar(db: Session, usuario: User) -> bool:
    """Aprobar o rechazar una solicitud."""
    return tiene(db, usuario, CAP_AUTORIZAR)


def puede_registrar(db: Session, usuario: User) -> bool:
    """Registrar el número de la nota crédito que ya se emitió."""
    return tiene(db, usuario, CAP_REGISTRAR)


def puede_radicar(usuario: User) -> bool:
    """
    Quién puede pedir una nota crédito.

    Hoy es cualquier usuario interno que escriba en el portal. La idea es que
    sean los puntos de venta y los vendedores institucionales, pero el usuario
    todavía no guarda a qué punto de venta pertenece —`User` tiene `area`, no
    canal—, así que no hay contra qué comprobarlo. Mientras tanto el punto de
    venta se elige de la lista cerrada al radicar y queda en el registro.
    """
    return usuario.rol not in ("lectura", "gerencia")


def puede_ver(db: Session, usuario: User, solicitud) -> bool:
    """
    Quién ve una solicitud.

    La ve quien la pidió, quien tenga CUALQUIERA de las dos capacidades —si
    solo viera con `puede_autorizar`, alguien a quien se le dio únicamente
    `notas_credito.registrar` podría registrar pero no encontrar la
    solicitud para hacerlo—, y los roles que ven todo el portal.

    Por defecto se cierra en vez de abrirse: una solicitud lleva números de
    factura y valores de un cliente, y ampliar después es más fácil que
    explicar por qué medio portal los estuvo viendo.
    """
    if usuario.rol in ("admin", "gerencia"):
        return True
    if puede_autorizar(db, usuario) or puede_registrar(db, usuario):
        return True
    return solicitud.solicitado_por == usuario.id


def mensaje_falta_capacidad(db: Session, tenant_id: int, capacidad: str, accion: str) -> str:
    """
    El mensaje del 403, armado con quién puede AHORA MISMO — no con un
    nombre de área quemado en el texto, que dejaría de ser cierto apenas un
    administrador reconfigure esto desde Administración › Capacidades.
    """
    areas = sorted({
        o.area for o in quienes_tienen(db, tenant_id, capacidad) if o.area
    })
    if areas:
        quien = f"el área de {' o '.join(areas)}" if len(areas) <= 2 else "alguna de estas áreas: " + ", ".join(areas)
    else:
        quien = "quien tenga el permiso otorgado"
    return (
        f"{accion} lo hace {quien}. Un administrador puede otorgar este "
        "permiso desde Administración › Capacidades."
    )
