"""
Las áreas de la empresa: verlas, crearlas, renombrarlas y desactivarlas.
Siempre en orden alfabético (ver `core.areas.nombres`).

Leerlas puede cualquiera con sesión: todos los formularios del portal las
ofrecen en un desplegable. Cambiarlas, solo `admin`. Ver `core/areas.py`.

No hay borrado. Un área se desactiva: deja de ofrecerse para lo nuevo, y lo
que ya la tenía —una PQRS de hace un año, un indicador— la conserva, igual
que se conservan los nombres de los usuarios que ya trabajaron.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core import areas
from app.core.database import get_db
from app.core.deps import get_current_tenant_id, get_current_user, require_role
from app.models.area import MAX_NOMBRE_AREA, Area
from app.models.user import User

router = APIRouter(prefix="/areas", tags=["Áreas"])


class AreaOut(BaseModel):
    id: int
    nombre: str
    activa: bool
    es_de_sedes: bool = False
    # Cuántas personas la tienen hoy: lo que hay que saber antes de
    # desactivarla o renombrarla.
    personas: int = 0


class AreaCrear(BaseModel):
    nombre: str = Field(min_length=2, max_length=MAX_NOMBRE_AREA)


class AreaCambiar(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=MAX_NOMBRE_AREA)
    activa: bool | None = None
    # Marcarla como el área de las sedes le quita la marca a la que la tenía.
    es_de_sedes: bool | None = None


class Renombrada(BaseModel):
    area: AreaOut
    # «tabla.columna» -> filas que cambiaron. Vacío si no se renombró.
    cambios: dict[str, int] = {}


def _salida(db: Session, area: Area) -> AreaOut:
    personas = db.query(User).filter(
        User.tenant_id == area.tenant_id, User.area == area.nombre, User.activo.is_(True),
    ).count()
    return AreaOut(id=area.id, nombre=area.nombre, activa=area.activa,
                   es_de_sedes=area.es_de_sedes, personas=personas)


def _limpio(nombre: str) -> str:
    # Dos espacios seguidos o uno al final hacen dos áreas que se ven iguales.
    return " ".join(nombre.split())


@router.get("", response_model=list[str])
def listar(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(get_current_user),
):
    """Las activas, en orden alfabético. Es lo que ofrecen los desplegables."""
    return areas.nombres(db, tenant_id)


@router.get("/de-sedes")
def area_de_sedes(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(get_current_user),
):
    """Cuál es el área de las sedes: el formulario de usuarios pide el punto de venta solo en ella."""
    return {"area": areas.area_de_sedes(db, tenant_id)}


@router.get("/todas", response_model=list[AreaOut])
def listar_todas(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(require_role("admin")),
):
    """Activas e inactivas, con cuánta gente tiene cada una: para administrarlas."""
    filas = db.query(Area).filter(Area.tenant_id == tenant_id).all()
    filas.sort(key=lambda a: areas.clave_alfabetica(a.nombre))
    return [_salida(db, a) for a in filas]


@router.post("", response_model=AreaOut, status_code=201)
def crear(
    payload: AreaCrear,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(require_role("admin")),
):
    nombre = _limpio(payload.nombre)
    existente = db.query(Area).filter(Area.tenant_id == tenant_id, Area.nombre == nombre).first()
    if existente:
        detalle = (f"Ya existe el área «{nombre}»."
                   if existente.activa else
                   f"El área «{nombre}» ya existe pero está desactivada: reactívala en vez de crearla otra vez.")
        raise HTTPException(status_code=409, detail=detalle)
    area = Area(tenant_id=tenant_id, nombre=nombre)
    db.add(area)
    db.commit()
    db.refresh(area)
    return _salida(db, area)


@router.patch("/{area_id}", response_model=Renombrada)
def cambiar(
    area_id: int,
    payload: AreaCambiar,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(require_role("admin")),
):
    """
    Renombrar reescribe el nombre en todo lo que lo lleva —usuarios, PQRS,
    proyectos, indicadores, capacidades otorgadas…— en una sola transacción, y
    responde cuánto cambió en cada sitio.
    """
    area = db.query(Area).filter(Area.id == area_id, Area.tenant_id == tenant_id).first()
    if not area:
        raise HTTPException(status_code=404, detail="Esa área no existe.")

    cambios: dict[str, int] = {}
    if payload.nombre is not None:
        nuevo = _limpio(payload.nombre)
        if nuevo != area.nombre:
            if db.query(Area).filter(Area.tenant_id == tenant_id, Area.nombre == nuevo).first():
                raise HTTPException(
                    status_code=409,
                    detail=(f"Ya existe un área «{nuevo}». Para juntar las dos, desactiva "
                            "una y pásale su gente a la otra desde Usuarios."),
                )
            try:
                cambios = areas.renombrar(db, tenant_id, area, nuevo)
            except Exception:
                db.rollback()
                raise

    if payload.activa is not None:
        area.activa = payload.activa
    if payload.es_de_sedes is not None:
        if payload.es_de_sedes:
            db.query(Area).filter(
                Area.tenant_id == tenant_id, Area.id != area.id,
            ).update({"es_de_sedes": False}, synchronize_session=False)
        area.es_de_sedes = payload.es_de_sedes

    db.commit()
    db.refresh(area)
    return Renombrada(area=_salida(db, area), cambios=cambios)
