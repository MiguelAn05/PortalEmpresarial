"""
Resolver una PQRS con solución, y lo que pasa después: el cliente confirma
con un clic o el sistema cierra solo si no contesta.

Lo que se defiende:
  - "resuelto" exige la solución, con mensaje que dice qué hacer;
  - la solución y sus adjuntos (pueden ser varios) quedan guardados, y
    fecha_resuelto arranca el plazo de 3 días hábiles;
  - reabrir borra `fecha_resuelto`, para que una PQRS reabierta no se cierre
    sola con el reloj de la primera vez;
  - el correo de "resuelto" y el de aviso al cliente NO necesitan sesión —
    son públicos, por código, igual que la encuesta;
  - confirmar cierra directo; rechazar reabre a en_proceso con el comentario
    del cliente y avisa al área;
  - `cerrar_vencidas()` solo toca las que de verdad vencieron, nunca las
    demás;
  - cerrar directo, sin pasar por "resuelto", sigue funcionando igual que
    antes — Servicio al Cliente conserva esa salida.
"""
from datetime import datetime, timedelta, timezone

from app.core.dias_habiles import limite_en_habiles
from app.models.pqrs import PQRSAdjuntoSolucion, PQRSSolicitud
from app.models.user import User
from app.modules.pqrs.cierre_automatico import (
    DIAS_ESPERA_CLIENTE, cerrar_vencidas, confirmar_solucion,
    plazo_confirmacion, rechazar_solucion,
)

AREA_SC = "Servicio al Cliente"


def _crear_pqrs(portal, area="Logística", estado="en_proceso", cliente_email="cliente@x.com"):
    db = portal.Session()
    p = PQRSSolicitud(
        tenant_id=portal.tenant_id,
        tipo="reclamo",
        cliente_nombre="Cliente de prueba",
        cliente_email=cliente_email,
        descripcion="Algo paso",
        estado=estado,
        prioridad="alta",
        area_responsable=area,
        origen_publico="publico",
    )
    db.add(p)
    db.commit()
    pid = p.id
    db.close()
    return pid


def _con_area(portal, clave, area):
    db = portal.Session()
    u = db.get(User, portal.ids[clave])
    u.area = area
    db.commit()
    db.close()


def _detalle(portal, pid):
    return portal.get(f"/pqrs/{pid}").json()


# ── Marcar "resuelto" exige la solución ───────────────────────────────────

def test_sin_solucion_no_pasa_a_resuelto(entorno, v):
    portal = entorno
    pid = _crear_pqrs(portal)

    portal.como("logistica")
    r = portal.patch(f"/pqrs/{pid}/gestion", data={"estado": "resuelto"})
    v.check("no entra", r.status_code == 400, r.status_code)
    v.check("el mensaje dice qué hacer",
            "solucion" in r.json().get("detail", "").lower(), r.json())
    v.check("el estado no cambió",
            _detalle(portal, pid)["estado"] == "en_proceso", _detalle(portal, pid))


def test_solo_espacios_tampoco_cuenta(entorno, v):
    portal = entorno
    pid = _crear_pqrs(portal)

    portal.como("logistica")
    r = portal.patch(f"/pqrs/{pid}/gestion", data={"estado": "resuelto", "solucion": "   "})
    v.check("no entra", r.status_code == 400, r.status_code)


def test_con_solucion_si_pasa_y_arranca_el_plazo(entorno, v):
    portal = entorno
    pid = _crear_pqrs(portal)

    portal.como("logistica")
    r = portal.patch(f"/pqrs/{pid}/gestion",
                     data={"estado": "resuelto", "solucion": "Se cambió el producto."})
    v.check("se registra", r.status_code == 200, r.text[:200])
    v.check("queda resuelto", r.json()["estado"] == "resuelto", r.json())
    v.check("con la solución guardada",
            r.json()["solucion"] == "Se cambió el producto.", r.json())
    v.check("y una fecha de resuelto", r.json()["fecha_resuelto"] is not None, r.json())

    detalle = _detalle(portal, pid)
    v.check("el detalle trae el plazo de confirmación",
            detalle["plazo_confirmacion"] is not None, detalle)


