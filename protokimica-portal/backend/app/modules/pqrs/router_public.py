f"""
Endpoints PÚBLICOS de PQRS — sin autenticación.
Soporta subida de archivos (imágenes del producto y factura).
"""
import os
from datetime import datetime, timezone

from fastapi import (
    APIRouter, BackgroundTasks, Depends, File, Form, HTTPException,
    UploadFile, status,
)
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.modules.pqrs.schemas import EncuestaCreate

from app.core import canales
from app.core.database import get_db
from app.models.pqrs import PQRSSolicitud, PQRSSeguimiento
from app.models.tenant import Tenant
from app.modules.pqrs import qr
from app.modules.pqrs.historial_publico import construir as historial_publico_de
from app.modules.pqrs.service import (
    calcular_fecha_limite_sla,
    calcular_prioridad,
    asignar_codigo_seguimiento,
    guardar_archivo,
    EXTENSIONES_VIDEO_PERMITIDAS,
    MAX_TAMANIO_VIDEO_MB,
)
from app.modules.pqrs.notificaciones import (
    avisos_creacion, enviar_avisos,
)

router = APIRouter(prefix="/public", tags=["Público — PQRS"])

# Carpeta donde se guardan los archivos subidos
UPLOAD_DIR = "/app/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ── Códigos QR de los puntos de venta ────────────────────────────────
# Van sin autenticación a propósito: lo único que contienen es una URL
# pública del portal, y así la pantalla de impresión puede mostrarlos con un
# `<img>` normal — una etiqueta de imagen no manda la cabecera de sesión.
# No hay nada que proteger, y el código de canal se valida contra la lista
# cerrada, así que de aquí no sale un QR que apunte a otra parte.

@router.get("/qr", tags=["Público — QR"])
def listar_qr():
    """Los canales que tienen QR, con su código y la URL que lleva dentro."""
    return qr.listar()


