"""
El flujo de conceptos: el de cada PQRS, y las plantillas de Administración.
La lógica y el porqué están en `pqrs/flujo.py`.

- **En cada PQRS** lo mueve quien reparte (`pqrs.cerrar`): iniciarlo,
  cambiar los pasos que faltan, reanudarlo tras un rechazo, terminarlo y
  elegir la bodega de despacho. Verlo puede cualquiera que vea la PQRS.
- **Las plantillas y las bodegas** las cambia `admin`.

Va con prefijo `/pqrs` y se registra ANTES que el router de PQRS: si no,
`/pqrs/{pqrs_id}` se come `/pqrs/flujos` y responde 422. Las bodegas son la
lista común (`core/bodegas.py`); aquí solo se elige el concepto de cada una.
"""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core import bodegas, capacidades
from app.core.database import get_db
from app.core.deps import get_current_tenant_id, get_current_user, require_role, solo_lectura_no
from app.core.modulos import contratado
from app.core.notificaciones import enviar_avisos
from app.models.autorizacion import TipoAutorizacion
from app.models.pqrs import (
    CLASES_PASO, MAX_NOMBRE_ASOCIADO, PQRSFlujo, PQRSFlujoPaso,
)
from app.models.user import User
from app.modules.pqrs import flujo
from app.modules.pqrs.notificaciones import avisos_autorizacion_pendiente
from app.modules.pqrs.permisos import CAPACIDAD_GESTION, obtener_visible, puede_gestionar_pqrs

router = APIRouter(prefix="/pqrs", tags=["PQRS — Flujo de conceptos"], dependencies=[Depends(contratado("pqrs"))])


class PasoElegido(BaseModel):
    id: int | None = None
    tipo_autorizacion_id: int
    origen: str | None = None


class Iniciar(BaseModel):
    pasos: list[PasoElegido] = Field(min_length=1, max_length=20)
    bodega_despacho_id: int | None = None


class Pasos(BaseModel):
    pasos: list[PasoElegido] = Field(max_length=20)


class Reanudar(BaseModel):
    repetir: bool = False


class Bodega(BaseModel):
    bodega_despacho_id: int | None = None


def _quien_reparte(db: Session, tenant_id: int, usuario: User) -> None:
    if not puede_gestionar_pqrs(usuario):
        quien = capacidades.quienes_lo_hacen(db, tenant_id, CAPACIDAD_GESTION)
        raise HTTPException(
            status_code=403,
            detail=f"El flujo de conceptos lo mueve {quien}, que es quien reparte los casos.",
        )


def _avisar(background: BackgroundTasks, db: Session, tenant_id: int, pqrs, pedido, usuario: User) -> None:
    """A la siguiente área le toca: se le avisa, como a cualquier autorización."""
    if not pedido:
        return
    paso, _autorizacion = pedido
    background.add_task(enviar_avisos, avisos_autorizacion_pendiente(
        db, tenant_id, pqrs, paso.tipo.area_autorizadora, paso.tipo.nombre, usuario.nombre,
        comentario="Lo pidió el flujo de conceptos de la PQRS.",
    ))


# ── El flujo de una PQRS ──────────────────────────────────────────────

@router.get("/{pqrs_id}/flujo")
def ver_flujo(
    pqrs_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
):
    pqrs = obtener_visible(db, tenant_id, pqrs_id, current_user)
    escribe = current_user.rol not in ("lectura", "gerencia")
    return flujo.resumen(db, pqrs, escribe and puede_gestionar_pqrs(current_user))


@router.post("/{pqrs_id}/flujo/iniciar")
def iniciar_flujo(
    pqrs_id: int,
    payload: Iniciar,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(solo_lectura_no),
):
    _quien_reparte(db, tenant_id, current_user)
    pqrs = obtener_visible(db, tenant_id, pqrs_id, current_user)
    pedido = flujo.iniciar(db, pqrs, current_user.id, [p.model_dump() for p in payload.pasos],
                           payload.bodega_despacho_id)
    db.commit()
    _avisar(background, db, tenant_id, pqrs, pedido, current_user)
    return flujo.resumen(db, pqrs, True)


