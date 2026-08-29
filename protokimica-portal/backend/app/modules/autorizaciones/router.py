"""
Módulo de autorizaciones.
- Admin y Líderes pueden crear tipos de autorización
- Agentes pueden solicitar autorización para una PQRS
- Quien pertenece al área autorizadora aprueba o rechaza (por área, no por cargo)
- Una PQRS con autorización pendiente queda bloqueada
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import (
    get_current_user, get_current_tenant_id, require_role, solo_lectura_no,
)
from app.modules.autorizaciones.permisos import puede_responder
from app.models.user import User
from app.models.pqrs import PQRSSolicitud, PQRSSeguimiento
from app.models.autorizacion import TipoAutorizacion, AutorizacionPQRS
from app.modules.autorizaciones.schemas import (
    TipoAutorizacionCreate, TipoAutorizacionOut,
    SolicitarAutorizacion, ResponderAutorizacion, AutorizacionOut,
)

router = APIRouter(prefix="/autorizaciones", tags=["Autorizaciones"])


# ── Tipos de autorización (configuración) ─────────────────────────

@router.get("/tipos", response_model=list[TipoAutorizacionOut])
def listar_tipos(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    return db.query(TipoAutorizacion).filter(
        TipoAutorizacion.tenant_id == tenant_id,
        TipoAutorizacion.activo == True,
    ).all()


@router.post("/tipos", response_model=TipoAutorizacionOut, status_code=201)
def crear_tipo(
    payload: TipoAutorizacionCreate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(require_role("admin")),
):
    tipo = TipoAutorizacion(
        tenant_id=tenant_id,
        nombre=payload.nombre,
        descripcion=payload.descripcion,
        area_autorizadora=payload.area_autorizadora,
    )
    db.add(tipo)
    db.commit()
    db.refresh(tipo)
    return tipo


@router.delete("/tipos/{tipo_id}", status_code=204)
def desactivar_tipo(
    tipo_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(require_role("admin")),
):
    tipo = db.query(TipoAutorizacion).filter(
        TipoAutorizacion.id == tipo_id,
        TipoAutorizacion.tenant_id == tenant_id,
    ).first()
    if not tipo:
        raise HTTPException(status_code=404, detail="Tipo no encontrado.")
    tipo.activo = False
    db.commit()


# ── Autorizaciones de PQRS ─────────────────────────────────────────

@router.get("/pqrs/{pqrs_id}", response_model=list[AutorizacionOut])
def listar_autorizaciones_pqrs(
    pqrs_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """Lista todas las autorizaciones de una PQRS."""
    return db.query(AutorizacionPQRS).filter(
        AutorizacionPQRS.pqrs_id == pqrs_id
    ).all()


@router.post("/pqrs/{pqrs_id}/solicitar", response_model=AutorizacionOut, status_code=201)
def solicitar_autorizacion(
    pqrs_id: int,
    payload: SolicitarAutorizacion,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
):
    """Solicita una autorización para una PQRS. La PQRS queda bloqueada."""
    if current_user.rol not in ("admin", "lider", "agente"):
        raise HTTPException(status_code=403, detail="Sin permisos.")

    pqrs = db.query(PQRSSolicitud).filter(
        PQRSSolicitud.id == pqrs_id,
        PQRSSolicitud.tenant_id == tenant_id,
    ).first()
    if not pqrs:
        raise HTTPException(status_code=404, detail="PQRS no encontrada.")
    if pqrs.estado == "cerrado":
        raise HTTPException(status_code=400, detail="No se puede solicitar autorización en una PQRS cerrada.")

    # Verificar que no haya una autorización pendiente del mismo tipo
    existente = db.query(AutorizacionPQRS).filter(
        AutorizacionPQRS.pqrs_id == pqrs_id,
        AutorizacionPQRS.tipo_id == payload.tipo_id,
        AutorizacionPQRS.estado == "pendiente",
    ).first()
    if existente:
        raise HTTPException(status_code=400, detail="Ya existe una autorización pendiente de ese tipo.")

    autorizacion = AutorizacionPQRS(
        pqrs_id=pqrs_id,
        tipo_id=payload.tipo_id,
        estado="pendiente",
        solicitado_por=current_user.id,
        comentario_solicitud=payload.comentario_solicitud,
    )
    db.add(autorizacion)

    # Registrar en el historial
    tipo = db.query(TipoAutorizacion).filter(TipoAutorizacion.id == payload.tipo_id).first()
    db.add(PQRSSeguimiento(
        pqrs_id=pqrs_id,
        usuario_id=current_user.id,
        tipo_evento="autorizacion_solicitada",
        comentario=f"Se solicitó autorización: {tipo.nombre if tipo else 'N/A'}. {payload.comentario_solicitud or ''}",
    ))
    db.commit()
    db.refresh(autorizacion)
    return autorizacion


@router.post("/pqrs/{pqrs_id}/{autorizacion_id}/responder", response_model=AutorizacionOut)
def responder_autorizacion(
    pqrs_id: int,
    autorizacion_id: int,
    payload: ResponderAutorizacion,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(solo_lectura_no),
):
    """
    Aprueba o rechaza una autorización.

    La responde quien pertenece al ÁREA autorizadora, sin importar su cargo,
    más admin. Los roles "lectura" y "gerencia" no escriben nada en el portal
    y aquí tampoco: eso lo corta solo_lectura_no.
    """
    autorizacion = db.query(AutorizacionPQRS).filter(
        AutorizacionPQRS.id == autorizacion_id,
        AutorizacionPQRS.pqrs_id == pqrs_id,
    ).first()
    if not autorizacion:
        raise HTTPException(status_code=404, detail="Autorización no encontrada.")
    if autorizacion.estado != "pendiente":
        raise HTTPException(status_code=400, detail="Esta autorización ya fue respondida.")

    # Manda el área, no el cargo: quien trabaja en el área autorizadora puede
    # responder, sea líder o agente.
    area = autorizacion.tipo.area_autorizadora
    if not puede_responder(current_user, area):
        raise HTTPException(
            status_code=403,
            detail=(
                f"Esta autorización la responde el área de '{area}'. "
                f"Pídele a alguien de esa área que la revise."
            ),
        )

    if payload.decision not in ("aprobada", "rechazada"):
        raise HTTPException(status_code=400, detail="La decisión debe ser 'aprobada' o 'rechazada'.")

    autorizacion.estado = payload.decision
    autorizacion.autorizado_por = current_user.id
    autorizacion.comentario_respuesta = payload.comentario_respuesta
    autorizacion.fecha_respuesta = datetime.now(timezone.utc)

    # Registrar en historial
    db.add(PQRSSeguimiento(
        pqrs_id=pqrs_id,
        usuario_id=current_user.id,
        tipo_evento="autorizacion_respondida",
        comentario=f"Autorización '{autorizacion.tipo.nombre}' {payload.decision}. {payload.comentario_respuesta or ''}",
    ))
    db.commit()
    db.refresh(autorizacion)
    return autorizacion