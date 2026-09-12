"""
Notificaciones de PQRS.

Punto único donde se decide QUÉ se notifica y A QUIÉN, tanto para el
cliente (correo externo) como para los usuarios internos (por área/rol).
Los routers solo llaman a estas funciones en el momento en que ocurre
el evento — no arman payloads de n8n directamente.

**Se prepara dentro de la petición y se envía después de responder.**
Armar el aviso necesita la base de datos (hay que buscar los correos del
área), así que eso se hace con la sesión todavía abierta; mandarlo es una
llamada HTTP que puede tardar diez segundos por webhook y no tiene por qué
hacer esperar a quien radicó la PQRS. Radicar disparaba hasta tres webhooks
en serie: medio minuto mirando un botón girando, y si el navegador se
cansaba antes, la persona volvía a enviar el formulario y quedaba duplicado.

Por eso cada función devuelve una lista de avisos `(evento, payload)` y el
router los manda con `background.add_task(enviar_avisos, avisos)`.

Nada de esto puede tumbar la petición: para cuando se notifica, la PQRS ya
está guardada. Un fallo notificando se registra en el log y se acabó.

Para agregar una notificación nueva en el futuro (ej. "PQRS vencida"):
  1. Crear una función nueva aquí, siguiendo el mismo patrón.
  2. Llamarla desde el router en el punto donde ocurre el evento.
  3. Armar el flujo correspondiente en n8n (mismo webhook, nuevo path).
No hace falta tocar nada más.

Eventos que disparamos hoy (nombres = path del webhook en n8n):
  - pqrs-creada-cliente          -> confirmación de radicación al cliente
  - pqrs-resuelta-cliente        -> la solución, pidiendo que confirme
                                     (ver `pqrs/cierre_automatico.py` para
                                     qué pasa si no contesta)
  - pqrs-cerrada                 -> aviso de cierre al cliente (+ encuesta),
                                     con la solución de recuerdo
  - pqrs-notificacion-area       -> aviso a los usuarios de un área
                                     (motivo: "creacion" | "reasignacion")
  - pqrs-nueva-servicio-cliente  -> aviso SIEMPRE a Servicio al Cliente
                                     al crearse, sin importar el área
                                     asignada
"""
import logging

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User
from app.modules.pqrs.service import disparar_webhook_n8n

logger = logging.getLogger("pqrs.n8n")

# Un aviso es una tupla (evento, payload). Se arma primero y se manda después.
Aviso = tuple[str, dict]

# El nombre del evento ES el path del webhook en n8n. Se declaran aquí y no
# sueltos en cada función para que exista un solo sitio donde mirar cuando
# haya que armar el flujo del otro lado — y para que una prueba pueda
# comparar estos nombres contra los flujos de `backend/n8n/`. Un path mal
# escrito no falla: n8n contesta 404 y el correo no llega, sin más señal.
EVENTO_CREADA_CLIENTE = "pqrs-creada-cliente"
EVENTO_SERVICIO_CLIENTE = "pqrs-nueva-servicio-cliente"
EVENTO_AREA = "pqrs-notificacion-area"
EVENTO_CERRADA = "pqrs-cerrada"
EVENTO_AUTORIZACION = "pqrs-autorizacion"
EVENTO_RESUELTA = "pqrs-resuelta-cliente"

EVENTOS = frozenset({
    EVENTO_CREADA_CLIENTE,
    EVENTO_SERVICIO_CLIENTE,
    EVENTO_AREA,
    EVENTO_CERRADA,
    EVENTO_AUTORIZACION,
    EVENTO_RESUELTA,
})

# Días hábiles que se le dan al cliente para confirmar la solución antes de
# cerrar solo. Vive aquí —y no en `cierre_automatico.py`, que es quien lo
# usa para calcular el plazo— porque el correo de "resuelto" también lo
# necesita para decir el número correcto, y notificaciones.py no puede
# importar de cierre_automatico.py sin crear un ciclo (ese módulo sí importa
# de aquí, para mandar avisos_cierre al cerrar solo).
DIAS_ESPERA_CLIENTE = 3


def enviar_avisos(avisos: list[Aviso]) -> None:
    """
    Manda los avisos ya preparados. Se ejecuta después de responder.

    Cada uno va por su cuenta: que no llegue el correo del cliente no puede
    impedir que le llegue el aviso a Servicio al Cliente.
    """
    for evento, payload in avisos or []:
        disparar_webhook_n8n(evento, payload)


