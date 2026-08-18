"""
Notificar nunca puede tumbar una PQRS.

Cuando se avisa por correo, la solicitud YA está guardada. Si el aviso
falla y la excepción sube, el cliente ve un error 500 sobre una PQRS que sí
quedó radicada — y lo que hace entonces es volver a enviar el formulario,
así que el error se paga con solicitudes duplicadas.

Eso pasó de verdad: `disparar_webhook_n8n` capturaba `httpx.HTTPError`, pero
`httpx.InvalidURL` no hereda de esa clase. Un `N8N_WEBHOOK_URL` con un salto
de línea invisible al final —un `.env` mal pegado— se escapaba del `except`.
"""
import pytest

from app.core.config import settings
from app.modules.pqrs.notificaciones import (
    avisos_cierre, avisos_creacion, enviar_avisos,
)


@pytest.fixture
def n8n(monkeypatch):
    """Cambia la URL del webhook solo mientras dura la prueba."""
    def poner(valor):
        monkeypatch.setattr(settings, "N8N_WEBHOOK_URL", valor)
    return poner


# Cada uno de estos valores tumbaba la petición o podría hacerlo.
URLS_ROTAS = [
    pytest.param("http://n8n:5678/webhook\n", id="salto-de-linea-invisible"),
    pytest.param("http://n8n:5678/webhook\t", id="tabulador-invisible"),
    pytest.param("  http://n8n:5678/webhook  ", id="espacios-alrededor"),
    pytest.param("n8n:5678/webhook", id="sin-esquema"),
    pytest.param("http://no-existe-este-host:5678/webhook", id="host-inalcanzable"),
    pytest.param("", id="sin-configurar"),
]


@pytest.mark.parametrize("url", URLS_ROTAS)
def test_un_webhook_roto_no_tumba_la_peticion(n8n, url):
    n8n(url)
    enviar_avisos([("pqrs-creada-cliente", {"pqrs_id": 1})])


@pytest.mark.parametrize("configurado", [
    "http://n8n:5678/webhook",
    "http://n8n:5678/webhook\n",      # el .env con un salto de línea al final
    "  http://n8n:5678/webhook  ",
    "http://n8n:5678/webhook/",       # con barra de más
])
def test_la_url_se_limpia_para_que_el_correo_salga(n8n, monkeypatch, configurado):
    """
    No basta con que no reviente: el correo tiene que salir igual.

    Un `.env` copiado a mano trae espacios o un salto de línea invisible al
    final, y esa basura convertía la URL en inválida. Se limpia antes de
    llamar, así que el aviso llega igual y nadie pierde una tarde buscando
    por qué "n8n no responde".
    """
    llamadas = []

    class Respuesta:
        status_code = 200
        text = "ok"

    def falso_post(url, **kwargs):
        llamadas.append(url)
        return Respuesta()

    monkeypatch.setattr("app.modules.pqrs.service.httpx.post", falso_post)
    n8n(configurado)

    enviar_avisos([("pqrs-creada-cliente", {"pqrs_id": 1})])

    assert llamadas == ["http://n8n:5678/webhook/pqrs-creada-cliente"], llamadas


def test_cada_aviso_va_por_su_cuenta(n8n, monkeypatch):
    """Que falle el correo del cliente no puede dejar sin aviso al área."""
    enviados = []

    def falso_post(url, **kwargs):
        if "creada-cliente" in url:
            raise RuntimeError("el servidor de correo del cliente rebotó")
        enviados.append(url)

        class R:
            status_code = 200
            text = "ok"
        return R()

    monkeypatch.setattr("app.modules.pqrs.service.httpx.post", falso_post)
    n8n("http://n8n:5678/webhook")

    enviar_avisos([
        ("pqrs-creada-cliente", {"pqrs_id": 1}),
        ("pqrs-notificacion-area", {"pqrs_id": 1}),
    ])

    assert enviados == ["http://n8n:5678/webhook/pqrs-notificacion-area"]


class SolicitudRota:
    """Un modelo al que le falta todo: simula un campo renombrado."""
    id = 1

    def __getattr__(self, nombre):
        raise RuntimeError(f"el campo '{nombre}' ya no existe")


def test_armar_el_aviso_tampoco_tumba_la_peticion(n8n):
    """No solo mandar el aviso puede fallar: armarlo también."""
    n8n("http://n8n:5678/webhook")
    assert avisos_creacion(None, 1, SolicitudRota()) == []
    assert avisos_cierre(SolicitudRota()) == []


def test_sin_correo_del_cliente_no_se_le_escribe_a_nadie(n8n):
    """Media PQRS entra sin correo: no hay a quién avisarle, y no es un error."""
    n8n("http://n8n:5678/webhook")

    class SinCorreo:
        id = 1
        cliente_email = None
        cliente_nombre = "Anónimo"
        codigo_seguimiento = "PK-2026-0001"
        tipo = "queja"
        area_responsable = None

    assert avisos_cierre(SinCorreo()) == []


def test_radicar_responde_bien_aunque_n8n_este_roto(entorno, n8n, monkeypatch):
    """La prueba de verdad: el endpoint completo, contra la API real."""
    n8n("http://n8n:5678/webhook\n")   # el valor que rompía

    respuesta = entorno.post("/pqrs", data={
        "tipo": "queja",
        "descripcion": "El producto llegó con el sello roto.",
        "cliente_nombre": "Cliente de prueba",
        "cliente_email": "cliente@ejemplo.com",
        "area_responsable": "Calidad",
    })

    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["codigo_seguimiento"]


def test_el_area_sin_gente_no_es_un_error(entorno, n8n):
    """Si nadie tiene esa área asignada no hay a quién escribirle, y ya."""
    n8n("http://n8n:5678/webhook")
    from app.models.pqrs import PQRSSolicitud

    db = entorno.Session()
    p = PQRSSolicitud(
        tenant_id=entorno.tenant_id,
        tipo="queja",
        cliente_nombre="Cliente",
        descripcion="Algo pasó",
        estado="recibido",
        area_responsable="Un área que nadie tiene",
    )
    db.add(p)
    db.commit()

    assert avisos_creacion(db, entorno.tenant_id, p) == []
    db.close()
