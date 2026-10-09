"""
Las bodegas: una sola lista para todo el portal, con sus responsables
(`core/bodegas.py`, `modules/bodegas/router.py`).

Lo que se prueba: se siembran solas, se crean y se renombran —reescribiendo
las notas crédito que guardan el nombre—, no repiten nombre, solo se borra la
que nadie usa, los responsables se eligen en la bodega, y una desactivada deja
de ofrecerse y de aceptarse.
"""
from sqlalchemy import String

from app.core import bodegas
from app.core.database import Base
from app.models.bodega import Bodega
from app.models.nota_credito import SolicitudNotaCredito
from app.models.pqrs import PQRSSolicitud


def _por_nombre(entorno):
    entorno.como("admin")
    return {b["nombre"]: b for b in entorno.get("/bodegas/todas").json()}


def _nota_credito(entorno, bodega):
    db = entorno.Session()
    nc = SolicitudNotaCredito(tenant_id=entorno.tenant_id, punto_venta="Venta institucional",
                              factura_afectada="FV-1", observaciones="x", estado="en_bodega",
                              institucional=True, bodega=bodega, solicitado_por=entorno.ids["admin"])
    db.add(nc)
    db.commit()
    nid = nc.id
    db.close()
    return nid


def test_arranca_con_las_tres(entorno, v):
    v.check("CD, La 65 y Guayabal", list(_por_nombre(entorno)) == ["CD", "La 65", "Guayabal"], list(_por_nombre(entorno)))
    entorno.como("logistica")
    r = entorno.get("/bodegas")
    v.check("cualquiera con sesión las lee", r.status_code == 200 and len(r.json()) == 3, r.text[:200])


def test_se_crea_con_responsables_y_no_repite_nombre(entorno, v):
    _por_nombre(entorno)
    r = entorno.post("/bodegas", json={"nombre": "  Sabaneta ", "responsables": [entorno.ids["logistica"]]})
    v.check("se crea, con el nombre limpio", r.status_code == 201 and r.json()["nombre"] == "Sabaneta", r.text[:200])
    v.check("con su responsable", [x["nombre"] for x in r.json()["responsables"]] == ["Logi"], r.json())
    r = entorno.post("/bodegas", json={"nombre": "Sabaneta"})
    v.check("repetida -> 409", r.status_code == 409, r.status_code)
    entorno.como("calidad")
    v.check("solo admin crea", entorno.post("/bodegas", json={"nombre": "Otra"}).status_code == 403)


def test_renombrar_reescribe_las_notas_credito(entorno, v):
    nid = _nota_credito(entorno, "La 65")
    la65 = _por_nombre(entorno)["La 65"]
    r = entorno.patch(f"/bodegas/{la65['id']}", json={"nombre": "Bodega La 65"})
    v.check("se renombra", r.status_code == 200 and r.json()["nombre"] == "Bodega La 65", r.text[:200])
    db = entorno.Session()
    v.check("y la nota crédito sigue apuntando a ella", db.get(SolicitudNotaCredito, nid).bodega == "Bodega La 65")
    db.close()
    r = entorno.patch(f"/bodegas/{la65['id']}", json={"nombre": "CD"})
    v.check("al nombre de otra -> 409", r.status_code == 409, r.status_code)


def test_los_responsables_se_cambian_en_la_bodega(entorno, v):
    cd = _por_nombre(entorno)["CD"]
    r = entorno.patch(f"/bodegas/{cd['id']}", json={"responsables": [entorno.ids["logistica"], entorno.ids["tics"]]})
    v.check("dos responsables", len(r.json()["responsables"]) == 2, r.json())
    db = entorno.Session()
    v.check("y el portal los reconoce", {u.nombre for u in bodegas.responsables(db, entorno.tenant_id, "CD")} == {"Logi", "Tico"})
    db.close()
    r = entorno.patch(f"/bodegas/{cd['id']}", json={"responsables": []})
    v.check("se quitan todos", r.json()["responsables"] == [], r.json())
    r = entorno.patch(f"/bodegas/{cd['id']}", json={"responsables": [99999]})
    v.check("alguien que no existe -> 400", r.status_code == 400, r.status_code)


def test_solo_se_borra_la_que_nadie_usa(entorno, v):
    _por_nombre(entorno)
    nueva = entorno.post("/bodegas", json={"nombre": "Por error"}).json()
    r = entorno.delete(f"/bodegas/{nueva['id']}")
    v.check("la que nadie usa se borra", r.status_code == 204, r.text[:200])
    v.check("y ya no está", "Por error" not in _por_nombre(entorno))

    _nota_credito(entorno, "Guayabal")
    guayabal = _por_nombre(entorno)["Guayabal"]
    v.check("la lista dice que se usa", guayabal["usos"] == 1, guayabal)
    r = entorno.delete(f"/bodegas/{guayabal['id']}")
    v.check("usada por una nota crédito -> 409", r.status_code == 409, r.status_code)
    v.check("y ofrece desactivarla", "Desactívala" in r.json()["detail"], r.json())


def test_tampoco_se_borra_la_que_usa_una_pqrs(entorno, v):
    cd = _por_nombre(entorno)["CD"]
    db = entorno.Session()
    db.add(PQRSSolicitud(tenant_id=entorno.tenant_id, tipo="reclamo", cliente_nombre="C", descripcion="x",
                         estado="en_proceso", prioridad="media", origen_publico="interno",
                         bodega_despacho_id=cd["id"]))
    db.commit()
    db.close()
    r = entorno.delete(f"/bodegas/{cd['id']}")
    v.check("usada por una PQRS -> 409", r.status_code == 409, r.text[:200])


def test_desactivada_no_se_ofrece_ni_se_acepta(entorno, v):
    cd = _por_nombre(entorno)["CD"]
    entorno.patch(f"/bodegas/{cd['id']}", json={"activo": False})
    entorno.como("logistica")
    v.check("no se ofrece", "CD" not in [b["nombre"] for b in entorno.get("/bodegas").json()])
    db = entorno.Session()
    v.check("ni se acepta en algo nuevo", bodegas.es_valida(db, entorno.tenant_id, "CD") is False)
    v.check("sin bodega sigue siendo válido", bodegas.es_valida(db, entorno.tenant_id, None) is True)
    db.close()


def test_toda_columna_que_guarda_la_bodega_por_nombre_esta_en_la_lista():
    """
    Renombrar reescribe `COLUMNAS_CON_BODEGA`. Una tabla nueva que guarde la
    bodega como texto y no esté ahí se quedaría con el nombre viejo en
    silencio. Las que guardan el id (llave foránea) no hacen falta.
    """
    en_esquema = {
        (t.name, c.name)
        for t in Base.metadata.sorted_tables for c in t.columns
        if "bodega" in c.name and isinstance(c.type, String) and t.name != Bodega.__tablename__
    }
    faltan = en_esquema - set(bodegas.COLUMNAS_CON_BODEGA)
    assert not faltan, f"Agrega a COLUMNAS_CON_BODEGA: {sorted(faltan)}"
