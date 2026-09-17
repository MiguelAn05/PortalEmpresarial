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

from app.core import bodegas, canales
from app.core.capacidades import tiene
from app.core.database import get_db
from app.core.deps import (
    get_current_user, get_current_tenant_id, require_role, solo_lectura_no,
)
from app.models.nota_credito import (
    ESTADO_APLICADA, ESTADO_APROBADA, ESTADO_CANCELADA, ESTADO_DEVUELTA,
    ESTADO_RECHAZADA, ESTADOS_ABIERTOS,
    MotivoNotaCredito, SolicitudNotaCredito,
)
from app.models.user import User
from app.modules.notas_credito import flujo, service
from app.modules.notas_credito.permisos import (
    filtrar_visibles, mensaje_falta_capacidad, puede_atender, puede_radicar,
    puede_registrar, puede_ver,
)
from app.modules.notas_credito.schemas import (
    AlcanceNotaCredito, AplicarSolicitud, ComentarioOpcional, MotivoCreate, MotivoOut,
    HistorialOut, ResponderSolicitud, SolicitudDetailOut, SolicitudOut,
    MAX_FACTURA, MAX_NUMERO_NC, MAX_OBSERVACIONES,
)
from app.modules.notas_credito.notificaciones import (
    avisos_devuelta, avisos_en_turno, avisos_por_emitir, avisos_respondida,
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

    motivo = MotivoNotaCredito(tenant_id=tenant_id, nombre=nombre, activo=True,
                               requiere_bodega=payload.requiere_bodega)
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
    bodega: str | None = Form(None),
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

    # De qué cadena es: el canal decide la rama y el motivo decide si hay que
    # pasar por bodega. Las dos cosas se resuelven aquí, una sola vez, y de
    # ahí sale el primer turno.
    institucional = flujo.es_institucional(punto_venta)
    pasa_por_bodega = institucional and service.requiere_bodega(db, tenant_id, motivo_id)

    bodega = bodegas.normalizar(bodega)
    if not bodegas.es_valida(bodega):
        raise HTTPException(
            status_code=400,
            detail=f"'{bodega}' no es una bodega del portal. Elige una de la lista.",
        )
    if pasa_por_bodega and not bodega:
        raise HTTPException(
            status_code=400,
            detail=(
                "Este motivo implica producto devuelto: dinos a qué bodega "
                "entró para que allá confirmen que llegó."
            ),
        )
    if not pasa_por_bodega:
        # Una bodega en algo que no mueve producto solo puede confundir
        # después: nadie tendría que confirmarla y quedaría en el informe
        # diciendo que entró mercancía donde no entró ninguna.
        bodega = None

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
        bodega=bodega,
        observaciones=observaciones,
        adjunto=ruta_adjunto,
        solicitado_por=current_user.id,
        estado=flujo.estado_inicial(punto_venta, pasa_por_bodega),
    )
    db.add(solicitud)
    db.commit()
    db.refresh(solicitud)

    # El consecutivo se asigna con el id ya real, igual que el código de
    # seguimiento de una PQRS.
    solicitud.codigo = service.generar_codigo(db, tenant_id)
    service.anotar(db, solicitud, solicitud.estado, "creada", current_user, observaciones)
    db.commit()
    db.refresh(solicitud)

    # El aviso se ARMA aquí, con la sesión viva, y se MANDA después de
    # responder: la solicitud ya quedó guardada, y si notificar reventara, el
    # punto de venta vería un error sobre algo que sí se radicó y lo volvería
    # a enviar.
    background.add_task(enviar_avisos, avisos_en_turno(db, tenant_id, solicitud))

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
    if estado == "abiertas":
        # Un atajo con nombre propio: «lo que todavía está en trámite» es lo
        # que la gente mira de verdad, y pedirlo estado por estado obligaría
        # a la pantalla a conocer la cadena — que es justo lo que vive en el
        # servidor.
        query = query.filter(SolicitudNotaCredito.estado.in_(ESTADOS_ABIERTOS))
    elif estado == "mi_turno":
        query = query.filter(SolicitudNotaCredito.estado.in_(_estados_que_atiende(db, current_user)))
    elif estado:
        query = query.filter(SolicitudNotaCredito.estado == estado)

    query = filtrar_visibles(query, db, current_user)
    return query.order_by(SolicitudNotaCredito.creado_en.desc()).all()


