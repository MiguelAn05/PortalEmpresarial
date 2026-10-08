"""
El flujo de conceptos de una PQRS (`pqrs/flujo.py`): que el portal pida el
siguiente concepto solo, y que se detenga cuando alguien dice que no.

El escenario es el que salió del análisis de las PQRS reales: una de venta
institucional que salió del CD (concepto de Logística), por calidad del
producto (Área Técnica), y luego Analista Financiera → Contable → Cartera.
"""
from app.models.autorizacion import AutorizacionPQRS, TipoAutorizacion
from app.models.pqrs import PQRSBodegaDespacho, PQRSSeguimiento, PQRSSolicitud
from app.modules.pqrs import asociados

CONCEPTOS = [
    ("Concepto Coordinación Logistica", "Logística"),
    ("Concepto Producción", "Producción"),
    ("Concepto Área Técnica Protokimica", "Aseguramiento"),
    ("Concepto Analista Financiera", "Comercial"),
    ("Concepto Analista Contable", "Contabilidad"),
    ("Concepto Cartera", "Facturación"),
]


def _preparar(entorno, bodega="CD", causa="Calidad del Producto", canal="Venta institucional"):
    """Los conceptos de Protokimica, y una PQRS institucional sin flujo."""
    db = entorno.Session()
    tipos = {}
    for nombre, area in CONCEPTOS:
        t = TipoAutorizacion(tenant_id=entorno.tenant_id, nombre=nombre, area_autorizadora=area)
        db.add(t)
        db.flush()
        tipos[nombre] = t.id
    p = PQRSSolicitud(tenant_id=entorno.tenant_id, tipo="reclamo", cliente_nombre="C", descripcion="x",
                      estado="en_proceso", prioridad="alta", origen_publico="interno",
                      canal_atencion=canal, area_responsable="Servicio al Cliente", codigo_seguimiento="VI0099")
    db.add(p)
    db.commit()
    pid = p.id
    db.close()

    entorno.como("admin")
    # La primera vez que se pide algo del flujo se siembran las plantillas.
    r = entorno.get(f"/pqrs/{pid}/flujo")
    assert r.status_code == 200, r.text
    db = entorno.Session()
    p = db.get(PQRSSolicitud, pid)
    if causa:
        p.asociado_id = next(a.id for a in asociados.del_tenant(db, entorno.tenant_id) if a.nombre == causa)
    if bodega:
        p.bodega_despacho_id = db.query(PQRSBodegaDespacho).filter_by(tenant_id=entorno.tenant_id, nombre=bodega).one().id
    db.commit()
    db.close()
    return pid, tipos


def _area(entorno, pid):
    db = entorno.Session()
    area = db.get(PQRSSolicitud, pid).area_responsable
    db.close()
    return area


def _pendiente(entorno, pid):
    db = entorno.Session()
    a = db.query(AutorizacionPQRS).filter_by(pqrs_id=pid, estado="pendiente").one_or_none()
    out = (a.id, db.get(TipoAutorizacion, a.tipo_id).nombre) if a else (None, None)
    db.close()
    return out


def _responder(entorno, pid, decision, comentario=None):
    aut_id, _ = _pendiente(entorno, pid)
    data = {"decision": decision}
    if comentario:
        data["comentario_respuesta"] = comentario
    r = entorno.post(f"/autorizaciones/pqrs/{pid}/{aut_id}/responder", data=data)
    assert r.status_code == 200, r.text


def _iniciar(entorno, pid):
    propuesta = entorno.get(f"/pqrs/{pid}/flujo").json()["propuesta"]
    pasos = [{"tipo_autorizacion_id": p["tipo_autorizacion_id"], "origen": p["origen"]} for p in propuesta["pasos"]]
    return entorno.post(f"/pqrs/{pid}/flujo/iniciar", json={"pasos": pasos})


# ── La propuesta ─────────────────────────────────────────────────────────

def test_la_propuesta_resuelve_bodega_y_causa(entorno, v):
    pid, _ = _preparar(entorno)
    r = entorno.get(f"/pqrs/{pid}/flujo").json()
    v.check("sin flujo todavía", r["estado"] == "sin_flujo", r)
    v.check("la plantilla de venta institucional", r["propuesta"]["flujo"]["nombre"] == "Venta institucional", r)
    v.check("bodega → técnico → financiera → contable → cartera",
            [p["concepto"] for p in r["propuesta"]["pasos"]] == [
                "Concepto Coordinación Logistica", "Concepto Área Técnica Protokimica",
                "Concepto Analista Financiera", "Concepto Analista Contable", "Concepto Cartera",
            ], r["propuesta"]["pasos"])
    v.check("nada falta", r["propuesta"]["faltan"] == [], r["propuesta"]["faltan"])
    v.check("ofrece las tres bodegas", [b["nombre"] for b in r["bodegas"]] == ["CD", "La 65", "Guayabal"], r["bodegas"])


