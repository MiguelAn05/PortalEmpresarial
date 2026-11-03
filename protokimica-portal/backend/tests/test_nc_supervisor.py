"""
En el mostrador, una nota crédito con producto pasa PRIMERO por el
supervisor de los puntos de venta (desde la 0.72).

    sin producto:  Comercial → el punto emite
    con producto:  Supervisor → Comercial → el punto emite

Lo que se protege:
  - nace en el supervisor solo si el motivo trae producto y es del mostrador;
  - el orden lo impone el servidor: Comercial no aprueba antes que él;
  - lo atiende quien tenga `notas_credito.supervisar_punto` (por persona), y
    ve todo el mostrador pero no las institucionales;
  - la cadena se fija al radicar: cambiarle la marca al motivo después no
    mueve a las que van en camino;
  - devuelta y reenviada, vuelve a empezar por el supervisor;
  - el aviso le llega a él, con Comercial en copia.
"""
from app.core import bodegas
from app.core.capacidades import otorgar_a_area, otorgar_a_usuario
from app.models.nota_credito import MotivoNotaCredito, SolicitudNotaCredito
from app.models.user import User
from app.modules.notas_credito import notificaciones

GUAYABAL = "Punto de venta Guayabal"
INSTITUCIONAL = "Venta institucional"


def _usuario(entorno, clave, area, punto=None, rol="agente"):
    db = entorno.Session()
    u = User(tenant_id=entorno.tenant_id, nombre=clave.title(), email=f"{clave}@p.com",
             password_hash="x", rol=rol, area=area, punto_venta=punto, activo=True)
    db.add(u)
    db.commit()
    entorno.ids[clave] = u.id
    db.close()


def _motivo(entorno, nombre, con_producto):
    db = entorno.Session()
    m = MotivoNotaCredito(tenant_id=entorno.tenant_id, nombre=nombre,
                          activo=True, requiere_bodega=con_producto)
    db.add(m)
    db.commit()
    mid = m.id
    db.close()
    return mid


def _montar(entorno):
    """Comercial por área, el supervisor por persona, el punto con su permiso."""
    _usuario(entorno, "comercial", "Comercial", rol="lider")
    _usuario(entorno, "super", "Puntos de Venta", rol="lider")
    _usuario(entorno, "guayabal1", "Puntos de Venta", punto="PVG")
    db = entorno.Session()
    admin = entorno.ids["admin"]
    otorgar_a_area(db, entorno.tenant_id, "notas_credito.aprobar_comercial", "Comercial", admin)
    otorgar_a_area(db, entorno.tenant_id, "notas_credito.registrar", "Puntos de Venta", admin)
    otorgar_a_usuario(db, entorno.tenant_id, "notas_credito.supervisar_punto", entorno.ids["super"], admin)
    db.commit()
    db.close()


def _radicar(entorno, motivo_id, punto=GUAYABAL, bodega=None):
    datos = {"punto_venta": punto, "factura_afectada": "POS#100",
             "observaciones": "El cliente devolvió el producto.", "motivo_id": motivo_id}
    if bodega:
        datos["bodega"] = bodega
    r = entorno.post("/notas-credito", data=datos)
    assert r.status_code == 201, r.text[:300]
    return r.json()["id"]


def _estado(entorno, sid):
    db = entorno.Session()
    estado = db.get(SolicitudNotaCredito, sid).estado
    db.close()
    return estado


def _responder(entorno, sid, decision="aprobar", comentario=None):
    cuerpo = {"decision": decision}
    if comentario:
        cuerpo["comentario"] = comentario
    return entorno.post(f"/notas-credito/{sid}/responder", json=cuerpo)


def test_con_producto_pasa_por_el_supervisor_antes_que_comercial(entorno, v):
    _montar(entorno)
    entorno.como("guayabal1")
    sid = _radicar(entorno, _motivo(entorno, "Devolución de mercancía", True))
    v.check("nace esperando al supervisor", _estado(entorno, sid) == "en_supervision", _estado(entorno, sid))

    entorno.como("comercial")
    r = _responder(entorno, sid)
    v.check("Comercial no se la salta", r.status_code == 403, r.text[:200])

    entorno.como("super")
    r = _responder(entorno, sid)
    v.check("el supervisor aprueba", r.status_code == 200, r.text[:200])
    v.check("y pasa a Comercial", _estado(entorno, sid) == "en_comercial", _estado(entorno, sid))

    entorno.como("comercial")
    r = _responder(entorno, sid)
    v.check("Comercial aprueba", r.status_code == 200, r.text[:200])
    v.check("y queda para que el punto la emita", _estado(entorno, sid) == "aprobada", _estado(entorno, sid))

    entorno.como("guayabal1")
    r = entorno.post(f"/notas-credito/{sid}/aplicar", json={"numero_nc": "NC-77"})
    v.check("el punto la emite", r.status_code == 200, r.text[:200])


