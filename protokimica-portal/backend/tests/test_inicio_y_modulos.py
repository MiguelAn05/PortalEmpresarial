"""
Acceso por módulo y armado del inicio.

Hasta ahora el portal solo controlaba la escritura: cualquier usuario
autenticado podía LEER cualquier módulo. Un agente de Logística veía todos
los indicadores de la empresa.
"""
from datetime import datetime, timedelta, timezone


def _proyecto_con_tarea(portal, area="TICS", asignado=None, dias=-2):
    """Un proyecto con una tarea asignada y vencida hace `dias`."""
    portal.como("admin")
    pid = portal.post("/master-planner/proyectos",
                      json={"nombre": f"Proyecto {area}", "area": area}).json()["id"]
    fin = (datetime.now(timezone.utc) + timedelta(days=dias)).isoformat()
    tid = portal.post(f"/master-planner/proyectos/{pid}/tareas", json={
        "titulo": "Migrar base de datos", "asignado_a": asignado, "fecha_fin": fin,
    }).json()["id"]
    return pid, tid


# ── Acceso por módulo ─────────────────────────────────────────

def test_un_agente_no_entra_a_indicadores(entorno, v):
    portal = entorno
    portal.como("admin")
    ind = portal.post("/indicadores", json={
        "nombre": "Oportunidad PQRS", "unidad": "porcentaje", "tipo_captura": "valor",
        "area": "TICS", "meta": 90,
    }).json()

    portal.como("logistica")   # agente
    v.check("el tablero le da 403", portal.get("/indicadores/tablero").status_code == 403)
    v.check("el listado también", portal.get("/indicadores").status_code == 403)
    v.check("el detalle también", portal.get(f"/indicadores/{ind['id']}").status_code == 403)
    v.check("el catálogo también", portal.get("/indicadores/catalogo").status_code == 403)

    r = portal.get("/indicadores/tablero")
    v.check("el mensaje explica y dice a quién pedirle",
            "Indicadores" in r.json().get("detail", "")
            and "administrador" in r.json().get("detail", ""), r.json())

    # Pero lo suyo sigue funcionando
    v.check("PQRS sí", portal.get("/pqrs").status_code == 200)
    v.check("Master Planner sí", portal.get("/master-planner/proyectos").status_code == 200)
    v.check("y sus tareas", portal.get("/master-planner/tareas/mias").status_code == 200)


def test_lectura_tampoco_entra_a_indicadores(entorno, v):
    portal = entorno
    portal.como("lectura")
    v.check("solo lectura no entra a indicadores",
            portal.get("/indicadores/tablero").status_code == 403)
    v.check("pero sí consulta PQRS", portal.get("/pqrs").status_code == 200)


def test_gerencia_y_admin_ven_todo(entorno, v):
    portal = entorno
    for quien in ("admin", "gerencia"):
        portal.como(quien)
        v.check(f"{quien} entra a indicadores",
                portal.get("/indicadores/tablero").status_code == 200)
        v.check(f"{quien} entra a master planner",
                portal.get("/master-planner/resumen").status_code == 200)


def test_un_lider_solo_ve_los_indicadores_de_su_area(entorno, v):
    portal = entorno
    portal.como("admin")
    portal.post("/indicadores", json={
        "nombre": "Indicador de TICS", "unidad": "porcentaje",
        "tipo_captura": "valor", "area": "TICS", "meta": 90,
    })
    ajeno = portal.post("/indicadores", json={
        "nombre": "Indicador de Calidad", "unidad": "porcentaje",
        "tipo_captura": "valor", "area": "Calidad", "meta": 90,
    }).json()

    portal.como("tics")   # líder de TICS
    r = portal.get("/indicadores")
    v.check("el líder entra al módulo", r.status_code == 200, r.text[:120])
    nombres = {i["nombre"] for i in r.json()}
    v.check("ve el de su área", "Indicador de TICS" in nombres, nombres)
    v.check("NO ve el de otra área", "Indicador de Calidad" not in nombres, nombres)

    tab = portal.get("/indicadores/tablero").json()
    v.check("el tablero también se acota",
            {i["nombre"] for i in tab["indicadores"]} == {"Indicador de TICS"},
            [i["nombre"] for i in tab["indicadores"]])

    v.check("abrir uno de otra área da 404, no 403",
            portal.get(f"/indicadores/{ajeno['id']}").status_code == 404)
    v.check("y tampoco puede editarlo",
            portal.patch(f"/indicadores/{ajeno['id']}", json={"meta": 1}).status_code == 404)


def test_el_lider_no_puede_saltarse_el_filtro_con_el_parametro_area(entorno, v):
    """El filtro se impone en el servidor; mandar otra área no lo abre."""
    portal = entorno
    portal.como("admin")
    portal.post("/indicadores", json={
        "nombre": "Indicador de Calidad", "unidad": "porcentaje",
        "tipo_captura": "valor", "area": "Calidad", "meta": 90,
    })

    portal.como("tics")
    tab = portal.get("/indicadores/tablero?area=Calidad").json()
    v.check("pedir otra área no devuelve nada ajeno",
            all(i["area"] == "TICS" for i in tab["indicadores"]),
            [i["area"] for i in tab["indicadores"]])


# ── El inicio ─────────────────────────────────────────────────

