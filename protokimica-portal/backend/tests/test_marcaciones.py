"""
Marcaciones: lo que importa probar es que las reglas den lo mismo que los
correos de alerta, que cada quien vea solo lo suyo y que el envío del reloj
sea seguro de repetir.

Los días de prueba son PASADOS a propósito: un día pasado se evalúa con el
reloj en su último segundo, así que el resultado no depende de la hora a la
que corran las pruebas.
"""
import datetime as dt

from app.core import capacidades
from app.core.config import settings
from app.core.dias_habiles import hoy
from app.models.marcaciones import MarEmpleado, MarMarcacion
from app.models.tenant import TenantModulo
from app.modules.marcaciones import evaluacion
from app.modules.marcaciones.schemas import EmpleadoIn

CLAVE = "clave-de-prueba-marcaciones"
MARTES = "2026-11-03"


def _a(fecha: str, hm: str) -> str:
    return f"{fecha} {hm}:00"


def _turno(**dias):
    base = {"lun": "07:00-17:00", "mar": "07:00-17:00", "mie": "07:00-17:00", "jue": "07:00-17:00",
            "vie": "07:00-17:00", "sab": "", "dom": ""}
    base.update(dias)
    return base


MALLA = [
    {"emp_code": "100", "nombre": "Ana Puntual", "area": "TICS", "correo": "ana@p.com", **_turno()},
    {"emp_code": "101", "nombre": "Beto Tarde", "area": "TICS", "correo": None, **_turno()},
    {"emp_code": "200", "nombre": "Carla Ausente", "area": "Calidad", "correo": None, **_turno()},
    {"emp_code": "300", "nombre": "Luis Logística", "area": "Logística", "correo": "logistica@p.com", **_turno()},
    {"emp_code": "400", "nombre": "Elena Dudosa", "area": "Calidad", "correo": None,
     **_turno(mar="06:00-14:00/14:00-22:00")},
]

MARCAS = [
    {"emp_code": "100", "momento": _a(MARTES, "06:58"), "estado": "0"},
    {"emp_code": "100", "momento": _a(MARTES, "17:01"), "estado": "1"},
    {"emp_code": "101", "momento": _a(MARTES, "07:30"), "estado": "0"},
    # Luis: almuerzo de 60 minutos (permitido 45).
    {"emp_code": "300", "momento": _a(MARTES, "06:55"), "estado": "0"},
    {"emp_code": "300", "momento": _a(MARTES, "12:00"), "estado": "2"},
    {"emp_code": "300", "momento": _a(MARTES, "13:00"), "estado": "3"},
    {"emp_code": "300", "momento": _a(MARTES, "17:00"), "estado": "1"},
    # Elena entra a las 10:00: fuera de la ventana de sus dos turnos, sin historial.
    {"emp_code": "400", "momento": _a(MARTES, "10:00"), "estado": "0"},
]


def _enviar(portal, cuerpo, clave=CLAVE):
    return portal.post("/marcaciones/sincronizar", json=cuerpo, headers={"X-Clave-Marcaciones": clave})


def _con_clave(fn):
    original = settings.CLAVE_MARCACIONES
    settings.CLAVE_MARCACIONES = CLAVE
    try:
        return fn()
    finally:
        settings.CLAVE_MARCACIONES = original


def _cargar(portal, cuerpo=None):
    r = _con_clave(lambda: _enviar(portal, cuerpo or {"empleados": MALLA, "marcaciones": MARCAS}))
    assert r.status_code == 200, r.text
    return r.json()


def _dia(portal, fecha=MARTES, **params):
    r = portal.get("/marcaciones/dia", params={"fecha": fecha, **params})
    assert r.status_code == 200, r.text
    return r.json()


def _por_codigo(datos):
    return {p["emp_code"]: p for p in datos["personas"]}


# ── La entrada del reloj ─────────────────────────────────────────────────

def test_el_envio_exige_la_clave(entorno, v):
    cuerpo = {"empleados": MALLA}
    v.check("una clave equivocada se rechaza", _con_clave(lambda: _enviar(entorno, cuerpo, "otra")).status_code == 403)
    r = _con_clave(lambda: entorno.post("/marcaciones/sincronizar", json=cuerpo))
    v.check("sin clave tampoco entra (aunque haya sesión de usuario)", r.status_code == 403, r.status_code)


def test_sin_clave_configurada_esta_cerrado(entorno, v):
    original = settings.CLAVE_MARCACIONES
    settings.CLAVE_MARCACIONES = ""
    try:
        r = _enviar(entorno, {"empleados": MALLA}, "lo-que-sea")
    finally:
        settings.CLAVE_MARCACIONES = original
    v.check("responde que no está configurado", r.status_code == 503, r.status_code)
    v.check("y dice qué falta", "CLAVE_MARCACIONES" in r.text, r.text)


