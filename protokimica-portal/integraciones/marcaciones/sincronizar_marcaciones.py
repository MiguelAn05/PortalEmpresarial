#!/usr/bin/env python3
"""Del reloj ZKBio Time al portal: marcaciones y malla de turnos.

El portal NO se conecta a ZKBio. Este script corre en el servidor de ZKBio
(el mismo de las alertas de asistencia), lee el reloj y EMPUJA al portal con
una clave propia (CLAVE_MARCACIONES). Ver LEEME.md.

Cada ejecucion manda:
  - las marcaciones de los ultimos N dias (3 por defecto). Reenviar es inofensivo:
    el portal no duplica;
  - la malla de turnos (schedules.csv), con el area ya traducida al nombre del portal;
  - los festivos (festivos.csv) y las excepciones (excepciones.csv), si existen.

Solo usa la libreria estandar de Python 3.8+. Solo LEE de ZKBio.

Secretos por variables de entorno (nunca en archivos):
  ZK_USER, ZK_PASS      usuario de lectura de ZKBio Time
  CLAVE_MARCACIONES     la misma del .env.prod del portal

Uso:
  py -3 sincronizar_marcaciones.py                 ejecucion normal
  py -3 sincronizar_marcaciones.py --dias 30       carga inicial: los ultimos 30 dias
  py -3 sincronizar_marcaciones.py --dry-run       arma el envio y lo resume, sin enviarlo
  py -3 sincronizar_marcaciones.py --areas         lista las areas de la malla y como quedarian en el portal
  py -3 sincronizar_marcaciones.py --selftest      prueba la logica sin red
"""
import argparse
import csv
import datetime as dt
import json
import logging
import os
import re
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from logging.handlers import RotatingFileHandler

BASE = os.path.dirname(os.path.abspath(__file__))
FMT = "%Y-%m-%d %H:%M:%S"
DIAS = ["lun", "mar", "mie", "jue", "vie", "sab", "dom"]
ESTADOS_VALIDOS = {"0", "1", "2", "3", "4", "5"}
TURNO = re.compile(r"^([01]\d|2[0-3]):[0-5]\d-([01]\d|2[0-3]):[0-5]\d$")
LOTE = 5000          # el portal acepta hasta 20.000 por envio; asi cada peticion es liviana
log = logging.getLogger("marcaciones")


def setup_logging():
    h = RotatingFileHandler(os.path.join(BASE, "sincronizar_marcaciones.log"), maxBytes=1000000,
                            backupCount=3, encoding="utf-8")
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(h)
    log.addHandler(logging.StreamHandler(sys.stdout))
    log.setLevel(logging.INFO)