def _correos_por_area(db: Session, tenant_id: int, area: str) -> list[str]:
    """Correos de los usuarios activos del tenant que pertenecen a esa área."""
    if not area:
        return []

    area_norm = area.strip().lower()
    usuarios = (
        db.query(User)
        .filter(User.tenant_id == tenant_id, User.activo == True)  # noqa: E712
        .all()
    )
    return [
        u.email for u in usuarios
        if u.area and u.area.strip().lower() == area_norm and u.email
    ]


def _protegido(fn, *args, **kwargs) -> list[Aviso]:
    """
    Arma un aviso sin poder tumbar la petición.

    Preparar también falla: un campo que ya no existe en el modelo, la
    consulta de correos contra una base que se cayó. Y como esto corre
    después del commit, una excepción aquí dejaba la PQRS creada y al
    cliente viendo un error 500 — que es peor que no avisar, porque lo
    normal es que vuelva a enviar el formulario.
    """
    try:
        return fn(*args, **kwargs) or []
    except Exception as exc:
        logger.error(
            "No se pudo preparar la notificación %s: %s: %s",
            getattr(fn, "__name__", fn), type(exc).__name__, exc,
        )
        return []


# ── Notificaciones al cliente (externas) ────────────────────────────

def _aviso_cliente_creacion(solicitud) -> list[Aviso]:
    """Confirmación al cliente de que su PQRS fue radicada."""
    if not solicitud.cliente_email:
        return []
    return [(EVENTO_CREADA_CLIENTE, {
        "pqrs_id": solicitud.id,
        "codigo_seguimiento": solicitud.codigo_seguimiento,
        "cliente_nombre": solicitud.cliente_nombre,
        "cliente_email": solicitud.cliente_email,
        "tipo": solicitud.tipo,
        "link_seguimiento": f"{settings.FRONTEND_URL}/seguimiento",
    })]


def _aviso_servicio_cliente(db: Session, tenant_id: int, solicitud) -> list[Aviso]:
    """
    Avisa SIEMPRE al equipo de Servicio al Cliente cuando entra una PQRS
    nueva — a diferencia de los avisos de área, esto no depende de a qué
    área quedó asignada la solicitud (podría quedar asignada a Calidad,
    Logística, etc., y aun así Servicio al Cliente debe enterarse).

    Requiere que al menos un usuario activo tenga el campo `area` igual
    a "Servicio al Cliente". Si no hay ninguno configurado así, no se
    envía nada (no es un error, pero se deja dicho en el log: es la causa
    más común de "a Servicio al Cliente no le llega nada").
    """
    destinatarios = _correos_por_area(db, tenant_id, "Servicio al Cliente")
    if not destinatarios:
        logger.warning(
            "PQRS %s: ningún usuario activo tiene el área 'Servicio al Cliente', "
            "así que nadie recibirá el aviso de radicación. Se asigna en "
            "Administración › Usuarios.",
            solicitud.id,
        )
        return []

    return [(EVENTO_SERVICIO_CLIENTE, {
        "pqrs_id": solicitud.id,
        "codigo_seguimiento": solicitud.codigo_seguimiento,
        "radicado_calidad": solicitud.radicado_calidad,
        "tipo": solicitud.tipo,
        "area_responsable": solicitud.area_responsable,
        "cliente_nombre": solicitud.cliente_nombre,
        "canal_atencion": solicitud.canal_atencion,
        "descripcion": (solicitud.descripcion or "")[:280],
        "destinatarios": destinatarios,
        "link_portal": f"{settings.FRONTEND_URL}/pqrs/{solicitud.id}",
    })]


def _aviso_area(db: Session, tenant_id: int, solicitud, area: str, motivo: str) -> list[Aviso]:
    """
    Avisa únicamente a los usuarios pertenecientes a `area` — nunca a
    todo el sistema ni a otras áreas.

    motivo: "creacion"     -> se acaba de radicar y quedó asignada a esta área
            "reasignacion" -> se movió de otra área a esta

    Lo de las autorizaciones va por su propio evento (`_aviso_autorizacion`):
    compartir esta plantilla hacía que a quien le pedían firmar le llegara un
    «Les asignaron una PQRS».
    """
    if not area:
        return []

    destinatarios = _correos_por_area(db, tenant_id, area)
    if not destinatarios:
        return []  # nadie configurado en esa área todavía — nada que enviar

    return [(EVENTO_AREA, {
        "pqrs_id": solicitud.id,
        "codigo_seguimiento": solicitud.codigo_seguimiento,
        "radicado_calidad": solicitud.radicado_calidad,  # solo va lleno si area == Calidad
        "area": area,
        "motivo": motivo,
        "tipo": solicitud.tipo,
        "cliente_nombre": solicitud.cliente_nombre,
        "descripcion": (solicitud.descripcion or "")[:280],
        "destinatarios": destinatarios,
        "link_portal": f"{settings.FRONTEND_URL}/pqrs/{solicitud.id}",
    })]