def test_un_envio_vacio_no_se_aplica(entorno, v):
    _cargar(entorno)
    for nombre, cuerpo in {
        "sin nada": {},
        "malla vacía": {"empleados": []},
        "festivos vacíos": {"festivos": []},
    }.items():
        r = _con_clave(lambda c=cuerpo: _enviar(entorno, c))
        v.check(f"{nombre} se rechaza", r.status_code == 400, (r.status_code, r.text))
    # Lo importante: la malla sigue ahí, nadie quedó desactivado.
    db = entorno.Session()
    v.check("nadie se desactivó", db.query(MarEmpleado).filter_by(activo=False).count() == 0)
    db.close()
    entorno.como("admin")
    estado = entorno.get("/marcaciones/estado").json()
    v.check("el rechazo quedó registrado", estado["ultimo_error"] is not None, estado)


def test_el_envio_es_idempotente(entorno, v):
    primero = _cargar(entorno)
    v.check("la primera vez guarda todo", primero["marcaciones_nuevas"] == len(MARCAS), primero)
    segundo = _cargar(entorno)
    v.check("reenviar lo mismo no duplica", segundo["marcaciones_nuevas"] == 0, segundo)
    db = entorno.Session()
    v.check("en la base hay una sola vez cada marcación", db.query(MarMarcacion).count() == len(MARCAS))
    db.close()


def test_el_envio_valida_los_datos(entorno, v):
    casos = {
        "turno mal escrito": {"empleados": [{**MALLA[0], "mar": "7 a 5"}]},
        "turno con hora imposible": {"empleados": [{**MALLA[0], "mar": "25:00-17:00"}]},
        "estado desconocido": {"marcaciones": [{"emp_code": "100", "momento": _a(MARTES, "07:00"), "estado": "9"}]},
        "hora con zona": {"marcaciones": [{"emp_code": "100", "momento": "2026-11-03T07:00:00+00:00", "estado": "0"}]},
        "nombre larguísimo": {"empleados": [{**MALLA[0], "nombre": "x" * 400}]},
    }
    for nombre, cuerpo in casos.items():
        r = _con_clave(lambda c=cuerpo: _enviar(entorno, c))
        v.check(f"{nombre}: 422", r.status_code == 422, (r.status_code, r.text[:200]))


def test_quien_sale_de_la_malla_se_desactiva_sin_perder_su_historia(entorno, v):
    _cargar(entorno)
    _cargar(entorno, {"empleados": [m for m in MALLA if m["emp_code"] != "101"]})
    db = entorno.Session()
    beto = db.query(MarEmpleado).filter_by(emp_code="101").one()
    v.check("Beto quedó inactivo", beto.activo is False)
    v.check("su marcación se conserva", db.query(MarMarcacion).filter_by(emp_code="101").count() == 1)
    db.close()
    entorno.como("admin")
    datos = _dia(entorno)
    v.check("el día que marcó sigue apareciendo", "101" in _por_codigo(datos))
    otro = _dia(entorno, "2026-11-04")
    v.check("pero los días siguientes ya no se le espera", "101" not in _por_codigo(otro))


def test_el_estado_dice_si_el_script_esta_al_dia(entorno, v):
    entorno.como("admin")
    antes = entorno.get("/marcaciones/estado").json()
    v.check("sin envíos, está atrasado y dice que nunca", antes["nunca"] and antes["atrasado"], antes)
    _cargar(entorno)
    despues = entorno.get("/marcaciones/estado").json()
    v.check("con un envío reciente está al día", not despues["atrasado"] and not despues["nunca"], despues)
    v.check("trae la última marcación", despues["ultima_marcacion"] == _a(MARTES, "17:01"), despues)


