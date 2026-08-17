"""
Qué módulos puede abrir cada quien.

Hasta ahora el portal solo controlaba la ESCRITURA (`solo_lectura_no`) y la
visibilidad por área dentro de Master Planner. Cualquier usuario autenticado
podía leer cualquier módulo — un agente de Logística veía todos los
indicadores de la empresa.

Esto se aplica en el backend, no escondiendo el menú: esconder un botón no
impide escribir la URL a mano.

Regla general: **el rol decide a qué módulo entras, el área decide qué ves
dentro.** Un líder entra a Indicadores, pero solo ve los de su área.
"""
from fastapi import Depends, HTTPException, status

from app.core.deps import get_current_user
from app.models.user import User

# modulo -> roles que pueden abrirlo. `admin` va en todos por definición.
ACCESO_POR_MODULO: dict[str, set[str]] = {
    "inicio": {"admin", "gerencia", "lider", "agente", "lectura"},
    "pqrs": {"admin", "gerencia", "lider", "agente", "lectura"},
    "master_planner": {"admin", "gerencia", "lider", "agente", "lectura"},
    # Un agente organiza su trabajo en PQRS y Master Planner; los indicadores
    # son de quien responde por ellos. El líder entra porque le toca registrar
    # los de su área cada mes.
    "indicadores": {"admin", "gerencia", "lider"},
    # Las encuestas quedan abiertas como PQRS: la satisfacción del cliente la
    # consulta cualquiera que atienda. Si un día hay que cerrarlas, se cambia
    # aquí y no en veinte endpoints.
    "encuestas": {"admin", "gerencia", "lider", "agente", "lectura"},
    "admin": {"admin"},
}

ETIQUETAS = {
    "inicio": "Inicio",
    "pqrs": "PQRS",
    "master_planner": "Master Planner",
    "indicadores": "Indicadores",
    "encuestas": "Encuestas",
    "admin": "Administración",
}


def puede_ver_modulo(usuario: User, modulo: str) -> bool:
    permitidos = ACCESO_POR_MODULO.get(modulo)
    if permitidos is None:
        raise ValueError(f"Módulo desconocido: '{modulo}'")
    return usuario.rol in permitidos


def modulos_de(usuario: User) -> list[str]:
    """Los módulos que este usuario puede abrir, en orden de menú."""
    return [m for m in ACCESO_POR_MODULO if puede_ver_modulo(usuario, m)]


def requiere_modulo(modulo: str):
    """
    Dependencia de FastAPI: corta el acceso a un módulo completo.

    Uso:  _: User = Depends(requiere_modulo("indicadores"))
    """
    def verificar(current_user: User = Depends(get_current_user)) -> User:
        if not puede_ver_modulo(current_user, modulo):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Tu rol no tiene acceso al módulo de {ETIQUETAS.get(modulo, modulo)}. "
                    "Si necesitas entrar, pídeselo a un administrador."
                ),
            )
        return current_user
    return verificar


# ── Alcance dentro de Indicadores ─────────────────────────────

def ve_todos_los_indicadores(usuario: User) -> bool:
    """
    Gerencia y admin ven la empresa completa. Un líder ve los indicadores de
    su área: son los que le toca responder y registrar.
    """
    return usuario.rol in ("admin", "gerencia")