def test_guayabal_va_a_produccion(entorno, v):
    pid, _ = _preparar(entorno, bodega="Guayabal")
    pasos = entorno.get(f"/pqrs/{pid}/flujo").json()["propuesta"]["pasos"]
    v.check("el primer concepto es Producción", pasos[0]["concepto"] == "Concepto Producción", pasos)


def test_dice_lo_que_falta_para_resolver_la_propuesta(entorno, v):
    pid, _ = _preparar(entorno, bodega=None, causa=None)
    r = entorno.get(f"/pqrs/{pid}/flujo").json()["propuesta"]
    v.check("falta la bodega y la causa", {f["clase"] for f in r["faltan"]} == {"bodega", "tecnico"}, r["faltan"])
    v.check("y propone lo que sí sabe", [p["concepto"] for p in r["pasos"]] == [
        "Concepto Analista Financiera", "Concepto Analista Contable", "Concepto Cartera"], r["pasos"])


def test_un_concepto_no_se_repite(entorno, v):
    """Una mala entrega del CD pediría Logística por la bodega y por la causa."""
    pid, _ = _preparar(entorno, causa="Mala Entrega (CEDI)")
    pasos = entorno.get(f"/pqrs/{pid}/flujo").json()["propuesta"]["pasos"]
    v.check("Logística una sola vez",
            [p["concepto"] for p in pasos].count("Concepto Coordinación Logistica") == 1, pasos)


# ── El flujo andando ─────────────────────────────────────────────────────

def test_al_aprobar_pide_el_siguiente_solo(entorno, v):
    pid, _ = _preparar(entorno)
    r = _iniciar(entorno, pid)
    v.check("se inicia", r.status_code == 200, r.text[:200])
    v.check("pide el primero", _pendiente(entorno, pid)[1] == "Concepto Coordinación Logistica")
    v.check("y la PQRS pasa a Logística", _area(entorno, pid) == "Logística")

    _responder(entorno, pid, "aprobada")
    v.check("aprobado el primero, se pide el segundo SOLO",
            _pendiente(entorno, pid)[1] == "Concepto Área Técnica Protokimica", _pendiente(entorno, pid))
    v.check("y el caso va directo a Aseguramiento, sin pasar por Servicio al Cliente",
            _area(entorno, pid) == "Aseguramiento", _area(entorno, pid))

    for _ in range(3):
        _responder(entorno, pid, "aprobada")
    v.check("ya va en Cartera", _pendiente(entorno, pid)[1] == "Concepto Cartera")
    _responder(entorno, pid, "aprobada")

    r = entorno.get(f"/pqrs/{pid}/flujo").json()
    v.check("completo", r["estado"] == "completa", r["estado"])
    v.check("todos aprobados", all(p["estado"] == "aprobado" for p in r["pasos"]), r["pasos"])
    v.check("y vuelve a quien reparte para resolverla", _area(entorno, pid) == "Servicio al Cliente")

    db = entorno.Session()
    textos = [s.comentario for s in db.query(PQRSSeguimiento).filter_by(pqrs_id=pid).order_by(PQRSSeguimiento.id)]
    db.close()
    i_respuesta = next(i for i, t in enumerate(textos) if "El flujo sigue con: Concepto Área Técnica" in t)
    i_pedido = next(i for i, t in enumerate(textos) if "Se solicitó autorización: Concepto Área Técnica" in t)
    v.check("el historial se lee en orden: primero la respuesta, después el pedido", i_respuesta < i_pedido, textos)


def test_un_rechazo_detiene_y_se_puede_volver_a_pedir(entorno, v):
    pid, _ = _preparar(entorno)
    _iniciar(entorno, pid)
    _responder(entorno, pid, "aprobada")          # Logística
    _responder(entorno, pid, "rechazada")         # Área Técnica
    r = entorno.get(f"/pqrs/{pid}/flujo").json()
    v.check("se detiene", r["estado"] == "detenida", r["estado"])
    v.check("no pide nada más", _pendiente(entorno, pid) == (None, None))
    v.check("y vuelve a Servicio al Cliente", _area(entorno, pid) == "Servicio al Cliente")

    r = entorno.post(f"/pqrs/{pid}/flujo/reanudar", json={"repetir": True})
    v.check("se vuelve a pedir", r.status_code == 200, r.text[:200])
    v.check("el mismo concepto", _pendiente(entorno, pid)[1] == "Concepto Área Técnica Protokimica")
    v.check("con el rechazado como constancia",
            [p["estado"] for p in r.json()["pasos"]][:3] == ["aprobado", "rechazado", "en_curso"], r.json()["pasos"])


def test_tras_un_rechazo_se_puede_seguir_con_el_siguiente(entorno, v):
    pid, _ = _preparar(entorno)
    _iniciar(entorno, pid)
    _responder(entorno, pid, "devuelta", "Esto no es de Logística.")
    r = entorno.post(f"/pqrs/{pid}/flujo/reanudar", json={"repetir": False})
    v.check("sigue con el siguiente", r.status_code == 200 and _pendiente(entorno, pid)[1] == "Concepto Área Técnica Protokimica",
            r.text[:200])


