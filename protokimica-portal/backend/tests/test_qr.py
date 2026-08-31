"""
Los códigos QR de los puntos de venta.

Lo que hay que proteger aquí es que el QR apunte a donde debe: va impreso en
un letrero pegado en un mostrador, así que un error no se corrige actualizando
una página — hay que volver a imprimir y recorrer las sedes.

Y que el canal llegue bien, porque de él sale el prefijo del código de
seguimiento (`PVG0010`) y con ese prefijo se arman los reportes por sede.
"""
from app.core import canales
from app.core.config import settings
from app.modules.pqrs import qr


def _con_dominio(fn, dominio="https://portal.protokimica.com"):
    """Corre algo con FRONTEND_URL fijo y lo deja como estaba."""
    original = settings.FRONTEND_URL
    settings.FRONTEND_URL = dominio
    try:
        return fn()
    finally:
        settings.FRONTEND_URL = original


# ── La URL que queda dentro del código ───────────────────────────────

def test_el_qr_apunta_al_dominio_publico(v):
    def probar():
        v.check("usa FRONTEND_URL",
                qr.url_del_canal("PVG") == "https://portal.protokimica.com/q/PVG",
                qr.url_del_canal("PVG"))
    _con_dominio(probar)


def test_una_barra_de_mas_en_el_env_no_parte_la_url(v):
    """Un `.env` escrito a mano trae barras de más; `//q/PVG` no resuelve."""
    def probar():
        v.check("se limpia la barra final",
                qr.url_del_canal("PVG") == "https://portal.protokimica.com/q/PVG",
                qr.url_del_canal("PVG"))
    _con_dominio(probar, "https://portal.protokimica.com/  ")


def test_el_codigo_va_en_mayusculas(v):
    """El QR lleva siempre la forma canónica, venga como venga."""
    def probar():
        v.check("normaliza", qr.url_del_canal("pvg").endswith("/q/PVG"),
                qr.url_del_canal("pvg"))
    _con_dominio(probar)


# ── Solo canales de verdad ───────────────────────────────────────────

def test_no_se_genera_un_qr_de_un_canal_inventado(v):
    """
    Un letrero apuntando a un canal que el servidor no conoce mandaría esas
    PQRS al radicado genérico sin que nadie se entere.
    """
    for malo in ("XXX", "", "  ", "DROP"):
        try:
            qr.svg(malo)
            v.check(f"'{malo}' se rechaza", False, "no levantó ValueError")
        except ValueError:
            v.check(f"'{malo}' se rechaza", True)


def test_todos_los_canales_con_prefijo_tienen_su_qr(v):
    def probar():
        for canal, prefijo in canales.PREFIJOS_POR_CANAL.items():
            contenido = qr.svg(prefijo)
            v.check(f"{canal} genera su código", contenido.startswith(b"<svg"),
                    contenido[:40])
    _con_dominio(probar)


def test_la_url_no_se_arma_con_nada_que_venga_de_la_peticion(v):
    """
    El código se valida contra la lista cerrada antes de entrar a la URL, así
    que este endpoint no sirve para fabricar un QR con el dominio del portal
    que lleve a otra parte.
    """
    for intento in ("PVG/../otro", "PVG?x=1", "https://otrositio.com"):
        try:
            qr.svg(intento)
            v.check(f"'{intento}' se rechaza", False, "no levantó ValueError")
        except ValueError:
            v.check(f"'{intento}' se rechaza", True)


# ── Los endpoints ────────────────────────────────────────────────────

def test_el_qr_no_pide_sesion(entorno, v):
    """
    Va abierto a propósito: solo contiene una URL pública, y así la pantalla
    de impresión lo muestra con un `<img>` normal — una etiqueta de imagen no
    manda la cabecera de sesión.
    """
    r = entorno.get("/public/qr/PVG.svg")

    v.check("responde 200", r.status_code == 200, r.status_code)
    v.check("es un SVG", r.headers["content-type"].startswith("image/svg+xml"),
            r.headers.get("content-type"))
    v.check("y trae el dibujo", r.content.startswith(b"<svg"), r.content[:40])


def test_tambien_hay_png(entorno, v):
    r = entorno.get("/public/qr/PVG.png")

    v.check("responde 200", r.status_code == 200, r.status_code)
    v.check("es un PNG", r.headers["content-type"] == "image/png",
            r.headers.get("content-type"))
    # La firma de un PNG. Si esto cambia, el archivo no es un PNG.
    v.check("con la firma correcta", r.content[:8] == b"\x89PNG\r\n\x1a\n", r.content[:8])


def test_un_codigo_que_no_existe_responde_404(entorno, v):
    r = entorno.get("/public/qr/XXX.svg")

    v.check("404", r.status_code == 404, r.status_code)
    v.check("y dice dónde ver los buenos", "/public/qr" in r.json()["detail"],
            r.json()["detail"])


def test_la_lista_trae_codigo_canal_y_url(entorno, v):
    r = entorno.get("/public/qr")

    v.check("responde 200", r.status_code == 200, r.status_code)
    puntos = r.json()
    v.check("hay uno por canal con prefijo",
            len(puntos) == len(canales.PREFIJOS_POR_CANAL), len(puntos))

    guayabal = next((p for p in puntos if p["codigo"] == "PVG"), None)
    v.check("está Guayabal", guayabal is not None, puntos)
    if guayabal:
        v.check("con su nombre", guayabal["canal"] == "Punto de venta Guayabal", guayabal)
        v.check("y la url ya resuelta", guayabal["url"].endswith("/q/PVG"), guayabal)
        v.check("marcado como punto de venta", guayabal["es_punto_de_venta"] is True)

    institucional = next((p for p in puntos if p["codigo"] == "VI"), None)
    # Venta institucional tiene prefijo pero no es una sede donde alguien
    # pueda escanear algo pegado en un mostrador.
    v.check("venta institucional no es punto de venta",
            institucional and institucional["es_punto_de_venta"] is False, institucional)


# ── Del QR a la PQRS ─────────────────────────────────────────────────

def test_el_codigo_del_qr_lleva_al_canal_y_ese_al_prefijo(entorno, v):
    """
    El viaje completo: `PVG` → «Punto de venta Guayabal» → radicado `PVG0001`.
    Es la razón de ser del QR — que el canal no dependa de que el cliente
    acierte en una lista.
    """
    canal = canales.canal_por_codigo("PVG")
    r = entorno.post("/pqrs", data={
        "tipo": "reclamo",
        "descripcion": "El producto llegó con el sello roto.",
        "cliente_nombre": "Cliente",
        "canal_atencion": canal,
    })

    v.check("radica", r.status_code == 201, r.text[:200])
    v.check("con el prefijo de la sede",
            r.json()["codigo_seguimiento"].startswith("PVG"),
            r.json()["codigo_seguimiento"])


def test_el_nombre_viejo_del_canal_se_traduce_al_radicar(entorno, v):
    """
    Un formulario cacheado puede seguir mandando «Llamada telefónica». Se
    guarda con el nombre actual para que no abra un canal paralelo en los
    reportes.
    """
    r = entorno.post("/pqrs", data={
        "tipo": "peticion",
        "descripcion": "Quiero saber el estado de mi pedido.",
        "cliente_nombre": "Cliente",
        "canal_atencion": "Llamada telefónica",
    })

    v.check("radica", r.status_code == 201, r.text[:200])
    v.check("y queda con el nombre actual",
            r.json()["canal_atencion"] == "Línea telefónica", r.json()["canal_atencion"])
