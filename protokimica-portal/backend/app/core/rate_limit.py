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
