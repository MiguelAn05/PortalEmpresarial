"""
Volver una PQRS una OMP.

La casilla «puede volverse OMP» de un asociado existía desde que llegó el
catálogo, y nada la leía. Lo que se defiende:
  - la propuesta arranca con lo que ya se sabe del caso: el radicado, lo que
    contó el cliente y el área CAUSANTE;
  - dice si la causa lo sugiere, y por qué;
  - avisa de las OMP que ya nacieron de esa PQRS;
  - la OMP guarda de qué PQRS nació, y no acepta una que no existe o de
    otra empresa;
  - una PQRS por la MISMA causa se suma a la OMP abierta en vez de abrir
    otra, y eso queda en el historial;
  - solo quien abre Mejora (admin y líderes);
  - Mejora no importa nada de PQRS: lo lee por el contrato
    (`core/origenes_omp.py`).
"""
from app.models.pqrs import PQRSAsociado, PQRSSolicitud
from app.models.tenant import Tenant


def _pqrs(portal, *, asociado=None, area_causante="Logística", tenant_id=None, estado="en_proceso",
          codigo="PVG0042"):
    db = portal.Session()
    asociado_id = None
    if asociado:
        portal.get("/pqrs/asociados")   # siembra el catálogo
        asociado_id = db.query(PQRSAsociado.id).filter(PQRSAsociado.nombre == asociado).scalar()
    p = PQRSSolicitud(
        tenant_id=tenant_id or portal.tenant_id, tipo="queja", cliente_nombre="Cliente",
        cliente_email="c@x.com", descripcion="Me atendieron mal en el mostrador.",
        estado=estado, prioridad="media", area_responsable="Servicio al Cliente",
        codigo_seguimiento=codigo, asociado_id=asociado_id, area_causante=area_causante,
    )
    db.add(p)
    db.commit()
    pid = p.id
    db.close()
    return pid


def test_la_propuesta_trae_lo_que_ya_se_sabe(entorno, v):
    portal = entorno
    pid = _pqrs(portal, asociado="Servicio")

    r = portal.get(f"/mejora/desde/pqrs/{pid}")
    v.check("responde", r.status_code == 200, r.text[:300])
    p = r.json()
    v.check("nombra la PQRS por su radicado", p["referencia"] == "PQRS PVG0042", p)
    v.check("el título lleva la causa y el radicado", "Servicio" in p["titulo"] and "PVG0042" in p["titulo"], p)
    v.check("el detalle es lo que contó el cliente", p["descripcion"] == "Me atendieron mal en el mostrador.", p)
    v.check("el área es la CAUSANTE, no la responsable", p["area"] == "Logística", p)
    v.check("dice que la causa lo sugiere, y por qué", p["sugiere"] is True and "Servicio" in p["motivo"], p)
    v.check("todavía no tiene OMP", p["existentes"] == [], p)


def test_tambien_con_la_pqrs_cerrada(entorno, v):
    """
    Es el caso normal: al cliente ya se le respondió, y lo que queda es que
    no se repita. La causa además se puede marcar después de cerrar, así que
    la sugerencia puede aparecer recién entonces.
    """
    portal = entorno
    pid = _pqrs(portal, asociado="Servicio", estado="cerrado")
    p = portal.get(f"/mejora/desde/pqrs/{pid}")
    v.check("hay propuesta", p.status_code == 200 and p.json()["sugiere"] is True, p.text[:200])
    r = portal.post("/mejora", json={"titulo": "Atención en mostrador", "origen": "pqrs", "pqrs_id": pid})
    v.check("y se crea la OMP", r.status_code == 201, r.text[:200])


def test_una_causa_que_no_lo_sugiere_lo_dice(entorno, v):
    portal = entorno
    pid = _pqrs(portal, asociado="Transportadora")
    p = portal.get(f"/mejora/desde/pqrs/{pid}").json()
    v.check("sugiere = falso", p["sugiere"] is False and p["motivo"] is None, p)


