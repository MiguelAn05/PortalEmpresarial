"""
Dos defectos que se veían en la lista de proyectos.

1. **Todos salían «Sin asignar»** aunque tuvieran líder. `ProyectoOut`
   declaraba `lider_nombre` pero el modelo no tenía esa propiedad, así que
   Pydantic caía en el valor por defecto. El `lider_id` sí viajaba, y por eso
   el formulario de edición mostraba a la persona correcta mientras la lista
   y el detalle decían lo contrario — que es lo que hace difícil de ver este
   tipo de fallo.

2. **El líder de un área no veía los proyectos donde su área PARTICIPA**,
   solo aquellos donde es la responsable. Es el mismo defecto que ya había
   mordido en el filtro por área (ver `condicion_area`), que en la
   visibilidad no se había corregido.
"""
from app.models.user import User


def _proyecto(entorno, nombre, area=None, lider=None, participantes=None):
    entorno.como("admin")
    r = entorno.post("/master-planner/proyectos", json={
        "nombre": nombre, "area": area, "lider_id": lider,
        "areas_participantes": participantes or [],
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _lista(entorno, quien):
    entorno.como(quien)
    return entorno.get("/master-planner/proyectos").json()


# ── El nombre del líder ──────────────────────────────────────────────

def test_la_lista_dice_quien_lidera(entorno, v):
    """El defecto: salía «Sin asignar» con el líder ya puesto."""
    _proyecto(entorno, "Bodega nueva", area="Calidad", lider=entorno.ids["calidad"])

    proyecto = next(p for p in _lista(entorno, "admin") if p["nombre"] == "Bodega nueva")

    v.check("viaja el id", proyecto["lider_id"] == entorno.ids["calidad"], proyecto)
    v.check("y también el nombre", proyecto["lider_nombre"] == "Cali", proyecto)


def test_el_detalle_dice_lo_mismo_que_la_lista(entorno, v):
    """
    Si los dos no coinciden, nadie sabe cuál creer. Era el síntoma que
    delataba el defecto.
    """
    pid = _proyecto(entorno, "Bodega nueva", area="Calidad", lider=entorno.ids["calidad"])

    entorno.como("admin")
    detalle = entorno.get(f"/master-planner/proyectos/{pid}").json()
    listado = next(p for p in _lista(entorno, "admin") if p["id"] == pid)

    v.check("el detalle trae el nombre", detalle["lider_nombre"] == "Cali", detalle)
    v.check("y coincide con la lista",
            detalle["lider_nombre"] == listado["lider_nombre"],
            {"detalle": detalle["lider_nombre"], "lista": listado["lider_nombre"]})


def test_un_proyecto_sin_lider_sigue_diciendo_que_no_tiene(entorno, v):
    """Que el arreglo no invente un nombre donde no lo hay."""
    # Sin líder explícito queda a nombre de quien lo creó (admin), para que
    # no desaparezca de la lista de nadie.
    pid = _proyecto(entorno, "Proyecto huérfano", area="Calidad")

    entorno.como("admin")
    detalle = entorno.get(f"/master-planner/proyectos/{pid}").json()

    v.check("queda a nombre de quien lo creó",
            detalle["lider_id"] == entorno.ids["admin"], detalle)
    v.check("con su nombre", detalle["lider_nombre"] == "Admin", detalle)


# ── Áreas participantes, no solo la responsable ──────────────────────

def test_el_lider_ve_los_proyectos_donde_su_area_participa(entorno, v):
    """
    El caso que reportaron: el proyecto es de TICS, pero Calidad está adentro
    como área participante. El líder de Calidad tiene que verlo.
    """
    _proyecto(entorno, "Migración de servidores", area="TICS",
              lider=entorno.ids["tics"], participantes=["Calidad"])

    nombres = {p["nombre"] for p in _lista(entorno, "calidad")}

    v.check("el líder de Calidad lo ve", "Migración de servidores" in nombres, nombres)


def test_y_puede_abrirlo_no_solo_verlo_en_la_lista(entorno, v):
    """
    Verlo en la lista y recibir 404 al abrirlo es peor que no verlo: la
    visibilidad de la lista y la del detalle tienen que decir lo mismo.
    """
    pid = _proyecto(entorno, "Migración de servidores", area="TICS",
                    lider=entorno.ids["tics"], participantes=["Calidad"])

    entorno.como("calidad")
    r = entorno.get(f"/master-planner/proyectos/{pid}")

    v.check("abre", r.status_code == 200, r.status_code)


def test_el_area_responsable_sigue_funcionando(entorno, v):
    """Que arreglar lo de participantes no rompa lo que ya servía."""
    _proyecto(entorno, "Auditoría interna", area="Calidad", lider=entorno.ids["tics"])

    nombres = {p["nombre"] for p in _lista(entorno, "calidad")}

    v.check("lo ve por ser el área responsable",
            "Auditoría interna" in nombres, nombres)


def test_un_agente_no_gana_visibilidad_por_el_area_participante(entorno, v):
    """
    La regla sigue dependiendo del rol: el que ejecuta ve lo suyo. Si esto
    cambiara, volveríamos a llenarle la lista de proyectos ajenos.
    """
    _proyecto(entorno, "Ampliación de bodega", area="TICS",
              lider=entorno.ids["tics"], participantes=["Logística"])

    # `logistica` es agente del área Logística, y no participa en el proyecto.
    nombres = {p["nombre"] for p in _lista(entorno, "logistica")}

    v.check("el agente no lo ve", "Ampliación de bodega" not in nombres, nombres)


def test_el_presupuesto_sigue_siendo_solo_del_area_responsable(entorno, v):
    """
    La asimetría es a propósito: ver el proyecto no es ver cuánta plata mueve.
    El presupuesto se le carga al área RESPONSABLE, así que el líder de un
    área participante lo ve en la lista pero no su presupuesto.
    """
    from app.models.master_planner import Proyecto
    from app.modules.master_planner.permisos import puede_ver_presupuesto

    pid = _proyecto(entorno, "Migración de servidores", area="TICS",
                    lider=entorno.ids["tics"], participantes=["Calidad"])

    db = entorno.Session()
    proyecto = db.get(Proyecto, pid)
    lider_calidad = db.get(User, entorno.ids["calidad"])
    lider_tics = db.get(User, entorno.ids["tics"])

    v.check("el área participante NO ve el presupuesto",
            puede_ver_presupuesto(proyecto, lider_calidad) is False)
    v.check("el área responsable sí",
            puede_ver_presupuesto(proyecto, lider_tics) is True)
    db.close()