def test_cada_marcacion_dice_en_que_biometrico_se_hizo(entorno, v):
    # Primero llegan sin equipo, como las de antes de que el script lo mandara.
    _cargar(entorno)
    entorno.como("admin")
    ana = _por_codigo(_dia(entorno))["100"]
    v.check("sin equipo conocido, dispositivo es None", ana["marcas"][0]["dispositivo"] is None, ana["marcas"])

    con_equipo = [dict(m, dispositivo="CJIN203560028") for m in MARCAS]
    con_equipo[1]["dispositivo"] = "CJIN203560037"  # Ana sale por La 65
    r = _cargar(entorno, {"marcaciones": con_equipo, "dispositivos": [
        {"serie": "CJIN203560028", "nombre": "SEDE GUAYABAL PISO 1", "sede": "SEDE GUAYABAL"},
        {"serie": "CJIN203560037", "nombre": "SEDE LA 65", "sede": "SEDE 65"},
    ]})
    v.check("reenviarlas no las duplica", r["marcaciones_nuevas"] == 0, r)
    ana = _por_codigo(_dia(entorno))["100"]
    v.check("las viejas reciben su equipo al reenviarse",
            [m["dispositivo"]["nombre"] for m in ana["marcas"]] == ["SEDE GUAYABAL PISO 1", "SEDE LA 65"], ana["marcas"])
    v.check("con la sede y la serie", ana["marcas"][1]["dispositivo"] == {
        "serie": "CJIN203560037", "nombre": "SEDE LA 65", "sede": "SEDE 65"}, ana["marcas"][1])
    v.check("la última marcación dice dónde", ana["ultima_marca"]["dispositivo"]["nombre"] == "SEDE LA 65", ana["ultima_marca"])

    # Renombrar el equipo en ZKBio cambia el nombre sin tocar las marcaciones.
    _cargar(entorno, {"marcaciones": con_equipo[:1], "dispositivos": [
        {"serie": "CJIN203560028", "nombre": "GUAYABAL P1", "sede": None}]})
    ana = _por_codigo(_dia(entorno))["100"]
    v.check("el nombre nuevo se ve y la sede vacía no borra la que había",
            ana["marcas"][0]["dispositivo"] == {"serie": "CJIN203560028", "nombre": "GUAYABAL P1", "sede": "SEDE GUAYABAL"},
            ana["marcas"][0])
    csv_ = entorno.get("/marcaciones/informe.csv", params={"desde": MARTES, "hasta": MARTES}).content.decode()
    v.check("el CSV dice en qué equipo", "17:01 Salida (SEDE LA 65)" in csv_, csv_)


# ── Las reglas ───────────────────────────────────────────────────────────

def test_las_novedades_del_dia(entorno, v):
    _cargar(entorno)
    entorno.como("admin")
    p = _por_codigo(_dia(entorno))
    tipos = lambda c: [n["tipo"] for n in p[c]["novedades"]]  # noqa: E731
    v.check("Ana marcó a tiempo: sin novedades", tipos("100") == [], p["100"])
    v.check("Beto llegó 30 min tarde", tipos("101") == ["llegada_tarde"], p["101"])
    v.check("Carla no marcó: ausente", tipos("200") == ["ausencia"] and p["200"]["presencia"] == "ausente", p["200"])
    v.check("Luis se pasó del almuerzo", tipos("300") == ["exceso_almuerzo"], p["300"])
    v.check("Elena: turno por confirmar, no se le acusa", tipos("400") == ["turno_por_confirmar"], p["400"])
    v.check("Ana ya salió", p["100"]["presencia"] == "salio")
    v.check("Beto sigue adentro", p["101"]["presencia"] == "adentro")


def test_totales_por_area_y_por_lider(entorno, v):
    _cargar(entorno)
    entorno.como("admin")
    datos = _dia(entorno)
    tot = datos["resumen"]["totales"]
    v.check("5 personas", tot["personas"] == 5, tot)
    v.check("4 con novedad", tot["con_novedad"] == 4, tot)
    areas = {a["area"]: a for a in datos["resumen"]["por_area"]}
    v.check("TICS: 2 personas, 1 novedad", (areas["TICS"]["personas"], areas["TICS"]["total_novedades"]) == (2, 1), areas["TICS"])
    v.check("Calidad: 2 personas, 2 novedades", (areas["Calidad"]["personas"], areas["Calidad"]["total_novedades"]) == (2, 2), areas["Calidad"])
    lideres = {x["lider"]: x for x in datos["resumen"]["por_lider"]}
    v.check("el líder de TICS ve a su gente", lideres["Tico"]["personas"] == 2, lideres)
    v.check("el líder de Calidad ve a su gente", lideres["Cali"]["personas"] == 2, lideres)
    v.check("Logística no tiene líder y lo dice", lideres["Sin líder asignado"]["personas"] == 1, lideres)
    quienes = areas["TICS"]["quienes"]
    v.check("la cifra de novedades dice de quién es", [q["emp_code"] for q in quienes] == ["101"], quienes)
    v.check("y cuáles tiene", quienes[0]["novedades"] == ["Llegada tarde"], quienes)
    v.check("quien no tiene novedad no aparece", all(q["novedades"] for a in areas.values() for q in a["quienes"]), areas)


def test_filtro_por_area(entorno, v):
    _cargar(entorno)
    entorno.como("admin")
    datos = _dia(entorno, area="Calidad")
    v.check("solo Calidad", {p["area"] for p in datos["personas"]} == {"Calidad"}, datos["personas"])