def test_la_omp_guarda_de_que_pqrs_nacio_y_avisa_la_segunda_vez(entorno, v):
    portal = entorno
    pid = _pqrs(portal, asociado="Servicio")

    r = portal.post("/mejora", json={
        "titulo": "Atención en mostrador", "origen": "pqrs", "pqrs_id": pid, "area": "Logística",
    })
    v.check("se crea", r.status_code == 201, r.text[:300])
    v.check("con la PQRS de origen", r.json()["pqrs_id"] == pid, r.json())

    existentes = portal.get(f"/mejora/desde/pqrs/{pid}").json()["existentes"]
    v.check("la segunda vez avisa que ya tiene una",
            [o["id"] for o in existentes] == [r.json()["id"]], existentes)


def test_no_acepta_una_pqrs_que_no_existe(entorno, v):
    portal = entorno
    r = portal.post("/mejora", json={"titulo": "Algo que mejorar", "origen": "pqrs", "pqrs_id": 999})
    v.check("404 y dice qué hacer", r.status_code == 404 and "detalle" in r.json()["detail"], r.text[:200])
    v.check("la propuesta tampoco", portal.get("/mejora/desde/pqrs/999").status_code == 404)


def test_no_acepta_la_pqrs_de_otra_empresa(entorno, v):
    portal = entorno
    db = portal.Session()
    otra = Tenant(nombre="Otra", slug="otra")
    db.add(otra)
    db.commit()
    otra_id = otra.id
    db.close()
    ajena = _pqrs(portal, tenant_id=otra_id)

    r = portal.post("/mejora", json={"titulo": "Algo que mejorar", "origen": "pqrs", "pqrs_id": ajena})
    v.check("la llave foránea no basta: 404", r.status_code == 404, r.status_code)


def test_el_origen_tiene_que_ser_pqrs(entorno, v):
    portal = entorno
    pid = _pqrs(portal)
    r = portal.post("/mejora", json={"titulo": "Algo que mejorar", "origen": "otro", "pqrs_id": pid})
    v.check("400", r.status_code == 400, r.text[:200])


def test_solo_quien_abre_mejora(entorno, v):
    portal = entorno
    pid = _pqrs(portal, asociado="Servicio")

    portal.como("logistica")   # agente: no abre Mejora
    v.check("un agente no", portal.get(f"/mejora/desde/pqrs/{pid}").status_code == 403)
    portal.como("gerencia")
    v.check("gerencia tampoco", portal.get(f"/mejora/desde/pqrs/{pid}").status_code == 403)
    portal.como("calidad")     # líder
    v.check("un líder sí", portal.get(f"/mejora/desde/pqrs/{pid}").status_code == 200)


def test_un_origen_que_no_existe(entorno, v):
    portal = entorno
    v.check("404", portal.get("/mejora/desde/auditoria/1").status_code == 404)


def test_mejora_no_importa_pqrs():
    """Lo lee por el contrato: el origen lo declara PQRS en su propio paquete."""
    from app.modules.mejora import origenes
    assert "pqrs" in origenes.ORIGENES
    assert origenes.ORIGENES["pqrs"][0] == "pqrs"


# ── Varias PQRS por la misma causa, una sola OMP ────────────────────

