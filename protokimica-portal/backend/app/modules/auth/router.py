"""
Endpoints de autenticación.
El registro público (/register) está cerrado por defecto — requiere una
llave de configuración (REGISTER_SETUP_KEY) y solo se usa para crear el
primer admin de una empresa nueva. La creación de usuarios del día a día
se hace desde /usuarios (requiere sesión de administrador).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core import bodegas, canales
from app.core.database import get_db
from app.core.config import settings
from app.core.security import hash_password, verify_password, create_access_token
from app.core.deps import get_current_user, get_current_tenant_id, require_role, ROLES_VALIDOS
from app.core.rate_limit import limitar_login
from app.core.areas import AREAS
from app.models.capacidad import CapacidadOtorgada
from app.models.user import AreaSupervisada, User
from app.models.tenant import Tenant
from app.modules.pqrs.permisos import AREA_PUNTOS_DE_VENTA
from app.modules.auth.rastros import explicar, rastros_de
from app.modules.auth.schemas import (
    RegisterRequest, LoginRequest, TokenResponse, UserOut,
    UsuarioCreate, UsuarioUpdate, UsuarioOut, CambiarPasswordRequest,
)

router = APIRouter(prefix="/auth", tags=["Autenticación"])


def resolver_areas_supervisadas(areas: list[str] | None, area_propia: str | None) -> list[str]:
    """
    Las áreas que se le guardan a alguien como supervisadas, ya validadas.

    Se quita la propia: supervisarla no agrega nada —ya la ve— y dejarla
    guardada haría que cambiar de área se llevara consigo una supervisión que
    nadie pidió.
    """
    limpias = []
    for area in areas or []:
        area = (area or "").strip()
        if not area:
            continue
        if area not in AREAS:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"«{area}» no es un área del portal. Elige una de la lista "
                    "para que la supervisión se pueda aplicar."
                ),
            )
        if area != area_propia and area not in limpias:
            limpias.append(area)
    return limpias


def aplicar_areas_supervisadas(usuario: User, areas: list[str]) -> None:
    """Deja exactamente esas: lo que no viene se quita, lo que falta se agrega."""
    actuales = {a.area: a for a in usuario.areas_supervisadas}
    for area, fila in actuales.items():
        if area not in areas:
            usuario.areas_supervisadas.remove(fila)
    for area in areas:
        if area not in actuales:
            usuario.areas_supervisadas.append(AreaSupervisada(area=area))


def resolver_punto_venta(prefijo: str | None, area: str | None) -> str | None:
    """
    El punto de venta que se le guarda a alguien, ya validado.

    Solo tiene sentido en el área «Puntos de Venta»: en cualquier otra se
    descarta, para que no quede un punto olvidado que vuelva a acotarle las
    PQRS el día que alguien lo pase de vuelta al área. Y tiene que ser una
    SEDE: «VI» tiene prefijo pero no es un mostrador donde trabaje alguien.
    """
    prefijo = (prefijo or "").strip().upper() or None
    if prefijo is None or area != AREA_PUNTOS_DE_VENTA:
        return None
    canal = canales.canal_por_codigo(prefijo)
    if canal not in canales.puntos_de_venta():
        validos = ", ".join(canales.prefijo_de(c) for c in canales.puntos_de_venta())
        raise HTTPException(
            status_code=400,
            detail=(
                f"«{prefijo}» no es un punto de venta. Elige uno de la lista "
                f"({validos}), o déjalo vacío si la persona coordina todos."
            ),
        )
    return prefijo


def resolver_bodega(nombre: str | None) -> str | None:
    """
    La bodega que se le guarda a alguien, ya validada.

    A diferencia del punto de venta, **no se amarra a un área**: el
    coordinador de La 65 está en Logística y el de Guayabal en Producción, y
    mañana pueden estar en otra. Lo que decide si esto significa algo es la
    capacidad `notas_credito.confirmar_producto`, que se otorga aparte.

    Vacío es «responde por las dos», igual que un usuario de Puntos de Venta
    sin punto coordina los seis.
    """
    bodega = bodegas.normalizar(nombre)
    if bodega is None:
        return None
    if not bodegas.es_valida(bodega):
        raise HTTPException(
            status_code=400,
            detail=(
                f"«{bodega}» no es una bodega del portal. Elige una de la "
                f"lista ({', '.join(bodegas.BODEGAS)}), o déjalo vacío si "
                "responde por todas."
            ),
        )
    return bodega


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
                f"Solicítale a la persona su cuenta de la empresa; si de verdad "
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
        punto_venta=resolver_punto_venta(payload.punto_venta, payload.area),
        bodega=resolver_bodega(payload.bodega),
    )
    aplicar_areas_supervisadas(
        user, resolver_areas_supervisadas(payload.areas_supervisadas, payload.area),
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

    if payload.nombre is not None:
        nombre = payload.nombre.strip()
        if not nombre:
            raise HTTPException(
                status_code=400,
                detail="El nombre no puede quedar vacío: es con lo que se le "
                       "reconoce en las asignaciones y en el historial.",
            )
        usuario.nombre = nombre

    if payload.email is not None:
        email = payload.email.strip().lower()
        if not email:
            raise HTTPException(
                status_code=400, detail="El correo no puede quedar vacío: es con lo que entra.",
            )
        validar_dominio_email(email)
        # Dentro de la misma empresa, claro: dos tenants pueden tener el
        # mismo correo y eso no es asunto de este admin.
        repetido = (
            db.query(User)
            .filter(User.tenant_id == tenant_id, User.email == email, User.id != usuario.id)
            .first()
        )
        if repetido:
            raise HTTPException(
                status_code=400,
                detail=f"Ese correo ya es de {repetido.nombre}. Cada persona entra con el suyo.",
            )
        usuario.email = email

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

    # Después del área a propósito: si en el mismo guardado sale de «Puntos
    # de Venta», el punto se le quita; si solo cambió el área, el punto que
    # tenía se revalida contra la nueva.
    if payload.areas_supervisadas is not None:
        aplicar_areas_supervisadas(
            usuario,
            resolver_areas_supervisadas(payload.areas_supervisadas, usuario.area),
        )
    elif "area" in payload.model_fields_set:
        # Cambió de área: si supervisaba la que ahora es la suya, esa fila
        # sobra — la ve por ser suya, no por supervisarla.
        aplicar_areas_supervisadas(
            usuario,
            resolver_areas_supervisadas(usuario.areas_que_supervisa, usuario.area),
        )

    if "punto_venta" in payload.model_fields_set:
        usuario.punto_venta = resolver_punto_venta(payload.punto_venta, usuario.area)
    elif usuario.area != AREA_PUNTOS_DE_VENTA:
        usuario.punto_venta = None

    # La bodega NO se limpia al cambiar de área: el coordinador de La 65 está
    # en Logística y el de Guayabal en Producción, así que no hay un área
    # "correcta" contra la que compararla.
    if "bodega" in payload.model_fields_set:
        usuario.bodega = resolver_bodega(payload.bodega)

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


@router.delete("/usuarios/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_usuario(
    usuario_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(require_role("admin")),
):
    """
    Borra un usuario que nunca hizo nada.

    Es para el que se creó con el correo mal escrito, o dos veces, o para
    alguien que al final no entró. **Uno que ya trabajó no se borra**: su id
    está escrito en quién aprobó, quién autorizó y quién firmó, y vaciar eso
    dejaría el historial diciendo «alguien». Ahí se responde 409 diciendo qué
    tiene y ofreciendo desactivarlo, que es lo que de verdad se necesita
    cuando una persona se va. Ver `auth/rastros.py`.
    """
    usuario = (
        db.query(User)
        .filter(User.id == usuario_id, User.tenant_id == tenant_id)
        .first()
    )
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    if usuario.id == current_user.id:
        raise HTTPException(
            status_code=400,
            detail="No puedes eliminar tu propia cuenta: te quedarías sin "
                   "cómo entrar a deshacerlo.",
        )

    conteos = rastros_de(db, usuario.id)
    if conteos:
        raise HTTPException(status_code=409, detail=explicar(usuario.nombre, conteos))

    # Lo único que se va con él es su propia configuración: las áreas que
    # supervisaba y los permisos que le habían otorgado.
    db.query(AreaSupervisada).filter(
        AreaSupervisada.usuario_id == usuario.id
    ).delete(synchronize_session=False)
    db.query(CapacidadOtorgada).filter(
        CapacidadOtorgada.usuario_id == usuario.id
    ).delete(synchronize_session=False)

    db.delete(usuario)
    db.commit()
