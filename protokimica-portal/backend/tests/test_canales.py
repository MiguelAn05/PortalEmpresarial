"""
Los canales de cada empresa: el prefijo que no se cambia, el tipo que decide
la cadena de las notas crédito, y las sedes que acotan qué PQRS ve cada quien.

Hasta la fase 4c del plan de modularización eran una lista en el código con
los seis puntos de venta de Protokimica escritos a mano.
"""
from app.core import canales
from app.core.canales import CANALES_INICIALES, COLUMNAS_CON_CANAL
from app.core.database import Base
from app.main import app  # noqa: F401  (carga todos los modelos)
from app.models.area import Area
from app.models.canal import Canal
from app.models.nota_credito import SolicitudNotaCredito
from app.models.pqrs import PQRSSolicitud
from app.models.user import User


def _canal_id(entorno, nombre):
    db = entorno.Session()
    cid = db.query(Canal.id).filter_by(tenant_id=entorno.tenant_id, nombre=nombre).scalar()
    db.close()
    return cid


# ── Lo de arranque ───────────────────────────────────────────

def test_la_empresa_arranca_con_los_canales_y_prefijos_de_siempre(entorno, v):
    db = entorno.Session()
    tabla = {c.nombre: (c.prefijo, c.tipo) for c in canales.del_tenant(db, entorno.tenant_id)}
    db.close()
    for nombre, prefijo, tipo in CANALES_INICIALES:
        v.check(f"{nombre} con {prefijo} ({tipo})", tabla.get(nombre) == (prefijo, tipo), tabla.get(nombre))


def test_los_formularios_los_reciben_del_servidor(entorno, v):
    entorno.como("logistica")
    interno = entorno.get("/canales").json()
    publico = entorno.get("/public/canales").json()
    v.check("cualquiera con sesión los ve", len(interno) == len(CANALES_INICIALES), len(interno))
    v.check("el formulario del cliente también, con el prefijo", publico == interno)
    v.check("con su prefijo para el QR",
            any(c["prefijo"] == "PVG" and c["tipo"] == "sede" for c in interno))


# ── El prefijo no se cambia ──────────────────────────────────

def test_el_prefijo_de_un_canal_no_se_cambia(entorno, v):
    r = entorno.patch(f"/canales/{_canal_id(entorno, 'Punto de venta Guayabal')}", json={"prefijo": "GUA"})
    v.check("409", r.status_code == 409, r.status_code)
    v.check("y explica por qué: el QR impreso", "QR" in r.text, r.text[:200])


def test_a_un_canal_sin_prefijo_se_le_puede_poner_uno(entorno, v):
    r = entorno.patch(f"/canales/{_canal_id(entorno, 'WhatsApp')}", json={"prefijo": "wa"})
    v.check("200", r.status_code == 200, r.text[:200])
    v.check("queda en mayúsculas", r.json()["canal"]["prefijo"] == "WA", r.json())


def test_un_prefijo_invalido_o_repetido_se_rechaza(entorno, v):
    v.check("con guion -> 400",
            entorno.post("/canales", json={"nombre": "Sede Norte", "prefijo": "PV-N", "tipo": "sede"}).status_code == 400)
    v.check("repetido -> 409",
            entorno.post("/canales", json={"nombre": "Sede Norte", "prefijo": "PVG", "tipo": "sede"}).status_code == 409)
    v.check("una sede sin prefijo -> 400",
            entorno.post("/canales", json={"nombre": "Sede Norte", "tipo": "sede"}).status_code == 400)
    r = entorno.post("/canales", json={"nombre": "Sede Norte", "prefijo": "pvn", "tipo": "sede"})
    v.check("bien escrito -> 201", r.status_code == 201, r.text[:200])


def test_una_sede_nueva_trae_su_qr_y_su_consecutivo(entorno, v):
    entorno.post("/canales", json={"nombre": "Sede Norte", "prefijo": "PVN", "tipo": "sede"})
    v.check("tiene QR", entorno.get("/public/qr/PVN.svg").status_code == 200)
    r = entorno.post("/pqrs", data={"tipo": "queja", "descripcion": "Atención lenta en caja.",
                                    "cliente_nombre": "Cliente", "canal_atencion": "Sede Norte"})
    v.check("y sus PQRS numeran con su prefijo",
            r.status_code == 201 and r.json()["codigo_seguimiento"].startswith("PVN"), r.text[:200])


# ── Renombrar y desactivar ───────────────────────────────────

def test_renombrar_un_canal_reescribe_sus_pqrs_y_notas_credito(entorno, v):
    db = entorno.Session()
    db.add(PQRSSolicitud(tenant_id=entorno.tenant_id, tipo="queja", cliente_nombre="C",
                         descripcion="x", estado="recibido", canal_atencion="Punto de venta Belén"))
    db.add(SolicitudNotaCredito(tenant_id=entorno.tenant_id, punto_venta="Punto de venta Belén",
                                factura_afectada="FV-1", observaciones="Devolución.",
                                solicitado_por=entorno.ids["admin"],
                                estado="en_comercial"))
    db.commit()
    db.close()

    r = entorno.patch(f"/canales/{_canal_id(entorno, 'Punto de venta Belén')}", json={"nombre": "Sede Belén"})
    v.check("200", r.status_code == 200, r.text[:200])
    v.check("dice qué cambió", r.json()["cambios"] == {
        "pqrs_solicitudes.canal_atencion": 1, "nc_solicitudes.punto_venta": 1}, r.json()["cambios"])
    v.check("y el prefijo sigue igual", r.json()["canal"]["prefijo"] == "PVB")


