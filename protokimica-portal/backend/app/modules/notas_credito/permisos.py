"""
Quién hace qué con una solicitud de nota crédito.

Igual que en el resto del portal, **cuando el permiso depende del trabajo va
por ÁREA y no por cargo**: autoriza quien trabaja en Contabilidad, sea líder o
auxiliar. Amarrarlo al rol dejaría fuera a la analista que hoy responde estos
correos, y obligaría a cambiarle el cargo solo para que pueda firmar.

Servicio al Cliente NO participa. Esto es un trámite entre el punto de venta y
Contabilidad; meterlos sería darles una bandeja más que revisar sin que tengan
nada que decidir en ella.
"""
from app.core.areas import AREAS
from app.models.user import User

# La escritura exacta importa: se compara como texto. Si alguien renombra el
# área en core/areas.py, este assert revienta al arrancar en vez de dejar el
# permiso roto en silencio — que es como se pierde una firma sin que nadie
# entienda por qué.
AREA_AUTORIZADORA = "Contabilidad"
assert AREA_AUTORIZADORA in AREAS, (
    f"'{AREA_AUTORIZADORA}' ya no está en app/core/areas.py. Actualiza esta "
    "constante o nadie podrá autorizar notas crédito."
)


def puede_autorizar(usuario: User) -> bool:
    """Aprobar, rechazar y registrar el número de la nota crédito emitida."""
    return usuario.rol == "admin" or usuario.area == AREA_AUTORIZADORA


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


def puede_ver(usuario: User, solicitud) -> bool:
    """
    Quién ve una solicitud.

    Regla provisional, a la espera de definir a quién más le interesa: la ve
    quien la pidió, quien la autoriza, y los roles que ven todo el portal.
    Por defecto se cierra en vez de abrirse — una solicitud lleva números de
    factura y valores de un cliente, y ampliar después es más fácil que
    explicar por qué medio portal los estuvo viendo.
    """
    if usuario.rol in ("admin", "gerencia"):
        return True
    if puede_autorizar(usuario):
        return True
    return solicitud.solicitado_por == usuario.id