def test_sin_producto_sigue_empezando_por_comercial(entorno, v):
    _montar(entorno)
    entorno.como("guayabal1")
    sid = _radicar(entorno, _motivo(entorno, "Error de precio", False))
    v.check("nace en Comercial", _estado(entorno, sid) == "en_comercial", _estado(entorno, sid))


def test_la_institucional_con_producto_no_pasa_por_el_supervisor(entorno, v):
    _montar(entorno)
    _usuario(entorno, "vendedor", "Ventas Institucionales")
    db = entorno.Session()
    bodegas.del_tenant(db, entorno.tenant_id)   # se siembran solas al pedirlas
    db.commit()
    db.close()
    entorno.como("vendedor")
    sid = _radicar(entorno, _motivo(entorno, "Devolución", True), punto=INSTITUCIONAL, bodega="Guayabal")
    v.check("sigue en Comercial, como siempre", _estado(entorno, sid) == "en_comercial", _estado(entorno, sid))

    entorno.como("super")
    v.check("y el supervisor no la ve -> 404", entorno.get(f"/notas-credito/{sid}").status_code == 404)


def test_el_supervisor_ve_el_mostrador_y_su_turno(entorno, v):
    _montar(entorno)
    entorno.como("guayabal1")
    con = _radicar(entorno, _motivo(entorno, "Devolución", True))
    sin = _radicar(entorno, _motivo(entorno, "Precio", False))

    entorno.como("super")
    ids = sorted(s["id"] for s in entorno.get("/notas-credito").json())
    v.check("ve las dos del mostrador", ids == sorted([con, sin]), ids)
    turno = [s["id"] for s in entorno.get("/notas-credito", params={"estado": "mi_turno"}).json()]
    v.check("y en «lo que me toca» solo la que trae producto", turno == [con], turno)
    filtro = [s["id"] for s in entorno.get("/notas-credito", params={"estado": "supervisor"}).json()]
    v.check("el filtro «supervisor» la encuentra", filtro == [con], filtro)


def test_la_cadena_se_fija_al_radicar(entorno, v):
    """Cambiarle la marca al motivo no hace saltar de cadena a la que va en camino."""
    _montar(entorno)
    motivo_id = _motivo(entorno, "Devolución", True)
    entorno.como("guayabal1")
    sid = _radicar(entorno, motivo_id)

    db = entorno.Session()
    db.get(MotivoNotaCredito, motivo_id).requiere_bodega = False
    db.commit()
    db.close()

    entorno.como("super")
    _responder(entorno, sid)
    v.check("después del supervisor sigue Comercial", _estado(entorno, sid) == "en_comercial", _estado(entorno, sid))


def test_devuelta_y_reenviada_vuelve_al_supervisor(entorno, v):
    _montar(entorno)
    entorno.como("guayabal1")
    sid = _radicar(entorno, _motivo(entorno, "Devolución", True))
    entorno.como("super")
    _responder(entorno, sid)
    entorno.como("comercial")
    r = _responder(entorno, sid, "devolver", "Falta la foto del producto.")
    v.check("Comercial la devuelve", r.status_code == 200, r.text[:200])

    entorno.como("guayabal1")
    r = entorno.post(f"/notas-credito/{sid}/reenviar", json={})
    v.check("se reenvía", r.status_code == 200, r.text[:200])
    v.check("y empieza otra vez por el supervisor",
            _estado(entorno, sid) == "en_supervision", _estado(entorno, sid))


def test_el_aviso_va_al_supervisor_con_comercial_en_copia(entorno, v):
    _montar(entorno)
    entorno.como("guayabal1")
    sid = _radicar(entorno, _motivo(entorno, "Devolución", True))

    db = entorno.Session()
    avisos = notificaciones.avisos_en_turno(db, entorno.tenant_id, db.get(SolicitudNotaCredito, sid))
    db.close()
    v.check("un aviso", len(avisos) == 1, avisos)
    _, payload = avisos[0]
    v.check("al supervisor", payload["destinatarios"] == ["super@p.com"], payload)
    v.check("con Comercial en copia", "comercial@p.com" in payload["en_copia"], payload)
    v.check("y dice qué hacer", "producto" in payload["que_hacer"], payload)