def _aviso_cliente_resuelta(solicitud) -> list[Aviso]:
    """
    La solución, pidiéndole al cliente que confirme si quedó bien.

    Antes el cliente nunca se enteraba de QUÉ se le solucionó — el correo
    de cierre solo traía la encuesta. El soporte (fotos, PDF) se ANUNCIA,
    nunca se enlaza: `/uploads` todavía no tiene control de acceso, así que
    poner la URL en un correo es repartir una evidencia a quien lo reenvíe.
    El botón lleva a una página del portal que sí las muestra.
    """
    if not solicitud.cliente_email:
        return []
    return [(EVENTO_RESUELTA, {
        "pqrs_id": solicitud.id,
        "codigo_seguimiento": solicitud.codigo_seguimiento,
        "cliente_nombre": solicitud.cliente_nombre,
        "cliente_email": solicitud.cliente_email,
        "tipo": solicitud.tipo,
        "solucion": solicitud.solucion or "",
        "tiene_adjuntos": bool(solicitud.adjuntos_solucion),
        # Se repite aquí en vez de que n8n lo calcule: el número de días es
        # una decisión de negocio (`cierre_automatico.DIAS_ESPERA_CLIENTE`),
        # y el correo no puede quedar diciendo un plazo que el código ya
        # cambió.
        "dias_espera": DIAS_ESPERA_CLIENTE,
        "link_confirmar": f"{settings.FRONTEND_URL}/confirmar/{solicitud.codigo_seguimiento}",
    })]


def _aviso_cliente_cierre(solicitud, motivo_cierre: str) -> list[Aviso]:
    """
    Aviso al cliente de que su PQRS fue cerrada (con link a la encuesta).

    motivo_cierre: "manual"           -> Servicio al Cliente la cerró directo
                   "cliente_confirmo" -> el cliente dijo que sí quedó bien
                   "automatico"       -> no respondió en el plazo

    La solución va de recuerdo: si cerró por confirmación o por plazo
    vencido, el cliente ya la vio en el correo de "resuelto", pero no
    todo el mundo guarda ese correo.
    """
    if not solicitud.cliente_email:
        return []
    return [(EVENTO_CERRADA, {
        "pqrs_id": solicitud.id,
        "codigo_seguimiento": solicitud.codigo_seguimiento,
        "cliente_nombre": solicitud.cliente_nombre,
        "cliente_email": solicitud.cliente_email,
        "tipo": solicitud.tipo,
        "area_responsable": solicitud.area_responsable,
        "motivo_cierre": motivo_cierre,
        "solucion": solicitud.solucion or "",
        "link_seguimiento": f"{settings.FRONTEND_URL}/seguimiento",
        "link_encuesta": f"{settings.FRONTEND_URL}/encuesta/{solicitud.codigo_seguimiento}",
    })]


# ── Lo que usan los routers ──────────────────────────────────────────

def _aviso_area_creacion(db: Session, tenant_id: int, solicitud) -> list[Aviso]:
    # El área se lee aquí dentro, no en el argumento de `_protegido`: un
    # argumento se evalúa ANTES de entrar a la función que lo protege, así
    # que leerlo afuera dejaba justo ese acceso sin red.
    return _aviso_area(db, tenant_id, solicitud, solicitud.area_responsable, "creacion")


def avisos_creacion(db: Session, tenant_id: int, solicitud) -> list[Aviso]:
    """Todo lo que se notifica cuando entra una PQRS, venga de donde venga."""
    return [
        *_protegido(_aviso_cliente_creacion, solicitud),
        *_protegido(_aviso_servicio_cliente, db, tenant_id, solicitud),
        *_protegido(_aviso_area_creacion, db, tenant_id, solicitud),
    ]


def avisos_reasignacion(db: Session, tenant_id: int, solicitud, area: str) -> list[Aviso]:
    return _protegido(_aviso_area, db, tenant_id, solicitud, area, "reasignacion")


