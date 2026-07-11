f"""
Endpoints PÚBLICOS de PQRS — sin autenticación.
Soporta subida de archivos (imágenes del producto y factura).
"""
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.database import get_db
from app.models.pqrs import PQRSSolicitud, PQRSSeguimiento
from app.models.tenant import Tenant
from app.modules.pqrs.service import (
    calcular_fecha_limite_sla,
    calcular_prioridad,
    generar_codigo_seguimiento,
    guardar_archivo,
)
from app.modules.pqrs.notificaciones import notificar_cliente_creacion, notificar_area

router = APIRouter(prefix="/public", tags=["Público — PQRS"])

# Carpeta donde se guardan los archivos subidos
UPLOAD_DIR = "/app/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


class PQRSPublicaOut(BaseModel):
    codigo_seguimiento: str
    tipo: str
    estado: str
    prioridad: str
    cliente_nombre: str
    area_responsable: str | None
    fecha_creacion: datetime
    fecha_limite_sla: datetime | None
    mensaje: str

    class Config:
        from_attributes = True


class SeguimientoPublicoOut(BaseModel):
    tipo_evento: str
    comentario: str | None
    fecha: datetime

    class Config:
        from_attributes = True


class PQRSConsultaOut(BaseModel):
    codigo_seguimiento: str
    tipo: str
    estado: str
    prioridad: str
    empresa: str | None
    area_responsable: str | None
    fecha_creacion: datetime
    fecha_limite_sla: datetime | None
    fecha_cierre: datetime | None
    historial: list[SeguimientoPublicoOut]

    class Config:
        from_attributes = True


@router.post("/pqrs", response_model=PQRSPublicaOut, status_code=status.HTTP_201_CREATED)
async def radicar_pqrs_publica(
    db: Session = Depends(get_db),
    # Tipo y descripción
    tipo: str = Form(...),
    descripcion: str = Form(...),
    area_responsable: str = Form(None),
    # Datos del cliente
    empresa: str = Form(None),
    nit_cedula: str = Form(None),
    cliente_nombre: str = Form(...),
    cliente_email: str = Form(None),
    cliente_telefono: str = Form(None),
    ciudad: str = Form(None),
    departamento: str = Form(None),
    # Datos del producto
    producto_codigo: str = Form(None),
    producto_nombre: str = Form(None),
    canal_atencion: str = Form(None),
    lote: str = Form(None),
    factura_numero: str = Form(None),
    cantidad_factura: str = Form(None),
    cantidad_reclamo: str = Form(None),
    # Archivos adjuntos
    adjunto_producto: UploadFile = File(None),
    adjunto_factura: UploadFile = File(None),
):
    tenant = db.query(Tenant).filter(Tenant.slug == "protokimica").first()
    if not tenant:
        raise HTTPException(status_code=500, detail="Error de configuración.")

    # Guardar archivos si vienen
    ruta_producto = None
    ruta_factura = None

    if adjunto_producto and adjunto_producto.filename:
        ruta_producto = await guardar_archivo(adjunto_producto, "productos")

    if adjunto_factura and adjunto_factura.filename:
        ruta_factura = await guardar_archivo(adjunto_factura, "facturas")

    solicitud = PQRSSolicitud(
        tenant_id=tenant.id,
        tipo=tipo,
        empresa=empresa,
        nit_cedula=nit_cedula,
        cliente_nombre=cliente_nombre,
        cliente_email=cliente_email,
        cliente_telefono=cliente_telefono,
        ciudad=ciudad,
        departamento=departamento,
        producto_codigo=producto_codigo,
        producto_nombre=producto_nombre,
        canal_atencion=canal_atencion,
        lote=lote,
        factura_numero=factura_numero,
        cantidad_factura=cantidad_factura,
        cantidad_reclamo=cantidad_reclamo,
        adjunto_producto=ruta_producto,
        adjunto_factura=ruta_factura,
        descripcion=descripcion,
        area_responsable=area_responsable,
        estado="recibido",
        prioridad=calcular_prioridad(tipo),
        fecha_limite_sla=calcular_fecha_limite_sla(tipo),
        origen_publico="publico",
    )
    db.add(solicitud)
    db.commit()
    db.refresh(solicitud)

    # El código se genera con el ID real ya asignado por la base de datos,
    # así coincide siempre con el número interno "PQRS #<id>".
    codigo = generar_codigo_seguimiento(solicitud.id)
    solicitud.codigo_seguimiento = codigo
    db.commit()
    db.refresh(solicitud)

    db.add(PQRSSeguimiento(
        pqrs_id=solicitud.id,
        usuario_id=None,
        tipo_evento="cambio_estado",
        comentario="Solicitud radicada por el cliente.",
    ))
    db.commit()

    notificar_cliente_creacion(solicitud)
    if solicitud.area_responsable:
        notificar_area(db, tenant.id, solicitud, solicitud.area_responsable, motivo="creacion")

    return PQRSPublicaOut(
        codigo_seguimiento=codigo,
        tipo=solicitud.tipo,
        estado=solicitud.estado,
        prioridad=solicitud.prioridad,
        cliente_nombre=solicitud.cliente_nombre,
        area_responsable=solicitud.area_responsable,
        fecha_creacion=solicitud.fecha_creacion,
        fecha_limite_sla=solicitud.fecha_limite_sla,
        mensaje=f"Solicitud radicada exitosamente. Tu código es {codigo}.",
    )


@router.get("/pqrs/{codigo}", response_model=PQRSConsultaOut)
def consultar_pqrs_publica(codigo: str, db: Session = Depends(get_db)):
    solicitud = db.query(PQRSSolicitud).filter(
        PQRSSolicitud.codigo_seguimiento == codigo.upper()
    ).first()

    if not solicitud:
        raise HTTPException(
            status_code=404,
            detail="No encontramos ninguna solicitud con ese código."
        )

    historial_publico = [
        SeguimientoPublicoOut(
            tipo_evento=seg.tipo_evento,
            comentario=seg.comentario,
            fecha=seg.fecha,
        )
        for seg in solicitud.seguimientos
        if seg.tipo_evento == "cambio_estado"
    ]

    return PQRSConsultaOut(
        codigo_seguimiento=solicitud.codigo_seguimiento,
        tipo=solicitud.tipo,
        estado=solicitud.estado,
        prioridad=solicitud.prioridad,
        empresa=solicitud.empresa,
        area_responsable=solicitud.area_responsable,
        fecha_creacion=solicitud.fecha_creacion,
        fecha_limite_sla=solicitud.fecha_limite_sla,
        fecha_cierre=solicitud.fecha_cierre,
        historial=historial_publico,
    )