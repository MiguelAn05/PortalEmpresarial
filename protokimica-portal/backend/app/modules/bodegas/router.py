"""
Las bodegas de la empresa: verlas, crearlas, renombrarlas, elegir sus
responsables, desactivarlas y borrar la que se creó por error.

Leerlas puede cualquiera con sesión (el formulario de nota crédito y el flujo
de PQRS las ofrecen). Cambiarlas, solo `admin`. Es parte de la base del
portal, como las áreas y los canales: no depende de ningún módulo contratado.
Ver `core/bodegas.py` y `models/bodega.py`.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core import bodegas
from app.core.database import get_db
from app.core.deps import get_current_tenant_id, get_current_user, require_role
from app.models.bodega import MAX_NOMBRE_BODEGA, Bodega, BodegaResponsable
from app.models.user import User

router = APIRouter(prefix="/bodegas", tags=["Bodegas"])


class BodegaOut(BaseModel):
    id: int
    nombre: str


class Responsable(BaseModel):
    id: int
    nombre: str


class BodegaAdminOut(BodegaOut):
    activo: bool
    # En cuántos registros aparece: lo que hay que saber antes de borrarla.
    usos: int = 0
    responsables: list[Responsable] = []


class BodegaCrear(BaseModel):
    nombre: str = Field(min_length=1, max_length=MAX_NOMBRE_BODEGA)
    responsables: list[int] = Field(default_factory=list)


class BodegaCambiar(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=MAX_NOMBRE_BODEGA)
    activo: bool | None = None
    # La lista completa de responsables; None la deja como está.
    responsables: list[int] | None = None


def _salida(db: Session, b: Bodega) -> BodegaAdminOut:
    ids = [r.usuario_id for r in b.responsables]
    gente = db.query(User).filter(User.id.in_(ids)).all() if ids else []
    return BodegaAdminOut(
        id=b.id, nombre=b.nombre, activo=b.activo, usos=bodegas.usos(db, b),
        responsables=sorted((Responsable(id=u.id, nombre=u.nombre) for u in gente),
                            key=lambda r: bodegas.clave_alfabetica(r.nombre)),
    )


def _nombre_libre(db: Session, tenant_id: int, nombre: str, excluir_id: int | None = None) -> None:
    otra = db.query(Bodega.id).filter(Bodega.tenant_id == tenant_id, Bodega.nombre == nombre)
    if excluir_id:
        otra = otra.filter(Bodega.id != excluir_id)
    if otra.first():
        raise HTTPException(status_code=409, detail=f"Ya existe la bodega «{nombre}».")


def _poner_responsables(db: Session, tenant_id: int, bodega: Bodega, ids: list[int]) -> None:
    ids = list(dict.fromkeys(ids))
    if ids:
        validos = {u.id for u in db.query(User).filter(User.id.in_(ids), User.tenant_id == tenant_id)}
        if len(validos) != len(ids):
            raise HTTPException(status_code=400, detail="Uno de los responsables no existe. Elígelo otra vez de la lista.")
    bodega.responsables = [BodegaResponsable(usuario_id=i) for i in ids]


@router.get("", response_model=list[BodegaOut])
def listar(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(get_current_user),
):
    """Las activas, en orden: lo que ofrecen los formularios."""
    lista = bodegas.del_tenant(db, tenant_id)
    db.commit()   # por si se acaban de sembrar
    return [BodegaOut(id=b.id, nombre=b.nombre) for b in lista]


@router.get("/todas", response_model=list[BodegaAdminOut])
def listar_todas(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(require_role("admin")),
):
    lista = bodegas.del_tenant(db, tenant_id, incluir_inactivas=True)
    db.commit()
    return [_salida(db, b) for b in lista]


@router.post("", response_model=BodegaAdminOut, status_code=201)
def crear(
    payload: BodegaCrear,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(require_role("admin")),
):
    bodegas.sembrar(db, tenant_id)
    nombre = bodegas.normalizar(payload.nombre)
    _nombre_libre(db, tenant_id, nombre)
    orden = db.query(Bodega).filter(Bodega.tenant_id == tenant_id).count()
    bodega = Bodega(tenant_id=tenant_id, nombre=nombre, orden=orden)
    db.add(bodega)
    _poner_responsables(db, tenant_id, bodega, payload.responsables)
    db.commit()
    db.refresh(bodega)
    return _salida(db, bodega)


@router.patch("/{bodega_id}", response_model=BodegaAdminOut)
def cambiar(
    bodega_id: int,
    payload: BodegaCambiar,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(require_role("admin")),
):
    """
    Renombrar reescribe el nombre en las notas crédito que lo guardan como
    texto; PQRS la guarda por su id y no hay nada que mover.
    """
    bodega = bodegas.obtener(db, tenant_id, bodega_id)
    if not bodega:
        raise HTTPException(status_code=404, detail="Esa bodega no existe.")
    if payload.nombre is not None:
        nuevo = bodegas.normalizar(payload.nombre)
        if nuevo != bodega.nombre:
            _nombre_libre(db, tenant_id, nuevo, excluir_id=bodega.id)
            bodegas.renombrar(db, tenant_id, bodega, nuevo)
    if payload.activo is not None:
        bodega.activo = payload.activo
    if payload.responsables is not None:
        _poner_responsables(db, tenant_id, bodega, payload.responsables)
    db.commit()
    db.refresh(bodega)
    return _salida(db, bodega)


@router.delete("/{bodega_id}", status_code=204)
def borrar(
    bodega_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(require_role("admin")),
):
    """
    Borrar es para la que se creó por error y nadie ha usado. Si una PQRS o
    una nota crédito ya la tiene, no se borra (409): perdería de dónde salió
    su producto, que es parte de su historial. Para dejar de ofrecerla está
    desactivarla.
    """
    bodega = bodegas.obtener(db, tenant_id, bodega_id)
    if not bodega:
        raise HTTPException(status_code=404, detail="Esa bodega no existe.")
    usada = bodegas.usos(db, bodega)
    if usada:
        raise HTTPException(
            status_code=409,
            detail=(f"«{bodega.nombre}» ya aparece en {usada} "
                    f"{'registro' if usada == 1 else 'registros'} (PQRS o notas crédito) y no se puede "
                    "borrar sin dejarlos sin bodega. Desactívala: deja de ofrecerse y lo que ya la "
                    "tiene la conserva."),
        )
    db.delete(bodega)
    db.commit()