@router.put("/{pqrs_id}/flujo/pasos")
def cambiar_pasos(
    pqrs_id: int,
    payload: Pasos,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(solo_lectura_no),
):
    _quien_reparte(db, tenant_id, current_user)
    pqrs = obtener_visible(db, tenant_id, pqrs_id, current_user)
    flujo.editar_pendientes(db, pqrs, current_user.id, [p.model_dump() for p in payload.pasos])
    db.commit()
    return flujo.resumen(db, pqrs, True)


@router.post("/{pqrs_id}/flujo/reanudar")
def reanudar_flujo(
    pqrs_id: int,
    payload: Reanudar,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(solo_lectura_no),
):
    _quien_reparte(db, tenant_id, current_user)
    pqrs = obtener_visible(db, tenant_id, pqrs_id, current_user)
    pedido = flujo.reanudar(db, pqrs, current_user.id, payload.repetir)
    if not pedido:
        raise HTTPException(status_code=400, detail="No quedan pasos por pedir. Agrega uno o da el flujo por terminado.")
    db.commit()
    _avisar(background, db, tenant_id, pqrs, pedido, current_user)
    return flujo.resumen(db, pqrs, True)


@router.post("/{pqrs_id}/flujo/terminar")
def terminar_flujo(
    pqrs_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(solo_lectura_no),
):
    _quien_reparte(db, tenant_id, current_user)
    pqrs = obtener_visible(db, tenant_id, pqrs_id, current_user)
    flujo.terminar(db, pqrs, current_user.id)
    db.commit()
    return flujo.resumen(db, pqrs, True)


@router.patch("/{pqrs_id}/bodega-despacho")
def elegir_bodega(
    pqrs_id: int,
    payload: Bodega,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(solo_lectura_no),
):
    _quien_reparte(db, tenant_id, current_user)
    pqrs = obtener_visible(db, tenant_id, pqrs_id, current_user)
    flujo.elegir_bodega(db, pqrs, payload.bodega_despacho_id)
    db.commit()
    return flujo.resumen(db, pqrs, True)


# ── Plantillas y bodegas (Administración) ─────────────────────────────

class PasoPlantilla(BaseModel):
    clase: str = "concepto"
    tipo_autorizacion_id: int | None = None


class Plantilla(BaseModel):
    nombre: str = Field(min_length=2, max_length=MAX_NOMBRE_ASOCIADO)
    aplica_a: str | None = None
    activo: bool = True
    pasos: list[PasoPlantilla] = Field(default_factory=list, max_length=20)


def _tipo(db: Session, tenant_id: int, tipo_id: int | None) -> TipoAutorizacion | None:
    if tipo_id is None:
        return None
    tipo = db.query(TipoAutorizacion).filter(
        TipoAutorizacion.id == tipo_id, TipoAutorizacion.tenant_id == tenant_id,
    ).first()
    if not tipo:
        raise HTTPException(status_code=400, detail="Ese tipo de autorización no existe. Elígelo de la lista.")
    return tipo


def _plantilla_out(db: Session, f: PQRSFlujo) -> dict:
    def nombre(tipo_id):
        t = db.get(TipoAutorizacion, tipo_id) if tipo_id else None
        return {"concepto": t.nombre, "area": t.area_autorizadora} if t else {"concepto": None, "area": None}
    return {
        "id": f.id, "nombre": f.nombre, "aplica_a": f.aplica_a, "activo": f.activo,
        "pasos": [{"clase": p.clase, "tipo_autorizacion_id": p.tipo_autorizacion_id, **nombre(p.tipo_autorizacion_id)}
                  for p in f.pasos],
    }