def test_un_festivo_no_acusa_a_nadie(entorno, v):
    _cargar(entorno, {"empleados": MALLA, "marcaciones": MARCAS,
                      "festivos": [{"fecha": "2026-11-04", "nombre": "Festivo de prueba"}]})
    entorno.como("admin")
    datos = _dia(entorno, "2026-11-04")
    v.check("sale marcado como festivo", datos["festivo"] == "Festivo de prueba", datos["festivo"])
    v.check("nadie es ausente", datos["resumen"]["totales"]["ausente"] == 0, datos["resumen"]["totales"])


def test_una_excepcion_justifica_la_ausencia(entorno, v):
    _cargar(entorno, {"empleados": MALLA, "marcaciones": MARCAS,
                      "excepciones": [{"emp_code": "200", "fecha": MARTES, "motivo": "Vacaciones"}]})
    entorno.como("admin")
    carla = _por_codigo(_dia(entorno))["200"]
    v.check("justificada, sin ausencia", carla["presencia"] == "justificado" and not carla["novedades"], carla)
    v.check("con su motivo", carla["motivo"] == "Vacaciones", carla)


def test_el_turno_se_deduce_del_historial(entorno, v):
    # Elena hace siempre el turno de las 14:00; un día llega a las 15:00 (tarde,
    # fuera de ventana): por su historial se sabe cuál era y se le marca la llegada.
    marcas = []
    for dia in ("2026-10-27", "2026-10-28", "2026-10-29", "2026-10-30"):
        marcas.append({"emp_code": "400", "momento": _a(dia, "13:50"), "estado": "0"})
    marcas.append({"emp_code": "400", "momento": _a(MARTES, "15:00"), "estado": "0"})
    malla = [{**MALLA[4], **{d: "06:00-14:00/14:00-22:00" for d in ("lun", "mar", "mie", "jue", "vie")}}]
    _cargar(entorno, {"empleados": malla, "marcaciones": marcas})
    entorno.como("admin")
    elena = _por_codigo(_dia(entorno))["400"]
    v.check("se infiere el turno de las 14:00", elena["turno"] == "14:00-22:00" and elena["confianza"] == "historial", elena)
    v.check("y la llegada tarde se detecta", [n["tipo"] for n in elena["novedades"]] == ["llegada_tarde"], elena)


# ── Quién ve qué ─────────────────────────────────────────────────────────

def _nombres(entorno):
    return sorted(p["nombre"] for p in _dia(entorno)["personas"])


def test_cada_rol_ve_lo_que_le_toca(entorno, v):
    _cargar(entorno)
    todos = sorted(m["nombre"] for m in MALLA)
    entorno.como("admin")
    v.check("admin ve todo", _nombres(entorno) == todos)
    entorno.como("gerencia")
    v.check("gerencia ve todo", _nombres(entorno) == todos)
    entorno.como("tics")
    v.check("el líder de TICS ve solo TICS", _nombres(entorno) == ["Ana Puntual", "Beto Tarde"], _nombres(entorno))
    entorno.como("calidad")
    v.check("el líder de Calidad ve solo Calidad", _nombres(entorno) == ["Carla Ausente", "Elena Dudosa"], _nombres(entorno))
    entorno.como("logistica")
    v.check("el agente ve solo lo suyo", _nombres(entorno) == ["Luis Logística"], _nombres(entorno))
    v.check("y su alcance lo dice", _dia(entorno)["alcance"]["tipo"] == "propio")
    entorno.como("lectura")
    v.check("lectura no entra", entorno.get("/marcaciones/dia", params={"fecha": MARTES}).status_code == 403)


def test_un_agente_sin_correo_en_la_malla_no_ve_nada(entorno, v):
    _cargar(entorno)
    db = entorno.Session()
    db.query(MarEmpleado).filter_by(emp_code="300").update({"correo": None})
    db.commit()
    db.close()
    entorno.como("logistica")
    v.check("no ve a nadie, ni «todo» por descarte", _dia(entorno)["personas"] == [])


def test_la_capacidad_da_la_vista_completa(entorno, v):
    _cargar(entorno)
    db = entorno.Session()
    capacidades.otorgar_a_usuario(db, entorno.tenant_id, "marcaciones.ver_todo",
                                  entorno.ids["logistica"], entorno.ids["admin"])
    capacidades.otorgar_a_usuario(db, entorno.tenant_id, "marcaciones.ver_todo",
                                  entorno.ids["lectura"], entorno.ids["admin"])
    db.close()
    entorno.como("logistica")
    v.check("el agente con la capacidad ve todo", len(_dia(entorno)["personas"]) == len(MALLA))
    entorno.como("lectura")
    v.check("lectura no entra ni con la capacidad",
            entorno.get("/marcaciones/dia", params={"fecha": MARTES}).status_code == 403)


