"""
Las áreas de cada empresa: la tabla, renombrar sin dejar nada huérfano y
desactivar sin perder lo que ya las tenía.

Hasta la fase 4b del plan de modularización las áreas eran una lista en el
código, igual para cualquier empresa. Ahora son de cada empresa (`areas`) y
se administran en Administración › Áreas.
"""
from app.core.areas import (
    AREAS_INICIALES, COLUMNAS_CON_AREA, EQUIVALENCIAS_HISTORICAS, clave_alfabetica,
    es_valida, nombres, normalizar,
)
from app.core.capacidades import tiene
from app.core.database import Base
from app.main import app  # noqa: F401  (carga todos los modelos)
from app.models.area import Area
from app.models.master_planner import Proyecto, ProyectoArea, Tarea
from app.models.tenant import Tenant
from app.models.user import User


# ── La lista de arranque y las equivalencias ─────────────────

def test_no_hay_areas_repetidas():
    assert len(AREAS_INICIALES) == len(set(AREAS_INICIALES)), "Hay áreas duplicadas"


def test_toda_equivalencia_apunta_a_un_area_real():
    for viejo, nuevo in EQUIVALENCIAS_HISTORICAS.items():
        assert nuevo in AREAS_INICIALES, f"'{viejo}' apunta a '{nuevo}', que no está en la lista"
        assert viejo not in AREAS_INICIALES, f"'{viejo}' es un nombre viejo"


def test_normalizar_traduce_los_nombres_viejos():
    assert normalizar("TI") == "TICS"
    assert normalizar("Sistemas") == "TICS"
    assert normalizar("Talento Humano") == "Gestión Humana"


def test_normalizar_limpia_los_vacios():
    # Cadena vacía y espacios vienen de formularios que envían "" en vez de nada.
    assert normalizar("") is None
    assert normalizar("   ") is None
    assert normalizar(None) is None
    assert normalizar("  Calidad  ") == "Calidad"


# ── Las de cada empresa ──────────────────────────────────────

def test_la_empresa_arranca_con_las_iniciales_en_orden_alfabetico(entorno, v):
    db = entorno.Session()
    v.check("las mismas", set(nombres(db, entorno.tenant_id)) == set(AREAS_INICIALES))
    v.check("en orden alfabético", nombres(db, entorno.tenant_id)
            == sorted(AREAS_INICIALES, key=clave_alfabetica))
    v.check("es_valida acepta una suya", es_valida(db, entorno.tenant_id, "Calidad"))
    v.check("y None", es_valida(db, entorno.tenant_id, None))
    v.check("pero no una inventada", not es_valida(db, entorno.tenant_id, "Inventada"))
    v.check("ni un nombre viejo", not es_valida(db, entorno.tenant_id, "TI"))
    db.close()


def test_cada_empresa_tiene_las_suyas(entorno, v):
    db = entorno.Session()
    otra = Tenant(nombre="Otra", slug="otra")
    db.add(otra)
    db.commit()
    db.add(Area(tenant_id=otra.id, nombre="Bodega Norte"))
    db.commit()
    v.check("la otra tiene la suya", nombres(db, otra.id) == ["Bodega Norte"])
    v.check("y no las de Protokimica", not es_valida(db, otra.id, "Calidad"))
    v.check("ni Protokimica la de la otra", not es_valida(db, entorno.tenant_id, "Bodega Norte"))
    db.close()


def test_get_areas_devuelve_las_activas(entorno, v):
    entorno.como("logistica")
    r = entorno.get("/areas")
    v.check("cualquiera con sesión las ve", r.status_code == 200, r.status_code)
    v.check("son las de la empresa", set(r.json()) == set(AREAS_INICIALES), r.json()[:3])
    v.check("y el formulario público también",
            entorno.get("/public/areas").json() == r.json())


# ── Administrarlas ───────────────────────────────────────────

def _id_de(entorno, nombre):
    db = entorno.Session()
    area_id = db.query(Area.id).filter_by(tenant_id=entorno.tenant_id, nombre=nombre).scalar()
    db.close()
    return area_id


def test_solo_admin_las_cambia(entorno, v):
    entorno.como("tics")
    v.check("un líder no crea -> 403", entorno.post("/areas", json={"nombre": "Nueva"}).status_code == 403)
    entorno.como("admin")
    r = entorno.post("/areas", json={"nombre": "  Planta   Norte "})
    v.check("admin sí -> 201", r.status_code == 201, r.text[:150])
    v.check("con los espacios limpios", r.json()["nombre"] == "Planta Norte", r.json())
    v.check("y queda en su lugar alfabético, no al final",
            entorno.get("/areas").json().index("Planta Norte")
            < entorno.get("/areas").json().index("Producción"))
    v.check("repetida -> 409", entorno.post("/areas", json={"nombre": "Planta Norte"}).status_code == 409)


def test_desactivar_la_quita_de_la_lista_pero_no_de_los_datos(entorno, v):
    db = entorno.Session()
    tics = db.get(User, entorno.ids["tics"])
    v.check("el líder es de TICS", tics.area == "TICS")
    db.close()

    r = entorno.patch(f"/areas/{_id_de(entorno, 'TICS')}", json={"activa": False})
    v.check("se desactiva", r.status_code == 200 and r.json()["area"]["activa"] is False, r.text[:150])
    v.check("ya no se ofrece", "TICS" not in entorno.get("/areas").json())
    db = entorno.Session()
    v.check("ni se puede asignar", not es_valida(db, entorno.tenant_id, "TICS"))
    v.check("pero su gente la conserva", db.get(User, entorno.ids["tics"]).area == "TICS")
    db.close()