def _estados_que_atiende(db: Session, usuario: User) -> list[str]:
    """
    Los turnos que esta persona puede atender hoy.

    Se resuelve por capacidad y no por área: quien tenga
    `notas_credito.aprobar_comercial` atiende `en_comercial`, lo hayan
    otorgado al área Comercial o a ella por su nombre.
    """
    return [
        estado for estado, capacidad in flujo.CAPACIDAD_POR_ESTADO.items()
        if tiene(db, usuario, capacidad)
    ]


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
    atiende = escribe and puede_atender(db, current_user, solicitud)
    suya = escribe and solicitud.solicitado_por == current_user.id

    detalle = SolicitudDetailOut.model_validate(solicitud)
    detalle.alcance = AlcanceNotaCredito(
        # Es su turno: puede aprobar, rechazar o devolverla para corregir.
        # «Aprobar» significa pasar al siguiente paso de la cadena, no
        # terminarla — quién sigue lo dice `etapa_siguiente`.
        puede_responder=atiende and solicitud.estado != ESTADO_APROBADA,
        # Es la capacidad de REGISTRAR, no la de autorizar — son dos permisos
        # distintos y pueden separarse desde Administración › Capacidades.
        # Solo aplica sobre una ya aprobada: dejarlo antes sería anotar una
        # nota crédito que nadie autorizó.
        puede_aplicar=escribe and puede_registrar(db, current_user)
        and solicitud.estado == ESTADO_APROBADA,
        # Corregir y volver a mandarla, o retirarla, es de quien la pidió.
        puede_reenviar=suya and solicitud.estado == ESTADO_DEVUELTA,
        puede_cancelar=suya and solicitud.estado in ESTADOS_ABIERTOS,
    )
    detalle.etapa_nombre = flujo.etiqueta(solicitud.estado)
    detalle.que_hacer = flujo.QUE_HACER.get(solicitud.estado, "")
    detalle.etapa_siguiente = flujo.etiqueta(siguiente) if (
        siguiente := flujo.siguiente(
            solicitud.estado, solicitud.punto_venta, bool(solicitud.bodega),
        )
    ) else None
    detalle.historial = [
        HistorialOut.model_validate(h) for h in solicitud.historial
    ]
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
    """
    Atiende el turno: aprobar, rechazar o devolver.

    Es **un solo endpoint para toda la cadena** y no uno por etapa. Quién
    puede responder y qué pasa después no depende de la URL que se llame
    sino de en qué etapa está la solicitud, que es lo único que no se puede
    falsear desde el cliente. Con un endpoint por etapa, aprobar «por
    comercial» algo que está en la bodega sería cuestión de escribir la otra
    URL.
    """
    if payload.decision not in flujo.ACCIONES:
        raise HTTPException(
            status_code=400,
            detail="La decisión debe ser 'aprobar', 'rechazar' o 'devolver'.",
        )

    solicitud = _buscar(db, tenant_id, solicitud_id, current_user)
    etapa = solicitud.estado

    if etapa not in ESTADOS_ABIERTOS or etapa in (ESTADO_APROBADA, ESTADO_DEVUELTA):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Esta solicitud está '{flujo.etiqueta(etapa)}'; en este "
                "momento no hay nada que responder."
            ),
        )
    if not puede_atender(db, current_user, solicitud):
        # Quien responde por otra bodega ni siquiera llega hasta aquí: para él
        # la solicitud no existe y `_buscar` ya respondió 404. Esto es para
        # quien SÍ la ve pero no es su turno — Comercial antes de que la
        # bodega confirme, por ejemplo.
        raise HTTPException(
            status_code=403,
            detail=mensaje_falta_capacidad(
                db, tenant_id, flujo.capacidad_de(etapa),
                f"El paso «{flujo.etiqueta(etapa)}»",
            ),
        )

    comentario = (payload.comentario or "").strip() or None
    if payload.decision == flujo.ACCION_DEVOLVER and not comentario:
        raise HTTPException(
            status_code=400,
            detail="Escribe qué hay que corregir: sin eso, quien la pidió no sabe qué arreglar.",
        )

    if payload.decision == flujo.ACCION_RECHAZAR:
        solicitud.estado = ESTADO_RECHAZADA
    elif payload.decision == flujo.ACCION_DEVOLVER:
        solicitud.estado = ESTADO_DEVUELTA
    else:
        solicitud.estado = flujo.siguiente(
            etapa, solicitud.punto_venta, bool(solicitud.bodega),
        ) or ESTADO_APROBADA

    # La última firma queda a la mano de la pantalla; todas las demás, en el
    # historial, que es donde caben.
    solicitud.autorizado_por = current_user.id
    solicitud.comentario_respuesta = comentario
    solicitud.fecha_respuesta = datetime.now(timezone.utc)
    service.anotar(db, solicitud, etapa, payload.decision, current_user, comentario)
    db.commit()
    db.refresh(solicitud)

    _avisar_del_movimiento(background, db, tenant_id, solicitud, etapa,
                           payload.decision, current_user, comentario)
    return solicitud


