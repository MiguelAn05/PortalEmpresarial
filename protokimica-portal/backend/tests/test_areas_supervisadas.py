"""
Un jefe ve las áreas que supervisa; su gente no ve la de él.

Dirección Técnica responde por IDI y por Salvak. El portal filtra por área
EXACTA, así que sin supervisión el director no vería nada de su gente. Y la
supervisión es de **una sola vía**: quien está en IDI sigue viendo solo IDI,
así que la gestión de la dirección no se le muestra.
"""
from app.models.indicadores import Indicador
from app.models.master_planner import Proyecto
from app.models.mejora import Oportunidad
from app.models.user import AreaSupervisada, User

DIRECCION = "Dirección Técnica"
IDI = "Investigación y Desarrollo (IDI)"
SALVAK = "Salvak"


def _usuario(entorno, clave, area, rol="lider", supervisa=()):
    db = entorno.Session()
    u = User(
        tenant_id=entorno.tenant_id, nombre=clave.title(), email=f"{clave}@p.com",
        password_hash="x", rol=rol, area=area, activo=True,
    )
    u.areas_supervisadas = [AreaSupervisada(area=a) for a in supervisa]
    db.add(u)
    db.commit()
    entorno.ids[clave] = u.id
    db.close()


def _escenario(entorno):
    """Un indicador, una OMP y un proyecto por área."""
    db = entorno.Session()
    ids = {}
    for clave, area in (("direccion", DIRECCION), ("idi", IDI), ("salvak", SALVAK)):
        ind = Indicador(tenant_id=entorno.tenant_id, nombre=f"Indicador {clave}",
                        area=area, tipo_captura="valor", unidad="cantidad")
        omp = Oportunidad(tenant_id=entorno.tenant_id, titulo=f"OMP {clave}",
                          codigo=f"OMP-{clave}", area=area, estado="abierta",
                          origen="auditoria")
        proyecto = Proyecto(tenant_id=entorno.tenant_id, nombre=f"Proyecto {clave}",
                            area=area, estado="en_ejecucion")
        db.add_all([ind, omp, proyecto])
        db.commit()
        ids[clave] = {"indicador": ind.id, "omp": omp.id, "proyecto": proyecto.id}
    db.close()
    return ids


def _nombres(respuesta, campo="nombre"):
    return {x[campo] for x in respuesta.json()}


# ── Indicadores ──────────────────────────────────────────────────────

def test_el_director_ve_los_indicadores_de_sus_areas(entorno, v):
    ids = _escenario(entorno)
    _usuario(entorno, "director", DIRECCION, supervisa=(IDI, SALVAK))
    entorno.como("director")

    listados = _nombres(entorno.get("/indicadores"))
    v.check("lista las tres",
            listados == {"Indicador direccion", "Indicador idi", "Indicador salvak"}, listados)
    for clave in ("direccion", "idi", "salvak"):
        v.check(f"abre la ficha de {clave}",
                entorno.get(f"/indicadores/{ids[clave]['indicador']}").status_code == 200)

    tablero = entorno.get("/indicadores/tablero").json()
    v.check("el tablero trae las tres",
            {f["area"] for f in tablero["indicadores"]} == {DIRECCION, IDI, SALVAK},
            tablero["indicadores"])
    v.check("y el filtro ofrece solo sus áreas",
            set(tablero["areas_disponibles"]) == {DIRECCION, IDI, SALVAK},
            tablero["areas_disponibles"])


def test_el_equipo_no_ve_hacia_arriba(entorno, v):
    ids = _escenario(entorno)
    _usuario(entorno, "quimico", IDI)
    entorno.como("quimico")

    listados = _nombres(entorno.get("/indicadores"))
    v.check("solo los suyos", listados == {"Indicador idi"}, listados)
    v.check("el de la dirección responde 404",
            entorno.get(f"/indicadores/{ids['direccion']['indicador']}").status_code == 404)
    v.check("y el de Salvak también",
            entorno.get(f"/indicadores/{ids['salvak']['indicador']}").status_code == 404)


def test_pedir_un_area_ajena_no_la_abre(entorno, v):
    _escenario(entorno)
    _usuario(entorno, "quimico", IDI)
    entorno.como("quimico")
    tablero = entorno.get("/indicadores/tablero", params={"area": DIRECCION}).json()
    v.check("se ignora y muestra lo suyo",
            {f["area"] for f in tablero["indicadores"]} == {IDI}, tablero["indicadores"])


def test_el_director_puede_mirar_una_sola_de_sus_areas(entorno, v):
    _escenario(entorno)
    _usuario(entorno, "director", DIRECCION, supervisa=(IDI, SALVAK))
    entorno.como("director")
    tablero = entorno.get("/indicadores/tablero", params={"area": IDI}).json()
    v.check("filtra a IDI",
            {f["area"] for f in tablero["indicadores"]} == {IDI}, tablero["indicadores"])
    v.check("sin perder sus áreas en el selector",
            set(tablero["areas_disponibles"]) == {DIRECCION, IDI, SALVAK},
            tablero["areas_disponibles"])


