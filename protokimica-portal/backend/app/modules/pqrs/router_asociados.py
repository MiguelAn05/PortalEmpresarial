"""
El catálogo «Asociado a» de las PQRS: verlo, y administrarlo.

Leerlo puede cualquiera con sesión en PQRS (la lista filtra por él, el
detalle lo muestra). Cambiarlo, solo `admin`, desde Administración ›
Asociados. No se borra: se desactiva, y las PQRS que ya lo tenían lo
conservan. Ver `pqrs/asociados.py`.

Va con prefijo `/pqrs/asociados` y se registra ANTES que el router de PQRS:
si no, `/pqrs/{pqrs_id}` se come la ruta y responde 422.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core import areas
from app.core.database import get_db
from app.core.deps import get_current_tenant_id, get_current_user, require_role
from app.core.modulos import contratado
from app.models.pqrs import (
    MAX_CODIGO_ASOCIADO, MAX_GRUPO_ASOCIADO, MAX_NOMBRE_ASOCIADO,
    PQRSAsociado, PQRSSolicitud,
)
from app.models.user import User
from app.modules.pqrs import asociados

router = APIRouter(
    prefix="/pqrs/asociados", tags=["PQRS — Asociado a"],
    dependencies=[Depends(contratado("pqrs"))],
)


class AsociadoOut(BaseModel):
    id: int
    codigo: str
    nombre: str
    grupo: str
    area_sugerida: str | None = None
    aplica_a: str | None = None
    sugiere_omp: bool = False

    class Config:
        from_attributes = True


class AsociadoAdminOut(AsociadoOut):
    activo: bool
    # Cuántas PQRS lo tienen: lo que hay que saber antes de desactivarlo o
    # renombrarlo.
    pqrs: int = 0


class AsociadoCrear(BaseModel):
    codigo: str = Field(min_length=1, max_length=MAX_CODIGO_ASOCIADO)
    nombre: str = Field(min_length=2, max_length=MAX_NOMBRE_ASOCIADO)
    grupo: str = Field(min_length=2, max_length=MAX_GRUPO_ASOCIADO)
    area_sugerida: str | None = None
    aplica_a: str | None = None
    sugiere_omp: bool = False


class AsociadoCambiar(BaseModel):
    codigo: str | None = Field(default=None, min_length=1, max_length=MAX_CODIGO_ASOCIADO)
    nombre: str | None = Field(default=None, min_length=2, max_length=MAX_NOMBRE_ASOCIADO)
    grupo: str | None = Field(default=None, min_length=2, max_length=MAX_GRUPO_ASOCIADO)
    # "" quita el área sugerida; None la deja como está.
    area_sugerida: str | None = None
    aplica_a: str | None = None
    sugiere_omp: bool | None = None
    activo: bool | None = None


def _limpio(texto: str) -> str:
    return " ".join(texto.split())


def _validar_area(db: Session, tenant_id: int, area: str | None) -> str | None:
    area = _limpio(area or "") or None
    if area and not areas.es_valida(db, tenant_id, area):
        raise HTTPException(status_code=400, detail=f"'{area}' no es un área del portal. Elige una de la lista.")
    return area


def _validar_aplica_a(aplica_a: str | None) -> str | None:
    aplica_a = (aplica_a or "").strip() or None
    if aplica_a and aplica_a not in asociados.TIPOS_CANAL:
        raise HTTPException(
            status_code=400,
            detail="El tipo de canal es 'sede', 'institucional' o vacío (aplica a cualquiera).",
        )
    return aplica_a


def _nombre_libre(db: Session, tenant_id: int, nombre: str, excluir_id: int | None = None) -> None:
    otro = db.query(PQRSAsociado).filter(
        PQRSAsociado.tenant_id == tenant_id, PQRSAsociado.nombre == nombre,
    )
    if excluir_id:
        otro = otro.filter(PQRSAsociado.id != excluir_id)
    if otro.first():
        raise HTTPException(status_code=409, detail=f"Ya existe el asociado «{nombre}».")


def _salida(db: Session, asociado: PQRSAsociado) -> AsociadoAdminOut:
    n = db.query(func.count(PQRSSolicitud.id)).filter(
        PQRSSolicitud.asociado_id == asociado.id,
    ).scalar()
    return AsociadoAdminOut(**AsociadoOut.model_validate(asociado).model_dump(),
                            activo=asociado.activo, pqrs=n or 0)


@router.get("", response_model=list[AsociadoOut])
def listar(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(get_current_user),
):
    """Los activos, en el orden en que se ofrecen."""
    return asociados.del_tenant(db, tenant_id)


@router.get("/todos", response_model=list[AsociadoAdminOut])
def listar_todos(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(require_role("admin")),
):
    return [_salida(db, a) for a in asociados.del_tenant(db, tenant_id, incluir_inactivos=True)]


@router.post("", response_model=AsociadoAdminOut, status_code=201)
def crear(
    payload: AsociadoCrear,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(require_role("admin")),
):
    asociados.sembrar(db, tenant_id)
    nombre = _limpio(payload.nombre)
    _nombre_libre(db, tenant_id, nombre)
    ultimo = db.query(func.max(PQRSAsociado.orden)).filter(
        PQRSAsociado.tenant_id == tenant_id,
    ).scalar()
    asociado = PQRSAsociado(
        tenant_id=tenant_id,
        codigo=_limpio(payload.codigo).upper(),
        nombre=nombre,
        grupo=_limpio(payload.grupo),
        area_sugerida=_validar_area(db, tenant_id, payload.area_sugerida),
        aplica_a=_validar_aplica_a(payload.aplica_a),
        sugiere_omp=payload.sugiere_omp,
        orden=(ultimo or 0) + 1,
    )
    db.add(asociado)
    db.commit()
    db.refresh(asociado)
    return _salida(db, asociado)


@router.patch("/{asociado_id}", response_model=AsociadoAdminOut)
def cambiar(
    asociado_id: int,
    payload: AsociadoCambiar,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(require_role("admin")),
):
    """
    Las PQRS guardan el id, no el nombre: renombrarlo no reescribe nada y los
    informes siguen juntando lo mismo.
    """
    asociado = asociados.obtener(db, tenant_id, asociado_id)
    if not asociado:
        raise HTTPException(status_code=404, detail="Ese asociado no existe.")

    if payload.nombre is not None:
        nombre = _limpio(payload.nombre)
        _nombre_libre(db, tenant_id, nombre, excluir_id=asociado.id)
        asociado.nombre = nombre
    if payload.codigo is not None:
        asociado.codigo = _limpio(payload.codigo).upper()
    if payload.grupo is not None:
        asociado.grupo = _limpio(payload.grupo)
    if payload.area_sugerida is not None:
        asociado.area_sugerida = _validar_area(db, tenant_id, payload.area_sugerida)
    if payload.aplica_a is not None:
        asociado.aplica_a = _validar_aplica_a(payload.aplica_a)
    if payload.sugiere_omp is not None:
        asociado.sugiere_omp = payload.sugiere_omp
    if payload.activo is not None:
        asociado.activo = payload.activo

    db.commit()
    db.refresh(asociado)
    return _salida(db, asociado)