def test_varios_adjuntos_quedan_todos_asociados(entorno, v):
    portal = entorno
    pid = _crear_pqrs(portal)

    portal.como("logistica")
    # Varios archivos bajo la misma llave: hay que armar el multipart a mano,
    # `data=` solo alcanza para un valor por campo.
    import io
    archivos = [
        ("adjuntos_solucion", ("foto1.jpg", io.BytesIO(b"img1"), "image/jpeg")),
        ("adjuntos_solucion", ("foto2.png", io.BytesIO(b"img2"), "image/png")),
        ("adjuntos_solucion", ("factura.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")),
    ]
    r = portal.patch(
        f"/pqrs/{pid}/gestion",
        data={"estado": "resuelto", "solucion": "Ver soportes adjuntos."},
        files=archivos,
    )
    v.check("se registra con 3 adjuntos", r.status_code == 200, r.text[:200])

    db = portal.Session()
    guardados = db.query(PQRSAdjuntoSolucion).filter(PQRSAdjuntoSolucion.pqrs_id == pid).all()
    db.close()
    v.check("los 3 quedaron guardados", len(guardados) == 3, len(guardados))


# ── Reabrir borra el plazo ─────────────────────────────────────────────────

def test_reabrir_borra_fecha_resuelto(entorno, v):
    portal = entorno
    pid = _crear_pqrs(portal)

    portal.como("logistica")
    portal.patch(f"/pqrs/{pid}/gestion", data={"estado": "resuelto", "solucion": "x"})
    v.check("tiene fecha_resuelto", _detalle(portal, pid)["fecha_resuelto"] is not None)

    portal.patch(f"/pqrs/{pid}/gestion", data={"estado": "en_proceso"})
    detalle = _detalle(portal, pid)
    v.check("se borró al reabrir", detalle["fecha_resuelto"] is None, detalle)
    v.check("y el plazo de confirmación también desaparece",
            detalle["plazo_confirmacion"] is None, detalle)


# ── Cerrar directo, sin pasar por resuelto, sigue funcionando ────────────

def test_cerrar_directo_no_exige_solucion(entorno, v):
    """
    Servicio al Cliente conserva la salida de cerrar sin esperar al cliente
    —por ejemplo, si ya habló con él por teléfono—; no todo tiene que pasar
    por el correo de confirmación.
    """
    portal = entorno
    _con_area(portal, "calidad", AREA_SC)
    pid = _crear_pqrs(portal)

    portal.como("calidad")
    r = portal.patch(f"/pqrs/{pid}/gestion", data={"estado": "cerrado"})
    v.check("cierra sin solución", r.status_code == 200, r.text[:200])


# ── El correo público, por código, sin sesión ────────────────────────────

def test_confirmar_no_disponible_si_no_esta_resuelto(entorno, v):
    portal = entorno
    pid = _crear_pqrs(portal)
    db = portal.Session()
    p = db.get(PQRSSolicitud, pid)
    p.codigo_seguimiento = "TEST0001"
    db.commit()
    db.close()

    r = portal.get("/public/confirmar/TEST0001")
    v.check("responde 200", r.status_code == 200, r.text[:150])
    v.check("no disponible", r.json()["disponible"] is False, r.json())
    v.check("y no está decidida", r.json()["ya_decidido"] is False, r.json())


def test_confirmar_codigo_inexistente_da_404(entorno, v):
    portal = entorno
    r = portal.get("/public/confirmar/NOEXISTE")
    v.check("404", r.status_code == 404, r.status_code)


def test_confirmar_disponible_trae_la_solucion(entorno, v):
    portal = entorno
    pid = _crear_pqrs(portal)
    portal.como("logistica")
    portal.patch(f"/pqrs/{pid}/gestion",
                data={"estado": "resuelto", "solucion": "Cambiamos el lote."})

    db = portal.Session()
    p = db.get(PQRSSolicitud, pid)
    p.codigo_seguimiento = "TEST0002"
    db.commit()
    db.close()

    r = portal.get("/public/confirmar/TEST0002")
    v.check("disponible", r.json()["disponible"] is True, r.json())
    v.check("con la solución", r.json()["solucion"] == "Cambiamos el lote.", r.json())
    v.check("y el plazo", r.json()["plazo"] is not None, r.json())