def test_el_inicio_dice_quien_eres_y_a_que_entras(entorno, v):
    portal = entorno
    portal.como("logistica")
    r = portal.get("/inicio")
    v.check("responde 200", r.status_code == 200, r.text[:150])
    d = r.json()
    v.check("trae el nombre", d["usuario"]["nombre"] == "Logi", d["usuario"])
    v.check("y el rol", d["usuario"]["rol"] == "agente", d["usuario"])
    v.check("y el área", d["usuario"]["area"] == "Logística", d["usuario"])
    v.check("lista sus módulos sin indicadores",
            "indicadores" not in d["modulos"] and "pqrs" in d["modulos"], d["modulos"])

    portal.como("gerencia")
    d = portal.get("/inicio").json()
    v.check("gerencia sí tiene indicadores en sus módulos",
            "indicadores" in d["modulos"], d["modulos"])
    v.check("pero no administración", "admin" not in d["modulos"], d["modulos"])


def test_el_inicio_trae_mis_tareas_vencidas(entorno, v):
    portal = entorno
    _proyecto_con_tarea(portal, asignado=portal.ids["logistica"], dias=-2)
    _proyecto_con_tarea(portal, asignado=portal.ids["logistica"], dias=1)   # por vencer
    _proyecto_con_tarea(portal, asignado=portal.ids["calidad"], dias=-5)    # de otro

    portal.como("logistica")
    d = portal.get("/inicio").json()
    t = d["mis_tareas"]
    v.check("cuenta solo las suyas", t["abiertas"] == 2, t)
    v.check("una vencida", t["vencidas"] == 1, t)
    v.check("una por vencer", t["por_vencer"] == 1, t)
    v.check("la lista trae el proyecto de cada tarea",
            all(x["proyecto"] for x in t["lista"]), t["lista"])
    v.check("las vencidas van primero",
            t["lista"][0]["id"] != t["lista"][1]["id"], t["lista"])
    v.check("el total urgente refleja lo vencido", d["total_urgente"] == 1, d["total_urgente"])


def test_el_inicio_no_muestra_la_empresa_a_un_agente(entorno, v):
    portal = entorno
    portal.como("logistica")
    d = portal.get("/inicio").json()
    v.check("un agente no ve el titular de empresa", d["empresa"] is None, d["empresa"])
    v.check("ni el bloque de área", d["mi_area"] is None, d["mi_area"])
    v.check("ni indicadores por registrar",
            d["indicadores_por_registrar"] == [], d["indicadores_por_registrar"])


def test_el_inicio_muestra_la_empresa_a_gerencia(entorno, v):
    portal = entorno
    _proyecto_con_tarea(portal, asignado=portal.ids["logistica"])
    portal.como("gerencia")
    d = portal.get("/inicio").json()
    e = d["empresa"]
    v.check("gerencia sí ve el titular", e is not None, e)
    if e:
        for campo in ("proyectos_activos", "pqrs_abiertas", "presupuesto_planeado",
                      "presupuesto_pagado", "indicadores_en_rojo"):
            v.check(f"trae '{campo}'", campo in e, sorted(e))
        v.check("cuenta el proyecto", e["proyectos_activos"] == 1, e)


def test_el_inicio_de_un_lider_trae_su_area(entorno, v):
    portal = entorno
    _proyecto_con_tarea(portal, area="TICS", asignado=portal.ids["tics"], dias=-3)

    portal.como("tics")
    d = portal.get("/inicio").json()
    a = d["mi_area"]
    v.check("el líder ve el bloque de su área", a is not None, a)
    if a:
        v.check("con el nombre del área", a["area"] == "TICS", a)
        v.check("cuenta sus proyectos", a["total_proyectos"] == 1, a)
        v.check("y las tareas vencidas del equipo", a["tareas_vencidas_equipo"] == 1, a)
        v.check("lista los proyectos", len(a["proyectos"]) == 1, a["proyectos"])


def test_el_inicio_avisa_que_indicadores_faltan_por_registrar(entorno, v):
    portal = entorno
    portal.como("admin")
    portal.post("/indicadores", json={
        "nombre": "Rotación de personal", "unidad": "porcentaje",
        "tipo_captura": "valor", "area": "TICS", "meta": 5, "direccion": "abajo",
    })
    portal.post("/indicadores", json={
        "nombre": "Automático", "unidad": "porcentaje", "tipo_captura": "automatico",
        "fuente_automatica": "pqrs_oportunidad_sla", "area": "TICS",
    })

    portal.como("tics")
    d = portal.get("/inicio").json()
    nombres = [i["nombre"] for i in d["indicadores_por_registrar"]]
    v.check("avisa del manual sin registrar", "Rotación de personal" in nombres, nombres)
    v.check("no pide registrar los automáticos", "Automático" not in nombres, nombres)


def test_el_inicio_no_revienta_sin_datos(entorno, v):
    """Un portal recién instalado tiene que abrir sin nada cargado."""
    portal = entorno
    for quien in ("admin", "gerencia", "tics", "logistica", "lectura"):
        portal.como(quien)
        r = portal.get("/inicio")
        v.check(f"{quien} abre el inicio", r.status_code == 200, r.text[:120])
        if r.status_code == 200:
            d = r.json()
            v.check(f"{quien} sin pendientes inventados", d["total_pendiente"] == 0, d["total_pendiente"])
