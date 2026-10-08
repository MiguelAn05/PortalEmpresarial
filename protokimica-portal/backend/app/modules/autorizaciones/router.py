"""
Módulo de autorizaciones.
- Admin y Líderes pueden crear tipos de autorización
- Agentes pueden solicitar autorización para una PQRS
- Quien pertenece al área autorizadora aprueba, rechaza o DEVUELVE (por
  área, no por cargo)
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

**Devolver no es rechazar.** Rechazar es un «no» del área que firma: el caso
es suyo y la respuesta es negativa. Devolver es «esto no me tocaba» —la PQRS
estaba mal dirigida, el tipo de autorización no aplica a esta área, o falta
información para decidir—. Antes solo había sí o no, así que una PQRS mal
dirigida se quedaba quieta en la bandeja de quien no podía hacer nada con
ella, o se rechazaba para sacársela de encima y el informe contaba un «no»
que nadie dio. Vuelve a quien reparte, como las otras dos, y exige comentario:
una devolución muda obliga a una llamada para saber qué pasó.
"""
from datetime import datetime, timezone

from fastapi import (
    APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile,
)
from sqlalchemy.orm import Session

from app.core.modulos import contratado
from app.core.database import get_db
from app.core.deps import (
    get_current_user, get_current_tenant_id, require_role, solo_lectura_no,
)
from app.modules.autorizaciones.permisos import puede_responder
from app.modules.autorizaciones.service import registrar_solicitud
from app.modules.pqrs import flujo
from app.models.user import User
from app.models.pqrs import PQRSSeguimiento
from app.models.autorizacion import TipoAutorizacion, AutorizacionPQRS
from app.modules.autorizaciones.schemas import (
    TipoAutorizacionCreate, TipoAutorizacionOut, AutorizacionOut,
)
from app.core import capacidades
from app.modules.pqrs.permisos import CAPACIDAD_GESTION, obtener_visible
from app.core.archivos import guardar_archivo
from app.core.notificaciones import enviar_avisos
from app.modules.pqrs import tiempo_en_area
from app.modules.pqrs.notificaciones import (
    avisos_autorizacion_pendiente, avisos_autorizacion_respondida,
)

# aprobada: el área firmó que sí. rechazada: firmó que no. devuelta: no le
# correspondía o le falta información — no es un «no», y se cuenta aparte.
DECISIONES = ("aprobada", "rechazada", "devuelta")