def test_el_detalle_de_una_persona_respeta_el_alcance(entorno, v):
    _cargar(entorno)
    entorno.como("logistica")
    otra = entorno.get("/marcaciones/persona/100", params={"desde": MARTES, "hasta": MARTES})
    v.check("la de otra persona no se ve (404, no 403)", otra.status_code == 404, otra.status_code)
    propia = entorno.get("/marcaciones/persona/300", params={"desde": MARTES, "hasta": MARTES})
    v.check("la propia sí", propia.status_code == 200, propia.text)
    v.check("trae su día", propia.json()["dias"][0]["novedades"][0]["tipo"] == "exceso_almuerzo", propia.json())
    entorno.como("tics")
    v.check("un líder no ve a la gente de otra área", entorno.get("/marcaciones/persona/200").status_code == 404)
    v.check("pero sí a la suya", entorno.get("/marcaciones/persona/100").status_code == 200)


# ── Informe y CSV ────────────────────────────────────────────────────────

def test_informe_del_rango(entorno, v):
    _cargar(entorno)
    entorno.como("admin")
    r = entorno.get("/marcaciones/informe", params={"desde": MARTES, "hasta": MARTES})
    v.check("responde", r.status_code == 200, r.text)
    d = r.json()
    por_persona = {p["emp_code"]: p for p in d["por_persona"]}
    v.check("Beto: una llegada tarde", por_persona["101"]["llegada_tarde"] == 1, por_persona["101"])
    v.check("Carla: una ausencia", por_persona["200"]["ausencia"] == 1, por_persona["200"])
    v.check("el primero es quien más novedades tiene o empata", d["por_persona"][0]["total_novedades"] >= 1)
    solo = entorno.get("/marcaciones/informe", params={"desde": MARTES, "hasta": MARTES, "solo_novedades": True}).json()
    v.check("solo novedades quita a Ana", "100" not in {f["emp_code"] for f in solo["filas"]}, solo["filas"])
    beto = entorno.get("/marcaciones/informe", params={"desde": MARTES, "hasta": MARTES, "emp_code": "101"}).json()
    v.check("filtrar por persona deja solo a esa persona",
            [p["emp_code"] for p in beto["por_persona"]] == ["101"] and {f["emp_code"] for f in beto["filas"]} == {"101"}, beto["por_persona"])
    v.check("y los totales son los suyos", beto["totales"]["total_novedades"] == 1, beto["totales"])
    v.check("el desplegable sigue ofreciendo a todos", len(beto["personas"]) == len(d["personas"]) >= 5, beto["personas"])


def test_el_rango_del_informe_tiene_limites(entorno, v):
    entorno.como("admin")
    r = entorno.get("/marcaciones/informe", params={"desde": MARTES, "hasta": "2026-10-01"})
    v.check("fin antes del inicio: 400", r.status_code == 400, r.status_code)
    r = entorno.get("/marcaciones/informe", params={"desde": "2026-01-01", "hasta": MARTES})
    v.check("más de 93 días: 400 y dice qué hacer", r.status_code == 400 and "tramos" in r.text, r.text)


def test_el_csv(entorno, v):
    _cargar(entorno)
    entorno.como("admin")
    r = entorno.get("/marcaciones/informe.csv", params={"desde": MARTES, "hasta": MARTES})
    v.check("es CSV descargable", r.status_code == 200 and r.headers["content-type"].startswith("text/csv"), r.headers)
    v.check("con nombre de archivo", "marcaciones_2026-11-03_2026-11-03.csv" in r.headers["content-disposition"])
    texto = r.content.decode("utf-8")
    v.check("con BOM para Excel", texto.startswith("﻿"))
    lineas = texto.lstrip("﻿").splitlines()
    v.check("encabezado en español con «;»", lineas[0].startswith("Fecha;Código;Nombre;Área"), lineas[0])
    v.check("una fila por persona", len(lineas) == 1 + len(MALLA), len(lineas))
    v.check("las novedades van legibles", any("Exceso de almuerzo" in l for l in lineas), lineas)
    entorno.como("tics")
    propio = entorno.get("/marcaciones/informe.csv", params={"desde": MARTES, "hasta": MARTES}).content.decode()
    v.check("el CSV de un líder trae solo su área", "Carla" not in propio and "Ana Puntual" in propio, propio)


def test_el_csv_no_ejecuta_formulas(entorno, v):
    malla = [{**MALLA[0], "nombre": "=HYPERLINK(\"http://x\")"}]
    _cargar(entorno, {"empleados": malla, "marcaciones": []})
    entorno.como("admin")
    texto = entorno.get("/marcaciones/informe.csv", params={"desde": MARTES, "hasta": MARTES}).content.decode()
    v.check("el nombre queda como texto", "'=HYPERLINK" in texto, texto)


