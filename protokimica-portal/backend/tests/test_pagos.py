"""
Flujo de aprobacion y pago del presupuesto: planeado -> aprobado -> pagado.

Administracion aprueba y Tesoreria desembolsa — dos manos distintas.
"""
from app.models.user import User


def _area(portal, clave, area):
    db = portal.Session()
    u = db.get(User, portal.ids[clave])
    u.area = area
    db.commit()
    db.close()


def _montar(portal):
    """Un proyecto con un item de $4.000.000 y los roles de plata repartidos."""
    _area(portal, "calidad", "Administración")   # aprueba
    _area(portal, "logistica", "Tesorería")      # paga
    portal.como("admin")
    pid = portal.post("/master-planner/proyectos",
                      json={"nombre": "Portal Web", "area": "TICS"}).json()["id"]
    item = portal.post(f"/master-planner/proyectos/{pid}/presupuesto", json={
        "concepto": "Licencias", "valor_unitario": 1000000, "cantidad": 4,
    }).json()
    return pid, item["id"]


def test_un_item_nace_sin_aprobar(entorno, v):
    portal = entorno
    _, iid = _montar(portal)
    item = portal.get(f"/master-planner/proyectos/1/presupuesto").json()[0]

    v.check("el planeado sale de unitario x cantidad", item["valor_total"] == 4000000, item)
    v.check("nace sin aprobar", item["esta_aprobado"] is False, item)
    v.check("sin valor aprobado", item["valor_aprobado"] is None, item)
    v.check("estado 'por_aprobar'", item["estado_pago"] == "por_aprobar", item)
    v.check("nada pagado", item["valor_pagado"] == 0, item)
    # Sin aprobacion no hay obligacion: pendiente es 0, no el planeado.
    v.check("sin aprobar no hay nada pendiente de pago",
            item["pendiente_de_pago"] == 0, item)


def test_solo_administracion_aprueba(entorno, v):
    portal = entorno
    _, iid = _montar(portal)

    portal.como("tics")
    r = portal.patch(f"/master-planner/presupuesto/{iid}/aprobar",
                     json={"valor_aprobado": 4000000})
    v.check("TICS no puede aprobar -> 403", r.status_code == 403, r.text[:120])

    portal.como("logistica")   # Tesoreria tampoco aprueba
    r = portal.patch(f"/master-planner/presupuesto/{iid}/aprobar",
                     json={"valor_aprobado": 4000000})
    v.check("Tesoreria tampoco aprueba -> 403", r.status_code == 403, r.text[:120])

    portal.como("calidad")     # Administracion
    r = portal.patch(f"/master-planner/presupuesto/{iid}/aprobar",
                     json={"valor_aprobado": 3800000, "nota": "Se negocio descuento"})
    v.check("Administracion aprueba -> 200", r.status_code == 200, r.text[:180])
    item = r.json()
    v.check("queda aprobado", item["esta_aprobado"] is True, item)
    v.check("se puede aprobar menos de lo planeado", item["valor_aprobado"] == 3800000, item)
    v.check("registra quien aprobo", item["aprobado_por_nombre"] == "Cali", item)
    v.check("y con que nota", "descuento" in (item["nota_aprobacion"] or ""), item)
    v.check("estado pasa a 'aprobado'", item["estado_pago"] == "aprobado", item)
    v.check("y ahora si hay pendiente de pago", item["pendiente_de_pago"] == 3800000, item)


