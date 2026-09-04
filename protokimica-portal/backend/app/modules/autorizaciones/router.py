"""
Módulo de autorizaciones.
- Admin y Líderes pueden crear tipos de autorización
- Agentes pueden solicitar autorización para una PQRS
- Quien pertenece al área autorizadora aprueba o rechaza (por área, no por cargo)
- Una PQRS con autorización pendiente queda bloqueada

**Pedir una autorización mueve la PQRS al área autorizadora, y responderla la
devuelve a Servicio al Cliente.** El caso viaja con la pregunta: si se quedara
en el área que pidió, la autorización aparecería como pendiente en la bandeja
de quien no puede firmarla y no en la de quien sí, que es exactamente cómo una
PQRS se queda tres días esperando a que alguien se acuerde de mirarla.

Ese movimiento lo hace el flujo, no una persona, y por eso no pasa por
`pqrs.permisos.puede_cambiar_area`: reasignar a mano sigue siendo de Servicio
al Cliente. Y por eso mismo vuelve a Servicio al Cliente al responderse — es
quien reparte, y quien decide qué sigue después del sí o del no.
"""
from datetime import datetime, timezone

from fastapi import (
    APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status,
)
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
    TipoAutorizacionCreate, TipoAutorizacionOut, AutorizacionOut,
)
from app.modules.pqrs.permisos import AREA_SERVICIO_CLIENTE
from app.modules.pqrs.service import guardar_archivo
from app.modules.pqrs.notificaciones import (
    avisos_autorizacion_pendiente, avisos_autorizacion_respondida, enviar_avisos,
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
    current_user: User = Depends(get_current_user),
):
    """
    Las autorizaciones de una PQRS, cada una con si quien mira puede firmarla.

    `puede_responder` lo resuelve el servidor. La pantalla lo calculaba por su
    cuenta mirando el ROL, y así escondía los botones a los agentes del área
    autorizadora — que son justamente quienes hacen ese trabajo.
    """
    autorizaciones = db.query(AutorizacionPQRS).filter(
        AutorizacionPQRS.pqrs_id == pqrs_id
    ).all()

    # 'lectura' y 'gerencia' no firman nada: es la misma regla que impone
    # solo_lectura_no al responder.
    escribe = current_user.rol not in ("lectura", "gerencia")

    salida = []
    for autorizacion in autorizaciones:
        item = AutorizacionOut.model_validate(autorizacion)
        item.puede_responder = (
            autorizacion.estado == "pendiente"
            and escribe
            and puede_responder(current_user, autorizacion.tipo.area_autorizadora)
        )
        salida.append(item)
    return salida


@router.post("/pqrs/{pqrs_id}/solicitar", response_model=AutorizacionOut, status_code=201)
async def solicitar_autorizacion(
    pqrs_id: int,
    background: BackgroundTasks,
    tipo_id: int = Form(...),
    comentario_solicitud: str | None = Form(None),
    adjunto: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
):
    """
    Solicita una autorización. La PQRS queda bloqueada y pasa al área que firma.

    El soporte va adjunto aquí, con la pregunta. Mandarlo por correo aparte
    obligaba a quien firma a buscar en dos sitios lo que necesita para decidir,
    y dejaba la autorización aprobada sin nada que la sustentara para cuando
    alguien la audite.
    """
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

    tipo = db.query(TipoAutorizacion).filter(
        TipoAutorizacion.id == tipo_id,
        TipoAutorizacion.tenant_id == tenant_id,
    ).first()
    if not tipo:
        raise HTTPException(
            status_code=404,
            detail="Ese tipo de autorización no existe. Revisa la lista o pídele a un administrador que lo cree.",
        )

    # Verificar que no haya una autorización pendiente del mismo tipo
    existente = db.query(AutorizacionPQRS).filter(
        AutorizacionPQRS.pqrs_id == pqrs_id,
        AutorizacionPQRS.tipo_id == tipo_id,
        AutorizacionPQRS.estado == "pendiente",
    ).first()
    if existente:
        raise HTTPException(status_code=400, detail="Ya existe una autorización pendiente de ese tipo.")

    ruta_adjunto = None
    if adjunto is not None and adjunto.filename:
        ruta_adjunto = await guardar_archivo(adjunto, "autorizaciones")

    autorizacion = AutorizacionPQRS(
        pqrs_id=pqrs_id,
        tipo_id=tipo_id,
        estado="pendiente",
        solicitado_por=current_user.id,
        comentario_solicitud=comentario_solicitud,
        adjunto_solicitud=ruta_adjunto,
    )
    db.add(autorizacion)

    # La PQRS pasa al área que tiene que firmar: la pregunta y el caso viajan
    # juntos, así aparece en la bandeja de quien puede resolverla.
    area_anterior = pqrs.area_responsable
    pqrs.area_responsable = tipo.area_autorizadora

    detalle = [f"Se solicitó autorización: {tipo.nombre}."]
    if tipo.area_autorizadora != area_anterior:
        detalle.append(
            f"Área: {area_anterior or 'sin asignar'} -> {tipo.area_autorizadora} "
            "mientras se responde."
        )
    if comentario_solicitud:
        detalle.append(comentario_solicitud.strip())

    db.add(PQRSSeguimiento(
        pqrs_id=pqrs_id,
        usuario_id=current_user.id,
        tipo_evento="autorizacion_solicitada",
        comentario=" ".join(detalle),
        adjunto_evidencia=ruta_adjunto,
    ))
    db.commit()
    db.refresh(autorizacion)

    # El aviso se ARMA aquí, con la sesión viva, y se MANDA después de
    # responder. Mover la PQRS al área que firma sin avisarle es dejarla
    # esperando a que a alguien de esa área se le ocurra abrir el portal.
    background.add_task(enviar_avisos, avisos_autorizacion_pendiente(
        db, tenant_id, pqrs, tipo.area_autorizadora,
        tipo.nombre, current_user.nombre,
    ))

    return autorizacion