def test_confirmar_que_si_cierra_la_pqrs(entorno, v):
    portal = entorno
    pid = _crear_pqrs(portal)
    portal.como("logistica")
    portal.patch(f"/pqrs/{pid}/gestion", data={"estado": "resuelto", "solucion": "x"})

    db = portal.Session()
    p = db.get(PQRSSolicitud, pid)
    p.codigo_seguimiento = "TEST0003"
    db.commit()
    db.close()

    r = portal.post("/public/confirmar/TEST0003", json={"conforme": True})
    v.check("se acepta", r.status_code == 200, r.text[:200])

    detalle = _detalle(portal, pid)
    v.check("queda cerrada", detalle["estado"] == "cerrado", detalle)
    v.check("con fecha de cierre", detalle["fecha_cierre"] is not None, detalle)
    v.check("y la encuesta nació pendiente de responder",
            detalle["encuesta"] is not None and detalle["encuesta"]["respondida_en"] is None,
            detalle["encuesta"])

    # No se puede volver a decidir
    r2 = portal.post("/public/confirmar/TEST0003", json={"conforme": True})
    v.check("ya no se puede confirmar otra vez", r2.status_code == 400, r2.status_code)


def test_rechazar_sin_comentario_no_pasa(entorno, v):
    portal = entorno
    pid = _crear_pqrs(portal)
    portal.como("logistica")
    portal.patch(f"/pqrs/{pid}/gestion", data={"estado": "resuelto", "solucion": "x"})

    db = portal.Session()
    p = db.get(PQRSSolicitud, pid)
    p.codigo_seguimiento = "TEST0004"
    db.commit()
    db.close()

    r = portal.post("/public/confirmar/TEST0004", json={"conforme": False})
    v.check("exige contar qué falta", r.status_code == 400, r.text[:150])


def test_rechazar_reabre_con_el_comentario_del_cliente(entorno, v):
    portal = entorno
    pid = _crear_pqrs(portal, area="Logística")
    portal.como("logistica")
    portal.patch(f"/pqrs/{pid}/gestion", data={"estado": "resuelto", "solucion": "x"})

    db = portal.Session()
    p = db.get(PQRSSolicitud, pid)
    p.codigo_seguimiento = "TEST0005"
    db.commit()
    db.close()

    r = portal.post("/public/confirmar/TEST0005",
                    json={"conforme": False, "comentario": "El olor sigue igual."})
    v.check("se acepta", r.status_code == 200, r.text[:200])

    detalle = _detalle(portal, pid)
    v.check("vuelve a en_proceso", detalle["estado"] == "en_proceso", detalle)
    v.check("sin plazo de confirmación", detalle["fecha_resuelto"] is None, detalle)
    v.check("el comentario del cliente quedó en el historial",
            any("El olor sigue igual" in (s["comentario"] or "") for s in detalle["seguimientos"]),
            detalle["seguimientos"])


# ── Los avisos que arma cada acción ──────────────────────────────────────

def test_confirmar_arma_el_aviso_de_cierre_con_motivo(entorno, v):
    portal = entorno
    pid = _crear_pqrs(portal)
    db = portal.Session()
    solicitud = db.get(PQRSSolicitud, pid)
    solicitud.estado = "resuelto"
    solicitud.solucion = "x"
    solicitud.fecha_resuelto = datetime.now(timezone.utc)
    db.commit()

    avisos = confirmar_solucion(db, solicitud)
    db.close()

    v.check("se arma un aviso", len(avisos) == 1, avisos)
    evento, payload = avisos[0]
    v.check("por el evento de cierre", evento == "pqrs-cerrada", evento)
    v.check("con el motivo correcto",
            payload["motivo_cierre"] == "cliente_confirmo", payload)


def test_rechazar_arma_el_aviso_al_area(entorno, v):
    portal = entorno
    pid = _crear_pqrs(portal, area="Logística")
    _con_area(portal, "logistica", "Logística")
    db = portal.Session()
    solicitud = db.get(PQRSSolicitud, pid)
    solicitud.estado = "resuelto"
    solicitud.solucion = "x"
    solicitud.fecha_resuelto = datetime.now(timezone.utc)
    db.commit()

    avisos = rechazar_solucion(db, solicitud, "No quedó bien")
    db.close()

    v.check("se arma un aviso", len(avisos) == 1, avisos)
    evento, payload = avisos[0]
    v.check("por el evento de área", evento == "pqrs-notificacion-area", evento)
    v.check("motivo cliente_rechazo", payload["motivo"] == "cliente_rechazo", payload)
    v.check("va a Logística",
            payload["destinatarios"] == ["logistica@p.com"], payload["destinatarios"])