def _validar_plantilla(db: Session, tenant_id: int, payload: Plantilla) -> list[PQRSFlujoPaso]:
    if payload.aplica_a is not None and payload.aplica_a not in flujo.TIPOS_CANAL:
        raise HTTPException(status_code=400, detail="«Aplica a» es punto de venta (sede), venta institucional, otros canales o vacío.")
    pasos = []
    for i, p in enumerate(payload.pasos):
        if p.clase not in CLASES_PASO:
            raise HTTPException(status_code=400, detail=f"Paso {i + 1}: la clase es concepto, bodega o técnico.")
        if p.clase == "concepto" and not p.tipo_autorizacion_id:
            raise HTTPException(status_code=400, detail=f"Paso {i + 1}: elige qué concepto se pide.")
        tipo = _tipo(db, tenant_id, p.tipo_autorizacion_id) if p.clase == "concepto" else None
        pasos.append(PQRSFlujoPaso(orden=i, clase=p.clase, tipo_autorizacion_id=tipo.id if tipo else None))
    return pasos


@router.get("/flujos")
def listar_plantillas(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(require_role("admin")),
):
    flujo.sembrar(db, tenant_id)
    plantillas = db.query(PQRSFlujo).filter(PQRSFlujo.tenant_id == tenant_id).order_by(PQRSFlujo.id).all()
    return [_plantilla_out(db, f) for f in plantillas]


@router.post("/flujos", status_code=201)
def crear_plantilla(
    payload: Plantilla,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(require_role("admin")),
):
    flujo.sembrar(db, tenant_id)
    nueva = PQRSFlujo(tenant_id=tenant_id, nombre=" ".join(payload.nombre.split()),
                      aplica_a=payload.aplica_a, activo=payload.activo)
    nueva.pasos = _validar_plantilla(db, tenant_id, payload)
    db.add(nueva)
    db.commit()
    db.refresh(nueva)
    return _plantilla_out(db, nueva)


@router.put("/flujos/{flujo_id}")
def cambiar_plantilla(
    flujo_id: int,
    payload: Plantilla,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(require_role("admin")),
):
    """
    Cambia la plantilla para lo que se inicie DE AQUÍ EN ADELANTE: las PQRS
    que ya tienen su cadena la conservan.
    """
    plantilla = db.query(PQRSFlujo).filter(PQRSFlujo.id == flujo_id, PQRSFlujo.tenant_id == tenant_id).first()
    if not plantilla:
        raise HTTPException(status_code=404, detail="Ese flujo no existe.")
    pasos = _validar_plantilla(db, tenant_id, payload)
    plantilla.nombre = " ".join(payload.nombre.split())
    plantilla.aplica_a = payload.aplica_a
    plantilla.activo = payload.activo
    plantilla.pasos = pasos
    db.commit()
    db.refresh(plantilla)
    return _plantilla_out(db, plantilla)


class ConceptoBodega(BaseModel):
    tipo_autorizacion_id: int | None = None


@router.get("/conceptos-bodega")
def listar_conceptos_bodega(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(require_role("admin")),
):
    """
    Cada bodega de la lista común con el concepto que pide el flujo de PQRS.
    Las bodegas se crean, renombran y borran en Administración › Bodegas;
    aquí solo se elige su concepto.
    """
    flujo.sembrar(db, tenant_id)
    salida = []
    for b in bodegas.del_tenant(db, tenant_id, incluir_inactivas=True):
        concepto = flujo._concepto_de(db, b.id)
        salida.append({"bodega_id": b.id, "nombre": b.nombre, "activo": b.activo,
                       "tipo_autorizacion_id": concepto.tipo_autorizacion_id if concepto else None})
    db.commit()
    return salida


@router.put("/conceptos-bodega/{bodega_id}")
def cambiar_concepto_bodega(
    bodega_id: int,
    payload: ConceptoBodega,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(require_role("admin")),
):
    bodega = bodegas.obtener(db, tenant_id, bodega_id)
    if not bodega:
        raise HTTPException(status_code=404, detail="Esa bodega no existe.")
    tipo = _tipo(db, tenant_id, payload.tipo_autorizacion_id)
    flujo.concepto_de_bodega(db, tenant_id, bodega, tipo.id if tipo else None)
    db.commit()
    return {"bodega_id": bodega.id, "nombre": bodega.nombre, "activo": bodega.activo,
            "tipo_autorizacion_id": tipo.id if tipo else None}
