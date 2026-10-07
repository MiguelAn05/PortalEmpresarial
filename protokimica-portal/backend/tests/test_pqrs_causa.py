"""
«Asociado a» y el área causante: la causa de cada PQRS.

Lo que se prueba (ver `pqrs/asociados.py`):

- El catálogo se siembra solo, con la lista del formato de Calidad pero SIN
  «En proceso» ni «Anulada», que no son causas.
- El área sugerida solo se siembra si la empresa la tiene.
- La causa la marca quien reparte (`pqrs.cerrar`), nadie más.
- Cerrar a mano exige las dos cosas; con la PQRS cerrada se puede marcar
  igual, para las que cerró el cliente sin pasar por quien reparte.
- Cada cambio queda en el historial con el valor anterior.
"""
from app.models.pqrs import PQRSAsociado, PQRSSeguimiento, PQRSSolicitud
from app.models.user import User
from app.modules.pqrs import asociados


def _pqrs(entorno, estado="en_proceso", codigo="PK-C-0001"):
    db = entorno.Session()
    p = PQRSSolicitud(tenant_id=entorno.tenant_id, tipo="reclamo", cliente_nombre="C",
                      descripcion="algo", estado=estado, prioridad="media",
                      origen_publico="publico", area_responsable="Servicio al Cliente",
                      codigo_seguimiento=codigo)
    db.add(p)
    db.commit()
    pid = p.id
    db.close()
    return pid


def _catalogo(entorno):
    entorno.como("admin")
    r = entorno.get("/pqrs/asociados")
    assert r.status_code == 200, r.text
    return {a["nombre"]: a for a in r.json()}


def _a_servicio_al_cliente(entorno, clave):
    db = entorno.Session()
    db.get(User, entorno.ids[clave]).area = "Servicio al Cliente"
    db.commit()
    db.close()


# ── El catálogo ──────────────────────────────────────────────────────────

def test_el_catalogo_se_siembra_solo_y_sin_lo_que_no_es_causa(entorno, v):
    catalogo = _catalogo(entorno)
    v.check("trae la lista del formato", len(catalogo) == len(asociados.ASOCIADOS_INICIALES),
            len(catalogo))
    v.check("con las dos malas entregas, que comparten sigla",
            catalogo["Mala Entrega (CEDI)"]["codigo"] == "ME"
            and catalogo["Mala Entrega (Pventa)"]["codigo"] == "ME")
    nombres = " ".join(catalogo).lower()
    v.check("sin «En proceso»", "en proceso" not in nombres, list(catalogo))
    v.check("sin «Anulada»", "anulada" not in nombres, list(catalogo))
    v.check("y agrupado", catalogo["Transportadora"]["grupo"] == "Entrega")

    # Pedirlo otra vez no lo duplica.
    v.check("idempotente", len(_catalogo(entorno)) == len(catalogo))


def test_el_area_sugerida_solo_si_la_empresa_la_tiene(entorno, v):
    catalogo = _catalogo(entorno)
    v.check("Mala entrega del CEDI propone Logística",
            catalogo["Mala Entrega (CEDI)"]["area_sugerida"] == "Logística")
    v.check("la del punto de venta, Puntos de Venta",
            catalogo["Mala Entrega (Pventa)"]["area_sugerida"] == "Puntos de Venta")
    v.check("y las dudosas quedan vacías para que Calidad las complete",
            catalogo["Calidad del Producto"]["area_sugerida"] is None)
    v.check("la variante del canal queda marcada",
            catalogo["Mala Entrega (Pventa)"]["aplica_a"] == "sede")
    v.check("y Servicio puede volverse OMP", catalogo["Servicio"]["sugiere_omp"] is True)


def test_solo_admin_administra_el_catalogo(entorno, v):
    entorno.como("calidad")
    r = entorno.post("/pqrs/asociados", json={"codigo": "X", "nombre": "Otra", "grupo": "Otro"})
    v.check("un líder no crea", r.status_code == 403, r.status_code)

    entorno.como("admin")
    r = entorno.post("/pqrs/asociados", json={"codigo": "pr", "nombre": "Precio errado",
                                              "grupo": "Facturación", "area_sugerida": "Facturación"})
    v.check("admin sí", r.status_code == 201, r.text[:200])
    v.check("la sigla en mayúsculas", r.json()["codigo"] == "PR")
    aid = r.json()["id"]

    r = entorno.post("/pqrs/asociados", json={"codigo": "PR", "nombre": "Precio errado", "grupo": "Otro"})
    v.check("no se repite el nombre", r.status_code == 409, r.status_code)

    r = entorno.patch(f"/pqrs/asociados/{aid}", json={"area_sugerida": "Inventada"})
    v.check("un área que no existe se rechaza", r.status_code == 400, r.text[:200])

    r = entorno.patch(f"/pqrs/asociados/{aid}", json={"activo": False})
    v.check("se desactiva", r.status_code == 200 and r.json()["activo"] is False, r.text[:200])
    v.check("y deja de ofrecerse", "Precio errado" not in _catalogo(entorno))


# ── Marcar la causa ──────────────────────────────────────────────────────

