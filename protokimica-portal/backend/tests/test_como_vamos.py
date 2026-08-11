"""
La portada gerencial de Indicadores.

Lo que se prueba no es que "responda 200", sino las decisiones que hacen que
el tablero sirva o engañe: qué cuenta como movimiento, que el alcance lo
mande el rol y no el que pide, que un mes futuro no se confunda con uno sin
reportar, y que los números coincidan con el tablero de siempre.
"""
from app.modules.indicadores.como_vamos import calcular_movimientos


def _crear(portal, nombre, area, meta=90, direccion="arriba",
           verde=90, amarillo=75, unidad="porcentaje"):
    r = portal.post("/indicadores", json={
        "nombre": nombre, "unidad": unidad, "tipo_captura": "valor", "area": area,
        "meta": meta, "direccion": direccion,
        "umbral_verde": verde, "umbral_amarillo": amarillo,
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _medir(portal, indicador_id, anio, mes, valor):
    return portal.post(f"/indicadores/{indicador_id}/mediciones",
                       data={"anio": anio, "mes": mes, "valor": valor})


# ── Qué cuenta como movimiento ───────────────────────────────────────────

def test_solo_se_reportan_los_que_cambiaron_de_semaforo(v):
    fichas = [
        {"id": 1, "nombre": "Bajó a rojo", "area": "Calidad", "unidad": "porcentaje",
         "semaforo": "rojo", "semaforo_mes_anterior": "verde",
         "valor": 60, "valor_mes_anterior": 95, "variacion_mes": -35},
        {"id": 2, "nombre": "Sigue verde", "area": "TICS", "unidad": "porcentaje",
         "semaforo": "verde", "semaforo_mes_anterior": "verde",
         "valor": 99, "valor_mes_anterior": 98, "variacion_mes": 1},
        {"id": 3, "nombre": "Se recuperó", "area": "Logística", "unidad": "porcentaje",
         "semaforo": "verde", "semaforo_mes_anterior": "amarillo",
         "valor": 96, "valor_mes_anterior": 80, "variacion_mes": 16},
    ]
    movs = calcular_movimientos(fichas)

    v.check("solo salen los que cambiaron", len(movs) == 2, [m["nombre"] for m in movs])
    v.check("el que empeoró va primero", movs[0]["id"] == 1, movs[0]["nombre"])
    v.check("y va marcado como empeoró", movs[0]["empeoro"] is True, movs[0])
    v.check("el que se recuperó no", movs[1]["empeoro"] is False, movs[1])


def test_un_indicador_que_nadie_ha_reportado_nunca_no_es_un_movimiento(v):
    """Sin dato dos meses seguidos es un pendiente de registro, no un cambio."""
    fichas = [{
        "id": 1, "nombre": "Nunca reportado", "area": "SST", "unidad": "cantidad",
        "semaforo": "sin_datos", "semaforo_mes_anterior": "sin_datos",
        "valor": None, "valor_mes_anterior": None, "variacion_mes": None,
    }]
    v.check("no aparece como movimiento", calcular_movimientos(fichas) == [])


def test_dejar_de_reportar_si_es_un_movimiento(v):
    """Pasar de tener dato a no tenerlo es información: alguien dejó de medir."""
    fichas = [{
        "id": 1, "nombre": "Se dejó de medir", "area": "Producción", "unidad": "porcentaje",
        "semaforo": "sin_datos", "semaforo_mes_anterior": "verde",
        "valor": None, "valor_mes_anterior": 97, "variacion_mes": None,
    }]
    movs = calcular_movimientos(fichas)
    v.check("sí aparece", len(movs) == 1, movs)
    v.check("y cuenta como empeorar", movs[0]["empeoro"] is True, movs[0])


# ── La portada completa, contra la API ───────────────────────────────────

def test_la_portada_responde_lo_que_pinta_el_tablero(entorno, v):
    portal = entorno
    A, M = 2026, 7

    bueno = _crear(portal, "Despachos a tiempo", "Logística")
    malo = _crear(portal, "Cumplimiento de producción", "Producción")

    _medir(portal, bueno, A, M - 1, 95)
    _medir(portal, bueno, A, M, 96)     # verde los dos meses: no se movió
    _medir(portal, malo, A, M - 1, 92)  # verde
    _medir(portal, malo, A, M, 60)      # rojo: se movió

    r = portal.get("/indicadores/como-vamos", params={"anio": A, "mes": M})
    v.check("responde 200", r.status_code == 200, r.text[:200])
    datos = r.json()

    v.check("un solo movimiento", len(datos["movimientos"]) == 1, datos["movimientos"])
    v.check("es el que se cayó",
            datos["movimientos"][0]["nombre"] == "Cumplimiento de producción",
            datos["movimientos"][0])

    # Los conteos tienen que ser los MISMOS que los del tablero de siempre:
    # si divergen, gerencia y calidad discuten sobre números distintos.
    t = portal.get("/indicadores/tablero", params={"anio": A, "mes": M}).json()
    v.check("el resumen coincide con el tablero",
            datos["resumen"] == t["resumen"], (datos["resumen"], t["resumen"]))


def test_la_matriz_separa_el_mes_futuro_del_no_reportado(entorno, v):
    """
    Un mes que no ha llegado no es un incumplimiento. Contarlos juntos haría
    ver la empresa peor de lo que está durante todo el año.
    """
    portal = entorno
    A, M = 2026, 7
    ind = _crear(portal, "Disponibilidad de sistemas", "TICS")
    _medir(portal, ind, A, 1, 99)
    # Febrero a julio quedan sin reportar a propósito.

    datos = portal.get("/indicadores/como-vamos", params={"anio": A, "mes": M}).json()
    meses = datos["matriz"][0]["meses"]

    v.check("enero tiene dato", meses[0]["semaforo"] == "verde", meses[0])
    v.check("febrero quedó sin reportar", meses[1]["semaforo"] == "sin_datos", meses[1])
    v.check("agosto aún no llega", meses[7]["semaforo"] == "futuro", meses[7])
    v.check("y diciembre tampoco", meses[11]["semaforo"] == "futuro", meses[11])


def test_las_areas_con_algo_en_rojo_van_primero(entorno, v):
    portal = entorno
    A, M = 2026, 7

    # Calidad: 1 de 2 en meta (50%) pero nada en rojo.
    _medir(portal, _crear(portal, "Auditorías cerradas", "Calidad"), A, M, 95)
    _medir(portal, _crear(portal, "Hallazgos resueltos", "Calidad"), A, M, 80)   # amarillo
    # Comercial: 2 de 3 en meta (67%) pero uno en rojo.
    _medir(portal, _crear(portal, "Ventas del plan", "Comercial"), A, M, 95)
    _medir(portal, _crear(portal, "Visitas cumplidas", "Comercial"), A, M, 92)
    _medir(portal, _crear(portal, "Cartera al día", "Comercial"), A, M, 40)      # rojo

    datos = portal.get("/indicadores/como-vamos", params={"anio": A, "mes": M}).json()
    areas = [a["area"] for a in datos["por_area"]]

    v.check("Comercial va antes que Calidad pese a tener mejor porcentaje",
            areas.index("Comercial") < areas.index("Calidad"), datos["por_area"])


# ── El alcance lo manda el rol ───────────────────────────────────────────

def test_gerencia_ve_toda_la_empresa(entorno, v):
    portal = entorno
    A, M = 2026, 7
    _medir(portal, _crear(portal, "Indicador de TICS", "TICS"), A, M, 95)
    _medir(portal, _crear(portal, "Indicador de Calidad", "Calidad"), A, M, 95)

    portal.como("gerencia")
    datos = portal.get("/indicadores/como-vamos", params={"anio": A, "mes": M}).json()

    v.check("el alcance es empresa", datos["alcance"]["actual"] == "empresa", datos["alcance"])
    v.check("puede cambiarlo", datos["alcance"]["puede_cambiar"] is True, datos["alcance"])
    v.check("ve los dos indicadores", datos["resumen"]["total"] == 2, datos["resumen"])


def test_un_lider_solo_ve_su_area_aunque_pida_la_empresa(entorno, v):
    """
    No se responde un error: se le devuelve lo suyo. Pedir "empresa" desde un
    enlace guardado o tras un cambio de rol no es un intento de saltarse nada.
    """
    portal = entorno
    A, M = 2026, 7
    _medir(portal, _crear(portal, "Indicador de TICS", "TICS"), A, M, 95)
    _medir(portal, _crear(portal, "Indicador de Calidad", "Calidad"), A, M, 95)

    portal.como("tics")   # líder del área TICS
    datos = portal.get("/indicadores/como-vamos",
                       params={"anio": A, "mes": M, "alcance": "empresa"}).json()

    v.check("el alcance cae a su área", datos["alcance"]["actual"] == "area", datos["alcance"])
    v.check("no puede cambiarlo", datos["alcance"]["puede_cambiar"] is False, datos["alcance"])
    v.check("solo ve el suyo", datos["resumen"]["total"] == 1, datos["resumen"])
    v.check("y es el de su área",
            datos["matriz"][0]["area"] == "TICS", datos["matriz"])


def test_gerencia_puede_bajar_a_un_area(entorno, v):
    portal = entorno
    A, M = 2026, 7
    _medir(portal, _crear(portal, "Indicador de TICS", "TICS"), A, M, 95)
    _medir(portal, _crear(portal, "Indicador de Calidad", "Calidad"), A, M, 95)

    portal.como("gerencia")
    datos = portal.get("/indicadores/como-vamos",
                       params={"anio": A, "mes": M, "alcance": "area"}).json()
    v.check("respeta el alcance pedido", datos["alcance"]["actual"] == "area", datos["alcance"])


def test_la_ruta_no_la_captura_el_path_variable(entorno, v):
    """/como-vamos va declarada antes que /{indicador_id}, o se la come."""
    r = entorno.get("/indicadores/como-vamos")
    v.check("no responde 422 por intentar leerla como id", r.status_code == 200, r.status_code)
