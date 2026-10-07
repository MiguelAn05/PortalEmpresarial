"""
Con quién nace una PQRS, y cómo un área devuelve una autorización.

**El área no se pide al radicar.** Ni el cliente ni el vendedor tienen con
qué criterio escogerla: adivinaban, y el caso arrancaba en un área que no le
tocaba. Toda PQRS nace con quien reparte (`pqrs.cerrar`, Servicio al Cliente)
y lo que mande un formulario viejo en `area_responsable` se ignora. Al
cliente tampoco se le dice qué área tiene su caso.

**Devolver no es rechazar.** El área que firma dice «esto no me toca» o
«falta información»: la autorización queda `devuelta`, la PQRS vuelve a
Servicio al Cliente y el comentario es obligatorio.
"""
from app.models.autorizacion import AutorizacionPQRS, TipoAutorizacion
from app.models.pqrs import PQRSSeguimiento, PQRSSolicitud


# ── Con quién nace ───────────────────────────────────────────────────────

def test_la_interna_nace_con_quien_reparte_aunque_manden_otra_area(entorno, v):
    """Una pestaña abierta con la versión anterior todavía manda el área."""
    r = entorno.post("/pqrs", data={"tipo": "reclamo", "descripcion": "Llegó roto",
                                    "cliente_nombre": "C", "area_responsable": "Calidad"})
    v.check("radica", r.status_code == 201, r.text[:200])
    v.check("nace con Servicio al Cliente, no con la que mandaron",
            r.json()["area_responsable"] == "Servicio al Cliente", r.json())
    v.check("y el radicado de Calidad no sale al radicar",
            r.json()["radicado_calidad"] is None, r.json())


def test_la_publica_nace_con_quien_reparte_y_no_le_dice_el_area(entorno, v):
    r = entorno.post("/public/pqrs", data={"tipo": "reclamo", "descripcion": "Llegó roto",
                                           "cliente_nombre": "Juan",
                                           "area_responsable": "Logística"})
    v.check("radica, aunque un formulario cacheado mande el área",
            r.status_code == 201, r.text[:200])
    v.check("la respuesta al cliente no trae el área",
            "area_responsable" not in r.json(), r.json())
    codigo = r.json()["codigo_seguimiento"]

    db = entorno.Session()
    p = db.query(PQRSSolicitud).filter_by(codigo_seguimiento=codigo).one()
    v.check("nace con Servicio al Cliente", p.area_responsable == "Servicio al Cliente",
            p.area_responsable)
    v.check("y su reloj corre", p.area_desde is not None)
    db.close()

    r = entorno.get(f"/public/pqrs/{codigo}")
    v.check("la consulta responde", r.status_code == 200, r.text[:200])
    v.check("y tampoco dice qué área la tiene", "area_responsable" not in r.json(), r.json())


# ── Devolver una autorización ────────────────────────────────────────────

def _pedida(entorno, area_autorizadora="Logística"):
    db = entorno.Session()
    tipo = TipoAutorizacion(tenant_id=entorno.tenant_id, nombre="Cambio de producto",
                            descripcion="x", area_autorizadora=area_autorizadora)
    p = PQRSSolicitud(tenant_id=entorno.tenant_id, tipo="reclamo", cliente_nombre="C",
                      descripcion="algo", estado="en_proceso", prioridad="media",
                      origen_publico="publico", area_responsable="Servicio al Cliente",
                      codigo_seguimiento="PK-D-0001")
    db.add_all([tipo, p])
    db.commit()
    pid, tipo_id = p.id, tipo.id
    db.close()

    entorno.como("admin")
    r = entorno.post(f"/autorizaciones/pqrs/{pid}/solicitar", data={"tipo_id": tipo_id})
    assert r.status_code == 201, r.text
    return pid, tipo_id, r.json()["id"]


def _area(entorno, pid):
    db = entorno.Session()
    area = db.get(PQRSSolicitud, pid).area_responsable
    db.close()
    return area


def test_devolver_exige_comentario(entorno, v):
    pid, _, aut_id = _pedida(entorno)
    v.check("mientras se firma, la tiene Logística", _area(entorno, pid) == "Logística")

    entorno.como("logistica")
    r = entorno.post(f"/autorizaciones/pqrs/{pid}/{aut_id}/responder",
                     data={"decision": "devuelta", "comentario_respuesta": "   "})
    v.check("sin comentario no se deja", r.status_code == 400, r.text[:200])
    v.check("y el mensaje dice qué escribir", "por qué" in r.json()["detail"], r.json())
    v.check("la PQRS sigue donde estaba", _area(entorno, pid) == "Logística")


def test_devolver_la_regresa_a_servicio_al_cliente(entorno, v):
    pid, tipo_id, aut_id = _pedida(entorno)

    entorno.como("logistica")
    r = entorno.post(f"/autorizaciones/pqrs/{pid}/{aut_id}/responder",
                     data={"decision": "devuelta",
                           "comentario_respuesta": "Esto es de Calidad, no de Logística."})
    v.check("se devuelve", r.status_code == 200, r.text[:200])
    v.check("queda devuelta, no rechazada", r.json()["estado"] == "devuelta", r.json())
    v.check("vuelve a quien reparte", _area(entorno, pid) == "Servicio al Cliente")

    db = entorno.Session()
    seg = db.query(PQRSSeguimiento).filter_by(
        pqrs_id=pid, tipo_evento="autorizacion_respondida").one()
    v.check("el historial dice que se devolvió y por qué",
            "devuelta" in seg.comentario and "Calidad" in seg.comentario, seg.comentario)
    db.close()

    # La PQRS ya no está bloqueada: se puede pedir otra vez, bien dirigida.
    entorno.como("admin")
    r = entorno.post(f"/autorizaciones/pqrs/{pid}/solicitar", data={"tipo_id": tipo_id})
    v.check("se puede volver a pedir", r.status_code == 201, r.text[:200])


def test_una_devuelta_no_se_vuelve_a_responder(entorno, v):
    pid, _, aut_id = _pedida(entorno)
    entorno.como("logistica")
    entorno.post(f"/autorizaciones/pqrs/{pid}/{aut_id}/responder",
                 data={"decision": "devuelta", "comentario_respuesta": "Falta la factura."})
    r = entorno.post(f"/autorizaciones/pqrs/{pid}/{aut_id}/responder",
                     data={"decision": "aprobada"})
    v.check("ya fue respondida", r.status_code == 400, r.text[:200])

    db = entorno.Session()
    v.check("y sigue devuelta", db.get(AutorizacionPQRS, aut_id).estado == "devuelta")
    db.close()


def test_una_decision_inventada_se_rechaza(entorno, v):
    pid, _, aut_id = _pedida(entorno)
    entorno.como("logistica")
    r = entorno.post(f"/autorizaciones/pqrs/{pid}/{aut_id}/responder",
                     data={"decision": "quizas"})
    v.check("400", r.status_code == 400, r.text[:200])
    v.check("y dice cuáles valen", "devuelta" in r.json()["detail"], r.json())