def test_desactivar_una_sede_no_le_quita_sus_pqrs_a_quien_estaba_en_ella(entorno, v):
    db = entorno.Session()
    u = db.get(User, entorno.ids["logistica"])
    u.area, u.punto_venta = "Puntos de Venta", "PVG"
    db.add(PQRSSolicitud(tenant_id=entorno.tenant_id, tipo="queja", cliente_nombre="C",
                         descripcion="x", estado="recibido", canal_atencion="Punto de venta Guayabal"))
    db.commit()
    db.close()

    entorno.patch(f"/canales/{_canal_id(entorno, 'Punto de venta Guayabal')}", json={"activo": False})
    v.check("ya no se ofrece", "Punto de venta Guayabal" not in [c["nombre"] for c in entorno.get("/canales").json()])
    v.check("su QR deja de abrir", entorno.get("/public/qr/PVG.svg").status_code == 404)
    entorno.como("logistica")
    v.check("pero quien estaba en ella sigue viendo sus PQRS", len(entorno.get("/pqrs").json()) == 1)


# ── El tipo decide la cadena de las notas crédito ────────────

def test_la_rama_de_una_nota_credito_sale_del_tipo_del_canal(entorno, v):
    r = entorno.post("/notas-credito", data={"punto_venta": "Venta institucional",
                                             "factura_afectada": "FV-1", "observaciones": "Devolución."})
    v.check("institucional por su tipo", r.status_code == 201 and r.json()["estado"] == "en_comercial", r.text[:200])
    db = entorno.Session()
    v.check("y queda guardada en la solicitud", db.get(SolicitudNotaCredito, r.json()["id"]).institucional is True)
    db.close()

    # Otro canal que se vuelve institucional: la rama la decide el tipo, no el nombre.
    entorno.post("/canales", json={"nombre": "Grandes superficies", "prefijo": "GS", "tipo": "institucional"})
    r = entorno.post("/notas-credito", data={"punto_venta": "Grandes superficies",
                                             "factura_afectada": "FV-2", "observaciones": "Devolución."})
    db = entorno.Session()
    v.check("un canal nuevo de tipo institucional también",
            r.status_code == 201 and db.get(SolicitudNotaCredito, r.json()["id"]).institucional is True,
            r.text[:200])
    db.close()


def test_cambiar_el_tipo_no_mueve_las_solicitudes_en_camino(entorno, v):
    r = entorno.post("/notas-credito", data={"punto_venta": "Venta institucional",
                                             "factura_afectada": "FV-1", "observaciones": "Devolución."})
    sid = r.json()["id"]
    entorno.patch(f"/canales/{_canal_id(entorno, 'Venta institucional')}", json={"tipo": "general"})
    db = entorno.Session()
    v.check("sigue en la cadena institucional", db.get(SolicitudNotaCredito, sid).institucional is True)
    db.close()


# ── El área de las sedes ─────────────────────────────────────

def test_el_area_de_sedes_se_puede_renombrar_y_sigue_acotando(entorno, v):
    db = entorno.Session()
    u = db.get(User, entorno.ids["logistica"])
    u.area, u.punto_venta = "Puntos de Venta", "PVB"
    db.add_all([
        PQRSSolicitud(tenant_id=entorno.tenant_id, tipo="queja", cliente_nombre="C", descripcion="x",
                      estado="recibido", canal_atencion="Punto de venta Belén"),
        PQRSSolicitud(tenant_id=entorno.tenant_id, tipo="queja", cliente_nombre="C", descripcion="y",
                      estado="recibido", canal_atencion="WhatsApp"),
    ])
    area_id = db.query(Area.id).filter_by(tenant_id=entorno.tenant_id, nombre="Puntos de Venta").scalar()
    db.commit()
    db.close()

    r = entorno.patch(f"/areas/{area_id}", json={"nombre": "Sedes"})
    v.check("se renombra", r.status_code == 200, r.text[:200])
    v.check("y sigue siendo el área de sedes", r.json()["area"]["es_de_sedes"] is True)
    entorno.como("logistica")
    v.check("la sede sigue viendo solo lo suyo", len(entorno.get("/pqrs").json()) == 1)


def test_marcar_otra_area_de_sedes_desmarca_la_anterior(entorno, v):
    db = entorno.Session()
    tics = db.query(Area.id).filter_by(tenant_id=entorno.tenant_id, nombre="TICS").scalar()
    db.close()
    entorno.patch(f"/areas/{tics}", json={"es_de_sedes": True})
    v.check("ahora es TICS", entorno.get("/areas/de-sedes").json() == {"area": "TICS"})
    db = entorno.Session()
    v.check("y solo una", db.query(Area).filter_by(tenant_id=entorno.tenant_id, es_de_sedes=True).count() == 1)
    db.close()


# ── Que renombrar no se olvide de ninguna columna ────────────

def test_toda_columna_que_guarda_un_canal_esta_en_la_lista():
    en_esquema = {
        (t.name, c.name)
        for t in Base.metadata.sorted_tables for c in t.columns
        if "canal" in c.name and str(c.type).startswith("VARCHAR")
    }
    declaradas = set(COLUMNAS_CON_CANAL)
    faltan = en_esquema - declaradas
    assert not faltan, f"Agrega a COLUMNAS_CON_CANAL: {sorted(faltan)}"
