"""
Avisar a n8n, que es quien manda los correos.

Lo usan todos los módulos que notifican. Vivía dentro de PQRS, y Master
Planner y Notas crédito lo importaban de ahí: ninguno podía instalarse sin
PQRS. Lo que se avisa y a quién sigue siendo de cada módulo (su
`notificaciones.py`); aquí solo está cómo se manda.

La regla que sostiene todo: **notificar no puede tumbar la petición.** Para
cuando se avisa, lo importante ya está guardado.
"""
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger("n8n")

# Un aviso es una tupla (evento, payload). Se arma primero y se manda después.
Aviso = tuple[str, dict]

# Se avisa una sola vez por proceso; si no, cada PQRS ensucia el log con tres
# líneas iguales.
_aviso_n8n_sin_configurar = False


def disparar_webhook_n8n(evento: str, payload: dict) -> None:
    """
    Notifica a n8n para automatizaciones: email, Teams, escalamiento, etc.

    Si n8n no está configurado (N8N_WEBHOOK_URL vacío), se ignora
    silenciosamente a propósito (ej. en desarrollo sin n8n levantado).

    Cualquier otro fallo (timeout, conexión rechazada, respuesta de
    error de n8n) SE LOGUEA siempre — nunca debe fallar en silencio,
    porque el único síntoma visible es "no llegó el correo" y sin log
    no hay forma de saber por qué. Nunca lanza excepción hacia arriba:
    un fallo notificando a n8n no debe tumbar la creación/cierre de la
    PQRS, que ya se guardó en la base de datos.

    Ese "nunca lanza" hay que sostenerlo con `except Exception` y no con
    `except httpx.HTTPError`: `httpx.InvalidURL` NO hereda de HTTPError, así
    que un `N8N_WEBHOOK_URL` con un salto de línea o un tabulador invisible
    —cosa de un `.env` mal pegado— se escapaba y tumbaba la petición DESPUÉS
    del commit. El cliente veía "error 500" y la PQRS quedaba radicada igual:
    el peor de los dos mundos, porque volvía a enviarla y quedaba duplicada.
    """
    # Se limpia lo que trae un `.env` escrito a mano: espacios, un salto de
    # línea al final, una barra de más. Con la barra de más la URL quedaba
    # `.../webhook//evento` y n8n contesta 404 — otro "no llega el correo"
    # sin causa aparente.
    url = (getattr(settings, "N8N_WEBHOOK_URL", None) or "").strip().rstrip("/")
    if not url:
        # Sin URL no hay correo. Se dice una vez y en WARNING: el silencio
        # total es lo que hace que "no llegó el correo" tarde días en
        # diagnosticarse.
        global _aviso_n8n_sin_configurar
        if not _aviso_n8n_sin_configurar:
            _aviso_n8n_sin_configurar = True
            logger.warning(
                "N8N_WEBHOOK_URL está vacío: NO se enviará ninguna notificación "
                "por correo (evento '%s' y los siguientes). Configúralo en el .env "
                "y recrea el contenedor con `up -d` (un restart no relee el .env).",
                evento,
            )
        return

    webhook_url = f"{url}/{evento}"
    try:
        resp = httpx.post(webhook_url, json=payload, timeout=10.0)
        if resp.status_code >= 400:
            logger.error(
                "n8n respondió error en '%s' (HTTP %s): %s",
                evento, resp.status_code, resp.text[:500],
            )
        else:
            logger.info("n8n webhook '%s' disparado OK (HTTP %s)", evento, resp.status_code)
    except Exception as exc:
        logger.error(
            "Fallo al llamar webhook de n8n '%s' (%s): %s: %s",
            evento, webhook_url, type(exc).__name__, exc,
        )


def enviar_avisos(avisos: list[Aviso]) -> None:
    """
    Manda los avisos ya preparados. Se ejecuta después de responder.

    Cada uno va por su cuenta: que no llegue el correo del cliente no puede
    impedir que le llegue el aviso a Servicio al Cliente.
    """
    for evento, payload in avisos or []:
        disparar_webhook_n8n(evento, payload)


def protegido(fn, *args, **kwargs) -> list[Aviso]:
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
