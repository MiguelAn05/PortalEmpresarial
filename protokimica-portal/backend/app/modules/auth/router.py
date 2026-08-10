"""
Endpoints de autenticación.
El registro público (/register) está cerrado por defecto — requiere una
llave de configuración (REGISTER_SETUP_KEY) y solo se usa para crear el
primer admin de una empresa nueva. La creación de usuarios del día a día
se hace desde /usuarios (requiere sesión de administrador).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import settings
from app.core.security import hash_password, verify_password, create_access_token
from app.core.deps import get_current_user, get_current_tenant_id, require_role, ROLES_VALIDOS
from app.core.rate_limit import limitar_login
from app.models.user import User
from app.models.tenant import Tenant
from app.modules.auth.schemas import (
    RegisterRequest, LoginRequest, TokenResponse, UserOut,
    UsuarioCreate, UsuarioUpdate, UsuarioOut, CambiarPasswordRequest,
)

router = APIRouter(prefix="/auth", tags=["Autenticación"])


def validar_dominio_email(email: str) -> None:
    """
    Solo se crean usuarios con correo de la empresa. No es una formalidad:
    quien entra con un correo personal no tiene buzón corporativo, así que
    nada de lo que dependa de la cuenta de la empresa (calendario de
    Outlook, notificaciones) le va a llegar nunca.

    Se configura con DOMINIOS_EMAIL_PERMITIDOS; vacío = se acepta cualquiera.
    """
    dominios = settings.dominios_email_list
    if not dominios:
        return

    dominio = email.rsplit("@", 1)[-1].lower()
    if dominio not in dominios:
        permitidos = ", ".join("@" + d for d in dominios)
        raise HTTPException(
            status_code=400,
            detail=(
                f"El correo debe ser corporativo ({permitidos}). "
                f"Pídele a la persona su cuenta de la empresa; si de verdad "
                f"necesita entrar con otro dominio, agrégalo a "
                f"DOMINIOS_EMAIL_PERMITIDOS en el .env del servidor."
            ),
        )


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    # Sin llave configurada en el servidor, o si no coincide, el endpoint
    # queda completamente cerrado. Esto evita que cualquier persona en
    # internet pueda crearse una cuenta (incluso de administrador) sola.
    if not settings.REGISTER_SETUP_KEY or payload.setup_key != settings.REGISTER_SETUP_KEY:
        raise HTTPException(status_code=403, detail="No autorizado para registrar usuarios por esta vía.")

    validar_dominio_email(payload.email)

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
def login(payload: LoginRequest, db: Session = Depends(get_db), _: None = Depends(limitar_login)):
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


@router.post("/cambiar-password")
def cambiar_password(
    payload: CambiarPasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(payload.password_actual, current_user.password_hash):
        raise HTTPException(status_code=400, detail="La contraseña actual no es correcta.")
    if len(payload.password_nueva) < 6:
        raise HTTPException(status_code=400, detail="La nueva contraseña debe tener al menos 6 caracteres.")

    current_user.password_hash = hash_password(payload.password_nueva)
    db.commit()
    return {"mensaje": "Contraseña actualizada correctamente."}


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

    validar_dominio_email(payload.email)

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

    if payload.password is not None:
        if len(payload.password) < 6:
            raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 6 caracteres.")
        usuario.password_hash = hash_password(payload.password)

    if payload.activo is not None:
        if usuario.id == current_user.id and payload.activo is False:
            raise HTTPException(status_code=400, detail="No puedes desactivar tu propia cuenta.")
        usuario.activo = payload.activo

    db.commit()
    db.refresh(usuario)
    return usuario