def _aviso_autorizacion(db: Session, tenant_id: int, solicitud, area: str,
                        motivo: str, autorizacion: str, persona: str,
                        decision: str, comentario: str | None,
                        tiene_adjunto: bool) -> list[Aviso]:
    """
    El correo de una autorización: la piden, o ya la respondieron.

    Va por su propio evento y no montado en el aviso de área, porque dice otra
    cosa. Cuando compartían plantilla, a quien le pedían autorizar una nota
    crédito le llegaba un correo que decía «Les asignaron una PQRS»: llegaba,
    y no decía a qué lo estaban llamando.

    motivo: "pendiente"  -> a esta área le toca firmar
            "respondida" -> ya hay sí o no, y el caso vuelve

    **El adjunto viaja como un sí/no, nunca como enlace.** `/uploads` todavía
    no tiene control de acceso, así que meter la URL en un correo es repartir
    una evidencia de auditoría a quien reenvíe el mensaje. El botón lleva al
    portal, donde hay sesión.
    """
    destinatarios = _correos_por_area(db, tenant_id, area)
    if not destinatarios:
        return []

    return [(EVENTO_AUTORIZACION, {
        "pqrs_id": solicitud.id,
        "codigo_seguimiento": solicitud.codigo_seguimiento,
        "tipo": solicitud.tipo,
        "cliente_nombre": solicitud.cliente_nombre,
        "area": area,
        "motivo": motivo,
        "autorizacion": autorizacion,
        "persona": persona,
        "decision": decision,
        "comentario": (comentario or "")[:280],
        "tiene_adjunto": tiene_adjunto,
        "destinatarios": destinatarios,
        "link_portal": f"{settings.FRONTEND_URL}/pqrs/{solicitud.id}",
    })]


def avisos_autorizacion_pendiente(db: Session, tenant_id: int, solicitud, area: str,
                                  autorizacion: str, solicitante: str,
                                  comentario: str | None = None,
                                  tiene_adjunto: bool = False) -> list[Aviso]:
    """
    Le avisa al área que tiene que firmar.

    Mover la PQRS a esa área sin avisarle es dejar la solicitud esperando a que
    alguien de Contabilidad, por su cuenta, se le ocurra abrir el portal. El
    plazo de la PQRS mientras tanto sigue corriendo.
    """
    return _protegido(
        _aviso_autorizacion, db, tenant_id, solicitud, area,
        "pendiente", autorizacion, solicitante, "", comentario, tiene_adjunto,
    )


def avisos_autorizacion_respondida(db: Session, tenant_id: int, solicitud, area: str,
                                   autorizacion: str, decision: str,
                                   respondida_por: str,
                                   comentario: str | None = None,
                                   tiene_adjunto: bool = False) -> list[Aviso]:
    """Le avisa al área a la que vuelve el caso, con el sí o el no ya dado."""
    return _protegido(
        _aviso_autorizacion, db, tenant_id, solicitud, area,
        "respondida", autorizacion, respondida_por, decision,
        comentario, tiene_adjunto,
    )


def avisos_cierre(solicitud, motivo_cierre: str = "manual") -> list[Aviso]:
    return _protegido(_aviso_cliente_cierre, solicitud, motivo_cierre)


def avisos_resuelta(solicitud) -> list[Aviso]:
    return _protegido(_aviso_cliente_resuelta, solicitud)


def _aviso_area_rechazo(db: Session, tenant_id: int, solicitud,
                        comentario_cliente: str) -> list[Aviso]:
    """
    El cliente dijo que la solución NO le sirvió: avisa al área que tiene
    el caso hoy. Va por el mismo evento que el resto de avisos de área
    (`EVENTO_AREA`) y se distingue por `motivo`, en vez de abrir un webhook
    nuevo en n8n para un aviso que en el fondo es "esto necesita que alguien
    lo mire otra vez".
    """
    area = solicitud.area_responsable
    if not area:
        return []
    destinatarios = _correos_por_area(db, tenant_id, area)
    if not destinatarios:
        return []
    return [(EVENTO_AREA, {
        "pqrs_id": solicitud.id,
        "codigo_seguimiento": solicitud.codigo_seguimiento,
        "radicado_calidad": solicitud.radicado_calidad,
        "area": area,
        "motivo": "cliente_rechazo",
        "tipo": solicitud.tipo,
        "cliente_nombre": solicitud.cliente_nombre,
        "descripcion": (comentario_cliente or "")[:280],
        "destinatarios": destinatarios,
        "link_portal": f"{settings.FRONTEND_URL}/pqrs/{solicitud.id}",
    })]


def avisos_cliente_rechazo(db: Session, tenant_id: int, solicitud,
                           comentario_cliente: str) -> list[Aviso]:
    return _protegido(_aviso_area_rechazo, db, tenant_id, solicitud, comentario_cliente)