def load_json(name, default=None):
    path = os.path.join(BASE, name)
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def http_json(url, method="GET", headers=None, body=None, timeout=60):
    data = None
    hdrs = dict(headers or {})
    if body is not None:
        data = json.dumps(body).encode()
        hdrs["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    return json.loads(raw) if raw else {}


def norm(s):
    s = unicodedata.normalize("NFD", str(s or ""))
    return "".join(c for c in s if unicodedata.category(c) != "Mn").casefold().strip()


# ------------------------------------------------------------------ ZKBio API
class ZK:
    def __init__(self, base_url):
        self.base = base_url.rstrip("/")
        self.headers = {}

    def login(self, user, password):
        errores = []
        for ruta in ("/jwt-api-token-auth/", "/staff-jwt-api-token-auth/"):
            try:
                j = http_json(self.base + ruta, "POST", body={"username": user, "password": password})
                self.headers = {"Authorization": "JWT " + j["token"]}
                return
            except urllib.error.HTTPError as e:
                errores.append("%s -> HTTP %s" % (ruta, e.code))
        raise RuntimeError("No se pudo iniciar sesion en ZKBio Time con el usuario '%s'. %s"
                           % (user, " | ".join(errores)))

    def pages(self, path, params):
        url = self.base + path + "?" + urllib.parse.urlencode(params)
        while url:
            j = http_json(url, headers=self.headers)
            for row in j.get("data") or j.get("results") or []:
                yield row
            # El "next" que devuelve ZKBio trae la direccion INTERNA del servidor
            # (localhost u otro puerto). Se conserva la ruta y se reusa la direccion
            # con la que ya estamos conectados.
            sig = j.get("next")
            if sig:
                u = urllib.parse.urlsplit(sig)
                sig = self.base + u.path + ("?" + u.query if u.query else "")
            url = sig

    def punches_range(self, d0, d1):
        p = {"start_time": d0.strftime("%Y-%m-%d 00:00:00"), "end_time": d1.strftime("%Y-%m-%d 23:59:59"),
             "page_size": 1000, "ordering": "punch_time"}
        return list(self.pages("/iclock/api/transactions/", p))


# --------------------------------------------------------------------- lectura
def read_csv(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def traducir_area(area, mapa):
    """El area de la malla -> el nombre EXACTO que tiene en Administracion > Areas del portal."""
    area = (area or "").strip()
    if not area:
        return None
    return mapa.get(norm(area), area)


def construir_empleados(filas, mapa_areas):
    """Una persona por fila de schedules.csv. Devuelve (empleados, avisos)."""
    mapa = {norm(k): v for k, v in (mapa_areas or {}).items()}
    out, avisos, vistos = [], [], set()
    for r in filas:
        codigo = (r.get("emp_code") or "").strip()
        if not codigo or codigo in vistos:
            if codigo:
                avisos.append("emp_code repetido en schedules.csv: %s (se usa la primera fila)" % codigo)
            continue
        vistos.add(codigo)
        nombre = ((r.get("nombre_zkbio") or "").strip().title() or (r.get("nombre_malla") or "").strip()
                  or codigo)[:150]
        emp = {"emp_code": codigo[:30], "nombre": nombre,
               "area": (traducir_area(r.get("area"), mapa) or None),
               "correo": ((r.get("correo") or "").strip().lower() or None)}
        for d in DIAS:
            valor = "/".join(t.strip() for t in (r.get(d) or "").split("/") if t.strip())
            for t in (valor.split("/") if valor else []):
                if not TURNO.match(t):
                    avisos.append("%s (%s): turno invalido '%s' en %s; se deja ese dia vacio" % (nombre, codigo, t, d))
                    valor = ""
                    break
            emp[d] = valor
        out.append(emp)
    return out, avisos


def construir_marcaciones(punches, codigos):
    """Las marcaciones de las personas de la malla, con el estado validado."""
    out, ignoradas, vistos = [], 0, set()
    for p in punches:
        codigo = str(p.get("emp_code") or "").strip()
        estado = str(p.get("punch_state"))
        momento = str(p.get("punch_time") or "")[:19]
        if codigo not in codigos or estado not in ESTADOS_VALIDOS or len(momento) != 19:
            ignoradas += 1
            continue
        clave = (codigo, momento, estado)
        if clave in vistos:
            continue
        vistos.add(clave)
        out.append({"emp_code": codigo, "momento": momento, "estado": estado})
    return out, ignoradas


def construir_festivos(filas):
    if not filas:
        return None          # sin archivo o vacio: no se toca lo del portal
    return [{"fecha": r["fecha"].strip(), "nombre": (r.get("nombre") or "").strip()[:100] or None}
            for r in filas if (r.get("fecha") or "").strip()] or None


def construir_excepciones(filas):
    if filas is None:
        return None          # sin archivo: no se toca. Con archivo (aunque vacio) es la fuente de verdad.
    return [{"emp_code": r["emp_code"].strip(), "fecha": r["fecha"].strip(),
             "motivo": (r.get("motivo") or "").strip()[:100] or None}
            for r in filas if (r.get("emp_code") or "").strip() and (r.get("fecha") or "").strip()]


# ---------------------------------------------------------------------- envio
def enviar(cfg, clave, cuerpo):
    url = cfg["portal_api"].rstrip("/") + "/marcaciones/sincronizar"
    try:
        return http_json(url, "POST", headers={"X-Clave-Marcaciones": clave}, body=cuerpo, timeout=120)
    except urllib.error.HTTPError as e:
        try:
            detalle = e.read().decode("utf-8", "replace")[:500]
        except Exception:
            detalle = ""
        raise RuntimeError("El portal rechazo el envio: HTTP %s %s" % (e.code, detalle))


def selftest():
    fallos = []

    def check(nombre, cond):
        print(("  OK   " if cond else "  FALLA") + "  " + nombre)
        if not cond:
            fallos.append(nombre)

    filas = [
        {"emp_code": "1", "nombre_zkbio": "ANA PEREZ", "nombre_malla": "Ana", "area": "Gestion Humana",
         "lun": "07:00-17:00", "mar": "06:00-14:00 / 14:00-22:00", "mie": "7 a 5", "correo": "Ana@P.com "},
        {"emp_code": "1", "nombre_zkbio": "REPETIDA", "area": "TICS"},
        {"emp_code": "2", "nombre_malla": "Beto", "area": "", "lun": ""},
    ]
    emps, avisos = construir_empleados(filas, {"Gestion Humana": "Gestión Humana"})
    check("el area se traduce sin importar tildes ni mayusculas", emps[0]["area"] == "Gestión Humana")
    check("el nombre sale de ZKBio en formato nombre propio", emps[0]["nombre"] == "Ana Perez")
    check("los turnos se limpian", emps[0]["mar"] == "06:00-14:00/14:00-22:00")
    check("un turno invalido deja el dia vacio y avisa", emps[0]["mie"] == "" and any("invalido" in a for a in avisos))
    check("el correo va en minusculas y sin espacios", emps[0]["correo"] == "ana@p.com")
    check("un codigo repetido se avisa y se ignora", len(emps) == 2 and any("repetido" in a for a in avisos))
    check("sin area queda en None", emps[1]["area"] is None)

    punches = [
        {"emp_code": 1, "punch_state": "0", "punch_time": "2026-11-03 06:58:00"},
        {"emp_code": 1, "punch_state": "0", "punch_time": "2026-11-03 06:58:00"},
        {"emp_code": 1, "punch_state": "255", "punch_time": "2026-11-03 07:00:00"},
        {"emp_code": 99, "punch_state": "0", "punch_time": "2026-11-03 07:00:00"},
        {"emp_code": 2, "punch_state": "1", "punch_time": "2026-11-03 17:00:00"},
    ]
    marcas, ign = construir_marcaciones(punches, {"1", "2"})
    check("se dedupe, se descartan estados raros y personas fuera de la malla", len(marcas) == 2 and ign == 2)
    check("festivos vacios no se mandan", construir_festivos([]) is None and construir_festivos(None) is None)
    check("excepciones sin archivo no se tocan; con archivo vacio se vacian",
          construir_excepciones(None) is None and construir_excepciones([]) == [])
    print()
    if fallos:
        print("FALLARON %d: %s" % (len(fallos), ", ".join(fallos)))
        return 1
    print("TODAS LAS PRUEBAS PASARON")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dias", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--areas", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()

    setup_logging()
    cfg = load_json("sincronizar_marcaciones.config.json") or load_json("sincronizar_marcaciones.config.ejemplo.json")
    if not cfg:
        log.error("Falta sincronizar_marcaciones.config.json (copia el .ejemplo.json y llenalo).")
        return 2
    ruta_malla = os.path.normpath(os.path.join(BASE, cfg.get("schedules_csv", "schedules.csv")))
    filas = read_csv(ruta_malla)
    if not filas:
        log.error("%s vacio o inexistente.", ruta_malla)
        return 2
    empleados, avisos = construir_empleados(filas, cfg.get("mapa_areas"))
    for av in avisos:
        log.warning(av)

    if a.areas:
        for ar in sorted({(f.get("area") or "").strip() for f in filas}):
            print("%-40s -> %s" % (ar or "(sin area)", traducir_area(ar, {norm(k): v for k, v in cfg.get("mapa_areas", {}).items()}) or "(sin area)"))
        return 0

    hoy = dt.date.today()
    dias = a.dias if a.dias is not None else cfg.get("dias_atras", 3)
    zk = ZK(cfg["zk_url"])
    zk.login(os.environ["ZK_USER"], os.environ["ZK_PASS"])
    punches = zk.punches_range(hoy - dt.timedelta(days=dias), hoy)
    marcaciones, ignoradas = construir_marcaciones(punches, {e["emp_code"] for e in empleados})

    carpeta = os.path.dirname(ruta_malla)
    festivos = construir_festivos(read_csv(os.path.join(carpeta, "festivos.csv")))
    excepciones = construir_excepciones(read_csv(os.path.join(carpeta, "excepciones.csv")))
    log.info("Empleados=%d marcaciones=%d (ignoradas %d) festivos=%s excepciones=%s dias=%d",
             len(empleados), len(marcaciones), ignoradas,
             "-" if festivos is None else len(festivos), "-" if excepciones is None else len(excepciones), dias)

    if a.dry_run:
        print("Se enviaria: %d empleados, %d marcaciones de los ultimos %d dias." % (len(empleados), len(marcaciones), dias))
        sin_area = [e["nombre"] for e in empleados if not e["area"]]
        if sin_area:
            print("Sin area (el portal los muestra como 'Sin area'):", ", ".join(sin_area))
        return 0

    clave = os.environ["CLAVE_MARCACIONES"]
    lotes = [marcaciones[i:i + LOTE] for i in range(0, len(marcaciones), LOTE)] or [[]]
    nuevas = 0
    for i, lote in enumerate(lotes):
        cuerpo = {"marcaciones": lote}
        if i == 0:                       # la malla y lo demas viajan una sola vez, en el primer lote
            cuerpo["empleados"] = empleados
            if festivos is not None:
                cuerpo["festivos"] = festivos
            if excepciones is not None:
                cuerpo["excepciones"] = excepciones
        r = enviar(cfg, clave, cuerpo)
        nuevas += r.get("marcaciones_nuevas", 0)
    log.info("Enviado. Marcaciones nuevas en el portal: %d", nuevas)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        if not log.handlers:
            setup_logging()
        log.exception("Fallo la sincronizacion")
        sys.exit(1)
