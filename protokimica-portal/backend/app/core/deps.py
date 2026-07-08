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

# Roles válidos del sistema
ROLES_VALIDOS = {"admin", "lider", "agente", "lectura"}


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
    """Bloquea usuarios de solo lectura en endpoints de escritura."""
    if current_user.rol == "lectura":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tu usuario es de solo lectura.",
        )
    return current_user