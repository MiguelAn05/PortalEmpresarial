"""
Endpoints del módulo PQRS.
Todos quedan aislados bajo /pqrs y filtrados siempre por tenant_id del usuario
logueado, para que cada empresa solo vea sus propias solicitudes.
"""
from datetime import datetime, timezone

from fastapi import (
    APIRouter, BackgroundTasks, Depends, File, Form, HTTPException,
    UploadFile, status,
)
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, get_current_tenant_id, solo_lectura_no
from app.models.user import User
from app.models.pqrs import PQRSSolicitud, PQRSSeguimiento, PQRSEncuesta
from app.models.autorizacion import AutorizacionPQRS
from app.modules.pqrs.schemas import (
    PQRSOut, PQRSDetailOut, PQRSAsignar,
    PQRSAsignarArea, PQRSAreaCausante,
)
from app.modules.pqrs.permisos import solo_servicio_al_cliente, es_servicio_al_cliente
from app.modules.pqrs import pendientes
from app.modules.pqrs.service import (
    calcular_fecha_limite_sla, calcular_prioridad, disparar_webhook_n8n,
    asignar_codigo_seguimiento, generar_radicado_calidad, guardar_archivo,
    EXTENSIONES_VIDEO_PERMITIDAS, MAX_TAMANIO_VIDEO_MB, SLA_DIAS_POR_TIPO,
)
from app.modules.pqrs.notificaciones import (
    avisos_creacion, avisos_reasignacion, avisos_cierre, enviar_avisos,
)

router = APIRouter(prefix="/pqrs", tags=["PQRS"])


@router.post("", response_model=PQRSOut, status_code=status.HTTP_201_CREATED)
async def crear_pqrs(
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _: User = Depends(solo_lectura_no),
    # Tipo y descripción
    tipo: str = Form(...),
    descripcion: str = Form(...),
    area_responsable: str = Form(None),
    # Datos del cliente — mismos campos que el formulario público
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
    # Archivos adjuntos (opcionales también internamente)
    adjunto_producto: UploadFile = File(None),
    adjunto_factura: UploadFile = File(None),
    adjunto_video: UploadFile = File(None),
):
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

    solicitud = PQRSSolicitud(
        tenant_id=tenant_id,
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
        origen_publico="interno",
    )
    db.add(solicitud)
    db.commit()
    db.refresh(solicitud)

    # El código de seguimiento se genera con el ID real ya asignado,
    # así el número que ve el cliente coincide con el radicado interno.
    # El prefijo cambia si el canal es un punto de venta específico o
    # venta institucional (ver PREFIJOS_POR_CANAL en service.py).
    asignar_codigo_seguimiento(db, solicitud, tenant_id, canal_atencion)

    if area_responsable and area_responsable.strip().lower() == "calidad":
        solicitud.radicado_calidad = generar_radicado_calidad(db, tenant_id)

    db.add(PQRSSeguimiento(
        pqrs_id=solicitud.id,
        usuario_id=current_user.id,
        tipo_evento="cambio_estado",
        comentario=f"Solicitud registrada internamente por {current_user.nombre}.",
    ))
    db.commit()
    db.refresh(solicitud)

    background.add_task(enviar_avisos, avisos_creacion(db, tenant_id, solicitud))

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


@router.get("/por-vencer")
def pqrs_por_vencer(
    dias: int = 2,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(get_current_user),
):
    """
    Las PQRS que vencen dentro de `dias` hábiles o que ya vencieron, con el
    correo de cada responsable y solo SUS casos.

    Lo consume la automatización del recordatorio diario. Va declarada antes
    que /{pqrs_id}, o el path variable se la come.
    """
    return pendientes.por_vencer(db, tenant_id, dias)


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
    _: User = Depends(solo_lectura_no),
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
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _: User = Depends(solo_lectura_no),
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

    area_anterior = solicitud.area_responsable
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

    if payload.area != area_anterior:
        background.add_task(
            enviar_avisos, avisos_reasignacion(db, tenant_id, solicitud, payload.area),
        )

    return solicitud


@router.patch("/{pqrs_id}/area-causante", response_model=PQRSOut)
def asignar_area_causante(
    pqrs_id: int,
    payload: PQRSAreaCausante,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _: User = Depends(solo_lectura_no),
):
    """
    Marca qué área fue la CAUSANTE del problema (ej: 'Producción fue el
    culpable'). Es distinto de area_responsable (que gestiona el caso día
    a día) — este campo es de uso interno, no lo llena el cliente, y sirve
    para sacar reportes de cuántas PQRS son causadas por cada área.
    """
    solicitud = (
        db.query(PQRSSolicitud)
        .filter(PQRSSolicitud.id == pqrs_id, PQRSSolicitud.tenant_id == tenant_id)
        .first()
    )
    if not solicitud:
        raise HTTPException(status_code=404, detail="PQRS no encontrada.")

    solicitud.area_causante = payload.area_causante

    db.add(PQRSSeguimiento(
        pqrs_id=solicitud.id,
        usuario_id=current_user.id,
        tipo_evento="area_causante",
        comentario=f"Área causante marcada como: {payload.area_causante}.",
    ))
    db.commit()
    db.refresh(solicitud)
    return solicitud


