"""
Endpoints de las solicitudes de nota crédito.

Reemplaza el correo que hoy le manda el punto de venta a Contabilidad. Lo que
el correo no daba y esto sí: un consecutivo, un estado, y el número de la nota
crédito que se emitió al final — que es lo que permite encontrar las
aprobadas que nunca se ejecutaron.
"""
from datetime import datetime, timezone

from fastapi import (
    APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.core import canales
from app.core.database import get_db
from app.core.deps import (
    get_current_user, get_current_tenant_id, require_role, solo_lectura_no,
)
from app.models.nota_credito import (
    ESTADO_APLICADA, ESTADO_APROBADA, ESTADO_RECHAZADA, ESTADO_SOLICITADA,
    MotivoNotaCredito, SolicitudNotaCredito,
)
from app.models.user import User
from app.modules.notas_credito import service
from app.modules.notas_credito.permisos import (
    mensaje_falta_capacidad, puede_autorizar, puede_radicar,
    puede_registrar, puede_ver,
)
from app.modules.notas_credito.schemas import (
    AlcanceNotaCredito, AplicarSolicitud, MotivoCreate, MotivoOut,
    ResponderSolicitud, SolicitudDetailOut, SolicitudOut,
    MAX_FACTURA, MAX_NUMERO_NC, MAX_OBSERVACIONES,
)
from app.modules.notas_credito.notificaciones import (
    avisos_respondida, avisos_solicitada,
)
from app.modules.pqrs.notificaciones import enviar_avisos
from app.modules.pqrs.service import guardar_archivo

router = APIRouter(prefix="/notas-credito", tags=["Notas crédito"])


# ── Catálogo de motivos ────────────────────────────────────────────
# Va declarado ANTES que /{solicitud_id} o el path variable se lo come:
# "motivos" entraría como id y respondería un 422.

@router.get("/motivos", response_model=list[MotivoOut])
def listar_motivos(
    incluir_inactivos: bool = False,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(get_current_user),
):
    """Los motivos, sembrados solos la primera vez que alguien los pide."""
    service.sembrar_motivos(db, tenant_id)
    query = db.query(MotivoNotaCredito).filter(
        MotivoNotaCredito.tenant_id == tenant_id
    )
    if not incluir_inactivos:
        query = query.filter(MotivoNotaCredito.activo.is_(True))
    return query.order_by(MotivoNotaCredito.id).all()


@router.post("/motivos", response_model=MotivoOut, status_code=201)
def crear_motivo(
    payload: MotivoCreate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(require_role("admin")),
):
    nombre = payload.nombre.strip()
    if not nombre:
        raise HTTPException(status_code=400, detail="Escribe el nombre del motivo.")

    motivo = MotivoNotaCredito(tenant_id=tenant_id, nombre=nombre, activo=True)
    db.add(motivo)
    db.commit()
    db.refresh(motivo)
    return motivo


@router.delete("/motivos/{motivo_id}", status_code=204)
def desactivar_motivo(
    motivo_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(require_role("admin")),
):
    """
    Se desactiva, no se borra: las solicitudes viejas siguen apuntando a él y
    borrarlo dejaría sin motivo un histórico que alguien va a auditar.
    """
    motivo = db.query(MotivoNotaCredito).filter(
        MotivoNotaCredito.id == motivo_id,
        MotivoNotaCredito.tenant_id == tenant_id,
    ).first()
    if not motivo:
        raise HTTPException(status_code=404, detail="Motivo no encontrado.")
    motivo.activo = False
    db.commit()


# ── Solicitudes ────────────────────────────────────────────────────

@router.post("", response_model=SolicitudOut, status_code=status.HTTP_201_CREATED)
async def crear_solicitud(
    background: BackgroundTasks,
    punto_venta: str = Form(...),
    factura_afectada: str = Form(...),
    observaciones: str = Form(...),
    factura_reemplaza: str | None = Form(None),
    valor: str | None = Form(None),
    motivo_id: int | None = Form(None),
    adjunto: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _: User = Depends(solo_lectura_no),
):
    if not puede_radicar(current_user):
        raise HTTPException(status_code=403, detail="Tu usuario no puede pedir notas crédito.")

    # Lista cerrada: escrito a mano, «Itagüí», «itagui» y «Almacén Itagüí»
    # son tres sitios distintos y el informe por almacén deja de servir.
    punto_venta = canales.normalizar(punto_venta)
    if punto_venta not in canales.CANALES:
        raise HTTPException(
            status_code=400,
            detail=f"'{punto_venta}' no es un canal del portal. Elige uno de la lista.",
        )

    factura_afectada = factura_afectada.strip()
    observaciones = observaciones.strip()
    if not factura_afectada:
        raise HTTPException(status_code=400, detail="Escribe la factura sobre la que va la nota crédito.")
    if not observaciones:
        raise HTTPException(
            status_code=400,
            detail="Cuenta qué pasó: es lo que necesita Contabilidad para autorizar.",
        )
    if len(factura_afectada) > MAX_FACTURA:
        raise HTTPException(status_code=400, detail=f"La factura no puede pasar de {MAX_FACTURA} caracteres.")
    if len(observaciones) > MAX_OBSERVACIONES:
        raise HTTPException(status_code=400, detail=f"Las observaciones no pueden pasar de {MAX_OBSERVACIONES} caracteres.")

    if motivo_id is not None:
        motivo = db.query(MotivoNotaCredito).filter(
            MotivoNotaCredito.id == motivo_id,
            MotivoNotaCredito.tenant_id == tenant_id,
        ).first()
        if not motivo:
            raise HTTPException(status_code=404, detail="Ese motivo no está en la lista.")

    valor_decimal = None
    if valor not in (None, ""):
        try:
            valor_decimal = round(float(valor), 2)
        except ValueError:
            raise HTTPException(status_code=400, detail="El valor tiene que ser un número.")
        if valor_decimal < 0:
            raise HTTPException(status_code=400, detail="El valor no puede ser negativo.")

    ruta_adjunto = None
    if adjunto is not None and adjunto.filename:
        ruta_adjunto = await guardar_archivo(adjunto, "notas-credito")

    solicitud = SolicitudNotaCredito(
        tenant_id=tenant_id,
        punto_venta=punto_venta,
        factura_afectada=factura_afectada,
        factura_reemplaza=(factura_reemplaza or "").strip() or None,
        valor=valor_decimal,
        motivo_id=motivo_id,
        observaciones=observaciones,
        adjunto=ruta_adjunto,
        solicitado_por=current_user.id,
        estado=ESTADO_SOLICITADA,
    )
    db.add(solicitud)
    db.commit()
    db.refresh(solicitud)

    # El consecutivo se asigna con el id ya real, igual que el código de
    # seguimiento de una PQRS.
    solicitud.codigo = service.generar_codigo(db, tenant_id)
    db.commit()
    db.refresh(solicitud)

    # El aviso se ARMA aquí, con la sesión viva, y se MANDA después de
    # responder: la solicitud ya quedó guardada, y si notificar reventara, el
    # punto de venta vería un error sobre algo que sí se radicó y lo volvería
    # a enviar.
    background.add_task(enviar_avisos, avisos_solicitada(
        db, tenant_id, solicitud, current_user.nombre,
    ))

    return solicitud


@router.get("", response_model=list[SolicitudOut])
def listar_solicitudes(
    estado: str | None = None,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
):
    """
    Las que puede ver quien pregunta.

    El filtro se impone en el servidor: quien radica ve las suyas y nada más.
    Esconder filas en la pantalla no impide pedirlas por la URL.
    """
    query = db.query(SolicitudNotaCredito).filter(
        SolicitudNotaCredito.tenant_id == tenant_id
    )
    if estado:
        query = query.filter(SolicitudNotaCredito.estado == estado)

    ve_todas = current_user.rol in ("admin", "gerencia") or puede_autorizar(db, current_user)
    if not ve_todas:
        query = query.filter(SolicitudNotaCredito.solicitado_por == current_user.id)

    return query.order_by(SolicitudNotaCredito.creado_en.desc()).all()


def _buscar(db: Session, tenant_id: int, solicitud_id: int, usuario: User) -> SolicitudNotaCredito:
    """
    Trae la solicitud si esta persona puede verla.

    Responde 404 y no 403 cuando no le corresponde: un 403 confirma que la
    solicitud existe, y con un id correlativo eso ya dice cuántas van.
    """
    solicitud = db.query(SolicitudNotaCredito).filter(
        SolicitudNotaCredito.id == solicitud_id,
        SolicitudNotaCredito.tenant_id == tenant_id,
    ).first()
    if not solicitud or not puede_ver(db, usuario, solicitud):
        raise HTTPException(status_code=404, detail="Solicitud no encontrada.")
    return solicitud


@router.get("/{solicitud_id}", response_model=SolicitudDetailOut)
def obtener_solicitud(
    solicitud_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
):
    solicitud = _buscar(db, tenant_id, solicitud_id, current_user)

    escribe = current_user.rol not in ("lectura", "gerencia")
    autoriza = escribe and puede_autorizar(db, current_user)
    registra = escribe and puede_registrar(db, current_user)

    detalle = SolicitudDetailOut.model_validate(solicitud)
    detalle.alcance = AlcanceNotaCredito(
        puede_autorizar=autoriza and solicitud.estado == ESTADO_SOLICITADA,
        # Es la capacidad de REGISTRAR, no la de autorizar — hoy las tiene la
        # misma gente porque así quedó sembrado, pero son dos permisos
        # distintos y pueden separarse desde Administración › Capacidades.
        # Solo aplica sobre una ya aprobada: dejarlo antes sería anotar una
        # nota crédito que nadie autorizó.
        puede_aplicar=registra and solicitud.estado == ESTADO_APROBADA,
    )
    return detalle


@router.post("/{solicitud_id}/responder", response_model=SolicitudOut)
def responder_solicitud(
    solicitud_id: int,
    payload: ResponderSolicitud,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(solo_lectura_no),
):
    """Aprueba o rechaza. Manda la capacidad otorgada, no el cargo."""
    if payload.decision not in (ESTADO_APROBADA, ESTADO_RECHAZADA):
        raise HTTPException(status_code=400, detail="La decisión debe ser 'aprobada' o 'rechazada'.")

    solicitud = _buscar(db, tenant_id, solicitud_id, current_user)

    if not puede_autorizar(db, current_user):
        raise HTTPException(
            status_code=403,
            detail=mensaje_falta_capacidad(
                db, tenant_id, "notas_credito.autorizar", "Autorizar una nota crédito",
            ),
        )
    if solicitud.estado != ESTADO_SOLICITADA:
        raise HTTPException(
            status_code=400,
            detail=f"Esta solicitud ya está '{solicitud.estado}'; solo se responde una vez.",
        )

    solicitud.estado = payload.decision
    solicitud.autorizado_por = current_user.id
    solicitud.comentario_respuesta = (payload.comentario or "").strip() or None
    solicitud.fecha_respuesta = datetime.now(timezone.utc)
    db.commit()
    db.refresh(solicitud)

    background.add_task(enviar_avisos, avisos_respondida(
        db, tenant_id, solicitud, payload.decision, current_user.nombre,
    ))

    return solicitud


@router.post("/{solicitud_id}/aplicar", response_model=SolicitudOut)
def aplicar_solicitud(
    solicitud_id: int,
    payload: AplicarSolicitud,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(solo_lectura_no),
):
    """
    Registra el número de la nota crédito que se emitió, y con eso cierra.

    Es el paso que hace auditable la cadena: sin él, una solicitud aprobada y
    una realmente ejecutada se ven exactamente igual, y las que se aprobaron y
    nunca se hicieron no aparecen por ninguna parte.
    """
    solicitud = _buscar(db, tenant_id, solicitud_id, current_user)

    if not puede_registrar(db, current_user):
        raise HTTPException(
            status_code=403,
            detail=mensaje_falta_capacidad(
                db, tenant_id, "notas_credito.registrar",
                "Registrar el número de una nota crédito emitida",
            ),
        )
    if solicitud.estado != ESTADO_APROBADA:
        raise HTTPException(
            status_code=400,
            detail=(
                "Solo se registra el número de una solicitud aprobada. Esta "
                f"está '{solicitud.estado}'."
            ),
        )

    numero = payload.numero_nc.strip()
    if not numero:
        raise HTTPException(status_code=400, detail="Escribe el número de la nota crédito.")
    if len(numero) > MAX_NUMERO_NC:
        raise HTTPException(status_code=400, detail=f"El número no puede pasar de {MAX_NUMERO_NC} caracteres.")

    solicitud.numero_nc = numero
    solicitud.estado = ESTADO_APLICADA
    solicitud.aplicada_por = current_user.id
    solicitud.fecha_aplicacion = datetime.now(timezone.utc)
    if payload.comentario:
        # Se agrega, no se pisa: el comentario de la aprobación es de otra
        # persona y de otro momento.
        anterior = solicitud.comentario_respuesta or ""
        solicitud.comentario_respuesta = f"{anterior} {payload.comentario.strip()}".strip()
    db.commit()
    db.refresh(solicitud)

    # Quien la pidio necesita saber que ya existe, y con que numero: es lo
    # que le dice al cliente del almacen que su caso quedo resuelto.
    background.add_task(enviar_avisos, avisos_respondida(
        db, tenant_id, solicitud, ESTADO_APLICADA, current_user.nombre,
    ))

    return solicitud