def _avisar_del_movimiento(background: BackgroundTasks, db: Session, tenant_id: int,
                           solicitud, etapa: str, decision: str, usuario: User,
                           comentario: str | None) -> None:
    """
    A quién le toca enterarse de que la solicitud se movió.

    Vive en una función aparte porque son tres caminos y la regla es la misma
    la use quien la use: si la respuesta cierra el caso se avisa a quien lo
    pidió, si lo devuelve también, y si lo hace avanzar se avisa a quien
    recibe el turno.
    """
    if decision == flujo.ACCION_RECHAZAR:
        background.add_task(enviar_avisos, avisos_respondida(
            db, tenant_id, solicitud, ESTADO_RECHAZADA, usuario.nombre,
        ))
        return

    if decision == flujo.ACCION_DEVOLVER:
        background.add_task(enviar_avisos, avisos_devuelta(
            db, tenant_id, solicitud, etapa, usuario.nombre, comentario,
        ))
        return

    # Avanzó. Aprobada es «falta emitirla» y tiene su propio aviso, que sabe
    # buscar al punto de venta de la factura; las etapas intermedias avisan a
    # quien reciba el turno.
    if solicitud.estado == ESTADO_APROBADA:
        background.add_task(enviar_avisos, avisos_respondida(
            db, tenant_id, solicitud, ESTADO_APROBADA, usuario.nombre,
        ))
        background.add_task(enviar_avisos, avisos_por_emitir(
            db, tenant_id, solicitud, usuario.nombre,
        ))
    else:
        background.add_task(enviar_avisos, avisos_en_turno(db, tenant_id, solicitud))


@router.post("/{solicitud_id}/reenviar", response_model=SolicitudOut)
def reenviar_solicitud(
    solicitud_id: int,
    payload: ComentarioOpcional,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(solo_lectura_no),
):
    """
    La corrigieron y vuelve a empezar su cadena.

    **Vuelve al PRINCIPIO, no al paso donde la devolvieron.** Quien ya había
    aprobado lo hizo mirando unos datos que acaban de cambiar; arrastrar esa
    firma sería darla por buena sin que nadie la vuelva a mirar, que es la
    forma silenciosa de que una devolución no sirva para nada.
    """
    solicitud = _buscar(db, tenant_id, solicitud_id, current_user)

    if solicitud.solicitado_por != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Solo quien pidió la nota crédito puede corregirla y volver a mandarla.",
        )
    if solicitud.estado != ESTADO_DEVUELTA:
        raise HTTPException(
            status_code=400,
            detail=f"Esta solicitud está '{flujo.etiqueta(solicitud.estado)}', no devuelta.",
        )

    solicitud.estado = flujo.estado_inicial(solicitud.punto_venta, bool(solicitud.bodega))
    service.anotar(db, solicitud, ESTADO_DEVUELTA, "reenviada", current_user,
                   payload.comentario)
    db.commit()
    db.refresh(solicitud)

    background.add_task(enviar_avisos, avisos_en_turno(db, tenant_id, solicitud))
    return solicitud


@router.post("/{solicitud_id}/cancelar", response_model=SolicitudOut)
def cancelar_solicitud(
    solicitud_id: int,
    payload: ComentarioOpcional,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(solo_lectura_no),
):
    """
    La retira quien la pidió.

    Es distinto de que se la hayan rechazado, y en el informe tiene que verse
    distinto: una que el vendedor retira porque al revisar no procedía no es
    un caso que la empresa negó. Sin este botón, la salida sería dejarla
    abierta para siempre o pedirle a alguien que la rechace por él — y
    entonces el número de rechazos deja de significar algo.
    """
    solicitud = _buscar(db, tenant_id, solicitud_id, current_user)

    if solicitud.solicitado_por != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Solo quien pidió la nota crédito puede retirarla.",
        )
    if solicitud.estado not in ESTADOS_ABIERTOS:
        raise HTTPException(
            status_code=400,
            detail=f"Esta solicitud ya está '{flujo.etiqueta(solicitud.estado)}'.",
        )

    etapa = solicitud.estado
    solicitud.estado = ESTADO_CANCELADA
    service.anotar(db, solicitud, etapa, "cancelada", current_user, payload.comentario)
    db.commit()
    db.refresh(solicitud)
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

    etapa = solicitud.estado
    solicitud.numero_nc = numero
    solicitud.estado = ESTADO_APLICADA
    solicitud.aplicada_por = current_user.id
    solicitud.fecha_aplicacion = datetime.now(timezone.utc)
    if payload.comentario:
        # Se agrega, no se pisa: el comentario de la aprobación es de otra
        # persona y de otro momento.
        anterior = solicitud.comentario_respuesta or ""
        solicitud.comentario_respuesta = f"{anterior} {payload.comentario.strip()}".strip()
    service.anotar(db, solicitud, etapa, "aplicada", current_user,
                   f"Nota crédito {numero}. {(payload.comentario or '').strip()}".strip())
    db.commit()
    db.refresh(solicitud)

    # Quien la pidio necesita saber que ya existe, y con que numero: es lo
    # que le dice al cliente del almacen que su caso quedo resuelto.
    background.add_task(enviar_avisos, avisos_respondida(
        db, tenant_id, solicitud, ESTADO_APLICADA, current_user.nombre,
    ))

    return solicitud