@router.get("/qr/{codigo}.svg", tags=["Público — QR"])
def qr_svg(codigo: str):
    """El QR de un punto de venta, en vectorial: se imprime a cualquier tamaño."""
    try:
        contenido = qr.svg(codigo)
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No hay ningún punto de venta con el código '{codigo}'. "
                "Los códigos válidos salen de /public/qr."
            ),
        )
    return Response(
        content=contenido,
        media_type="image/svg+xml",
        # Un QR de un punto de venta solo cambia si cambia el dominio del
        # portal. Guardarlo un día evita regenerarlo en cada vista previa.
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get("/qr/{codigo}.png", tags=["Público — QR"])
def qr_png(codigo: str):
    """El mismo QR en PNG, para meterlo en un diseño o en un documento."""
    try:
        contenido = qr.png(codigo)
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No hay ningún punto de venta con el código '{codigo}'. "
                "Los códigos válidos salen de /public/qr."
            ),
        )
    return Response(
        content=contenido,
        media_type="image/png",
        headers={
            "Cache-Control": "public, max-age=86400",
            # Para que al descargarlo quede con un nombre que se entienda.
            "Content-Disposition": f'inline; filename="qr-{codigo.upper()}.png"',
        },
    )


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
    # Solo el movimiento y cuándo. Sin comentario y sin adjuntos: lo que se
    # escribe por dentro se queda por dentro.
    movimiento: str
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
    background: BackgroundTasks,
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
    presentacion: str = Form(None),
    cantidad_presentacion: str = Form(None),
    canal_atencion: str = Form(None),
    lote: str = Form(None),
    factura_numero: str = Form(None),
    cantidad_factura: str = Form(None),
    cantidad_reclamo: str = Form(None),
    # Archivos adjuntos
    adjunto_producto: UploadFile = File(None),
    adjunto_factura: UploadFile = File(None),
    adjunto_video: UploadFile = File(None),
):
    tenant = db.query(Tenant).filter(Tenant.slug == "protokimica").first()
    if not tenant:
        raise HTTPException(status_code=500, detail="Error de configuración.")

    # Guardar archivos si vienen
    ruta_producto = None
    ruta_factura = None
    ruta_video = None

    if adjunto_producto and adjunto_producto.filename:
        ruta_producto = await guardar_archivo(adjunto_producto, "productos")

    if adjunto_factura and adjunto_factura.filename:
        ruta_factura = await guardar_archivo(adjunto_factura, "facturas")

    if adjunto_video and adjunto_video.filename:
        ruta_video = await guardar_archivo(
            adjunto_video, "videos",
            extensiones_permitidas=EXTENSIONES_VIDEO_PERMITIDAS,
            max_mb=MAX_TAMANIO_VIDEO_MB,
        )

    # ¿El producto vino del catálogo o lo escribió el cliente?
    #
    # Se DEDUCE de los datos en vez de confiar en una bandera del formulario:
    # una bandera puede llegar diciendo lo contrario de lo que muestran los
    # campos —por un error del navegador o porque alguien arme la petición a
    # mano— y entonces un nombre escrito a mano entraría al catálogo de los
    # informes como si fuera un código real. Sin código no hay producto
    # identificado, y punto.
    producto_codigo = (producto_codigo or "").strip() or None
    producto_nombre = (producto_nombre or "").strip() or None
    producto_por_confirmar = bool(producto_nombre) and not producto_codigo

    # Un formulario viejo que quedó cacheado puede seguir mandando «Llamada
    # telefónica»; se traduce al nombre actual para que no abra un canal
    # paralelo en los reportes.
    canal_atencion = canales.normalizar(canal_atencion)

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
        producto_por_confirmar=producto_por_confirmar,
        presentacion=presentacion,
        cantidad_presentacion=cantidad_presentacion,
        canal_atencion=canal_atencion,
        lote=lote,
        factura_numero=factura_numero,
        cantidad_factura=cantidad_factura,
        cantidad_reclamo=cantidad_reclamo,
        adjunto_producto=ruta_producto,
        adjunto_factura=ruta_factura,
        adjunto_video=ruta_video,
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
    # así coincide siempre con el número interno "PQRS #<id>". El prefijo
    # cambia solo si el canal es un punto de venta específico o venta
    # institucional (ver PREFIJOS_POR_CANAL en service.py).
    codigo = asignar_codigo_seguimiento(db, solicitud, tenant.id, canal_atencion)

    db.add(PQRSSeguimiento(
        pqrs_id=solicitud.id,
        usuario_id=None,
        tipo_evento="cambio_estado",
        comentario="Solicitud radicada por el cliente.",
        estado_nuevo="recibido",
    ))
    db.commit()

    # Los avisos se arman aquí —necesitan la base— y se mandan después de
    # responder: quien radica no tiene por qué esperar tres llamadas HTTP.
    background.add_task(enviar_avisos, avisos_creacion(db, tenant.id, solicitud))

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

    # El texto lo redacta el portal a partir del estado. El `comentario` del
    # seguimiento NO sale de aquí: es donde el área escribe sus notas de
    # trabajo, y eso no le corresponde al cliente.
    historial_publico = [
        SeguimientoPublicoOut(**movimiento)
        for movimiento in historial_publico_de(solicitud.seguimientos)
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
    
class EncuestaEstadoOut(BaseModel):
    disponible: bool
    ya_respondida: bool
    cliente_nombre: str | None = None
    tipo_pqrs: str | None = None
    mensaje: str


@router.get("/encuesta/{codigo}", response_model=EncuestaEstadoOut)
def consultar_estado_encuesta(codigo: str, db: Session = Depends(get_db)):
    solicitud = db.query(PQRSSolicitud).filter(
        PQRSSolicitud.codigo_seguimiento == codigo.upper()
    ).first()

    if not solicitud:
        raise HTTPException(status_code=404, detail="No encontramos ninguna solicitud con ese código.")

    if solicitud.estado != "cerrado" or not solicitud.encuesta:
        return EncuestaEstadoOut(
            disponible=False, ya_respondida=False,
            mensaje="Esta solicitud aún no tiene una encuesta disponible.",
        )

    if solicitud.encuesta.respondida_en:
        return EncuestaEstadoOut(
            disponible=False, ya_respondida=True,
            mensaje="Ya registramos su respuesta a esta encuesta. ¡Gracias!",
        )

    return EncuestaEstadoOut(
        disponible=True, ya_respondida=False,
        cliente_nombre=solicitud.cliente_nombre,
        tipo_pqrs=solicitud.tipo,
        mensaje="Encuesta disponible.",
    )


@router.post("/encuesta/{codigo}")
def responder_encuesta_publica(codigo: str, payload: EncuestaCreate, db: Session = Depends(get_db)):
    solicitud = db.query(PQRSSolicitud).filter(
        PQRSSolicitud.codigo_seguimiento == codigo.upper()
    ).first()

    if not solicitud:
        raise HTTPException(status_code=404, detail="No encontramos ninguna solicitud con ese código.")
    if solicitud.estado != "cerrado" or not solicitud.encuesta:
        raise HTTPException(status_code=400, detail="Esta solicitud no tiene una encuesta disponible.")
    if solicitud.encuesta.respondida_en:
        raise HTTPException(status_code=400, detail="Esta encuesta ya fue respondida.")

    if payload.tipo_solicitud not in {"peticion", "queja", "reclamo", "sugerencia", "felicitacion"}:
        raise HTTPException(status_code=400, detail="tipo_solicitud inválido.")
    if not (1 <= payload.calificacion <= 5):
        raise HTTPException(status_code=400, detail="La calificación debe estar entre 1 y 5.")
    if payload.solucionada not in {"si", "parcial", "no"}:
        raise HTTPException(status_code=400, detail="solucionada debe ser 'si', 'parcial' o 'no'.")
    if payload.calificacion_tiempo_respuesta not in {"excelente", "bueno", "regular", "malo"}:
        raise HTTPException(status_code=400, detail="calificacion_tiempo_respuesta inválida.")

    encuesta = solicitud.encuesta
    encuesta.tipo_solicitud = payload.tipo_solicitud
    encuesta.calificacion = payload.calificacion
    encuesta.solucionada = payload.solucionada
    encuesta.calificacion_tiempo_respuesta = payload.calificacion_tiempo_respuesta
    encuesta.recomendaria = payload.recomendaria
    encuesta.comentario = payload.comentario
    encuesta.respondida_en = datetime.now(timezone.utc)
    db.commit()

    return {"mensaje": "¡Gracias por su tiempo! Su respuesta fue registrada."}