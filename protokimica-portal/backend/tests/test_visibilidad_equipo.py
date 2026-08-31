"""
El jefe ve lo de su gente.

El caso: a alguien que NO es jefe le encargan liderar un proyecto. Con la
visibilidad puramente personal, su jefe de área no podía ni abrirlo — y es
quien responde por el área ante gerencia.

La regla quedó dependiendo del rol: quien ejecuta ve lo suyo, quien responde
por un área ve lo de su equipo.
"""
from app.models.user import User


def _proyecto(entorno, nombre, area=None, lider=None):
    entorno.como("admin")
    r = entorno.post("/master-planner/proyectos", json={
        "nombre": nombre, "area": area, "lider_id": lider,
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _ve(entorno, quien):
    entorno.como(quien)
    return {p["nombre"] for p in entorno.get("/master-planner/proyectos").json()}


def test_al_agente_que_lidera_lo_ve_su_jefe(entorno):
    """El caso exacto: no es jefe, pero le dieron un proyecto."""
    _proyecto(entorno, "Bodega nueva", area="Logística",
              lider=entorno.ids["logistica"])          # logistica es agente

    assert "Bodega nueva" in _ve(entorno, "logistica"), "quien lo lidera debe verlo"


def test_el_jefe_ve_el_proyecto_de_otra_area_que_lidera_su_gente(entorno):
    """
    Lo importante: el proyecto es de OTRA área, así que no se ve por área.
    Se ve porque lo lidera alguien del equipo.
    """
    # Un agente de Logística lidera un proyecto de Calidad.
    _proyecto(entorno, "Muestreo en planta", area="Calidad",
              lider=entorno.ids["logistica"])

    # Entre los usuarios de prueba no hay líder de Logística: se nombra uno,
    # que es el jefe de quien lidera el proyecto.
    db = entorno.Session()
    u = db.get(User, entorno.ids["tics"])
    u.area = "Logística"          # ahora es el jefe de esa área
    db.commit()
    db.close()

    assert "Muestreo en planta" in _ve(entorno, "tics"), (
        "el jefe del área de quien lidera tiene que poder verlo"
    )


def test_un_agente_no_ve_lo_de_su_area_si_no_participa(entorno):
    """Lo que se quitó: al que ejecuta no se le llena la lista de ajenos."""
    _proyecto(entorno, "Inventario anual", area="Logística")   # sin él adentro

    assert "Inventario anual" not in _ve(entorno, "logistica")


def test_el_jefe_si_lo_ve(entorno):
    """El mismo proyecto, mirado por quien responde por el área."""
    _proyecto(entorno, "Inventario anual", area="Calidad")

    assert "Inventario anual" in _ve(entorno, "calidad")


def test_lo_que_crea_un_admin_no_se_le_carga_al_area_del_admin(entorno):
    """
    Un admin suele tener área propia pero crea proyectos de toda la empresa.
    Si contara como parte del equipo, el jefe de su área vería el portal
    entero — justo lo contrario de lo que se busca.
    """
    _proyecto(entorno, "Proyecto de otra área", area="Logística")

    # El admin de prueba es del área TICS y queda como líder al no indicar uno.
    assert "Proyecto de otra área" not in _ve(entorno, "tics")


def test_el_presupuesto_del_area_lo_ve_su_jefe(entorno):
    """
    El presupuesto se le carga al área responsable, así que su líder responde
    por él aunque el proyecto lo lidere alguien de su equipo.
    """
    pid = _proyecto(entorno, "Renovación de equipos", area="Calidad",
                    lider=entorno.ids["logistica"])
    entorno.como("admin")
    entorno.post(f"/master-planner/proyectos/{pid}/presupuesto", json={
        "concepto": "Equipos", "valor_unitario": 1000000, "cantidad": 1,
    })

    entorno.como("calidad")     # jefe del área responsable
    assert entorno.get(f"/master-planner/proyectos/{pid}/presupuesto").status_code == 200


def test_tener_una_tarea_no_da_acceso_a_la_plata(entorno):
    """Esta regla no cambió: se trabaja en el proyecto sin ver cuánto mueve."""
    pid = _proyecto(entorno, "Ampliación de planta", area="Calidad")
    entorno.como("admin")
    entorno.post(f"/master-planner/proyectos/{pid}/tareas", json={
        "titulo": "Montar el equipo", "asignado_a": entorno.ids["logistica"],
    })

    entorno.como("logistica")
    assert entorno.get(f"/master-planner/proyectos/{pid}").status_code == 200
    assert entorno.get(f"/master-planner/proyectos/{pid}/presupuesto").status_code == 403
