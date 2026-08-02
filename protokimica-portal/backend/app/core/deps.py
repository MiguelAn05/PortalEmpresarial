"""
Dependencias reutilizables en TODOS los módulos (PQRS, Indicadores, Proyectos...).
get_current_user: protege cualquier endpoint exigiendo un JWT válido.
get_current_tenant_id: extrae el tenant del usuario logueado, para que cada
empresa solo vea sus propios datos.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# Roles válidos del sistema.
# - admin:    lo puede todo, incluida la configuración.
# - gerencia: ve TODO el portal sin límite de área, pero no modifica nada
#             estructural. Pensado para gerencia y dirección administrativa:
#             consultan indicadores, no operan. Lo único que sí puede hacer
#             es dejar comentarios/actualizaciones (ver `puede_comentar`).
# - lider:    opera su área.
# - agente:   opera lo que le asignan.
# - lectura:  no escribe nada.
ROLES_VALIDOS = {"admin", "gerencia", "lider", "agente", "lectura"}

# Roles que ven todas las áreas sin restricción.
ROLES_VISION_TOTAL = {"admin", "gerencia"}


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudo validar la sesión. Inicia sesión de nuevo.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    user_id = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None or not user.activo:
        raise credentials_exception
    return user


def get_current_tenant_id(current_user: User = Depends(get_current_user)) -> int:
    return current_user.tenant_id


def require_role(*roles: str):
    """
    Uso: Depends(require_role("admin", "lider"))
    Restringe un endpoint a ciertos roles.
    """
    def checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.rol not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Necesitas uno de estos roles: {', '.join(roles)}.",
            )
        return current_user
    return checker


def solo_lectura_no(current_user: User = Depends(get_current_user)) -> User:
    """
    Bloquea en endpoints de escritura a quien no debe modificar datos.

    Incluye a `gerencia` a propósito: ese rol existe para consultar todo el
    portal sin poder dañar nada. Al vivir el bloqueo aquí, cubre también los
    módulos que ya estaban en producción sin tener que tocarlos uno por uno.
    """
    if current_user.rol in ("lectura", "gerencia"):
        detalle = (
            "Tu usuario de gerencia tiene acceso de consulta a todo el portal, "
            "pero no puede modificar proyectos, tareas ni presupuesto."
            if current_user.rol == "gerencia"
            else "Tu usuario es de solo lectura."
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detalle)
    return current_user


def puede_comentar(current_user: User = Depends(get_current_user)) -> User:
    """
    Más permisivo que `solo_lectura_no`: deja pasar a `gerencia`.

    Se usa solo donde el aporte es un comentario o una actualización de
    seguimiento — cosas que suman contexto sin alterar la planeación.
    """
    if current_user.rol == "lectura":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tu usuario es de solo lectura.",
        )
    return current_user