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

from app.core.deps import get_current_user
from app.models.user import User

AREA_SERVICIO_CLIENTE = "Servicio al cliente"


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
                "Solo el área de Servicio al cliente puede hacer esto. "
                "Si la PQRS ya está resuelta, pídele a Servicio al cliente que la cierre."
            ),
        )
    return current_user
