"""
El inicio del portal. Un solo endpoint que devuelve la página ya armada
según quién entra: sus pendientes, sus accesos y —si le corresponde— el
titular de la empresa y el estado de su área.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.modules.inicio.service import construir_inicio

router = APIRouter(prefix="/inicio", tags=["Inicio"])


@router.get("")
def inicio(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return construir_inicio(db, current_user)
