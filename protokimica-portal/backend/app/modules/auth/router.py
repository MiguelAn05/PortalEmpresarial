"""
Endpoints de autenticación.
Cualquier persona puede registrarse con el correo que quiera (corporativo o
personal) siempre que indique a qué empresa (tenant_slug) pertenece.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token
from app.core.deps import get_current_user, get_current_tenant_id, require_role, ROLES_VALIDOS
from app.models.user import User
from app.models.tenant import Tenant
from app.modules.auth.schemas import (
    RegisterRequest, LoginRequest, TokenResponse, UserOut,
    UsuarioCreate, UsuarioUpdate, UsuarioOut,
)

router = APIRouter(prefix="/auth", tags=["Autenticación"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    tenant = db.query(Tenant).filter(Tenant.slug == payload.tenant_slug).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="La empresa (tenant) indicada no existe.")

    existing = (
        db.query(User)
        .filter(User.tenant_id == tenant.id, User.email == payload.email)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Ese correo ya está registrado en esta empresa.")

    user = User(
        tenant_id=tenant.id,
        nombre=payload.nombre,
        email=payload.email,
        password_hash=hash_password(payload.password),
        rol=payload.rol,
        area=payload.area,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    tenant = db.query(Tenant).filter(Tenant.slug == payload.tenant_slug).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="La empresa (tenant) indicada no existe.")

    user = (
        db.query(User)
        .filter(User.tenant_id == tenant.id, User.email == payload.email)
        .first()
    )
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos.")

    if not user.activo:
        raise HTTPException(status_code=403, detail="Tu usuario está inactivo. Contacta al administrador.")

    token = create_access_token(
        data={"sub": str(user.id), "tenant_id": user.tenant_id, "rol": user.rol}
    )
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user


# ─── Gestión de usuarios (solo admin, dentro de su propio tenant) ──────────
# A diferencia de /auth/register (público, para el primer ingreso a un
# tenant), estos endpoints requieren sesión de administrador y el tenant
# SIEMPRE se toma del token del admin logueado — nunca de lo que mande
# el cliente — para que un admin no pueda crear usuarios en otra empresa.

@router.get("/usuarios", response_model=list[UsuarioOut])
def listar_usuarios(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(require_role("admin")),
):
    return db.query(User).filter(User.tenant_id == tenant_id).order_by(User.nombre).all()


@router.post("/usuarios", response_model=UsuarioOut, status_code=status.HTTP_201_CREATED)
def crear_usuario(
    payload: UsuarioCreate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(require_role("admin")),
):
    if payload.rol not in ROLES_VALIDOS:
        raise HTTPException(
            status_code=400,
            detail=f"Rol inválido. Usa uno de: {', '.join(sorted(ROLES_VALIDOS))}."
        )

    existing = (
        db.query(User)
        .filter(User.tenant_id == tenant_id, User.email == payload.email)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Ese correo ya está registrado en tu empresa.")

    user = User(
        tenant_id=tenant_id,
        nombre=payload.nombre,
        email=payload.email,
        password_hash=hash_password(payload.password),
        rol=payload.rol,
        area=payload.area,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/usuarios/{usuario_id}", response_model=UsuarioOut)
def actualizar_usuario(
    usuario_id: int,
    payload: UsuarioUpdate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(require_role("admin")),
):
    usuario = (
        db.query(User)
        .filter(User.id == usuario_id, User.tenant_id == tenant_id)
        .first()
    )
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    if payload.rol is not None:
        if payload.rol not in ROLES_VALIDOS:
            raise HTTPException(
                status_code=400,
                detail=f"Rol inválido. Usa uno de: {', '.join(sorted(ROLES_VALIDOS))}."
            )
        if usuario.id == current_user.id and payload.rol != "admin":
            raise HTTPException(status_code=400, detail="No puedes quitarte tu propio rol de administrador.")
        usuario.rol = payload.rol

    if payload.area is not None:
        usuario.area = payload.area or None

    if payload.activo is not None:
        if usuario.id == current_user.id and payload.activo is False:
            raise HTTPException(status_code=400, detail="No puedes desactivar tu propia cuenta.")
        usuario.activo = payload.activo

    db.commit()
    db.refresh(usuario)
    return usuario