# ── Contrato ─────────────────────────────────────────────────────────────

def test_sin_contratar_nadie_entra_ni_el_script(entorno, v):
    _cargar(entorno)
    db = entorno.Session()
    db.query(TenantModulo).filter_by(tenant_id=entorno.tenant_id, modulo="marcaciones").update({"activo": False})
    db.commit()
    db.close()
    entorno.como("admin")
    r = entorno.get("/marcaciones/dia", params={"fecha": MARTES})
    v.check("ni admin entra", r.status_code == 403 and "Marcaciones" in r.text, (r.status_code, r.text))
    r = _con_clave(lambda: _enviar(entorno, {"empleados": MALLA}))
    v.check("el script tampoco", r.status_code == 403, (r.status_code, r.text))
    modulos = entorno.get("/auth/me").json().get("modulos", [])
    v.check("y no aparece en el menú", "marcaciones" not in modulos, modulos)

# ── Justificar una novedad ────────────────────────────────────────────────

def _justificar(portal, emp, tipo, texto="Cita médica con soporte", fecha=MARTES):
    return portal.put("/marcaciones/justificacion",
                      json={"emp_code": emp, "fecha": fecha, "tipo": tipo, "texto": texto})


def test_el_lider_justifica_una_novedad_de_su_gente(entorno, v):
    _cargar(entorno)
    entorno.como("tics")
    r = _justificar(entorno, "101", "llegada_tarde")
    v.check("el líder de TICS justifica a Beto", r.status_code == 200, r.text)
    v.check("queda con el texto y quién lo escribió", r.json()["texto"] == "Cita médica con soporte" and r.json()["autor"], r.json())
    entorno.como("admin")
    beto = _por_codigo(_dia(entorno))["101"]
    n = beto["novedades"][0]
    v.check("la novedad sigue ahí, con su justificación", n["tipo"] == "llegada_tarde" and n["justificacion"]["texto"].startswith("Cita"), n)
    t = _dia(entorno)["resumen"]["totales"]
    v.check("se cuenta como justificada y no se oculta", t["justificadas"] == 1 and t["sin_justificar"] == t["total_novedades"] - 1, t)
    v.check("las demás siguen sin justificar", _por_codigo(_dia(entorno))["200"]["novedades"][0]["justificacion"] is None)


def test_justificar_se_puede_corregir_y_quitar(entorno, v):
    _cargar(entorno)
    entorno.como("admin")
    _justificar(entorno, "200", "ausencia", "Incapacidad en trámite")
    r = _justificar(entorno, "200", "ausencia", "Incapacidad aprobada por la EPS")
    v.check("repetirlo lo corrige", r.status_code == 200, r.text)
    n = _por_codigo(_dia(entorno))["200"]["novedades"][0]
    v.check("queda una sola, la nueva", n["justificacion"]["texto"] == "Incapacidad aprobada por la EPS", n)
    r = entorno.delete("/marcaciones/justificacion", params={"emp_code": "200", "fecha": MARTES, "tipo": "ausencia"})
    v.check("se quita", r.status_code == 204, r.text)
    n = _por_codigo(_dia(entorno))["200"]["novedades"][0]
    v.check("la ausencia vuelve a estar sin justificar", n["justificacion"] is None, n)


def test_quien_puede_justificar(entorno, v):
    _cargar(entorno)
    entorno.como("tics")
    v.check("un líder no justifica a gente de otra área",
            _justificar(entorno, "200", "ausencia").status_code == 404)
    entorno.como("calidad")
    v.check("el líder de Calidad sí justifica a la suya", _justificar(entorno, "200", "ausencia").status_code == 200)
    entorno.como("logistica")
    v.check("el agente no justifica ni lo suyo", _justificar(entorno, "300", "exceso_almuerzo").status_code == 403)
    entorno.como("gerencia")
    v.check("gerencia consulta, no escribe", _justificar(entorno, "200", "ausencia").status_code == 403)
    entorno.como("lectura")
    v.check("lectura no escribe", _justificar(entorno, "200", "ausencia").status_code == 403)
    entorno.como("calidad")
    v.check("el alcance avisa si se puede justificar", _dia(entorno)["alcance"]["puede_justificar"] is True)
    entorno.como("logistica")
    v.check("y al agente le avisa que no", _dia(entorno)["alcance"]["puede_justificar"] is False)