def test_solo_quien_reparte_marca_la_causa(entorno, v):
    pid = _pqrs(entorno)
    me = _catalogo(entorno)["Mala Entrega (CEDI)"]

    entorno.como("logistica")
    r = entorno.patch(f"/pqrs/{pid}/causa", json={"asociado_id": me["id"], "area_causante": "Logística"})
    v.check("otra área no -> 403", r.status_code == 403, r.status_code)
    v.check("y el mensaje dice a quién pedírselo",
            "Servicio al Cliente" in r.json()["detail"], r.json())

    _a_servicio_al_cliente(entorno, "calidad")
    entorno.como("calidad")
    r = entorno.patch(f"/pqrs/{pid}/causa", json={"asociado_id": me["id"], "area_causante": "Logística"})
    v.check("Servicio al Cliente sí", r.status_code == 200, r.text[:200])
    v.check("queda el asociado", r.json()["asociado_id"] == me["id"], r.json())
    v.check("y el área causante", r.json()["area_causante"] == "Logística")

    r = entorno.get(f"/pqrs/{pid}")
    v.check("el detalle dice que puede marcarla", r.json()["alcance"]["puede_marcar_causa"] is True)
    v.check("y trae el asociado con su sigla", r.json()["asociado"]["codigo"] == "ME", r.json()["asociado"])


def test_el_historial_guarda_el_valor_anterior(entorno, v):
    pid = _pqrs(entorno)
    catalogo = _catalogo(entorno)
    entorno.patch(f"/pqrs/{pid}/causa", json={"asociado_id": catalogo["Mala Entrega (CEDI)"]["id"],
                                              "area_causante": "Logística"})
    entorno.patch(f"/pqrs/{pid}/causa", json={"asociado_id": catalogo["Calidad del Producto"]["id"],
                                              "area_causante": "Producción"})
    # Guardar lo mismo no es un movimiento.
    entorno.patch(f"/pqrs/{pid}/causa", json={"asociado_id": catalogo["Calidad del Producto"]["id"],
                                              "area_causante": "Producción"})

    db = entorno.Session()
    eventos = [s.comentario for s in db.query(PQRSSeguimiento).filter_by(
        pqrs_id=pid, tipo_evento="causa").order_by(PQRSSeguimiento.id)]
    db.close()
    v.check("dos movimientos, no tres", len(eventos) == 2, eventos)
    v.check("el segundo dice de dónde venía",
            "(ME) Mala Entrega (CEDI) -> (CP) Calidad del Producto" in eventos[1]
            and "Logística -> Producción" in eventos[1], eventos)


def test_no_se_pone_un_asociado_desactivado_ni_un_area_inventada(entorno, v):
    pid = _pqrs(entorno)
    tr = _catalogo(entorno)["Transportadora"]
    db = entorno.Session()
    db.get(PQRSAsociado, tr["id"]).activo = False
    db.commit()
    db.close()

    r = entorno.patch(f"/pqrs/{pid}/causa", json={"asociado_id": tr["id"]})
    v.check("desactivado -> 400", r.status_code == 400, r.text[:200])
    r = entorno.patch(f"/pqrs/{pid}/causa", json={"asociado_id": 99999})
    v.check("inexistente -> 404", r.status_code == 404, r.status_code)
    r = entorno.patch(f"/pqrs/{pid}/causa", json={"area_causante": "Inventada"})
    v.check("área inventada -> 400", r.status_code == 400, r.text[:200])


# ── Cerrar ───────────────────────────────────────────────────────────────

def test_no_se_cierra_a_mano_sin_causa(entorno, v):
    pid = _pqrs(entorno)
    r = entorno.patch(f"/pqrs/{pid}/estado", data={"estado": "cerrado"})
    v.check("sin causa -> 400", r.status_code == 400, r.text[:200])
    detalle = r.json()["detail"]
    v.check("dice qué falta", "Asociado a" in detalle and "área causante" in detalle, detalle)

    me = _catalogo(entorno)["Mala Entrega (CEDI)"]
    entorno.patch(f"/pqrs/{pid}/causa", json={"asociado_id": me["id"]})
    r = entorno.patch(f"/pqrs/{pid}/estado", data={"estado": "cerrado"})
    v.check("con solo el asociado tampoco", r.status_code == 400, r.text[:200])
    v.check("y ya solo pide el área", "Asociado a" not in r.json()["detail"], r.json())

    entorno.patch(f"/pqrs/{pid}/causa", json={"asociado_id": me["id"], "area_causante": "Logística"})
    r = entorno.patch(f"/pqrs/{pid}/estado", data={"estado": "cerrado"})
    v.check("con las dos, cierra", r.status_code == 200, r.text[:200])


def test_una_cerrada_sin_causa_se_clasifica_despues(entorno, v):
    """La que cerró el cliente al confirmar no pasó por quien reparte."""
    pid = _pqrs(entorno, estado="cerrado")
    r = entorno.get("/pqrs")
    fila = next(p for p in r.json() if p["id"] == pid)
    v.check("la lista dice que no tiene causa", fila["asociado_id"] is None, fila)

    cp = _catalogo(entorno)["Calidad del Producto"]
    r = entorno.patch(f"/pqrs/{pid}/causa", json={"asociado_id": cp["id"], "area_causante": "Producción"})
    v.check("cerrada, igual se clasifica", r.status_code == 200, r.text[:200])

    r = entorno.get("/pqrs")
    fila = next(p for p in r.json() if p["id"] == pid)
    v.check("y la lista ya lo trae", fila["asociado_id"] == cp["id"], fila)
