"""
Endpoints del módulo PQRS.
Todos quedan aislados bajo /pqrs y filtrados siempre por tenant_id del usuario
logueado, para que cada empresa solo vea sus propias solicitudes.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, get_current_tenant_id
from app.models.user import User
from app.models.pqrs import PQRSSolicitud, PQRSSeguimiento, PQRSEncuesta
from app.models.autorizacion import AutorizacionPQRS
from app.modules.pqrs.schemas import (
    PQRSCreate, PQRSOut, PQRSDetailOut, PQRSUpdateEstado, PQRSAsignar,
    PQRSAsignarArea, EncuestaCreate,
)
from app.modules.pqrs.service import (
    calcular_fecha_limite_sla, calcular_prioridad, disparar_webhook_n8n,
    generar_codigo_seguimiento, generar_radicado_calidad,
)

router = APIRouter(prefix="/pqrs", tags=["PQRS"])


@router.post("", response_model=PQRSOut, status_code=status.HTTP_201_CREATED)
def crear_pqrs(
    payload: PQRSCreate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
):
    solicitud = PQRSSolicitud(
        tenant_id=tenant_id,
        tipo=payload.tipo,
        cliente_nombre=payload.cliente_nombre,
        cliente_email=payload.cliente_email,
        cliente_telefono=payload.cliente_telefono,
        descripcion=payload.descripcion,
        area_responsable=payload.area_responsable,
        estado="recibido",
        prioridad=calcular_prioridad(payload.tipo),
        fecha_limite_sla=calcular_fecha_limite_sla(payload.tipo),
    )
    db.add(solicitud)
    db.commit()
    db.refresh(solicitud)

    # El código de seguimiento se genera con el ID real ya asignado,
    # así el número que ve el cliente coincide con el "PQRS #<id>" interno.
    solicitud.codigo_seguimiento = generar_codigo_seguimiento(solicitud.id)

    db.add(PQRSSeguimiento(
        pqrs_id=solicitud.id,
        usuario_id=current_user.id,
        tipo_evento="cambio_estado",
        comentario="Solicitud registrada en el sistema.",
    ))
    db.commit()
    db.refresh(solicitud)

    disparar_webhook_n8n("pqrs-creada", {
        "pqrs_id": solicitud.id,
        "tenant_id": tenant_id,
        "tipo": solicitud.tipo,
        "area_responsable": solicitud.area_responsable,
        "prioridad": solicitud.prioridad,
    })

    return solicitud


@router.get("", response_model=list[PQRSOut])
def listar_pqrs(
    estado: str | None = None,
    tipo: str | None = None,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    query = db.query(PQRSSolicitud).filter(PQRSSolicitud.tenant_id == tenant_id)
    if estado:
        query = query.filter(PQRSSolicitud.estado == estado)
    if tipo:
        query = query.filter(PQRSSolicitud.tipo == tipo)
    return query.order_by(PQRSSolicitud.fecha_creacion.desc()).all()


@router.get("/{pqrs_id}", response_model=PQRSDetailOut)
def obtener_pqrs(
    pqrs_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    solicitud = (
        db.query(PQRSSolicitud)
        .filter(PQRSSolicitud.id == pqrs_id, PQRSSolicitud.tenant_id == tenant_id)
        .first()
    )
    if not solicitud:
        raise HTTPException(status_code=404, detail="PQRS no encontrada.")
    return solicitud


@router.patch("/{pqrs_id}/asignar", response_model=PQRSOut)
def asignar_pqrs(
    pqrs_id: int,
    payload: PQRSAsignar,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
):
    solicitud = (
        db.query(PQRSSolicitud)
        .filter(PQRSSolicitud.id == pqrs_id, PQRSSolicitud.tenant_id == tenant_id)
        .first()
    )
    if not solicitud:
        raise HTTPException(status_code=404, detail="PQRS no encontrada.")

    solicitud.asignado_a = payload.usuario_id
    if solicitud.estado == "recibido":
        solicitud.estado = "asignado"

    db.add(PQRSSeguimiento(
        pqrs_id=solicitud.id,
        usuario_id=current_user.id,
        tipo_evento="asignacion",
        comentario=payload.comentario or f"Asignada al usuario {payload.usuario_id}.",
    ))
    db.commit()
    db.refresh(solicitud)

    disparar_webhook_n8n("pqrs-asignada", {
        "pqrs_id": solicitud.id,
        "asignado_a": solicitud.asignado_a,
    })

    return solicitud


@router.patch("/{pqrs_id}/area", response_model=PQRSOut)
def asignar_area(
    pqrs_id: int,
    payload: PQRSAsignarArea,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
):
    """Asigna el área responsable de una PQRS (actualiza el campo real, no solo el historial)."""
    solicitud = (
        db.query(PQRSSolicitud)
        .filter(PQRSSolicitud.id == pqrs_id, PQRSSolicitud.tenant_id == tenant_id)
        .first()
    )
    if not solicitud:
        raise HTTPException(status_code=404, detail="PQRS no encontrada.")
    if solicitud.estado == "cerrado":
        raise HTTPException(status_code=400, detail="No se puede reasignar área en una PQRS cerrada.")

    solicitud.area_responsable = payload.area

    # Si se asigna a Calidad, se genera su propio consecutivo de radicado interno,
    # distinto del código de seguimiento del cliente.
    if payload.area.strip().lower() == "calidad" and not solicitud.radicado_calidad:
        solicitud.radicado_calidad = generar_radicado_calidad(db, tenant_id)

    comentario = payload.comentario or f"Área asignada: {payload.area}."
    if solicitud.radicado_calidad and payload.area.strip().lower() == "calidad":
        comentario += f" Radicado de Calidad: {solicitud.radicado_calidad}."

    db.add(PQRSSeguimiento(
        pqrs_id=solicitud.id,
        usuario_id=current_user.id,
        tipo_evento="asignacion_area",
        comentario=comentario,
    ))
    db.commit()
    db.refresh(solicitud)

    disparar_webhook_n8n("pqrs-area-asignada", {
        "pqrs_id": solicitud.id,
        "area_responsable": solicitud.area_responsable,
        "radicado_calidad": solicitud.radicado_calidad,
    })

    return solicitud


@router.patch("/{pqrs_id}/estado", response_model=PQRSOut)
def cambiar_estado_pqrs(
    pqrs_id: int,
    payload: PQRSUpdateEstado,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
):
    estados_validos = {"recibido", "asignado", "en_proceso", "resuelto", "cerrado"}
    if payload.estado not in estados_validos:
        raise HTTPException(status_code=400, detail=f"Estado inválido. Usa uno de: {estados_validos}")

    solicitud = (
        db.query(PQRSSolicitud)
        .filter(PQRSSolicitud.id == pqrs_id, PQRSSolicitud.tenant_id == tenant_id)
        .first()
    )
    if not solicitud:
        raise HTTPException(status_code=404, detail="PQRS no encontrada.")

    if payload.estado == "cerrado":
        hay_pendiente = db.query(AutorizacionPQRS).filter(
            AutorizacionPQRS.pqrs_id == pqrs_id,
            AutorizacionPQRS.estado == "pendiente",
        ).first()
        if hay_pendiente:
            raise HTTPException(
                status_code=400,
                detail="No se puede cerrar la PQRS: hay una autorización pendiente de respuesta."
            )

    solicitud.estado = payload.estado

    if payload.estado == "cerrado":
        solicitud.fecha_cierre = datetime.now(timezone.utc)
        # Crea automáticamente el registro de encuesta pendiente de respuesta
        if not solicitud.encuesta:
            db.add(PQRSEncuesta(pqrs_id=solicitud.id))

    db.add(PQRSSeguimiento(
        pqrs_id=solicitud.id,
        usuario_id=current_user.id,
        tipo_evento="cambio_estado",
        comentario=payload.comentario or f"Estado actualizado a '{payload.estado}'.",
    ))
    db.commit()
    db.refresh(solicitud)

    if payload.estado == "cerrado":
        disparar_webhook_n8n("pqrs-cerrada", {
            "pqrs_id": solicitud.id,
            "cliente_email": solicitud.cliente_email,
        })

    return solicitud


@router.post("/{pqrs_id}/encuesta", status_code=status.HTTP_201_CREATED)
def responder_encuesta(
    pqrs_id: int,
    payload: EncuestaCreate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    solicitud = (
        db.query(PQRSSolicitud)
        .filter(PQRSSolicitud.id == pqrs_id, PQRSSolicitud.tenant_id == tenant_id)
        .first()
    )
    if not solicitud:
        raise HTTPException(status_code=404, detail="PQRS no encontrada.")
    if not solicitud.encuesta:
        raise HTTPException(status_code=400, detail="Esta PQRS aún no tiene una encuesta pendiente.")
    if not (1 <= payload.calificacion <= 5):
        raise HTTPException(status_code=400, detail="La calificación debe estar entre 1 y 5.")

    solicitud.encuesta.calificacion = payload.calificacion
    solicitud.encuesta.comentario = payload.comentario
    solicitud.encuesta.respondida_en = datetime.now(timezone.utc)
    db.commit()

    return {"mensaje": "Gracias por tu respuesta."}
