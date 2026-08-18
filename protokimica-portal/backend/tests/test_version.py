"""
La versión del portal.

Es un dato pequeño pero se desincroniza fácil: se sube VERSION y no se agrega
la entrada al historial, o al revés. Estas pruebas no dejan que eso llegue a
producción.
"""
import re

from app.core.version import FECHA, HISTORIAL, TIPOS_DE_CAMBIO, VERSION, historial_publico

SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
FECHA_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def test_la_version_tiene_forma_de_version(v):
    v.check("VERSION es MAYOR.MENOR.PARCHE", bool(SEMVER.match(VERSION)), VERSION)
    v.check("la fecha es aaaa-mm-dd", bool(FECHA_ISO.match(FECHA)), FECHA)
    v.check("el historial empieza en la versión actual",
            HISTORIAL[0]["version"] == VERSION, HISTORIAL[0]["version"])
    v.check("y con su misma fecha", HISTORIAL[0]["fecha"] == FECHA, HISTORIAL[0]["fecha"])


def test_el_historial_esta_completo_y_en_orden(v):
    def numero(s):
        return tuple(int(x) for x in s.split("."))

    versiones = [e["version"] for e in HISTORIAL]
    v.check("no hay versiones repetidas", len(set(versiones)) == len(versiones), versiones)
    v.check("van de la más nueva a la más vieja",
            versiones == sorted(versiones, key=numero, reverse=True), versiones)

    for e in HISTORIAL:
        marca = f"v{e['version']}"
        v.check(f"{marca} tiene forma de versión", bool(SEMVER.match(e["version"])))
        v.check(f"{marca} tiene fecha válida", bool(FECHA_ISO.match(e["fecha"])), e["fecha"])
        v.check(f"{marca} tiene título", bool(e["titulo"].strip()))
        v.check(f"{marca} dice qué cambió", len(e["cambios"]) > 0)
        for tipo, texto in e["cambios"]:
            v.check(f"{marca}: '{tipo}' es un tipo conocido", tipo in TIPOS_DE_CAMBIO)
            # Sin esto el historial termina siendo un git log, que no le sirve
            # a quien usa el portal.
            v.check(f"{marca}: el cambio se explica", len(texto.strip()) > 15, texto)


def test_el_historial_publico_trae_etiqueta_y_color(v):
    """El estado nunca se comunica solo con color: cada cambio lleva su texto."""
    publico = historial_publico()
    v.check("trae todas las versiones", len(publico) == len(HISTORIAL))
    cambio = publico[0]["cambios"][0]
    for campo in ("tipo", "etiqueta", "color", "texto"):
        v.check(f"cada cambio trae '{campo}'", campo in cambio, sorted(cambio))
    v.check("la etiqueta no va vacía", bool(cambio["etiqueta"].strip()))
    v.check("el color es un hex", cambio["color"].startswith("#"), cambio["color"])


def test_version_se_consulta_sin_login(entorno, v):
    """El navegador la compara contra la suya antes de que nadie inicie sesión."""
    from app.main import app

    # Las pruebas corren siempre autenticadas, así que pedir el endpoint no
    # demuestra nada: hay que mirar que la ruta no exija nada.
    ruta = next(r for r in app.routes if getattr(r, "path", None) == "/version")
    v.check("la ruta no pide login", not ruta.dependant.dependencies,
            [d.call.__name__ for d in ruta.dependant.dependencies])
    protegida = next(r for r in app.routes if getattr(r, "path", None) == "/version/historial")
    v.check("pero el historial sí", len(protegida.dependant.dependencies) > 0)

    r = entorno.get("/version")
    v.check("responde 200", r.status_code == 200, r.text[:120])
    v.check("trae la versión", r.json().get("version") == VERSION, r.json())
    v.check("y la fecha", r.json().get("fecha") == FECHA, r.json())
    # Lo que NO puede traer: el detalle interno queda detrás del login.
    v.check("sin el historial", "historial" not in r.json(), sorted(r.json()))


def test_el_historial_va_detras_del_login(entorno, v):
    portal = entorno
    portal.como("lectura")
    r = portal.get("/version/historial")
    v.check("un usuario cualquiera sí lo ve", r.status_code == 200, r.text[:120])
    v.check("y viene el historial completo",
            len(r.json()["historial"]) == len(HISTORIAL), len(r.json().get("historial", [])))
    v.check("con la versión de encabezado", r.json()["version"] == VERSION)