@router.patch("/{pqrs_id}/tipo", response_model=PQRSOut)
def reclasificar_tipo_pqrs(
    pqrs_id: int,
    tipo: str = Form(...),
    motivo: str = Form(...),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(solo_servicio_al_cliente),
):
    """
    Corrige el tipo de una PQRS. El cliente casi nunca acierta al radicar, y
    esa clasificacion es la que alimenta los indicadores y los reportes de
    Calidad, asi que Servicio al cliente la ajusta antes de cerrar.

    Al cambiar el tipo se recalcula la fecha limite del SLA DESDE LA
    RADICACION, no desde hoy: si en realidad era un reclamo, el plazo que
    aplicaba fue siempre el del reclamo. Puede quedar vencida al instante, y
    eso es correcto — refleja el incumplimiento real.
    """
    tipos_validos = set(SLA_DIAS_POR_TIPO) | {"felicitacion"}
    if tipo not in tipos_validos:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo invalido. Usa uno de: {', '.join(sorted(tipos_validos))}.",
        )

    solicitud = (
        db.query(PQRSSolicitud)
        .filter(PQRSSolicitud.id == pqrs_id, PQRSSolicitud.tenant_id == tenant_id)
        .first()
    )
    if not solicitud:
        raise HTTPException(status_code=404, detail="PQRS no encontrada.")

    # Una PQRS cerrada ya se reporto y su tipo entro en los indicadores del
    # mes. Reclasificar despues cambiaria cifras ya presentadas.
    if solicitud.estado == "cerrado":
        raise HTTPException(
            status_code=400,
            detail=(
                "No se puede reclasificar una PQRS cerrada. El tipo se corrige "
                "antes de cerrarla."
            ),
        )

    tipo_anterior = solicitud.tipo
    if tipo_anterior == tipo:
        raise HTTPException(
            status_code=400,
            detail=f"La PQRS ya esta clasificada como '{tipo}'.",
        )

    if not motivo.strip():
        raise HTTPException(
            status_code=400,
            detail="Escribe por que se reclasifica: queda en la trazabilidad de la PQRS.",
        )

    prioridad_anterior = solicitud.prioridad
    limite_anterior = solicitud.fecha_limite_sla

    solicitud.tipo = tipo
    solicitud.fecha_limite_sla = calcular_fecha_limite_sla(tipo, solicitud.fecha_creacion)

    # La prioridad se ajusta al tipo nuevo SOLO si nadie la habia tocado a
    # mano: si alguien la subio por conocer el caso, ese criterio manda.
    prioridad_automatica_anterior = calcular_prioridad(tipo_anterior)
    if prioridad_anterior == prioridad_automatica_anterior:
        solicitud.prioridad = calcular_prioridad(tipo)

    detalle = [f"Tipo: {tipo_anterior} -> {tipo}."]
    if solicitud.prioridad != prioridad_anterior:
        detalle.append(f"Prioridad: {prioridad_anterior} -> {solicitud.prioridad}.")
    else:
        detalle.append(f"Prioridad sin cambio ({prioridad_anterior}).")
    if limite_anterior and solicitud.fecha_limite_sla:
        detalle.append(
            f"Fecha limite: {limite_anterior.date()} -> {solicitud.fecha_limite_sla.date()}."
        )
    detalle.append(f"Motivo: {motivo.strip()}")

    db.add(PQRSSeguimiento(
        pqrs_id=solicitud.id,
        usuario_id=current_user.id,
        tipo_evento="reclasificacion",
        comentario=" ".join(detalle),
    ))
    db.commit()
    db.refresh(solicitud)
    return solicitud


@router.patch("/{pqrs_id}/estado", response_model=PQRSOut)
async def cambiar_estado_pqrs(
    pqrs_id: int,
    background: BackgroundTasks,
    estado: str = Form(...),
    comentario: str | None = Form(None),
    evidencia: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _: User = Depends(solo_lectura_no),
):
    estados_validos = {"recibido", "asignado", "en_proceso", "resuelto", "cerrado"}
    if estado not in estados_validos:
        raise HTTPException(status_code=400, detail=f"Estado inválido. Usa uno de: {estados_validos}")

    solicitud = (
        db.query(PQRSSolicitud)
        .filter(PQRSSolicitud.id == pqrs_id, PQRSSolicitud.tenant_id == tenant_id)
        .first()
    )
    if not solicitud:
        raise HTTPException(status_code=404, detail="PQRS no encontrada.")

    # Cerrar es la unica transicion restringida: es la que dispara la
    # encuesta al cliente y congela la PQRS para los indicadores.
    if estado == "cerrado" and not es_servicio_al_cliente(current_user):
        raise HTTPException(
            status_code=403,
            detail=(
                "Solo el área de Servicio al Cliente puede cerrar una PQRS. "
                "Marcala como 'resuelto' y ellos la revisan y la cierran."
            ),
        )

    if estado == "cerrado":
        hay_pendiente = db.query(AutorizacionPQRS).filter(
            AutorizacionPQRS.pqrs_id == pqrs_id,
            AutorizacionPQRS.estado == "pendiente",
        ).first()
        if hay_pendiente:
            raise HTTPException(
                status_code=400,
                detail="No se puede cerrar la PQRS: hay una autorización pendiente de respuesta."
            )

    solicitud.estado = estado

    if estado == "cerrado":
        solicitud.fecha_cierre = datetime.now(timezone.utc)
        # Crea automáticamente el registro de encuesta pendiente de respuesta
        if not solicitud.encuesta:
            db.add(PQRSEncuesta(pqrs_id=solicitud.id))

    ruta_evidencia = None
    if evidencia is not None:
        ruta_evidencia = await guardar_archivo(evidencia, "evidencias")

    db.add(PQRSSeguimiento(
        pqrs_id=solicitud.id,
        usuario_id=current_user.id,
        tipo_evento="cambio_estado",
        comentario=comentario or f"Estado actualizado a '{estado}'.",
        adjunto_evidencia=ruta_evidencia,
    ))
    db.commit()
    db.refresh(solicitud)

    if estado == "cerrado":
        background.add_task(enviar_avisos, avisos_cierre(solicitud))

    return solicitud



