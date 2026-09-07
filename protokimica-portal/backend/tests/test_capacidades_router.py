"""
Endpoints de administración de capacidades, contra la API real.

Fase 2: la pantalla que le permite a un admin resolver el caso que motivó
todo esto — que Aseguramiento también tramite notas crédito sin volverse
Contabilidad — sin tocar código.
"""
from app.models.user import User

AREA_CONTABILIDAD = "Contabilidad"


def _con_area(portal, clave, area):
    db = portal.Session()
    u = db.get(User, portal.ids[clave])
    u.area = area
    db.commit()
    db.close()


# ── Quién puede administrar esto ──────────────────────────────────────────

def test_solo_admin_ve_el_catalogo(entorno, v):
    portal = entorno
    portal.como("tics")   # líder, no admin
    r = portal.get("/capacidades")
    v.check("un líder no entra", r.status_code == 403, r.status_code)

    portal.como("admin")
    r = portal.get("/capacidades")
    v.check("admin sí", r.status_code == 200, r.text[:200])


def test_solo_admin_otorga_y_revoca(entorno, v):
    portal = entorno
    portal.como("logistica")
    r = portal.post("/capacidades/notas_credito.autorizar/otorgar", json={"area": "Aseguramiento"})
    v.check("un agente no puede otorgar", r.status_code == 403, r.status_code)

    portal.como("admin")
    r = portal.post("/capacidades/notas_credito.autorizar/otorgar", json={"area": "Aseguramiento"})
    v.check("admin sí puede", r.status_code == 201, r.text[:200])

    otorgamiento_id = r.json()["id"]
    portal.como("logistica")
    r = portal.delete(f"/capacidades/otorgamientos/{otorgamiento_id}")
    v.check("un agente no puede revocar", r.status_code == 403, r.status_code)


# ── El catálogo trae quién tiene cada una ─────────────────────────────────

def test_el_catalogo_se_siembra_y_muestra_quien_tiene_cada_capacidad(entorno, v):
    portal = entorno
    portal.como("admin")
    catalogo = portal.get("/capacidades").json()

    v.check("trae las seis capacidades declaradas", len(catalogo) == 6, len(catalogo))
    nc = next(c for c in catalogo if c["clave"] == "notas_credito.autorizar")
    v.check("con su descripción", bool(nc["descripcion"]), nc)
    v.check("y Contabilidad ya sembrada",
            any(o["area"] == "Contabilidad" for o in nc["otorgamientos"]), nc["otorgamientos"])


def test_pedirlo_dos_veces_no_duplica_la_semilla(entorno, v):
    portal = entorno
    portal.como("admin")
    portal.get("/capacidades")
    catalogo = portal.get("/capacidades").json()
    nc = next(c for c in catalogo if c["clave"] == "notas_credito.autorizar")
    v.check("Contabilidad aparece una sola vez",
            len([o for o in nc["otorgamientos"] if o["area"] == "Contabilidad"]) == 1,
            nc["otorgamientos"])


# ── El caso real: una segunda área tramita notas crédito ─────────────────

def test_otorgar_una_segunda_area_no_le_quita_nada_a_la_primera(entorno, v):
    """
    Exactamente el caso que motivó esto: Aseguramiento también tramita notas
    crédito, y Contabilidad no deja de poder por eso.
    """
    portal = entorno
    portal.como("admin")
    r = portal.post("/capacidades/notas_credito.autorizar/otorgar", json={"area": "Aseguramiento"})
    v.check("se otorga a la segunda área", r.status_code == 201, r.text[:200])

    catalogo = portal.get("/capacidades").json()
    nc = next(c for c in catalogo if c["clave"] == "notas_credito.autorizar")
    areas = {o["area"] for o in nc["otorgamientos"] if o["area"]}
    v.check("las dos áreas aparecen", areas == {"Contabilidad", "Aseguramiento"}, areas)


def test_otorgar_a_una_persona_puntual(entorno, v):
    portal = entorno
    portal.como("admin")
    r = portal.post("/capacidades/notas_credito.autorizar/otorgar",
                    json={"usuario_id": portal.ids["logistica"]})
    v.check("se otorga a la persona", r.status_code == 201, r.text[:200])
    v.check("y queda el nombre a la mano",
            r.json()["usuario_nombre"] == "Logi", r.json())
    v.check("con quién lo otorgó",
            r.json()["otorgante_nombre"] == "Admin", r.json())


def test_revocar_lo_saca_del_catalogo_pero_no_de_la_historia(entorno, v):
    portal = entorno
    portal.como("admin")
    r = portal.post("/capacidades/notas_credito.autorizar/otorgar", json={"area": "Aseguramiento"})
    otorgamiento_id = r.json()["id"]

    r = portal.delete(f"/capacidades/otorgamientos/{otorgamiento_id}")
    v.check("se revoca", r.status_code == 204, r.status_code)

    catalogo = portal.get("/capacidades").json()
    nc = next(c for c in catalogo if c["clave"] == "notas_credito.autorizar")
    areas = {o["area"] for o in nc["otorgamientos"] if o["area"]}
    v.check("Aseguramiento ya no aparece como vigente", "Aseguramiento" not in areas, areas)


# ── Validaciones ───────────────────────────────────────────────────────

def test_una_capacidad_que_no_existe_da_404(entorno, v):
    portal = entorno
    portal.como("admin")
    r = portal.post("/capacidades/algo.inventado/otorgar", json={"area": "Contabilidad"})
    v.check("no entra", r.status_code == 404, r.status_code)


def test_un_area_que_no_existe_no_se_puede_otorgar(entorno, v):
    portal = entorno
    portal.como("admin")
    r = portal.post("/capacidades/notas_credito.autorizar/otorgar",
                    json={"area": "Departamento Inventado"})
    v.check("no entra", r.status_code == 400, r.status_code)


def test_hay_que_mandar_exactamente_uno(entorno, v):
    portal = entorno
    portal.como("admin")
    r = portal.post("/capacidades/notas_credito.autorizar/otorgar", json={})
    v.check("ninguno de los dos no pasa", r.status_code == 422, r.status_code)

    r = portal.post("/capacidades/notas_credito.autorizar/otorgar",
                    json={"area": "Contabilidad", "usuario_id": portal.ids["logistica"]})
    v.check("los dos juntos tampoco", r.status_code == 422, r.status_code)
