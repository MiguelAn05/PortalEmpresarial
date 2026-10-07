"""
Cada área tiene una PQRS máximo 3 días hábiles.

Regla de negocio de Protokimica, aparte del plazo legal. Lo que se prueba:
el reloj arranca al llegar a un área —también a Servicio al Cliente—, vuelve
a cero al cambiar de área aunque ya la hubiera tenido, pasa al área que firma
una autorización, se detiene al responderle al cliente, y cada tramo
terminado queda guardado para los informes. Ver `pqrs/tiempo_en_area.py`.
"""
from datetime import datetime, timedelta, timezone

from app.models.autorizacion import TipoAutorizacion
from app.models.pqrs import PQRSPasoArea, PQRSSolicitud
from app.models.user import User


def _pqrs(entorno, area="Servicio al Cliente", estado="en_proceso", desde=None, codigo="PK-T-0001"):
    db = entorno.Session()
    p = PQRSSolicitud(
        tenant_id=entorno.tenant_id, tipo="reclamo", cliente_nombre="Cliente",
        descripcion="algo", estado=estado, prioridad="media", origen_publico="publico",
        area_responsable=area, codigo_seguimiento=codigo,
        area_desde=desde or datetime.now(timezone.utc),
    )
    db.add(p)
    db.commit()
    pid = p.id
    db.close()
    return pid


def _leer(entorno, pid):
    db = entorno.Session()
    p = db.get(PQRSSolicitud, pid)
    datos = (p.area_responsable, p.area_desde, p.estado)
    pasos = [(x.area, x.excedio) for x in db.query(PQRSPasoArea).filter_by(pqrs_id=pid).order_by(PQRSPasoArea.id)]
    db.close()
    return datos, pasos




# ── Arranca, vuelve a cero, se detiene ───────────────────────

def test_radicar_arranca_el_reloj_de_quien_reparte(entorno, v):
    """Toda PQRS nace con Servicio al Cliente, y su reloj empieza ahí."""
    r = entorno.post("/pqrs", data={"tipo": "queja", "descripcion": "Atención lenta.",
                                    "cliente_nombre": "C"})
    v.check("radica", r.status_code == 201, r.text[:200])
    v.check("nace con Servicio al Cliente",
            r.json()["area_responsable"] == "Servicio al Cliente", r.json())
    v.check("y su reloj corre", r.json()["area_desde"] is not None, r.json())
    v.check("con 0 días", r.json()["dias_en_area"] == 0, r.json())
    v.check("y sin vencer", r.json()["area_vencida"] is False)


def test_cambiar_de_area_guarda_el_tramo_y_arranca_de_cero(entorno, v):
    pid = _pqrs(entorno, desde=datetime.now(timezone.utc) - timedelta(days=10))
    r = entorno.patch(f"/pqrs/{pid}/gestion", data={"area": "Calidad"})
    v.check("se reasigna", r.status_code == 200, r.text[:200])
    (area, desde, _), pasos = _leer(entorno, pid)
    v.check("ahora corre para Calidad", area == "Calidad")
    v.check("desde cero", datetime.now(timezone.utc) - desde.replace(tzinfo=desde.tzinfo or timezone.utc) < timedelta(minutes=1))
    v.check("el tramo de Servicio al Cliente quedó guardado y excedido",
            pasos == [("Servicio al Cliente", True)], pasos)


def test_volver_a_un_area_que_ya_la_tuvo_empieza_de_cero(entorno, v):
    pid = _pqrs(entorno, area="Calidad")
    entorno.patch(f"/pqrs/{pid}/gestion", data={"area": "Logística"})
    entorno.patch(f"/pqrs/{pid}/gestion", data={"area": "Calidad"})
    (area, _, _), pasos = _leer(entorno, pid)
    v.check("vuelve a Calidad", area == "Calidad")
    v.check("con dos tramos guardados", [a for a, _ in pasos] == ["Calidad", "Logística"], pasos)
    r = entorno.get(f"/pqrs/{pid}").json()
    v.check("y 0 días en el tramo nuevo", r["dias_en_area"] == 0, r)


def test_resolver_detiene_el_reloj(entorno, v):
    pid = _pqrs(entorno)
    entorno.patch(f"/pqrs/{pid}/gestion", data={"estado": "resuelto", "solucion": "Se cambió el producto."})
    (_, desde, estado), pasos = _leer(entorno, pid)
    v.check("resuelta", estado == "resuelto")
    v.check("ya no corre", desde is None)
    v.check("y su tramo quedó guardado", len(pasos) == 1, pasos)


