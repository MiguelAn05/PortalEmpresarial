"""
Administrar quién tiene cada capacidad.

Solo `admin`: es quien decide a quién se le abre una excepción, la misma
lógica que ya rige en Administración › Tipos de autorización y › Usuarios.
Ver `core/capacidades.py` para el porqué del diseño completo.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core import capacidades as cap
from app.core.areas import AREAS
from app.core.database import get_db
from app.core.deps import get_current_tenant_id, require_role
from app.models.user import User
from app.modules.capacidades.schemas import (
    CapacidadOut, OtorgamientoOut, OtorgarCapacidad,
)

router = APIRouter(prefix="/capacidades", tags=["Capacidades"])


@router.get("", response_model=list[CapacidadOut])
def listar_capacidades(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(require_role("admin")),
):
    """
    El catálogo entero, cada capacidad con quién la tiene hoy.

    Se siembra aquí, no al arrancar el servidor: igual que los catálogos de
    Mejora, así una empresa nueva no necesita un paso manual y la siembra no
    corre en cada arranque sin que nadie la esté pidiendo.
    """
    cap.sembrar_capacidades_iniciales(db, tenant_id, current_user.id)
    return [
        CapacidadOut(
            clave=clave,
            descripcion=descripcion,
            otorgamientos=[
                OtorgamientoOut.model_validate(o)
                for o in cap.quienes_tienen(db, tenant_id, clave)
            ],
        )
        for clave, descripcion in cap.CAPACIDADES.items()
    ]


@router.post("/{capacidad}/otorgar", response_model=OtorgamientoOut, status_code=201)
def otorgar(
    capacidad: str,
    payload: OtorgarCapacidad,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(require_role("admin")),
):
    if capacidad not in cap.CAPACIDADES:
        raise HTTPException(status_code=404, detail=f"'{capacidad}' no es una capacidad del portal.")

    if payload.area:
        if payload.area not in AREAS:
            raise HTTPException(
                status_code=400,
                detail=f"'{payload.area}' no es un área del portal. Elige una de la lista.",
            )
        otorgamiento = cap.otorgar_a_area(db, tenant_id, capacidad, payload.area, current_user.id)
    else:
        usuario = db.query(User).filter(
            User.id == payload.usuario_id, User.tenant_id == tenant_id,
        ).first()
        if not usuario:
            raise HTTPException(status_code=404, detail="Ese usuario no existe.")
        otorgamiento = cap.otorgar_a_usuario(db, tenant_id, capacidad, usuario.id, current_user.id)

    return otorgamiento


@router.delete("/otorgamientos/{otorgamiento_id}", status_code=204)
def revocar(
    otorgamiento_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(require_role("admin")),
):
    cap.revocar(db, tenant_id, otorgamiento_id)
