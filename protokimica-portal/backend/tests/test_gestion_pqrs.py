"""
Gestionar una PQRS en un solo movimiento, y el viaje del área cuando se pide
una autorización.

Lo que se defiende aquí:
  - área + estado + comentario se guardan juntos y dejan UN evento, con el
    texto de la persona escrito una sola vez;
  - ese evento se sigue llamando `cambio_estado`, que es de donde sale el
    historial que ve el cliente;
  - el área la reparte Servicio al Cliente, no cualquiera;
  - pedir una autorización mueve el caso al área que firma, y responderla lo
    devuelve a Servicio al Cliente;
  - el `alcance` que viaja con el detalle dice la verdad sobre lo que el
    servidor va a aceptar después.
"""
from app.models.autorizacion import TipoAutorizacion
from app.models.pqrs import PQRSSolicitud
from app.models.user import User

AREA_SC = "Servicio al Cliente"


def _crear_pqrs(portal, area="Logística", estado="asignado"):
    db = portal.Session()
    p = PQRSSolicitud(
        tenant_id=portal.tenant_id,
        tipo="reclamo",
        cliente_nombre="Cliente de prueba",
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


def _crear_tipo(portal, area_autorizadora="Calidad", nombre="Nota crédito"):
    db = portal.Session()
    tipo = TipoAutorizacion(
        tenant_id=portal.tenant_id, nombre=nombre,
        descripcion="Autoriza la nota", area_autorizadora=area_autorizadora,
    )
    db.add(tipo)
    db.commit()
    tid = tipo.id
    db.close()
    return tid


def _seguimientos(portal, pid):
    return portal.get(f"/pqrs/{pid}").json()["seguimientos"]


# ── Un movimiento, un evento ─────────────────────────────────────────────

def test_area_y_estado_en_un_solo_guardado(entorno, v):
    """
    El caso de todos los días: pasarle una PQRS a Calidad explicando por qué.

    Antes eran dos llamadas y dos eventos, y el motivo había que escribirlo en
    los dos formularios. Aquí va una vez y queda una vez.
    """
    portal = entorno
    _con_area(portal, "calidad", AREA_SC)
    pid = _crear_pqrs(portal, area="Logística", estado="asignado")

    portal.como("calidad")   # área Servicio al Cliente: reparte
    antes = len(_seguimientos(portal, pid))
    r = portal.patch(f"/pqrs/{pid}/gestion", data={
        "area": "Calidad",
        "estado": "en_proceso",
        "comentario": "El lote viene de la planta, lo revisa Calidad.",
    })
    v.check("guarda", r.status_code == 200, r.text[:250])

    detalle = portal.get(f"/pqrs/{pid}").json()
    v.check("el área quedó en Calidad", detalle["area_responsable"] == "Calidad",
            detalle["area_responsable"])
    v.check("y el estado en proceso", detalle["estado"] == "en_proceso", detalle["estado"])

    nuevos = detalle["seguimientos"][antes:]
    v.check("un solo evento para el movimiento completo", len(nuevos) == 1,
            [s["tipo_evento"] for s in nuevos])

    texto = nuevos[0]["comentario"]
    v.check("dice de dónde a dónde fue el área", "Logística -> Calidad" in texto, texto)
    v.check("y de qué estado a cuál", "asignado -> en proceso" in texto, texto)
    v.check("el comentario aparece UNA vez",
            texto.count("El lote viene de la planta") == 1, texto)


def test_el_evento_sigue_siendo_cambio_estado(entorno, v):
    """
    El historial del cliente sale de `cambio_estado` + `estado_nuevo`
    (ver historial_publico.EVENTOS_VISIBLES). Si esto cambiara de nombre, el
    cliente dejaría de ver los movimientos de su solicitud y nada fallaría.
    """
    portal = entorno
    _con_area(portal, "calidad", AREA_SC)
    pid = _crear_pqrs(portal)

    portal.como("calidad")
    portal.patch(f"/pqrs/{pid}/gestion", data={"area": "Calidad", "estado": "resuelto"})

    evento = _seguimientos(portal, pid)[-1]
    v.check("el tipo de evento es cambio_estado",
            evento["tipo_evento"] == "cambio_estado", evento["tipo_evento"])


def test_solo_area_no_finge_un_cambio_de_estado(entorno, v):
    portal = entorno
    _con_area(portal, "calidad", AREA_SC)
    pid = _crear_pqrs(portal, area="Logística")

    portal.como("calidad")
    portal.patch(f"/pqrs/{pid}/gestion", data={"area": "Calidad"})

    evento = _seguimientos(portal, pid)[-1]
    v.check("queda como asignación de área",
            evento["tipo_evento"] == "asignacion_area", evento["tipo_evento"])
    v.check("y el estado no se movió",
            portal.get(f"/pqrs/{pid}").json()["estado"] == "asignado")


def test_un_comentario_suelto_es_una_gestion_valida(entorno, v):
    """
    Antes había que mover el estado para poder escribir. Así es como un
    registro de seguimiento termina lleno de cambios de estado que nadie
    necesitaba.
    """
    portal = entorno
    pid = _crear_pqrs(portal)

    portal.como("logistica")   # agente, ni siquiera reparte áreas
    r = portal.patch(f"/pqrs/{pid}/gestion",
                     data={"comentario": "Ya hablé con bodega, falta el lote."})
    v.check("puede comentar", r.status_code == 200, r.text[:250])

    evento = _seguimientos(portal, pid)[-1]
    v.check("queda como comentario", evento["tipo_evento"] == "comentario",
            evento["tipo_evento"])
    v.check("sin inventar un estado nuevo", evento.get("estado_nuevo") in (None, ""),
            evento.get("estado_nuevo"))


def test_guardar_sin_nada_avisa_que_hacer(entorno, v):
    portal = entorno
    pid = _crear_pqrs(portal)

    portal.como("logistica")
    r = portal.patch(f"/pqrs/{pid}/gestion", data={})
    v.check("no guarda", r.status_code == 400, r.status_code)
    v.check("y el mensaje dice qué hacer",
            "comentario" in r.json().get("detail", "").lower(), r.json())


# ── El área la reparte Servicio al Cliente ───────────────────────────────

def test_un_agente_no_mueve_el_area(entorno, v):
    """
    Si cualquiera pudiera moverla, un caso incómodo cambia de dueño sin que
    nadie lo decida. El mensaje dice la salida: escribirlo en el comentario.
    """
    portal = entorno
    pid = _crear_pqrs(portal, area="Logística")

    portal.como("logistica")
    r = portal.patch(f"/pqrs/{pid}/gestion", data={"area": "Calidad"})
    v.check("no puede -> 403", r.status_code == 403, r.status_code)
    v.check("y le dice qué hacer en su lugar",
            "comentario" in r.json().get("detail", "").lower(), r.json())
    v.check("el área no se movió",
            portal.get(f"/pqrs/{pid}").json()["area_responsable"] == "Logística")


def test_un_area_inexistente_no_entra(entorno, v):
    portal = entorno
    _con_area(portal, "calidad", AREA_SC)
    pid = _crear_pqrs(portal)

    portal.como("calidad")
    r = portal.patch(f"/pqrs/{pid}/gestion", data={"area": "Servicio al cliente"})
    v.check("una escritura distinta no pasa", r.status_code == 400, r.text[:200])


# ── El alcance que viaja con el detalle ──────────────────────────────────

def test_el_agente_ve_el_area_aunque_no_pueda_moverla(entorno, v):
    """
    El área estaba escondida dentro del control de reasignar, así que quien no
    podía moverla tampoco sabía en qué área estaba el caso.
    """
    portal = entorno
    pid = _crear_pqrs(portal, area="Calidad")

    portal.como("logistica")
    detalle = portal.get(f"/pqrs/{pid}").json()
    v.check("ve el área", detalle["area_responsable"] == "Calidad")

    alcance = detalle["alcance"]
    v.check("puede gestionar", alcance["puede_gestionar"] is True, alcance)
    v.check("pero no mover el área", alcance["puede_cambiar_area"] is False, alcance)
    v.check("ni cerrar", alcance["puede_cerrar"] is False, alcance)


def test_el_alcance_de_servicio_al_cliente(entorno, v):
    portal = entorno
    _con_area(portal, "calidad", AREA_SC)
    pid = _crear_pqrs(portal)

    portal.como("calidad")
    alcance = portal.get(f"/pqrs/{pid}").json()["alcance"]
    v.check("mueve el área", alcance["puede_cambiar_area"] is True, alcance)
    v.check("cierra", alcance["puede_cerrar"] is True, alcance)
    v.check("y reclasifica", alcance["puede_reclasificar"] is True, alcance)


def test_gerencia_no_gestiona_nada(entorno, v):
    """Ve todo el portal y no modifica nada: el alcance tiene que decirlo."""
    portal = entorno
    pid = _crear_pqrs(portal)

    portal.como("gerencia")
    alcance = portal.get(f"/pqrs/{pid}").json()["alcance"]
    v.check("no gestiona", alcance["puede_gestionar"] is False, alcance)
    v.check("no mueve el área", alcance["puede_cambiar_area"] is False, alcance)


# ── El área viaja con la autorización ────────────────────────────────────

def test_pedir_autorizacion_mueve_la_pqrs_al_area_que_firma(entorno, v):
    """
    La pregunta y el caso viajan juntos: si el caso se quedara donde estaba,
    la autorización aparecería pendiente en la bandeja de quien no puede
    firmarla y no en la de quien sí.
    """
    portal = entorno
    pid = _crear_pqrs(portal, area="Logística", estado="en_proceso")
    tid = _crear_tipo(portal, area_autorizadora="Calidad")

    portal.como("logistica")
    r = portal.post(f"/autorizaciones/pqrs/{pid}/solicitar",
                    data={"tipo_id": tid, "comentario_solicitud": "Va nota crédito"})
    v.check("se solicita", r.status_code == 201, r.text[:250])

    detalle = portal.get(f"/pqrs/{pid}").json()
    v.check("la PQRS pasó a Calidad", detalle["area_responsable"] == "Calidad",
            detalle["area_responsable"])
    v.check("y el historial lo cuenta",
            "Logística -> Calidad" in detalle["seguimientos"][-1]["comentario"],
            detalle["seguimientos"][-1]["comentario"])


def test_responder_la_devuelve_a_servicio_al_cliente(entorno, v):
    portal = entorno
    pid = _crear_pqrs(portal, area="Logística", estado="en_proceso")
    tid = _crear_tipo(portal, area_autorizadora="Calidad")

    portal.como("logistica")
    aut_id = portal.post(f"/autorizaciones/pqrs/{pid}/solicitar",
                         data={"tipo_id": tid}).json()["id"]

    portal.como("calidad")   # área Calidad: firma
    r = portal.post(f"/autorizaciones/pqrs/{pid}/{aut_id}/responder",
                    data={"decision": "aprobada", "comentario_respuesta": "Aprobada"})
    v.check("responde", r.status_code == 200, r.text[:250])

    detalle = portal.get(f"/pqrs/{pid}").json()
    v.check("vuelve a Servicio al Cliente", detalle["area_responsable"] == AREA_SC,
            detalle["area_responsable"])
    v.check("el comentario de la respuesta aparece una vez",
            detalle["seguimientos"][-1]["comentario"].count("Aprobada") == 1,
            detalle["seguimientos"][-1]["comentario"])


def test_el_soporte_se_adjunta_a_la_solicitud(entorno, v):
    """
    El soporte iba por correo aparte, así que quien firma buscaba en dos
    sitios y la autorización quedaba aprobada sin nada que la sustentara.
    """
    portal = entorno
    pid = _crear_pqrs(portal, estado="en_proceso")
    tid = _crear_tipo(portal, area_autorizadora="Calidad")

    portal.como("logistica")
    r = portal.post(
        f"/autorizaciones/pqrs/{pid}/solicitar",
        data={"tipo_id": tid, "comentario_solicitud": "Adjunto la factura"},
        files={"adjunto": ("factura.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )
    v.check("se solicita con adjunto", r.status_code == 201, r.text[:250])
    v.check("y queda guardado", bool(r.json()["adjunto_solicitud"]), r.json())

    v.check("el historial también lo enseña",
            bool(_seguimientos(portal, pid)[-1]["adjunto_evidencia"]))


# ── Quién ve el botón de firmar ──────────────────────────────────────────

def test_puede_responder_lo_decide_el_area_y_no_el_rol(entorno, v):
    """
    La pantalla lo calculaba mirando el ROL y le escondía los botones a los
    agentes del área autorizadora, que son quienes hacen ese trabajo.
    """
    portal = entorno
    pid = _crear_pqrs(portal, estado="en_proceso")
    tid = _crear_tipo(portal, area_autorizadora="Logística")

    portal.como("admin")
    portal.post(f"/autorizaciones/pqrs/{pid}/solicitar", data={"tipo_id": tid})

    portal.como("logistica")   # agente de Logística: es su área
    lista = portal.get(f"/autorizaciones/pqrs/{pid}").json()
    v.check("el agente del área sí la puede firmar",
            lista[0]["puede_responder"] is True, lista[0])

    portal.como("tics")        # líder, pero de otra área
    lista = portal.get(f"/autorizaciones/pqrs/{pid}").json()
    v.check("un líder de otra área no",
            lista[0]["puede_responder"] is False, lista[0])

    portal.como("gerencia")
    lista = portal.get(f"/autorizaciones/pqrs/{pid}").json()
    v.check("gerencia tampoco", lista[0]["puede_responder"] is False, lista[0])


def test_una_autorizacion_ya_respondida_no_se_vuelve_a_firmar(entorno, v):
    portal = entorno
    pid = _crear_pqrs(portal, estado="en_proceso")
    tid = _crear_tipo(portal, area_autorizadora="Logística")

    portal.como("admin")
    aut_id = portal.post(f"/autorizaciones/pqrs/{pid}/solicitar",
                         data={"tipo_id": tid}).json()["id"]

    portal.como("logistica")
    portal.post(f"/autorizaciones/pqrs/{pid}/{aut_id}/responder",
                data={"decision": "rechazada"})

    lista = portal.get(f"/autorizaciones/pqrs/{pid}").json()
    v.check("ya no ofrece firmarla otra vez",
            lista[0]["puede_responder"] is False, lista[0])