def test_solo_tesoreria_paga(entorno, v):
    portal = entorno
    _, iid = _montar(portal)
    portal.como("calidad")
    portal.patch(f"/master-planner/presupuesto/{iid}/aprobar", json={"valor_aprobado": 4000000})

    portal.como("tics")
    r = portal.post(f"/master-planner/presupuesto/{iid}/pagos", data={"valor": 1000000})
    v.check("TICS no puede pagar -> 403", r.status_code == 403, r.text[:120])

    portal.como("calidad")   # quien aprueba no desembolsa
    r = portal.post(f"/master-planner/presupuesto/{iid}/pagos", data={"valor": 1000000})
    v.check("Administracion no puede pagar -> 403", r.status_code == 403, r.text[:120])
    v.check("el mensaje dice a quien pedirle",
            "Tesorería" in r.json().get("detail", ""), r.json())

    portal.como("logistica")
    r = portal.post(f"/master-planner/presupuesto/{iid}/pagos",
                    data={"valor": 2000000, "concepto": "Anticipo 50%"})
    v.check("Tesoreria registra el pago -> 201", r.status_code == 201, r.text[:180])
    v.check("con su concepto", r.json()["concepto"] == "Anticipo 50%", r.json())
    v.check("y quien lo registro", r.json()["registrado_por_nombre"] == "Logi", r.json())


def test_pagos_parciales(entorno, v):
    portal = entorno
    _, iid = _montar(portal)
    portal.como("calidad")
    portal.patch(f"/master-planner/presupuesto/{iid}/aprobar", json={"valor_aprobado": 4000000})
    portal.como("logistica")

    portal.post(f"/master-planner/presupuesto/{iid}/pagos",
                data={"valor": 1000000, "concepto": "Anticipo"})
    item = portal.get("/master-planner/proyectos/1/presupuesto").json()[0]
    v.check("con un abono queda 'parcial'", item["estado_pago"] == "parcial", item)
    v.check("suma lo pagado", item["valor_pagado"] == 1000000, item)
    v.check("y calcula lo que falta", item["pendiente_de_pago"] == 3000000, item)
    v.check("con su porcentaje", item["pagado_pct"] == 25.0, item)

    portal.post(f"/master-planner/presupuesto/{iid}/pagos",
                data={"valor": 3000000, "concepto": "Saldo"})
    item = portal.get("/master-planner/proyectos/1/presupuesto").json()[0]
    v.check("al saldarse pasa a 'pagado'", item["estado_pago"] == "pagado", item)
    v.check("no queda nada pendiente", item["pendiente_de_pago"] == 0, item)
    v.check("100% pagado", item["pagado_pct"] == 100.0, item)
    v.check("guarda los dos abonos por separado", len(item["pagos"]) == 2, item["pagos"])
    v.check("en orden", [p["concepto"] for p in item["pagos"]] == ["Anticipo", "Saldo"],
            [p["concepto"] for p in item["pagos"]])


def test_no_se_paga_sin_aprobacion(entorno, v):
    portal = entorno
    _, iid = _montar(portal)
    portal.como("logistica")
    r = portal.post(f"/master-planner/presupuesto/{iid}/pagos", data={"valor": 1000000})
    v.check("pagar sin aprobar -> 400", r.status_code == 400, r.text[:150])
    v.check("y explica el orden",
            "aprobar" in r.json().get("detail", "").lower(), r.json())


def test_no_se_paga_de_mas(entorno, v):
    portal = entorno
    _, iid = _montar(portal)
    portal.como("calidad")
    portal.patch(f"/master-planner/presupuesto/{iid}/aprobar", json={"valor_aprobado": 1000000})
    portal.como("logistica")

    r = portal.post(f"/master-planner/presupuesto/{iid}/pagos", data={"valor": 1500000})
    v.check("un pago mayor a lo aprobado -> 400", r.status_code == 400, r.text[:180])

    portal.post(f"/master-planner/presupuesto/{iid}/pagos", data={"valor": 600000})
    r = portal.post(f"/master-planner/presupuesto/{iid}/pagos", data={"valor": 600000})
    v.check("ni sumando abonos se pasa del aprobado", r.status_code == 400, r.text[:180])

    r = portal.post(f"/master-planner/presupuesto/{iid}/pagos", data={"valor": 0})
    v.check("un pago de cero -> 400", r.status_code == 400, r.text[:120])
    r = portal.post(f"/master-planner/presupuesto/{iid}/pagos", data={"valor": -100})
    v.check("un pago negativo -> 400", r.status_code == 400, r.text[:120])