def _omp_desde(portal, pid):
    r = portal.post("/mejora", json={
        "titulo": "Galón del ácido nítrico", "origen": "pqrs", "pqrs_id": pid, "area": "Logística",
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_la_segunda_pqrs_por_la_misma_causa_encuentra_la_omp_abierta(entorno, v):
    portal = entorno
    primera = _pqrs(portal, asociado="Servicio", codigo="PVG0042")
    omp_id = _omp_desde(portal, primera)
    segunda = _pqrs(portal, asociado="Servicio", codigo="PVG0043")
    otra_causa = _pqrs(portal, asociado="Transportadora", codigo="PVG0044")

    p = portal.get(f"/mejora/desde/pqrs/{segunda}").json()
    v.check("la ofrece por la misma causa", [o["id"] for o in p["misma_causa"]] == [omp_id], p)
    v.check("y nombra la causa", p["causa"] == "Servicio", p)
    v.check("pero no la cuenta como suya todavía", p["existentes"] == [], p)

    p = portal.get(f"/mejora/desde/pqrs/{otra_causa}").json()
    v.check("otra causa no la ofrece", p["misma_causa"] == [], p)


def test_vincular_la_suma_y_queda_en_el_historial(entorno, v):
    portal = entorno
    omp_id = _omp_desde(portal, _pqrs(portal, asociado="Servicio", codigo="PVG0042"))
    segunda = _pqrs(portal, asociado="Servicio", codigo="PVG0043")

    r = portal.post(f"/mejora/{omp_id}/vinculos", json={"origen": "pqrs", "origen_id": segunda})
    v.check("se vincula", r.status_code == 201, r.text[:300])
    vinc = r.json()["pqrs_vinculadas"]
    v.check("la OMP la lista con su radicado",
            [(x["pqrs_id"], x["referencia"]) for x in vinc] == [(segunda, "PQRS PVG0043")], vinc)
    v.check("con quién la vinculó", vinc[0]["vinculado_por_nombre"], vinc)

    historial = portal.get(f"/mejora/{omp_id}/historial").json()
    v.check("el historial lo dice",
            any(c["campo"] == "PQRS vinculada" and c["valor_nuevo"] == "PQRS PVG0043" for c in historial),
            historial)

    p = portal.get(f"/mejora/desde/pqrs/{segunda}").json()
    v.check("ahora la PQRS ya tiene esa OMP", [o["id"] for o in p["existentes"]] == [omp_id], p)
    v.check("y no se ofrece dos veces", p["misma_causa"] == [], p)

    r = portal.post(f"/mejora/{omp_id}/vinculos", json={"origen": "pqrs", "origen_id": segunda})
    v.check("dos veces la misma: 409", r.status_code == 409, r.text[:200])


def test_quitar_una_vinculada_deja_rastro(entorno, v):
    portal = entorno
    omp_id = _omp_desde(portal, _pqrs(portal, asociado="Servicio", codigo="PVG0042"))
    segunda = _pqrs(portal, asociado="Servicio", codigo="PVG0043")
    vinculo = portal.post(f"/mejora/{omp_id}/vinculos",
                          json={"origen": "pqrs", "origen_id": segunda}).json()["pqrs_vinculadas"][0]

    r = portal.delete(f"/mejora/{omp_id}/vinculos/{vinculo['id']}")
    v.check("se quita", r.status_code == 200 and r.json()["pqrs_vinculadas"] == [], r.text[:200])
    historial = portal.get(f"/mejora/{omp_id}/historial").json()
    v.check("el historial conserva cuál era",
            any(c["campo"] == "PQRS vinculada" and c["valor_anterior"] == "PQRS PVG0043"
                and c["valor_nuevo"] is None for c in historial), historial)


def test_no_se_vincula_a_una_omp_terminada_ni_la_de_origen(entorno, v):
    portal = entorno
    primera = _pqrs(portal, asociado="Servicio", codigo="PVG0042")
    omp_id = _omp_desde(portal, primera)

    r = portal.post(f"/mejora/{omp_id}/vinculos", json={"origen": "pqrs", "origen_id": primera})
    v.check("la de origen ya está: 409", r.status_code == 409, r.text[:200])

    portal.patch(f"/mejora/{omp_id}/estado", json={"estado": "descartada", "motivo": "Ya no aplica."})
    segunda = _pqrs(portal, asociado="Servicio", codigo="PVG0043")
    v.check("una descartada no se ofrece",
            portal.get(f"/mejora/desde/pqrs/{segunda}").json()["misma_causa"] == [])
    r = portal.post(f"/mejora/{omp_id}/vinculos", json={"origen": "pqrs", "origen_id": segunda})
    v.check("ni recibe PQRS: 409 y dice qué hacer", r.status_code == 409 and "nueva" in r.text, r.text[:200])


def test_vincular_pide_poder_gestionar_y_ver_la_pqrs(entorno, v):
    portal = entorno
    omp_id = _omp_desde(portal, _pqrs(portal, asociado="Servicio", codigo="PVG0042"))
    r = portal.post(f"/mejora/{omp_id}/vinculos", json={"origen": "pqrs", "origen_id": 999})
    v.check("una PQRS que no existe: 404", r.status_code == 404, r.text[:200])

    segunda = _pqrs(portal, asociado="Servicio", codigo="PVG0043")
    portal.como("gerencia")
    r = portal.post(f"/mejora/{omp_id}/vinculos", json={"origen": "pqrs", "origen_id": segunda})
    v.check("gerencia no", r.status_code == 403, r.status_code)
