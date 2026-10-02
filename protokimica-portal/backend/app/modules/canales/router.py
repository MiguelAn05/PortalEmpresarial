"""
Los canales de atención de la empresa: verlos, crearlos, renombrarlos,
cambiarles el tipo y desactivarlos.

Leerlos puede cualquiera con sesión: los formularios de PQRS y de notas
crédito los ofrecen. Cambiarlos, solo `admin`. Ver `core/canales.py` y
`models/canal.py` (los tipos, y por qué el prefijo no se cambia).
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core import canales
from app.core.database import get_db
from app.core.deps import get_current_tenant_id, get_current_user, require_role
from app.models.canal import MAX_NOMBRE_CANAL, MAX_PREFIJO, Canal
from app.models.user import User

router = APIRouter(prefix="/canales", tags=["Canales"])


class CanalOut(BaseModel):
    nombre: str
    prefijo: str | None
    tipo: str


class CanalAdminOut(CanalOut):
    id: int
    activo: bool
    # Cuántas personas lo tienen como su punto de venta: lo que hay que
    # saber antes de cambiarle el tipo o desactivarlo.
    personas: int = 0


class CanalCrear(BaseModel):
    nombre: str = Field(min_length=2, max_length=MAX_NOMBRE_CANAL)
    prefijo: str | None = Field(default=None, max_length=MAX_PREFIJO)
    tipo: str = "general"


class CanalCambiar(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=MAX_NOMBRE_CANAL)
    # Solo se acepta si el canal todavía no tiene: un prefijo no se cambia.
    prefijo: str | None = Field(default=None, max_length=MAX_PREFIJO)
    tipo: str | None = None
    activo: bool | None = None


class CanalCambiado(BaseModel):
    canal: CanalAdminOut
    cambios: dict[str, int] = {}


def _limpio(nombre: str) -> str:
    return " ".join(nombre.split())


def _salida(db: Session, canal: Canal) -> CanalAdminOut:
    personas = 0
    if canal.prefijo:
        personas = db.query(User).filter(
            User.tenant_id == canal.tenant_id, User.punto_venta == canal.prefijo,
            User.activo.is_(True),
        ).count()
    return CanalAdminOut(id=canal.id, nombre=canal.nombre, prefijo=canal.prefijo, tipo=canal.tipo,
                         activo=canal.activo, personas=personas)


def _validar(db: Session, tenant_id: int, prefijo: str | None, tipo: str | None,
             excluir_id: int | None = None) -> str | None:
    try:
        if tipo is not None:
            canales.validar_tipo(tipo)
        limpio = canales.validar_prefijo(prefijo)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if limpio:
        otro = db.query(Canal).filter(Canal.tenant_id == tenant_id, Canal.prefijo == limpio)
        if excluir_id:
            otro = otro.filter(Canal.id != excluir_id)
        if otro.first():
            raise HTTPException(status_code=409, detail=f"El prefijo «{limpio}» ya lo usa otro canal.")
    return limpio


@router.get("", response_model=list[CanalOut])
def listar(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(get_current_user),
):
    """Los activos, en orden alfabético: lo que ofrecen los formularios."""
    return [CanalOut(nombre=c.nombre, prefijo=c.prefijo, tipo=c.tipo)
            for c in canales.del_tenant(db, tenant_id)]


@router.get("/todos", response_model=list[CanalAdminOut])
def listar_todos(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(require_role("admin")),
):
    return [_salida(db, c) for c in canales.del_tenant(db, tenant_id, incluir_inactivos=True)]


@router.post("", response_model=CanalAdminOut, status_code=201)
def crear(
    payload: CanalCrear,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(require_role("admin")),
):
    nombre = _limpio(payload.nombre)
    if db.query(Canal).filter(Canal.tenant_id == tenant_id, Canal.nombre == nombre).first():
        raise HTTPException(status_code=409, detail=f"Ya existe el canal «{nombre}».")
    prefijo = _validar(db, tenant_id, payload.prefijo, payload.tipo)
    if payload.tipo == "sede" and not prefijo:
        raise HTTPException(
            status_code=400,
            detail=("Una sede necesita prefijo: es su código de QR y el comienzo del "
                    "consecutivo de sus PQRS (por ejemplo PVG)."),
        )
    canal = Canal(tenant_id=tenant_id, nombre=nombre, prefijo=prefijo, tipo=payload.tipo)
    db.add(canal)
    db.commit()
    db.refresh(canal)
    return _salida(db, canal)


@router.patch("/{canal_id}", response_model=CanalCambiado)
def cambiar(
    canal_id: int,
    payload: CanalCambiar,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(require_role("admin")),
):
    """
    Renombrar reescribe el nombre en las PQRS y las notas crédito que lo
    llevan, en una sola transacción. El prefijo no se cambia: solo se pone si
    el canal no tenía.
    """
    canal = db.query(Canal).filter(Canal.id == canal_id, Canal.tenant_id == tenant_id).first()
    if not canal:
        raise HTTPException(status_code=404, detail="Ese canal no existe.")

    if payload.prefijo is not None:
        nuevo_prefijo = _validar(db, tenant_id, payload.prefijo, None, excluir_id=canal.id)
        if canal.prefijo and nuevo_prefijo != canal.prefijo:
            raise HTTPException(
                status_code=409,
                detail=(f"El prefijo «{canal.prefijo}» no se cambia: es el código del QR "
                        "impreso en la sede y el comienzo del consecutivo de sus PQRS. Si "
                        "de verdad es otra sede, crea un canal nuevo y desactiva este."),
            )
        canal.prefijo = nuevo_prefijo

    if payload.tipo is not None:
        _validar(db, tenant_id, None, payload.tipo)
        if payload.tipo == "sede" and not canal.prefijo:
            raise HTTPException(status_code=400, detail="Para volverlo sede, ponle primero un prefijo.")
        canal.tipo = payload.tipo

    cambios: dict[str, int] = {}
    if payload.nombre is not None:
        nuevo = _limpio(payload.nombre)
        if nuevo != canal.nombre:
            if db.query(Canal).filter(Canal.tenant_id == tenant_id, Canal.nombre == nuevo).first():
                raise HTTPException(status_code=409, detail=f"Ya existe un canal «{nuevo}».")
            try:
                cambios = canales.renombrar(db, tenant_id, canal, nuevo)
            except Exception:
                db.rollback()
                raise

    if payload.activo is not None:
        canal.activo = payload.activo

    db.commit()
    db.refresh(canal)
    return CanalCambiado(canal=_salida(db, canal), cambios=cambios)