def test_solo_se_justifica_lo_que_existe(entorno, v):
    _cargar(entorno)
    entorno.como("admin")
    v.check("Ana no tiene ausencia: nada que justificar", _justificar(entorno, "100", "ausencia").status_code == 400)
    v.check("una novedad inventada se rechaza", _justificar(entorno, "100", "invento").status_code == 400)
    v.check("un día futuro se rechaza", _justificar(entorno, "100", "ausencia", fecha="2999-01-01").status_code == 400)
    v.check("sin motivo no se guarda", _justificar(entorno, "200", "ausencia", texto="  ").status_code == 422)
    v.check("un motivo larguísimo se rechaza", _justificar(entorno, "200", "ausencia", texto="x" * 600).status_code == 422)
    v.check("alguien que no existe, 404", _justificar(entorno, "999", "ausencia").status_code == 404)


def test_la_justificacion_sale_en_el_detalle_y_en_el_csv(entorno, v):
    _cargar(entorno)
    entorno.como("admin")
    _justificar(entorno, "200", "ausencia", "Permiso por calamidad")
    d = entorno.get("/marcaciones/persona/200", params={"desde": MARTES, "hasta": MARTES}).json()
    v.check("el detalle de la persona la trae", d["dias"][0]["novedades"][0]["justificacion"]["texto"] == "Permiso por calamidad", d)
    v.check("y dice si se puede justificar", d["puede_justificar"] is True)
    csv_ = entorno.get("/marcaciones/informe.csv", params={"desde": MARTES, "hasta": MARTES}).content.decode()
    v.check("el CSV trae la columna", "Justificación" in csv_.splitlines()[0], csv_.splitlines()[0])
    v.check("con el motivo y quién lo escribió", "Permiso por calamidad" in csv_, csv_)


# ── El motor, sin base de datos ──────────────────────────────────────────

def _emp(**k):
    return {"emp_code": "1", "nombre": "P", "area": "A", **_turno(), **k}


def _m(hm, estado, dia="2026-11-03"):
    h, mi = hm.split(":")
    return (dt.datetime.combine(dt.date.fromisoformat(dia), dt.time(int(h), int(mi))), estado)


FIN_DIA = dt.datetime(2026, 11, 3, 23, 59, 59)
DIA = dt.date(2026, 11, 3)


def _tipos(fila):
    return [n["tipo"] for n in fila["novedades"]]


def test_el_motor_break_y_almuerzo():
    marcas = [_m("07:00", "0"), _m("09:30", "2"), _m("09:50", "3"), _m("12:00", "2"), _m("12:40", "3"), _m("17:00", "1")]
    fila = evaluacion.evaluar_persona(DIA, FIN_DIA, _emp(), marcas)
    assert _tipos(fila) == ["exceso_break"], fila["novedades"]   # break 20 min > 15; almuerzo 40 min ≤ 45


def test_el_motor_un_solo_descanso_temprano_es_break():
    marcas = [_m("07:00", "0"), _m("09:30", "2"), _m("09:50", "3"), _m("17:00", "1")]
    assert _tipos(evaluacion.evaluar_persona(DIA, FIN_DIA, _emp(), marcas)) == ["exceso_break"]


def test_el_motor_descanso_abierto_cuenta_hasta_ahora_pero_no_si_ya_salio():
    abierto = [_m("07:00", "0"), _m("12:00", "2")]
    ahora = dt.datetime(2026, 11, 3, 13, 0)
    fila = evaluacion.evaluar_persona(DIA, ahora, _emp(), abierto)
    assert _tipos(fila) == ["exceso_almuerzo"] and fila["presencia"] == "en_descanso"
    olvido = abierto + [_m("17:00", "1")]
    assert _tipos(evaluacion.evaluar_persona(DIA, FIN_DIA, _emp(), olvido)) == []


def test_el_motor_un_regreso_sin_salida_abierta_es_la_salida():
    # El reloj marcó «regresa de descanso» al salir y al volver.
    marcas = [_m("07:00", "0"), _m("09:30", "3"), _m("09:50", "3"), _m("12:00", "3"), _m("12:40", "3"), _m("17:00", "1")]
    fila = evaluacion.evaluar_persona(DIA, FIN_DIA, _emp(), marcas)
    assert [m["estado"] for m in fila["marcas"]] == ["0", "2", "3", "2", "3", "1"], fila["marcas"]
    assert _tipos(fila) == ["exceso_break"], fila["novedades"]
    # Afuera con un solo «3»: está en descanso, no adentro.
    fila = evaluacion.evaluar_persona(DIA, dt.datetime(2026, 11, 3, 12, 10), _emp(), marcas[:4])
    assert fila["presencia"] == "en_descanso"