def test_renombrar_reescribe_todo_lo_que_la_lleva(entorno, v):
    """
    Lo que hace posible que otra empresa adapte las áreas: renombrar no puede
    dejar un proyecto, una tarea o una capacidad con el nombre viejo.
    """
    db = entorno.Session()
    p = Proyecto(tenant_id=entorno.tenant_id, nombre="P", area="Calidad", estado="en_ejecucion")
    db.add(p)
    db.commit()
    db.add_all([ProyectoArea(proyecto_id=p.id, area="Calidad"),
                Tarea(proyecto_id=p.id, titulo="T", area="Calidad")])
    db.commit()
    db.close()

    r = entorno.patch(f"/areas/{_id_de(entorno, 'Calidad')}", json={"nombre": "Aseguramiento de Calidad"})
    v.check("renombra -> 200", r.status_code == 200, r.text[:200])
    cambios = r.json()["cambios"]
    v.check("dice qué cambió", cambios.get("users.area") == 1 and cambios.get("mp_tareas.area") == 1, cambios)

    db = entorno.Session()
    v.check("el usuario", db.get(User, entorno.ids["calidad"]).area == "Aseguramiento de Calidad")
    v.check("el proyecto", db.query(Proyecto).first().area == "Aseguramiento de Calidad")
    v.check("su área participante", db.query(ProyectoArea).first().area == "Aseguramiento de Calidad")
    v.check("la tarea, que no tiene tenant_id propio", db.query(Tarea).first().area == "Aseguramiento de Calidad")
    calidad = db.get(User, entorno.ids["calidad"])
    v.check("y la capacidad sigue con su gente: valida el SGC",
            tiene(db, calidad, "mejora.validar_sgc"))
    v.check("el nombre viejo ya no es válido", not es_valida(db, entorno.tenant_id, "Calidad"))
    db.close()


def test_renombrar_no_toca_a_otra_empresa(entorno, v):
    db = entorno.Session()
    otra = Tenant(nombre="Otra", slug="otra")
    db.add(otra)
    db.commit()
    ajeno = User(tenant_id=otra.id, nombre="Ajeno", email="a@otra.com", password_hash="x",
                 rol="agente", area="Calidad", activo=True)
    proyecto_ajeno = Proyecto(tenant_id=otra.id, nombre="Ajeno", area="Calidad", estado="en_ejecucion")
    db.add_all([ajeno, proyecto_ajeno])
    db.commit()
    db.add(Tarea(proyecto_id=proyecto_ajeno.id, titulo="Ajena", area="Calidad"))
    db.commit()
    ajeno_id = ajeno.id
    db.close()

    entorno.patch(f"/areas/{_id_de(entorno, 'Calidad')}", json={"nombre": "SGC"})
    db = entorno.Session()
    v.check("el usuario de la otra empresa sigue en Calidad", db.get(User, ajeno_id).area == "Calidad")
    v.check("y su tarea también",
            db.query(Tarea).filter_by(titulo="Ajena").first().area == "Calidad")
    db.close()


def test_renombrar_a_un_nombre_que_existe_responde_409(entorno, v):
    r = entorno.patch(f"/areas/{_id_de(entorno, 'Calidad')}", json={"nombre": "TICS"})
    v.check("409", r.status_code == 409, r.status_code)
    v.check("y dice cómo juntarlas", "desactiva" in r.text, r.text[:200])


# ── Que renombrar no se olvide de ninguna columna ────────────

def test_toda_columna_que_guarda_un_area_esta_en_la_lista():
    """
    Una tabla nueva con una columna `area` quedaría con el nombre viejo
    después de renombrar, en silencio. Si esta prueba falla, agrégala a
    `COLUMNAS_CON_AREA` con su ruta a la empresa.
    """
    en_esquema = {
        (tabla.name, col.name)
        for tabla in Base.metadata.sorted_tables
        for col in tabla.columns
        if (col.name == "area" or col.name.startswith("area_"))
        and str(col.type).startswith("VARCHAR")
    }
    declaradas = {(t, c) for t, c, _ in COLUMNAS_CON_AREA}
    assert en_esquema == declaradas, {
        "faltan en COLUMNAS_CON_AREA": sorted(en_esquema - declaradas),
        "sobran": sorted(declaradas - en_esquema),
    }


def test_las_rutas_a_la_empresa_existen():
    for tabla, _col, ruta in COLUMNAS_CON_AREA:
        t = Base.metadata.tables[tabla]
        if ruta is None:
            assert "tenant_id" in t.c, f"{tabla} no tiene tenant_id: necesita ruta por su padre"
        else:
            fk, padre = ruta
            assert fk in t.c and "tenant_id" in Base.metadata.tables[padre].c, (tabla, ruta)


def test_el_orden_ignora_tildes_y_mayusculas():
    """«Área Técnica» va con las de la A, no después de «Ventas»."""
    lista = ["Ventas", "Área Técnica", "calidad", "Abastecimiento", "Éxito"]
    assert sorted(lista, key=clave_alfabetica) == [
        "Abastecimiento", "Área Técnica", "calidad", "Éxito", "Ventas",
    ]
