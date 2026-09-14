"""
Cada punto de venta ve las PQRS de su sede, no las de toda la empresa.

A Guayabal no le sirve una lista con las de Belén, las de Venta institucional
y las que entraron por WhatsApp: tiene que buscar lo suyo entre todo lo
ajeno. La regla:

- Alguien de «Puntos de Venta» CON punto asignado ve solo las de ese punto.
- Alguien de «Puntos de Venta» SIN punto asignado (el coordinador) ve las de
  los seis puntos, más lo que se le pasó al área.
- Lo que te ASIGNAN lo ves siempre.
- Todos los demás siguen viendo todo, como hasta hoy.
- Fuera de tu alcance una PQRS responde 404, también por URL directa.
"""
from app.models.pqrs import PQRSSolicitud
from app.models.user import User


def _usuario(entorno, clave, area="Puntos de Venta", punto=None, rol="agente"):
    db = entorno.Session()
    u = User(
        tenant_id=entorno.tenant_id, nombre=clave.title(), email=f"{clave}@p.com",
        password_hash="x", rol=rol, area=area, punto_venta=punto, activo=True,
    )
    db.add(u)
    db.commit()
    entorno.ids[clave] = u.id
    db.close()


def _pqrs(entorno, canal, codigo, **extra):
    db = entorno.Session()
    p = PQRSSolicitud(
        tenant_id=entorno.tenant_id, tipo="queja", cliente_nombre="Cliente",
        descripcion="Algo pasó", estado="recibido", prioridad="alta",
        canal_atencion=canal, codigo_seguimiento=codigo, origen_publico="publico",
        **extra,
    )
    db.add(p)
    db.commit()
    pid = p.id
    db.close()
    return pid


def _escenario(entorno):
    """Una PQRS por sitio, con los prefijos que se pisan (PVC y PVCR)."""
    return {
        "centro": _pqrs(entorno, "Punto de venta Centro", "PVC0001"),
        "cristo_rey": _pqrs(entorno, "Punto de venta Cristo Rey", "PVCR0001"),
        "guayabal": _pqrs(entorno, "Punto de venta Guayabal", "PVG0001"),
        "institucional": _pqrs(entorno, "Venta institucional", "VI0001"),
        "whatsapp": _pqrs(entorno, "WhatsApp", "PK-2026-0001"),
    }


def _ids_visibles(entorno):
    r = entorno.get("/pqrs")
    assert r.status_code == 200, r.text
    return {p["id"] for p in r.json()}


def test_una_sede_ve_solo_las_suyas(entorno, v):
    ids = _escenario(entorno)
    _usuario(entorno, "centro", punto="PVC")
    entorno.como("centro")

    visibles = _ids_visibles(entorno)
    v.check("ve la de su punto", ids["centro"] in visibles, visibles)
    v.check("y ninguna otra", visibles == {ids["centro"]}, visibles)


def test_pvc_no_se_confunde_con_pvcr(entorno, v):
    """
    `PVCR0001` también empieza por «PVC». Si el filtro fuera un LIKE a secas,
    Centro vería las de Cristo Rey.
    """
    db = entorno.Session()
    # Sin canal, para que solo decida el prefijo del radicado.
    p = PQRSSolicitud(
        tenant_id=entorno.tenant_id, tipo="queja", cliente_nombre="C",
        descripcion="x", estado="recibido", prioridad="alta",
        codigo_seguimiento="PVCR0009", origen_publico="publico",
    )
    db.add(p)
    db.commit()
    pid = p.id
    db.close()

    _usuario(entorno, "centro", punto="PVC")
    entorno.como("centro")
    v.check("Centro no ve la de Cristo Rey", pid not in _ids_visibles(entorno))

    _usuario(entorno, "cristo", punto="PVCR")
    entorno.como("cristo")
    v.check("Cristo Rey sí la ve", pid in _ids_visibles(entorno))


def test_el_coordinador_ve_todos_los_puntos(entorno, v):
    ids = _escenario(entorno)
    pasada = _pqrs(entorno, "WhatsApp", "PK-2026-0002", area_responsable="Puntos de Venta")
    _usuario(entorno, "coordinador", punto=None, rol="lider")
    entorno.como("coordinador")

    visibles = _ids_visibles(entorno)
    v.check("ve los tres puntos",
            {ids["centro"], ids["cristo_rey"], ids["guayabal"]} <= visibles, visibles)
    v.check("no ve Venta institucional", ids["institucional"] not in visibles)
    v.check("no ve WhatsApp", ids["whatsapp"] not in visibles)
    v.check("sí ve lo que le pasaron al área", pasada in visibles)