# ── Mejora ───────────────────────────────────────────────────────────

def test_las_omp_siguen_la_misma_regla(entorno, v):
    ids = _escenario(entorno)
    _usuario(entorno, "director", DIRECCION, supervisa=(IDI, SALVAK))
    entorno.como("director")
    titulos = _nombres(entorno.get("/mejora"), "titulo")
    v.check("el director ve las tres",
            titulos == {"OMP direccion", "OMP idi", "OMP salvak"}, titulos)
    v.check("y las abre", entorno.get(f"/mejora/{ids['salvak']['omp']}").status_code == 200)

    _usuario(entorno, "quimico", IDI)
    entorno.como("quimico")
    titulos = _nombres(entorno.get("/mejora"), "titulo")
    v.check("el equipo solo la suya", titulos == {"OMP idi"}, titulos)
    v.check("la de la dirección: 404",
            entorno.get(f"/mejora/{ids['direccion']['omp']}").status_code == 404)


# ── Master Planner ───────────────────────────────────────────────────

def test_los_proyectos_de_las_areas_supervisadas(entorno, v):
    ids = _escenario(entorno)
    _usuario(entorno, "director", DIRECCION, supervisa=(IDI, SALVAK))
    entorno.como("director")
    proyectos = _nombres(entorno.get("/master-planner/proyectos"))
    v.check("los ve en la lista", {"Proyecto idi", "Proyecto salvak"} <= proyectos, proyectos)
    v.check("y abre el de Salvak",
            entorno.get(f"/master-planner/proyectos/{ids['salvak']['proyecto']}").status_code == 200)

    _usuario(entorno, "quimico", IDI)
    entorno.como("quimico")
    proyectos = _nombres(entorno.get("/master-planner/proyectos"))
    v.check("el equipo no ve el de la dirección", "Proyecto direccion" not in proyectos, proyectos)
    v.check("y le responde 404",
            entorno.get(f"/master-planner/proyectos/{ids['direccion']['proyecto']}").status_code == 404)


# ── Administración ───────────────────────────────────────────────────

def _crear(entorno, **datos):
    cuerpo = {"nombre": "Directora", "email": "dir@protokimica.com",
              "password": "secreta", "rol": "lider", "area": DIRECCION}
    cuerpo.update(datos)
    return entorno.post("/auth/usuarios", json=cuerpo)


def test_admin_configura_a_quien_supervisa(entorno, v):
    entorno.como("admin")
    r = _crear(entorno, areas_supervisadas=[IDI, SALVAK])
    v.check("se crea", r.status_code == 201, r.text[:200])
    v.check("con sus áreas", r.json()["areas_supervisadas"] == [IDI, SALVAK], r.json())

    uid = r.json()["id"]
    r = entorno.patch(f"/auth/usuarios/{uid}", json={"areas_supervisadas": [IDI]})
    v.check("se puede quitar una", r.json()["areas_supervisadas"] == [IDI], r.json())

    r = entorno.patch(f"/auth/usuarios/{uid}", json={"rol": "lider"})
    v.check("y no se pierde al guardar otra cosa",
            r.json()["areas_supervisadas"] == [IDI], r.json())

    r = entorno.patch(f"/auth/usuarios/{uid}", json={"areas_supervisadas": []})
    v.check("mandar la lista vacía la quita toda",
            r.json()["areas_supervisadas"] == [], r.json())


def test_un_area_que_no_existe_se_rechaza(entorno, v):
    entorno.como("admin")
    r = _crear(entorno, areas_supervisadas=["Laboratorio"])
    v.check("400", r.status_code == 400, r.text[:200])
    v.check("dice qué hacer", "no es un área del portal" in r.json()["detail"], r.json())


def test_supervisar_la_propia_area_no_se_guarda(entorno, v):
    """Ya la ve por ser suya; guardarla la arrastraría al cambiar de área."""
    entorno.como("admin")
    r = _crear(entorno, areas_supervisadas=[DIRECCION, IDI])
    v.check("solo queda la ajena", r.json()["areas_supervisadas"] == [IDI], r.json())


def test_cambiar_de_area_limpia_la_supervision_redundante(entorno, v):
    entorno.como("admin")
    uid = _crear(entorno, areas_supervisadas=[IDI, SALVAK]).json()["id"]
    r = entorno.patch(f"/auth/usuarios/{uid}", json={"area": IDI})
    v.check("IDI sale de la lista: ahora es la suya",
            r.json()["areas_supervisadas"] == [SALVAK], r.json())
