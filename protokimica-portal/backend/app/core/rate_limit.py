"""
Freno de fuerza bruta para /auth/login.

Sin esto, cualquiera puede probar miles de contraseñas por segundo
contra el login. Con esto, una misma IP solo puede intentar 5 veces
por minuto — de ahí en adelante se bloquea temporalmente.

Si Redis no está disponible por algún motivo, se deja pasar la petición
(falla "abierto") para no tumbar el login completo del sistema por un
problema de infraestructura aparte; queda registrado en logs igual.
"""
import logging

from fastapi import HTTPException, Request

from app.core.redis_client import redis_client

logger = logging.getLogger(__name__)

MAX_INTENTOS = 5
VENTANA_SEGUNDOS = 60


def limitar_login(request: Request):
    ip = request.client.host if request.client else "desconocida"
    clave = f"login_intentos:{ip}"

    try:
        intentos = redis_client.incr(clave)
        if intentos == 1:
            redis_client.expire(clave, VENTANA_SEGUNDOS)

        if intentos > MAX_INTENTOS:
            ttl = redis_client.ttl(clave)
            raise HTTPException(
                status_code=429,
                detail=f"Demasiados intentos de inicio de sesión. Espera {max(ttl, 1)} segundos e intenta de nuevo.",
            )
    except HTTPException:
        raise
    except Exception:
        logger.warning("No se pudo aplicar el límite de login (Redis no disponible).")


# El buscador de productos vive en el formulario público, así que cualquiera
# en internet puede consultarlo. El límite no es contra fuerza bruta sino
# contra la enumeración: sin él, alguien con paciencia se descarga el
# catálogo entero letra por letra.
MAX_BUSQUEDAS = 30
VENTANA_BUSQUEDAS = 60


def limitar_busqueda_publica(request: Request):
    ip = request.client.host if request.client else "desconocida"
    clave = f"busqueda_productos:{ip}"

    try:
        consultas = redis_client.incr(clave)
        if consultas == 1:
            redis_client.expire(clave, VENTANA_BUSQUEDAS)

        if consultas > MAX_BUSQUEDAS:
            ttl = redis_client.ttl(clave)
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Demasiadas búsquedas seguidas. Espera {max(ttl, 1)} segundos. "
                    "Si no encuentras tu producto, escribe su nombre en la descripción."
                ),
            )
    except HTTPException:
        raise
    except Exception:
        # Igual que en el login: si Redis no está, se deja pasar. Perder el
        # límite es mejor que dejar sin formulario a quien quiere quejarse.
        logger.warning("No se pudo aplicar el límite de búsquedas (Redis no disponible).")