router = APIRouter(
    prefix="/autorizaciones", tags=["Autorizaciones"],
    dependencies=[Depends(contratado("pqrs"))],
)


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
    # Si la PQRS no es visible para quien pregunta, sus autorizaciones
    # tampoco: responden 404, igual que la PQRS.
    obtener_visible(db, tenant_id, pqrs_id, current_user)

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

    pqrs = obtener_visible(db, tenant_id, pqrs_id, current_user)

    tipo = db.query(TipoAutorizacion).filter(
        TipoAutorizacion.id == tipo_id,
        TipoAutorizacion.tenant_id == tenant_id,
    ).first()
    if not tipo:
        raise HTTPException(
            status_code=404,
            detail="Ese tipo de autorización no existe. Revisa la lista o pídele a un administrador que lo cree.",
        )

    ruta_adjunto = None
    if adjunto is not None and adjunto.filename:
        ruta_adjunto = await guardar_archivo(adjunto, "autorizaciones")

    autorizacion = registrar_solicitud(
        db, pqrs, tipo, current_user.id,
        comentario=comentario_solicitud, ruta_adjunto=ruta_adjunto,
    )
    # Pedida a mano con un flujo andando, entra a la cadena como un paso más:
    # si no, al responderla el flujo no sabría que existe.
    flujo.al_pedir_a_mano(db, pqrs, autorizacion, current_user.id)
    db.commit()
    db.refresh(autorizacion)

    # El aviso se ARMA aquí, con la sesión viva, y se MANDA después de
    # responder. Mover la PQRS al área que firma sin avisarle es dejarla
    # esperando a que a alguien de esa área se le ocurra abrir el portal.
    background.add_task(enviar_avisos, avisos_autorizacion_pendiente(
        db, tenant_id, pqrs, tipo.area_autorizadora,
        tipo.nombre, current_user.nombre,
        comentario=comentario_solicitud,
        tiene_adjunto=bool(ruta_adjunto),
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
    Aprueba, rechaza o devuelve una autorización, y la PQRS vuelve a quien
    reparte (Servicio al Cliente en Protokimica).

    La responde quien pertenece al ÁREA autorizadora, sin importar su cargo,
    más admin. Los roles "lectura" y "gerencia" no escriben nada en el portal
    y aquí tampoco: eso lo corta solo_lectura_no.
    """
    if decision not in DECISIONES:
        raise HTTPException(
            status_code=400,
            detail="La decisión debe ser 'aprobada', 'rechazada' o 'devuelta'.",
        )
    comentario_respuesta = (comentario_respuesta or "").strip() or None
    if decision == "devuelta" and not comentario_respuesta:
        raise HTTPException(
            status_code=400,
            detail=(
                "Para devolver la autorización escribe por qué: si no le "
                "corresponde a tu área, o qué información falta."
            ),
        )

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

    pqrs = obtener_visible(db, tenant_id, pqrs_id, current_user)

    ruta_adjunto = None
    if adjunto is not None and adjunto.filename:
        ruta_adjunto = await guardar_archivo(adjunto, "autorizaciones")

    autorizacion.estado = decision
    autorizacion.autorizado_por = current_user.id
    autorizacion.comentario_respuesta = comentario_respuesta
    autorizacion.adjunto_respuesta = ruta_adjunto
    autorizacion.fecha_respuesta = datetime.now(timezone.utc)

    detalle = [f"Autorización '{autorizacion.tipo.nombre}' {decision}."]
    if decision == "devuelta":
        detalle = [
            f"Autorización '{autorizacion.tipo.nombre}' devuelta por "
            f"{autorizacion.tipo.area_autorizadora}: no le corresponde o falta "
            "información."
        ]

    # Si la autorización es un paso del flujo, se marca y se sabe qué sigue
    # (todavía sin pedirlo: primero queda el renglón de esta respuesta).
    resultado = flujo.registrar_respuesta(db, pqrs, autorizacion, decision)
    sigue = resultado["sigue"] if pqrs.estado != "cerrado" else None

    if sigue:
        # El flujo sigue: el caso pasa DIRECTO a la siguiente área, sin
        # volver a Servicio al Cliente en cada paso. Eso es lo que evita que
        # alguien tenga que acordarse de a quién le toca.
        detalle.append(f"El flujo sigue con: {sigue.tipo.nombre}.")
    else:
        # Con la respuesta ya dada, el caso vuelve a quien reparte. Dejarlo en
        # el área autorizadora sería dejarlo con quien ya hizo su parte: nadie
        # más lo tiene en su bandeja y el plazo sigue corriendo. Quien reparte
        # es el área que tiene `pqrs.cerrar` —Servicio al Cliente en
        # Protokimica—; si nadie la tiene por área, el caso se queda donde está.
        if resultado["en_flujo"]:
            detalle.append(
                "Flujo completo: ya respondieron todos los conceptos."
                if resultado["estado"] == "completa"
                else "El flujo quedó detenido: Servicio al Cliente decide si se vuelve a pedir, se sigue o se termina."
            )
        reparte = capacidades.area_principal(db, tenant_id, CAPACIDAD_GESTION)
        if pqrs.estado != "cerrado" and reparte and pqrs.area_responsable != reparte:
            detalle.append(f"Área: {pqrs.area_responsable or 'sin asignar'} -> {reparte}.")
            area_que_firmo = pqrs.area_responsable
            pqrs.area_responsable = reparte
            # Vuelve a quien reparte con el reloj en cero.
            tiempo_en_area.registrar_cambio(db, pqrs, area_que_firmo, pqrs.estado)

    if comentario_respuesta:
        detalle.append(comentario_respuesta)

    db.add(PQRSSeguimiento(
        pqrs_id=pqrs_id,
        usuario_id=current_user.id,
        tipo_evento="autorizacion_respondida",
        comentario=" ".join(detalle),
        adjunto_evidencia=ruta_adjunto,
    ))
    db.flush()

    siguiente = flujo.pedir_siguiente(db, pqrs, current_user.id) if sigue else None
    db.commit()
    db.refresh(autorizacion)

    if siguiente:
        # Se avisa a la siguiente área que le toca. A Servicio al Cliente no
        # se le escribe en cada paso: se le avisa cuando el flujo termina o se
        # detiene, que es cuando tiene algo que hacer.
        paso, _nueva = siguiente
        background.add_task(enviar_avisos, avisos_autorizacion_pendiente(
            db, tenant_id, pqrs, paso.tipo.area_autorizadora,
            paso.tipo.nombre, current_user.nombre,
            comentario=f"Viene de «{autorizacion.tipo.nombre}», aprobada por {current_user.nombre}.",
        ))
    else:
        # Al área a la que vuelve el caso hay que decirle que ya hay
        # respuesta: es la que tiene que hacer algo con el sí o con el no.
        background.add_task(enviar_avisos, avisos_autorizacion_respondida(
            db, tenant_id, pqrs, pqrs.area_responsable,
            autorizacion.tipo.nombre, decision, current_user.nombre,
            comentario=comentario_respuesta,
            tiene_adjunto=bool(ruta_adjunto),
        ))

    return autorizacion