"""
Cliente mínimo de Microsoft Graph para escribir en los calendarios de Outlook.

Autentica como aplicación (client credentials), no como usuario: el portal
ya tiene su propio login, y pedirle además a cada persona que inicie sesión
con Microsoft sería pedir dos veces lo mismo. Por eso la app de Entra ID
lleva el permiso `Calendars.ReadWrite` de APLICACIÓN.

Regla de esta capa: **nada de lo que pase aquí puede tumbar una petición
del portal**. Si Microsoft está caído, si el secreto expiró o si alguien
no tiene buzón, se registra en el log y la vida sigue — el calendario es
un extra, y nadie puede quedarse sin registrar su trabajo porque Graph
falle. Por eso todas las funciones devuelven None en vez de reventar.
"""
import logging
import time

import httpx

from app.core.config import settings

logger = logging.getLogger("outlook.graph")

GRAPH_URL = "https://graph.microsoft.com/v1.0"
TIMEOUT = 15.0

# El token vale ~1 hora; se guarda para no pedir uno nuevo en cada llamada.
# Se renueva 5 minutos antes de vencer para no usar uno recién caducado.
_token_cache: dict = {"valor": None, "vence_en": 0.0}
MARGEN_RENOVACION = 300


def graph_configurado() -> bool:
    """¿Están las tres credenciales? Si no, la integración está apagada."""
    return bool(
        settings.MS_TENANT_ID and settings.MS_CLIENT_ID and settings.MS_CLIENT_SECRET
    )


def _obtener_token() -> str | None:
    if not graph_configurado():
        return None

    ahora = time.time()
    if _token_cache["valor"] and ahora < _token_cache["vence_en"] - MARGEN_RENOVACION:
        return _token_cache["valor"]

    url = f"https://login.microsoftonline.com/{settings.MS_TENANT_ID}/oauth2/v2.0/token"
    datos = {
        "client_id": settings.MS_CLIENT_ID,
        "client_secret": settings.MS_CLIENT_SECRET,
        "scope": "https://graph.microsoft.com/.default",
        "grant_type": "client_credentials",
    }
    try:
        r = httpx.post(url, data=datos, timeout=TIMEOUT)
        if r.status_code != 200:
            # El caso más común aquí es el secreto vencido o mal copiado
            # (haber pegado el "Id. secreto" en vez de su "Valor").
            logger.error(
                "Microsoft Graph rechazó las credenciales (%s): %s. "
                "Revisa MS_CLIENT_SECRET en el .env — si el secreto venció, "
                "hay que generar otro en Entra ID.",
                r.status_code, r.text[:300],
            )
            return None

        cuerpo = r.json()
        _token_cache["valor"] = cuerpo["access_token"]
        _token_cache["vence_en"] = ahora + float(cuerpo.get("expires_in", 3600))
        return _token_cache["valor"]

    except Exception:
        logger.exception("No se pudo pedir el token a Microsoft Graph.")
        return None


def _peticion(
    metodo: str,
    ruta: str,
    json: dict | None = None,
    params: dict | None = None,
    headers_extra: dict | None = None,
) -> dict | None:
    """
    Llama a Graph y devuelve el JSON de respuesta, o None si algo falló.
    `ruta` va sin el host, empezando por barra: "/users/x@y.com/events".
    """
    token = _obtener_token()
    if not token:
        return None

    cabeceras = {"Authorization": f"Bearer {token}"}
    if headers_extra:
        cabeceras.update(headers_extra)

    try:
        r = httpx.request(
            metodo,
            f"{GRAPH_URL}{ruta}",
            headers=cabeceras,
            json=json,
            params=params,
            timeout=TIMEOUT,
        )
    except Exception:
        logger.exception("Falló la llamada a Graph %s %s", metodo, ruta)
        return None

    if r.status_code == 404:
        # El evento ya no existe (alguien lo borró a mano en Outlook) o el
        # buzón no existe. No es un error que haya que gritar.
        logger.info("Graph respondió 404 en %s %s", metodo, ruta)
        return None

    if r.status_code == 403:
        logger.error(
            "Graph negó el acceso en %s %s. Revisa que el permiso "
            "Calendars.ReadWrite sea de APLICACIÓN y tenga el consentimiento "
            "de administrador; si configuraste una Application Access Policy, "
            "que esa persona esté en el grupo. Detalle: %s",
            metodo, ruta, r.text[:300],
        )
        return None

    if r.status_code >= 400:
        logger.error("Graph falló %s en %s %s: %s",
                     r.status_code, metodo, ruta, r.text[:300])
        return None

    if r.status_code == 204 or not r.content:
        return {}
    return r.json()


# ── Calendario ────────────────────────────────────────────────────────────

def crear_evento(email_usuario: str, evento: dict) -> str | None:
    """Crea el evento en el calendario de esa persona y devuelve su id."""
    respuesta = _peticion("POST", f"/users/{email_usuario}/events", json=evento)
    return respuesta.get("id") if respuesta else None


def actualizar_evento(email_usuario: str, evento_id: str, evento: dict) -> bool:
    respuesta = _peticion(
        "PATCH", f"/users/{email_usuario}/events/{evento_id}", json=evento
    )
    return respuesta is not None


def borrar_evento(email_usuario: str, evento_id: str) -> bool:
    respuesta = _peticion("DELETE", f"/users/{email_usuario}/events/{evento_id}")
    return respuesta is not None


def listar_eventos(email_usuario: str, desde: str, hasta: str, zona: str) -> list[dict]:
    """
    Los eventos del calendario entre dos fechas (ISO 8601).

    Usa calendarView y no /events porque calendarView expande las series
    repetidas: una reunión semanal aparece como sus ocurrencias reales en
    el rango, que es lo que hay que pintar en un calendario. Con /events
    llegaría una sola entrada con su regla de repetición, y habría que
    recalcular a mano las fechas de cada ocurrencia.

    La cabecera Prefer hace que Graph devuelva las horas ya en la zona
    pedida, en vez de en UTC.
    """
    respuesta = _peticion(
        "GET",
        f"/users/{email_usuario}/calendarView",
        params={
            "startDateTime": desde,
            "endDateTime": hasta,
            "$select": "id,subject,start,end,isAllDay,sensitivity,showAs,"
                       "isOnlineMeeting,onlineMeeting,webLink,organizer",
            "$orderby": "start/dateTime",
            "$top": "200",
        },
        headers_extra={"Prefer": f'outlook.timezone="{zona}"'},
    )
    if not respuesta:
        return []
    return respuesta.get("value", [])