def test_se_cambian_los_pasos_que_faltan(entorno, v):
    pid, tipos = _preparar(entorno)
    _iniciar(entorno, pid)
    pasos = entorno.get(f"/pqrs/{pid}/flujo").json()["pasos"]
    faltan = [p for p in pasos if p["estado"] == "pendiente"]
    # Quitar Cartera y agregar Producción al final.
    nuevos = [{"id": p["id"], "tipo_autorizacion_id": p["tipo_autorizacion_id"]} for p in faltan
              if p["concepto"] != "Concepto Cartera"] + [{"tipo_autorizacion_id": tipos["Concepto Producción"]}]
    r = entorno.put(f"/pqrs/{pid}/flujo/pasos", json={"pasos": nuevos})
    v.check("se guardan", r.status_code == 200, r.text[:200])
    conceptos = [p["concepto"] for p in r.json()["pasos"]]
    v.check("lo pedido no se toca y lo nuevo va al final",
            conceptos == ["Concepto Coordinación Logistica", "Concepto Área Técnica Protokimica",
                          "Concepto Analista Financiera", "Concepto Analista Contable", "Concepto Producción"], conceptos)


def test_solo_quien_reparte_mueve_el_flujo(entorno, v):
    pid, _ = _preparar(entorno)
    entorno.como("logistica")
    r = _iniciar(entorno, pid)
    v.check("otra área no -> 403", r.status_code == 403, r.status_code)
    v.check("y dice quién", "Servicio al Cliente" in r.json()["detail"], r.json())
    r = entorno.get(f"/pqrs/{pid}/flujo")
    v.check("pero sí lo ve", r.status_code == 200 and r.json()["puede_gestionar"] is False, r.text[:200])


def test_no_se_inicia_con_una_autorizacion_pendiente(entorno, v):
    pid, tipos = _preparar(entorno)
    entorno.post(f"/autorizaciones/pqrs/{pid}/solicitar", data={"tipo_id": tipos["Concepto Producción"]})
    r = _iniciar(entorno, pid)
    v.check("409 y dice qué esperar", r.status_code == 409 and "pendiente" in r.json()["detail"], r.text[:200])


def test_una_pedida_a_mano_con_flujo_entra_a_la_cadena(entorno, v):
    pid, tipos = _preparar(entorno)
    _iniciar(entorno, pid)
    _responder(entorno, pid, "rechazada")     # se detiene en Logística
    r = entorno.post(f"/autorizaciones/pqrs/{pid}/solicitar", data={"tipo_id": tipos["Concepto Producción"]})
    v.check("se pide a mano", r.status_code == 201, r.text[:200])
    pasos = entorno.get(f"/pqrs/{pid}/flujo").json()["pasos"]
    v.check("queda en la cadena, en curso, antes de lo que falta",
            [(p["concepto"], p["estado"]) for p in pasos][:3] == [
                ("Concepto Coordinación Logistica", "rechazado"),
                ("Concepto Producción", "en_curso"),
                ("Concepto Área Técnica Protokimica", "pendiente")], pasos)
    _responder(entorno, pid, "aprobada")
    v.check("y al aprobarla, el flujo sigue solo",
            _pendiente(entorno, pid)[1] == "Concepto Área Técnica Protokimica", _pendiente(entorno, pid))


def test_terminar_quita_lo_que_falta(entorno, v):
    pid, _ = _preparar(entorno)
    _iniciar(entorno, pid)
    _responder(entorno, pid, "rechazada")
    r = entorno.post(f"/pqrs/{pid}/flujo/terminar")
    v.check("se termina", r.status_code == 200 and r.json()["estado"] == "detenida", r.text[:200])
    v.check("sin pendientes", all(p["estado"] != "pendiente" for p in r.json()["pasos"]), r.json()["pasos"])


# ── Plantillas (Administración) ──────────────────────────────────────────

def test_las_plantillas_se_editan_en_administracion(entorno, v):
    _, tipos = _preparar(entorno)
    r = entorno.get("/pqrs/flujos")
    v.check("están las dos sembradas", [f["nombre"] for f in r.json()] == ["Venta institucional", "Punto de venta"], r.text[:200])
    punto = next(f for f in r.json() if f["nombre"] == "Punto de venta")
    r = entorno.put(f"/pqrs/flujos/{punto['id']}", json={
        "nombre": "Punto de venta", "aplica_a": "sede",
        "pasos": [{"clase": "bodega"}, {"clase": "concepto", "tipo_autorizacion_id": tipos["Concepto Analista Financiera"]},
                  {"clase": "concepto", "tipo_autorizacion_id": tipos["Concepto Cartera"]}],
    })
    v.check("se agrega un paso", r.status_code == 200 and len(r.json()["pasos"]) == 3, r.text[:200])
    r = entorno.post("/pqrs/flujos", json={"nombre": "Otro flujo", "pasos": [{"clase": "concepto"}]})
    v.check("un concepto sin elegir -> 400", r.status_code == 400, r.text[:200])
    entorno.como("calidad")
    v.check("solo admin", entorno.get("/pqrs/flujos").status_code == 403)
