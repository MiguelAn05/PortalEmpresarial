"""
Los flujos de n8n tienen que escuchar donde el portal llama.

El path del webhook es el único punto de encuentro entre el portal y n8n, y
es una cadena de texto en dos repositorios distintos. Si no coinciden no falla
nada visible: el portal dispara, n8n contesta 404 y el correo simplemente no
llega. Nadie se entera hasta que un cliente reclama que nunca le respondieron.

Esta prueba compara los dos lados: los eventos que dispara el código contra
los flujos que hay en `backend/n8n/`.
"""
import json
import re
from pathlib import Path

# Los flujos viven dentro de `backend/` a propósito: son el otro extremo de
# los webhooks que dispara `notificaciones.py`, y así esta prueba —que corre
# dentro del contenedor, y el contenedor solo monta backend/— puede
# compararlos con el código que los llama.
RAIZ = Path(__file__).resolve().parents[1]
FLUJOS = RAIZ / "n8n"
CODIGO = RAIZ / "app"


def eventos_que_dispara_el_portal() -> set[str]:
    """
    Todo lo que el portal puede mandarle a n8n: los eventos declarados en
    `notificaciones.EVENTOS` más las llamadas sueltas de otros módulos, que
    sí pasan el nombre como literal.
    """
    from app.modules.pqrs.notificaciones import EVENTOS

    encontrados = set(EVENTOS)
    for archivo in CODIGO.rglob("*.py"):
        texto = archivo.read_text(encoding="utf-8")
        encontrados |= set(re.findall(r'disparar_webhook_n8n\(\s*"([\w-]+)"', texto))
    return encontrados


def flujos_definidos() -> dict[str, dict]:
    return {f.stem: json.loads(f.read_text(encoding="utf-8")) for f in FLUJOS.glob("*.json")}


def test_hay_flujos_definidos():
    assert flujos_definidos(), f"No hay ningún flujo en {FLUJOS}"


def test_el_portal_dispara_eventos():
    assert eventos_que_dispara_el_portal(), "No se encontró ninguna llamada al webhook"


def test_cada_flujo_escucha_un_evento_real():
    """Un flujo con el path mal escrito no lo despierta nadie."""
    disparados = eventos_que_dispara_el_portal()
    huerfanos = {
        nombre for nombre in flujos_definidos()
        if nombre not in disparados
    }
    assert not huerfanos, (
        f"Estos flujos escuchan un evento que el portal nunca dispara: "
        f"{sorted(huerfanos)}. Los que sí se disparan: {sorted(disparados)}"
    )


def test_el_nombre_del_archivo_es_el_path_del_webhook():
    """Se buscan por nombre de archivo; si no coincide, se importa el que no era."""
    for nombre, flujo in flujos_definidos().items():
        webhook = next(
            n for n in flujo["nodes"] if n["type"] == "n8n-nodes-base.webhook"
        )
        assert webhook["parameters"]["path"] == nombre, (
            f"{nombre}.json define el path '{webhook['parameters']['path']}'"
        )


def test_cada_flujo_manda_un_correo():
    """Un webhook que recibe y no hace nada es peor que no tenerlo."""
    for nombre, flujo in flujos_definidos().items():
        tipos = {n["type"] for n in flujo["nodes"]}
        assert "n8n-nodes-base.emailSend" in tipos, f"{nombre} no envía ningún correo"


def test_los_webhooks_responden_sin_esperar_al_correo():
    """
    Si n8n respondiera al final, radicar tardaría lo que tarde el servidor de
    correo — y el portal espera esa respuesta.
    """
    for nombre, flujo in flujos_definidos().items():
        webhook = next(
            n for n in flujo["nodes"] if n["type"] == "n8n-nodes-base.webhook"
        )
        assert webhook["parameters"].get("responseMode") == "onReceived", nombre


def test_los_avisos_internos_van_a_todos_los_destinatarios():
    """
    `destinatarios` llega como lista. Sin unirla, n8n manda el correo a algo
    como "['a@x.com', 'b@x.com']" y no le llega a nadie.
    """
    for nombre in ["pqrs-nueva-servicio-cliente", "pqrs-notificacion-area"]:
        flujo = flujos_definidos()[nombre]
        correo = next(
            n for n in flujo["nodes"] if n["type"] == "n8n-nodes-base.emailSend"
        )
        assert "destinatarios.join" in correo["parameters"]["toEmail"], nombre