def test_lo_asignado_se_ve_siempre(entorno, v):
    _usuario(entorno, "centro", punto="PVC")
    ajena = _pqrs(entorno, "WhatsApp", "PK-2026-0003", asignado_a=entorno.ids["centro"])
    entorno.como("centro")

    v.check("la ve en la lista", ajena in _ids_visibles(entorno))
    v.check("y la abre", entorno.get(f"/pqrs/{ajena}").status_code == 200)


def test_las_demas_areas_siguen_viendo_todo(entorno, v):
    ids = _escenario(entorno)
    for quien in ("logistica", "calidad", "gerencia", "admin"):
        entorno.como(quien)
        v.check(f"{quien} ve todas", set(ids.values()) <= _ids_visibles(entorno))


def test_admin_con_area_de_puntos_no_queda_acotado(entorno, v):
    ids = _escenario(entorno)
    _usuario(entorno, "jefe", punto="PVC", rol="admin")
    entorno.como("jefe")
    v.check("admin ve todo", set(ids.values()) <= _ids_visibles(entorno))


def test_por_url_directa_responde_404(entorno, v):
    """Esconderla de la lista no basta: el número se puede escribir a mano."""
    ids = _escenario(entorno)
    _usuario(entorno, "centro", punto="PVC")
    entorno.como("centro")
    ajena = ids["guayabal"]

    v.check("detalle 404", entorno.get(f"/pqrs/{ajena}").status_code == 404)
    v.check("gestión 404", entorno.patch(
        f"/pqrs/{ajena}/gestion", data={"comentario": "hola"}).status_code == 404)
    v.check("editar datos 404", entorno.patch(
        f"/pqrs/{ajena}/datos", json={"ciudad": "Bello"}).status_code == 404)
    v.check("quitar adjunto 404",
            entorno.delete(f"/pqrs/{ajena}/adjuntos/factura").status_code == 404)
    v.check("autorizaciones 404",
            entorno.get(f"/autorizaciones/pqrs/{ajena}").status_code == 404)
    v.check("la suya sí abre", entorno.get(f"/pqrs/{ids['centro']}").status_code == 200)


def test_visibilidad_lo_dice_para_la_pantalla(entorno, v):
    _usuario(entorno, "centro", punto="PVC")
    _usuario(entorno, "coordinador")

    entorno.como("centro")
    r = entorno.get("/pqrs/visibilidad").json()
    v.check("sede: restringida", r["restringida"] is True, r)
    v.check("a un solo punto", [p["prefijo"] for p in r["puntos"]] == ["PVC"], r)

    entorno.como("coordinador")
    r = entorno.get("/pqrs/visibilidad").json()
    v.check("coordinador: los seis puntos", len(r["puntos"]) == 6, r)
    v.check("sin Venta institucional",
            "VI" not in [p["prefijo"] for p in r["puntos"]], r)

    entorno.como("logistica")
    r = entorno.get("/pqrs/visibilidad").json()
    v.check("los demás: sin restricción", r["restringida"] is False, r)


# ── Administración de usuarios ───────────────────────────────────────

def _crear_usuario(entorno, **datos):
    cuerpo = {"nombre": "Sede", "email": "sede@protokimica.com", "password": "secreta",
              "rol": "agente"}
    cuerpo.update(datos)
    return entorno.post("/auth/usuarios", json=cuerpo)


def test_admin_asigna_el_punto_de_venta(entorno, v):
    entorno.como("admin")
    r = _crear_usuario(entorno, area="Puntos de Venta", punto_venta="pvg")
    v.check("se crea", r.status_code == 201, r.text[:200])
    v.check("guarda el prefijo en mayúscula", r.json()["punto_venta"] == "PVG", r.json())

    uid = r.json()["id"]
    r = entorno.patch(f"/auth/usuarios/{uid}", json={"punto_venta": None})
    v.check("quitarlo lo vuelve coordinador", r.json()["punto_venta"] is None, r.json())


def test_venta_institucional_no_es_un_punto(entorno, v):
    entorno.como("admin")
    r = _crear_usuario(entorno, area="Puntos de Venta", punto_venta="VI")
    v.check("se rechaza", r.status_code == 400, r.text[:200])
    v.check("y dice qué elegir", "punto de venta" in r.json()["detail"], r.json())


def test_fuera_del_area_el_punto_se_descarta(entorno, v):
    """Un punto olvidado volvería a acotarle las PQRS el día que regrese al área."""
    entorno.como("admin")
    r = _crear_usuario(entorno, area="Puntos de Venta", punto_venta="PVG")
    uid = r.json()["id"]

    r = entorno.patch(f"/auth/usuarios/{uid}", json={"area": "Logística"})
    v.check("al cambiar de área se le quita", r.json()["punto_venta"] is None, r.json())

    r = _crear_usuario(entorno, email="otra@protokimica.com", area="Calidad", punto_venta="PVG")
    v.check("y en otra área ni se guarda", r.json()["punto_venta"] is None, r.json())
