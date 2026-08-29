"""
Filtrar proyectos por área cuenta también las áreas participantes.

El caso real: un proyecto de TICS donde Mercadeo también trabaja. Mercadeo lo
veía en la lista general —la visibilidad siempre estuvo bien— pero lo perdía
apenas filtraba por su propia área, que es justo cuando lo busca.

Lo que NO cambia: el presupuesto se le sigue cargando solo al área
responsable. Repartirlo entre las participantes inflaría los totales.
"""


def _proyecto(portal, nombre, area, participantes=None, presupuesto=None):
    r = portal.post("/master-planner/proyectos", json={
        "nombre": nombre, "area": area,
        "areas_participantes": participantes or [],
    })
    assert r.status_code == 201, r.text
    proyecto = r.json()
    if presupuesto:
        portal.post(f"/master-planner/proyectos/{proyecto['id']}/presupuesto", json={
            "concepto": "Equipos", "valor_unitario": presupuesto, "cantidad": 1,
        })
    return proyecto


def test_filtrar_por_area_participante_muestra_el_proyecto(entorno, v):
    portal = entorno
    _proyecto(portal, "Portal WMS", "TICS", ["Mercadeo"])
    _proyecto(portal, "Campaña navidad", "Mercadeo")
    _proyecto(portal, "Servidores", "TICS")

    nombres = [p["nombre"] for p in
               portal.get("/master-planner/proyectos", params={"area": "Mercadeo"}).json()]

    v.check("sale el proyecto propio de Mercadeo", "Campaña navidad" in nombres, nombres)
    v.check("y también aquel donde participa", "Portal WMS" in nombres, nombres)
    v.check("pero no uno ajeno de TICS", "Servidores" not in nombres, nombres)


def test_el_area_responsable_sigue_viendo_lo_suyo(entorno, v):
    portal = entorno
    _proyecto(portal, "Portal WMS", "TICS", ["Mercadeo"])

    nombres = [p["nombre"] for p in
               portal.get("/master-planner/proyectos", params={"area": "TICS"}).json()]
    v.check("TICS lo sigue viendo", "Portal WMS" in nombres, nombres)


def test_un_proyecto_con_varias_areas_sale_en_todas(entorno, v):
    portal = entorno
    _proyecto(portal, "Lanzamiento", "TICS", ["Mercadeo", "Comercial", "Logística"])

    for area in ["TICS", "Mercadeo", "Comercial", "Logística"]:
        nombres = [p["nombre"] for p in
                   portal.get("/master-planner/proyectos", params={"area": area}).json()]
        v.check(f"aparece al filtrar por {area}", "Lanzamiento" in nombres, nombres)


def test_el_presupuesto_no_se_duplica_entre_areas(entorno, v):
    """
    Lo que se arregló es el FILTRO, no la atribución. Un proyecto de 10
    millones con tres áreas sigue sumando 10, no 30: la plata es del área
    responsable, que es la dueña del presupuesto.
    """
    portal = entorno
    _proyecto(portal, "Lanzamiento", "TICS", ["Mercadeo", "Comercial"],
              presupuesto=10_000_000)

    resumen = portal.get("/master-planner/resumen").json()
    por_area = {a["area"]: a for a in resumen["presupuesto_por_area"]}

    v.check("la plata se le carga a TICS",
            por_area.get("TICS", {}).get("planeado") == 10_000_000, por_area)
    v.check("Mercadeo no hereda presupuesto ajeno",
            "Mercadeo" not in por_area, list(por_area))
    v.check("el total no se multiplica",
            sum(a["planeado"] for a in resumen["presupuesto_por_area"]) == 10_000_000,
            resumen["presupuesto_por_area"])


def test_el_resumen_filtrado_tambien_cuenta_las_participantes(entorno, v):
    portal = entorno
    _proyecto(portal, "Portal WMS", "TICS", ["Mercadeo"], presupuesto=5_000_000)
    _proyecto(portal, "Servidores", "TICS", presupuesto=3_000_000)

    resumen = portal.get("/master-planner/resumen", params={"area": "Mercadeo"}).json()
    v.check("el resumen de Mercadeo incluye el proyecto donde participa",
            resumen["kpis"]["proyectos_total"] == 1, resumen["kpis"])