# ── El cierre automático solo toca lo que de verdad venció ───────────────

def test_cerrar_vencidas_no_toca_lo_reciente(entorno, v):
    portal = entorno
    pid = _crear_pqrs(portal)
    db = portal.Session()
    solicitud = db.get(PQRSSolicitud, pid)
    solicitud.estado = "resuelto"
    solicitud.solucion = "x"
    solicitud.fecha_resuelto = datetime.now(timezone.utc)  # recién resuelta
    db.commit()
    db.close()

    db = portal.Session()
    cerradas = cerrar_vencidas(db, portal.tenant_id)
    db.close()

    v.check("no cierra ninguna", cerradas == [], cerradas)
    v.check("sigue resuelta", _detalle(portal, pid)["estado"] == "resuelto")


def test_cerrar_vencidas_cierra_lo_que_paso_el_plazo(entorno, v):
    portal = entorno
    pid = _crear_pqrs(portal)
    db = portal.Session()
    solicitud = db.get(PQRSSolicitud, pid)
    solicitud.estado = "resuelto"
    solicitud.solucion = "Se revisó el lote."
    # Bien atrás en el tiempo: sin importar festivos, ya pasaron de sobra
    # los DIAS_ESPERA_CLIENTE días hábiles.
    solicitud.fecha_resuelto = datetime.now(timezone.utc) - timedelta(days=30)
    db.commit()
    db.close()

    db = portal.Session()
    cerradas = cerrar_vencidas(db, portal.tenant_id)
    db.close()

    v.check("cierra una", len(cerradas) == 1, cerradas)
    solicitud_cerrada, avisos = cerradas[0]
    v.check("es la que vencio", solicitud_cerrada.id == pid)
    v.check("queda cerrada de verdad",
            _detalle(portal, pid)["estado"] == "cerrado", _detalle(portal, pid))
    v.check("el aviso trae el motivo automático",
            avisos[0][1]["motivo_cierre"] == "automatico", avisos)


def test_cerrar_vencidas_ignora_lo_que_no_esta_resuelto(entorno, v):
    """Una PQRS en cualquier otro estado no le interesa a este trabajo."""
    portal = entorno
    _crear_pqrs(portal, estado="en_proceso")
    _crear_pqrs(portal, estado="asignado")

    db = portal.Session()
    cerradas = cerrar_vencidas(db, portal.tenant_id)
    db.close()

    v.check("no cierra nada", cerradas == [], cerradas)


def test_endpoint_cerrar_vencidas_requiere_autenticacion(entorno, v):
    """Lo llama la automatización diaria con el usuario de servicio, logueado."""
    portal = entorno
    pid = _crear_pqrs(portal)
    db = portal.Session()
    solicitud = db.get(PQRSSolicitud, pid)
    solicitud.estado = "resuelto"
    solicitud.solucion = "x"
    solicitud.fecha_resuelto = datetime.now(timezone.utc) - timedelta(days=30)
    db.commit()
    db.close()

    portal.como("admin")
    r = portal.post("/pqrs/cerrar-vencidas")
    v.check("responde 200", r.status_code == 200, r.text[:150])
    v.check("dice cuál cerró", r.json()["cerradas"] == [pid], r.json())


# ── El plazo se calcula en días hábiles ──────────────────────────────────

def test_plazo_confirmacion_usa_dias_habiles(v):
    """
    Un viernes + 3 días hábiles cae el miércoles siguiente, no el lunes: se
    salta sábado y domingo. Es la misma cuenta que ya usa `fecha_limite_sla`.
    """
    viernes = datetime(2026, 9, 4, 15, 0, tzinfo=timezone.utc)  # viernes
    plazo = plazo_confirmacion(viernes)
    esperado = limite_en_habiles(viernes, DIAS_ESPERA_CLIENTE)

    v.check("coincide con el cálculo general de días hábiles",
            plazo == esperado, (plazo, esperado))
    v.check("cae después del fin de semana", plazo.date().weekday() < 5, plazo)