def test_no_se_aprueba_por_debajo_de_lo_pagado(entorno, v):
    portal = entorno
    _, iid = _montar(portal)
    portal.como("calidad")
    portal.patch(f"/master-planner/presupuesto/{iid}/aprobar", json={"valor_aprobado": 4000000})
    portal.como("logistica")
    portal.post(f"/master-planner/presupuesto/{iid}/pagos", data={"valor": 3000000})

    portal.como("calidad")
    r = portal.patch(f"/master-planner/presupuesto/{iid}/aprobar", json={"valor_aprobado": 1000000})
    v.check("bajar el aprobado por debajo de lo pagado -> 400", r.status_code == 400, r.text[:200])

    r = portal.patch(f"/master-planner/presupuesto/{iid}/aprobar", json={"valor_aprobado": 3500000})
    v.check("pero si se puede bajar hasta lo ya pagado", r.status_code == 200, r.text[:150])


def test_revocar_aprobacion(entorno, v):
    portal = entorno
    _, iid = _montar(portal)
    portal.como("calidad")
    portal.patch(f"/master-planner/presupuesto/{iid}/aprobar", json={"valor_aprobado": 4000000})

    r = portal.delete(f"/master-planner/presupuesto/{iid}/aprobar")
    v.check("revocar sin pagos -> 200", r.status_code == 200, r.text[:150])
    v.check("vuelve a 'por_aprobar'", r.json()["estado_pago"] == "por_aprobar", r.json())

    portal.patch(f"/master-planner/presupuesto/{iid}/aprobar", json={"valor_aprobado": 4000000})
    portal.como("logistica")
    portal.post(f"/master-planner/presupuesto/{iid}/pagos", data={"valor": 1000000})
    portal.como("calidad")
    r = portal.delete(f"/master-planner/presupuesto/{iid}/aprobar")
    v.check("revocar con pagos -> 409", r.status_code == 409, r.text[:180])


def test_anular_un_pago(entorno, v):
    portal = entorno
    _, iid = _montar(portal)
    portal.como("calidad")
    portal.patch(f"/master-planner/presupuesto/{iid}/aprobar", json={"valor_aprobado": 4000000})
    portal.como("logistica")
    pago = portal.post(f"/master-planner/presupuesto/{iid}/pagos", data={"valor": 1000000}).json()

    r = portal.delete(f"/master-planner/pagos/{pago['id']}")
    v.check("anular un pago -> 204", r.status_code == 204, r.text[:120])
    item = portal.get("/master-planner/proyectos/1/presupuesto").json()[0]
    v.check("el total pagado vuelve a cero", item["valor_pagado"] == 0, item)
    v.check("y el estado a 'aprobado'", item["estado_pago"] == "aprobado", item)


def test_no_se_borra_un_item_con_pagos(entorno, v):
    portal = entorno
    _, iid = _montar(portal)
    portal.como("calidad")
    portal.patch(f"/master-planner/presupuesto/{iid}/aprobar", json={"valor_aprobado": 4000000})
    portal.como("logistica")
    portal.post(f"/master-planner/presupuesto/{iid}/pagos", data={"valor": 1000000})

    portal.como("admin")
    r = portal.delete(f"/master-planner/presupuesto/{iid}")
    v.check("borrar un item con pagos -> 409", r.status_code == 409, r.text[:200])
    v.check("y dice cuanto se pago", "1" in r.json().get("detail", ""), r.json())