def test_el_motor_los_descansos_se_leen_por_el_orden_no_por_el_boton():
    # Caso real: 09:46 y 09:59 con el botón de salida, 13:01 con el de regreso.
    marcas = [_m("05:39", "0"), _m("09:46", "2"), _m("09:59", "2"), _m("13:01", "3"), _m("13:46", "2")]
    emp = _emp(mar="06:00-14:30")
    fila = evaluacion.evaluar_persona(DIA, FIN_DIA, emp, marcas)
    assert [m["estado"] for m in fila["marcas"]] == ["0", "2", "3", "2", "3"], fila["marcas"]
    assert _tipos(fila) == [], fila["novedades"]   # break 13 min, almuerzo 45 min
    # Volver con el botón de Entrada también cierra el descanso.
    fila = evaluacion.evaluar_persona(DIA, FIN_DIA, emp, [_m("05:39", "0"), _m("09:46", "2"), _m("10:30", "0")])
    assert [m["estado"] for m in fila["marcas"]] == ["0", "2", "3"] and _tipos(fila) == ["exceso_break"]


def test_el_motor_salida_anticipada_y_tolerancias():
    assert _tipos(evaluacion.evaluar_persona(DIA, FIN_DIA, _emp(), [_m("07:05", "0"), _m("16:56", "1")])) == []
    fila = evaluacion.evaluar_persona(DIA, FIN_DIA, _emp(), [_m("07:06", "0"), _m("16:30", "1")])
    assert _tipos(fila) == ["llegada_tarde", "salida_anticipada"]


def test_el_motor_ausencia_espera_a_todos_los_turnos():
    emp = _emp(mar="06:00-14:00/14:00-22:00")
    # A las 15:00 el turno de las 14:00 solo lleva 1 h: todavía no es ausente.
    assert evaluacion.evaluar_persona(DIA, dt.datetime(2026, 11, 3, 15, 0), emp, [])["presencia"] == "pendiente"
    assert evaluacion.evaluar_persona(DIA, dt.datetime(2026, 11, 3, 17, 1), emp, [])["presencia"] == "ausente"


def test_el_motor_sabado_usa_la_ventana_corta():
    sab = dt.date(2026, 11, 7)
    emp = _emp(sab="07:00-12:00")
    assert evaluacion.evaluar_persona(sab, dt.datetime(2026, 11, 7, 8, 29), emp, [])["presencia"] == "pendiente"
    assert evaluacion.evaluar_persona(sab, dt.datetime(2026, 11, 7, 8, 31), emp, [])["presencia"] == "ausente"


def test_el_motor_dia_sin_turno_y_sin_marcas_no_aparece():
    dom = dt.date(2026, 11, 8)
    assert evaluacion.evaluar_persona(dom, dt.datetime(2026, 11, 8, 12, 0), _emp(), []) is None


def test_el_motor_turno_de_noche():
    emp = _emp(mar="22:00-06:00")
    fila = evaluacion.evaluar_persona(DIA, FIN_DIA, emp, [_m("21:58", "0")])
    assert fila["turno"] == "22:00-06:00" and _tipos(fila) == []


def test_el_motor_horas_extra_no_se_evaluan():
    fila = evaluacion.evaluar_persona(DIA, FIN_DIA, _emp(), [_m("07:00", "0"), _m("17:00", "1"), _m("18:00", "4"), _m("20:00", "5")])
    assert _tipos(fila) == [] and len(fila["marcas"]) == 2


def test_las_constantes_son_las_de_las_alertas():
    """Si cambian aquí y no en el script del servidor, la pantalla y el correo dicen cosas distintas."""
    from app.modules.marcaciones import constants as C
    assert (C.TOLERANCIA_LLEGADA_MIN, C.TOLERANCIA_SALIDA_MIN, C.AUSENCIA_HORAS, C.AUSENCIA_HORAS_SABADO) == (5, 5, 3, 1.5)
    assert (C.VENTANA_ANTES_MIN, C.VENTANA_DESPUES_MIN, C.ALMUERZO_MIN, C.BREAK_MIN, C.CORTE_BREAK_HORAS) == (45, 10, 45, 15, 4)


def test_el_esquema_acepta_la_malla_de_verdad():
    e = EmpleadoIn(emp_code="1", nombre="X", lun="06:00-14:30/07:00-15:30", sab="")
    assert e.lun == "06:00-14:30/07:00-15:30"


def test_hoy_se_puede_consultar(entorno, v):
    _cargar(entorno)
    entorno.como("admin")
    d = _dia(entorno, hoy().isoformat())
    v.check("es hoy", d["es_hoy"] is True and d["futuro"] is False, d["es_hoy"])
    futuro = _dia(entorno, (hoy() + dt.timedelta(days=3)).isoformat())
    v.check("un día futuro no acusa a nadie", futuro["personas"] == [] and futuro["futuro"], futuro["futuro"])