def test_si_el_cliente_la_rechaza_el_area_empieza_de_cero(entorno, v):
    pid = _pqrs(entorno, codigo="PK-T-0009")
    entorno.patch(f"/pqrs/{pid}/gestion", data={"estado": "resuelto", "solucion": "Se cambió el producto."})
    r = entorno.post("/public/confirmar/PK-T-0009", json={"conforme": False, "comentario": "Sigue igual."})
    v.check("el cliente la rechaza", r.status_code == 200, r.text[:200])
    (_, desde, estado), _ = _leer(entorno, pid)
    v.check("se reabre", estado == "en_proceso")
    v.check("y el reloj vuelve a correr", desde is not None)


# ── Autorizaciones: el reloj es del área que firma ───────────

def test_una_autorizacion_le_pasa_el_reloj_al_area_que_firma(entorno, v):
    db = entorno.Session()
    tipo = TipoAutorizacion(tenant_id=entorno.tenant_id, nombre="Nota crédito",
                            descripcion="x", area_autorizadora="Contabilidad")
    db.add(tipo)
    db.commit()
    tipo_id = tipo.id
    db.close()
    pid = _pqrs(entorno, desde=datetime.now(timezone.utc) - timedelta(days=2))

    r = entorno.post(f"/autorizaciones/pqrs/{pid}/solicitar", data={"tipo_id": tipo_id})
    v.check("se pide", r.status_code == 201, r.text[:200])
    (area, desde, _), pasos = _leer(entorno, pid)
    v.check("corre para Contabilidad", area == "Contabilidad" and desde is not None)
    v.check("el tramo de quien pidió quedó guardado", [a for a, _ in pasos] == ["Servicio al Cliente"], pasos)

    r = entorno.post(f"/autorizaciones/pqrs/{pid}/{r.json()['id']}/responder", data={"decision": "aprobada"})
    v.check("se responde", r.status_code == 200, r.text[:200])
    (area, _, _), pasos = _leer(entorno, pid)
    v.check("vuelve a quien reparte", area == "Servicio al Cliente")
    v.check("con el tramo de Contabilidad guardado",
            [a for a, _ in pasos] == ["Servicio al Cliente", "Contabilidad"], pasos)


# ── Lo que avisa ─────────────────────────────────────────────

def test_pasarse_de_3_dias_habiles_la_marca_vencida(entorno, v):
    pid = _pqrs(entorno, area="Calidad", desde=datetime.now(timezone.utc) - timedelta(days=10))
    r = entorno.get(f"/pqrs/{pid}").json()
    v.check("vencida en el área", r["area_vencida"] is True, r)
    v.check("con más de 3 días hábiles", r["dias_en_area"] > 3, r)
    fila = next(p for p in entorno.get("/pqrs").json() if p["id"] == pid)
    v.check("y la lista también lo dice", fila["area_vencida"] is True, fila)


def test_el_aviso_va_agrupado_por_area_con_sus_correos(entorno, v):
    _pqrs(entorno, area="Calidad", desde=datetime.now(timezone.utc) - timedelta(days=10), codigo="PK-T-0001")
    _pqrs(entorno, area="Calidad", codigo="PK-T-0002")   # recién llegada: no avisa
    _pqrs(entorno, area="Mercadeo", desde=datetime.now(timezone.utc) - timedelta(days=10), codigo="PK-T-0003")

    r = entorno.get("/pqrs/vencidas-en-area")
    v.check("responde", r.status_code == 200, r.text[:200])
    datos = r.json()
    calidad = next((g for g in datos["areas"] if g["area"] == "Calidad"), None)
    v.check("Calidad con su caso vencido", calidad and calidad["total"] == 1 and calidad["vencidas"] == 1, datos)
    v.check("y el correo de su gente", calidad and calidad["destinatarios"] == ["calidad@p.com"], calidad)
    v.check("Mercadeo no tiene a nadie: va aparte",
            [g["area"] for g in datos["sin_destinatario"]] == ["Mercadeo"], datos["sin_destinatario"])
    v.check("para que lo mueva quien reparte", datos["correos_de_quien_reparte"] == [], datos["correos_de_quien_reparte"])


def test_quien_reparte_recibe_los_de_areas_sin_gente(entorno, v):
    db = entorno.Session()
    db.get(User, entorno.ids["logistica"]).area = "Servicio al Cliente"
    db.commit()
    db.close()
    _pqrs(entorno, area="Mercadeo", desde=datetime.now(timezone.utc) - timedelta(days=10))
    datos = entorno.get("/pqrs/vencidas-en-area").json()
    v.check("el correo de Servicio al Cliente", "logistica@p.com" in datos["correos_de_quien_reparte"], datos)