def test_totales_del_proyecto(entorno, v):
    portal = entorno
    pid, iid = _montar(portal)
    portal.como("admin")
    # Un segundo item que se queda sin aprobar
    portal.post(f"/master-planner/proyectos/{pid}/presupuesto", json={
        "concepto": "Equipos", "valor_unitario": 2000000, "cantidad": 1,
    })
    portal.como("calidad")
    portal.patch(f"/master-planner/presupuesto/{iid}/aprobar", json={"valor_aprobado": 4000000})
    portal.como("logistica")
    portal.post(f"/master-planner/presupuesto/{iid}/pagos", data={"valor": 2500000})

    p = portal.get(f"/master-planner/proyectos/{pid}").json()
    v.check("planeado suma los dos items", p["presupuesto_total"] == 6000000, p)
    v.check("aprobado solo el que se aprobo", p["presupuesto_aprobado"] == 4000000, p)
    v.check("pagado lo desembolsado", p["presupuesto_pagado"] == 2500000, p)
    v.check("pendiente = aprobado - pagado", p["presupuesto_pendiente"] == 1500000, p)
    # 2.5M de 4M aprobados = 62.5%, NO 2.5M de 6M planeados (41.7%)
    v.check("el % se mide sobre lo aprobado, no sobre lo planeado",
            p["pagado_pct"] == 62.5, p)
    v.check("cuenta los items por aprobar", p["items_por_aprobar"] == 1, p)


def test_totales_por_area_en_el_resumen(entorno, v):
    portal = entorno
    pid, iid = _montar(portal)
    portal.como("admin")
    pid2 = portal.post("/master-planner/proyectos",
                       json={"nombre": "Auditoria", "area": "Calidad"}).json()["id"]
    i2 = portal.post(f"/master-planner/proyectos/{pid2}/presupuesto", json={
        "concepto": "Consultoria", "valor_unitario": 2000000, "cantidad": 1,
    }).json()["id"]

    portal.como("calidad")
    portal.patch(f"/master-planner/presupuesto/{iid}/aprobar", json={"valor_aprobado": 4000000})
    portal.patch(f"/master-planner/presupuesto/{i2}/aprobar", json={"valor_aprobado": 2000000})
    portal.como("logistica")
    portal.post(f"/master-planner/presupuesto/{iid}/pagos", data={"valor": 4000000})
    portal.post(f"/master-planner/presupuesto/{i2}/pagos", data={"valor": 500000})

    portal.como("admin")
    res = portal.get("/master-planner/resumen").json()
    tot = res["presupuesto"]
    v.check("total planeado", tot["planeado"] == 6000000, tot)
    v.check("total aprobado", tot["aprobado"] == 6000000, tot)
    v.check("total pagado", tot["pagado"] == 4500000, tot)
    v.check("total pendiente de pago", tot["pendiente"] == 1500000, tot)
    v.check("% pagado global", tot["pagado_pct"] == 75.0, tot)

    areas = {a["area"]: a for a in res["presupuesto_por_area"]}
    v.check("TICS pagado completo", areas["TICS"]["pagado_pct"] == 100.0, areas["TICS"])
    v.check("Calidad al 25%", areas["Calidad"]["pagado_pct"] == 25.0, areas["Calidad"])
    v.check("TICS sin pendiente", areas["TICS"]["pendiente"] == 0, areas["TICS"])
    v.check("Calidad con pendiente", areas["Calidad"]["pendiente"] == 1500000, areas["Calidad"])


def test_todo_queda_en_el_historial(entorno, v):
    portal = entorno
    pid, iid = _montar(portal)
    portal.como("calidad")
    portal.patch(f"/master-planner/presupuesto/{iid}/aprobar", json={"valor_aprobado": 4000000})
    portal.como("logistica")
    pago = portal.post(f"/master-planner/presupuesto/{iid}/pagos", data={"valor": 1000000}).json()
    portal.delete(f"/master-planner/pagos/{pago['id']}")

    portal.como("admin")
    h = portal.get(f"/master-planner/proyectos/{pid}/historial").json()
    campos = [x["campo"] for x in h]
    for esperado in ("presupuesto_aprobado", "pago_registrado", "pago_anulado"):
        v.check(f"queda registrado '{esperado}'", esperado in campos, campos)

    aprobacion = next(x for x in h if x["campo"] == "presupuesto_aprobado")
    v.check("la aprobacion dice quien fue", aprobacion["usuario_nombre"] == "Cali", aprobacion)
    pagado = next(x for x in h if x["campo"] == "pago_registrado")
    v.check("el pago dice quien lo registro", pagado["usuario_nombre"] == "Logi", pagado)
