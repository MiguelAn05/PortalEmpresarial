"""
Anular una PQRS: el caso que no debía existir (duplicado, radicado por
error, spam).

Lo que se defiende:
  - la anula quien reparte, con motivo obligatorio, sin causa ni producto;
  - no lleva encuesta ni correo, y no se puede editar ni mover después;
  - el cliente la ve CERRADA, sin el motivo;
  - no cuenta en el informe ni en los indicadores, salvo en «Estado actual»;
  - con un concepto esperando firma no se anula;
  - se puede reabrir.
"""
from datetime import datetime, timezone

from app.models.autorizacion import AutorizacionPQRS, TipoAutorizacion
from app.models.pqrs import PQRSSolicitud
from app.modules.pqrs import fuentes_indicador

SEP = datetime(2026, 9, 15, 17, 0, tzinfo=timezone.utc)


def _pqrs(portal, estado="en_proceso", codigo="PVG0040", fecha=SEP):
    db = portal.Session()
    p = PQRSSolicitud(
        tenant_id=portal.tenant_id, tipo="reclamo", cliente_nombre="Cliente",
        cliente_email="c@x.com", descripcion="Duplicada", estado=estado,
        prioridad="media", area_responsable="Servicio al Cliente",
        codigo_seguimiento=codigo, fecha_creacion=fecha,
    )
    db.add(p)
    db.commit()
    pid = p.id
    db.close()
    return pid


def _anular(portal, pid, motivo="Duplicada de PVG0039"):
    datos = {"estado": "anulado"}
    if motivo is not None:
        datos["comentario"] = motivo
    return portal.patch(f"/pqrs/{pid}/gestion", data=datos)


def test_se_anula_con_motivo_y_sin_causa(entorno, v):
    portal = entorno
    pid = _pqrs(portal)

    r = _anular(portal, pid, motivo=None)
    v.check("sin motivo no -> 400 y dice qué escribir",
            r.status_code == 400 and "por qué" in r.json()["detail"], r.text[:200])

    r = _anular(portal, pid)
    v.check("con motivo sí, aunque no tenga causa", r.status_code == 200, r.text[:300])
    detalle = portal.get(f"/pqrs/{pid}").json()
    v.check("queda anulada", detalle["estado"] == "anulado", detalle["estado"])
    v.check("el motivo queda en el historial", "Duplicada de PVG0039" in detalle["seguimientos"][-1]["comentario"])
    v.check("no es un cierre: sin fecha de cierre", detalle["fecha_cierre"] is None, detalle["fecha_cierre"])
    v.check("ni requisitos de cierre", not detalle.get("requisitos_cierre"), detalle.get("requisitos_cierre"))
    v.check("y ya no se editan sus datos", detalle["alcance"]["puede_editar_datos"] is False, detalle["alcance"])


def test_no_lleva_encuesta_ni_correo(entorno, v):
    portal = entorno
    pid = _pqrs(portal)
    _anular(portal, pid)
    db = portal.Session()
    v.check("sin encuesta", db.get(PQRSSolicitud, pid).encuesta is None)
    db.close()
    r = portal.get("/public/pqrs/PVG0040/encuesta")
    v.check("y la página de encuesta no la ofrece", r.status_code != 200 or not r.json().get("disponible"), r.text[:200])


def test_solo_quien_reparte(entorno, v):
    portal = entorno
    pid = _pqrs(portal)
    portal.como("logistica")
    v.check("otra área no -> 403", _anular(portal, pid).status_code == 403)


def test_el_cliente_la_ve_cerrada_sin_el_motivo(entorno, v):
    portal = entorno
    pid = _pqrs(portal)
    _anular(portal, pid, motivo="Spam del competidor")

    r = portal.get("/public/pqrs/PVG0040")
    v.check("responde", r.status_code == 200, r.text[:200])
    p = r.json()
    v.check("el estado que ve es «cerrado»", p["estado"] == "cerrado", p["estado"])
    v.check("con fecha de cierre", p["fecha_cierre"] is not None, p)
    v.check("el movimiento dice «cerrada»", p["historial"][-1]["movimiento"] == "Tu solicitud fue cerrada", p["historial"])
    v.check("y el motivo no viaja por ningún lado", "competidor" not in r.text)


def test_no_se_mueve_despues(entorno, v):
    portal = entorno
    pid = _pqrs(portal)
    _anular(portal, pid)
    r = portal.patch(f"/pqrs/{pid}/gestion", data={"area": "Calidad"})
    v.check("no se mueve de área", r.status_code == 400, r.text[:200])


def test_se_puede_reabrir(entorno, v):
    portal = entorno
    pid = _pqrs(portal)
    _anular(portal, pid)
    r = portal.patch(f"/pqrs/{pid}/gestion", data={"estado": "en_proceso", "comentario": "No era duplicada"})
    v.check("vuelve a en proceso", r.status_code == 200 and r.json()["estado"] == "en_proceso", r.text[:200])


def test_con_un_concepto_esperando_no_se_anula(entorno, v):
    portal = entorno
    pid = _pqrs(portal)
    db = portal.Session()
    tipo = TipoAutorizacion(tenant_id=portal.tenant_id, nombre="Concepto", area_autorizadora="Calidad")
    db.add(tipo)
    db.flush()
    db.add(AutorizacionPQRS(pqrs_id=pid, tipo_id=tipo.id, solicitado_por=portal.ids["admin"], estado="pendiente"))
    db.commit()
    db.close()

    r = _anular(portal, pid)
    v.check("400 y dice qué hacer", r.status_code == 400 and "devuelva" in r.json()["detail"], r.text[:200])


def test_no_cuenta_en_el_informe_salvo_en_estado_actual(entorno, v):
    portal = entorno
    _pqrs(portal, codigo="PVG0001")
    pid = _pqrs(portal, codigo="PVG0002")
    _anular(portal, pid)

    inf = portal.get("/pqrs/informe", params={"desde": "2026-09-01", "hasta": "2026-09-30"}).json()
    r = inf["resumen"]
    v.check("el total es de los casos reales", r["total"] == 1, r)
    v.check("las anuladas se dicen aparte", r["anuladas"] == 1, r)
    v.check("los tipos tampoco la cuentan", sum(f["n"] for f in inf["por_tipo"]) == 1, inf["por_tipo"])
    anulada = next((f for f in inf["por_estado"] if f["clave"] == "anulado"), None)
    v.check("«Estado actual» sí la suma, como «Anulada»",
            anulada and anulada["n"] == 1 and anulada["etiqueta"] == "Anulada", inf["por_estado"])
    v.check("y su porcentaje es sobre todo lo que entró", anulada and anulada["pct"] == 50.0, anulada)


def test_no_cuenta_en_los_indicadores(entorno, v):
    portal = entorno
    _pqrs(portal, codigo="PVG0001")
    pid = _pqrs(portal, codigo="PVG0002")
    _anular(portal, pid)
    db = portal.Session()
    resultado = fuentes_indicador.pqrs_recibidas(db, portal.tenant_id, 2026, 9)
    db.close()
    v.check("«PQRS recibidas» no cuenta la anulada", resultado.valor == 1, resultado)