@router.post("/pqrs/{pqrs_id}/{autorizacion_id}/responder", response_model=AutorizacionOut)
async def responder_autorizacion(
    pqrs_id: int,
    autorizacion_id: int,
    background: BackgroundTasks,
    decision: str = Form(...),
    comentario_respuesta: str | None = Form(None),
    adjunto: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(solo_lectura_no),
):
    """
    Aprueba o rechaza una autorización, y devuelve la PQRS a Servicio al Cliente.

    La responde quien pertenece al ÁREA autorizadora, sin importar su cargo,
    más admin. Los roles "lectura" y "gerencia" no escriben nada en el portal
    y aquí tampoco: eso lo corta solo_lectura_no.
    """
    if decision not in ("aprobada", "rechazada"):
        raise HTTPException(status_code=400, detail="La decisión debe ser 'aprobada' o 'rechazada'.")

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
                f"Solicítale a alguien de esa área que la revise."
            ),
        )

    pqrs = db.query(PQRSSolicitud).filter(
        PQRSSolicitud.id == pqrs_id,
        PQRSSolicitud.tenant_id == tenant_id,
    ).first()
    if not pqrs:
        raise HTTPException(status_code=404, detail="PQRS no encontrada.")

    ruta_adjunto = None
    if adjunto is not None and adjunto.filename:
        ruta_adjunto = await guardar_archivo(adjunto, "autorizaciones")

    autorizacion.estado = decision
    autorizacion.autorizado_por = current_user.id
    autorizacion.comentario_respuesta = comentario_respuesta
    autorizacion.adjunto_respuesta = ruta_adjunto
    autorizacion.fecha_respuesta = datetime.now(timezone.utc)

    detalle = [f"Autorización '{autorizacion.tipo.nombre}' {decision}."]

    # Con la respuesta ya dada, el caso vuelve a quien reparte. Dejarlo en el
    # área autorizadora sería dejarlo con quien ya hizo su parte: nadie más lo
    # tiene en su bandeja y el plazo sigue corriendo.
    if pqrs.estado != "cerrado" and pqrs.area_responsable != AREA_SERVICIO_CLIENTE:
        detalle.append(
            f"Área: {pqrs.area_responsable or 'sin asignar'} -> {AREA_SERVICIO_CLIENTE}."
        )
        pqrs.area_responsable = AREA_SERVICIO_CLIENTE

    if comentario_respuesta:
        detalle.append(comentario_respuesta.strip())

    db.add(PQRSSeguimiento(
        pqrs_id=pqrs_id,
        usuario_id=current_user.id,
        tipo_evento="autorizacion_respondida",
        comentario=" ".join(detalle),
        adjunto_evidencia=ruta_adjunto,
    ))
    db.commit()
    db.refresh(autorizacion)

    # Al área a la que vuelve el caso hay que decirle que ya hay respuesta: es
    # la que tiene que hacer algo con el sí o con el no.
    background.add_task(enviar_avisos, avisos_autorizacion_respondida(
        db, tenant_id, pqrs, pqrs.area_responsable,
        autorizacion.tipo.nombre, decision, current_user.nombre,
    ))

    return autorizacion