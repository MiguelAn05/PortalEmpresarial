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

from app.core.areas import AREAS
from app.core.deps import get_current_user
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
