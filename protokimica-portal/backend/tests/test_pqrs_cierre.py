"""
Reclasificacion del tipo de una PQRS y cierre restringido a Servicio al
cliente, contra la API real.
"""
from datetime import datetime, timedelta, timezone

from app.models.pqrs import PQRSSolicitud
from app.models.user import User


def _crear_pqrs(portal, tipo="peticion", dias_atras=0):
    """
    Crea una PQRS directo en la base (el endpoint publico pide multipart),
    pero con los mismos calculos que hace el flujo real: prioridad y fecha
    limite derivadas del tipo.
    """
    from app.modules.pqrs.service import calcular_fecha_limite_sla, calcular_prioridad

    db = portal.Session()
    creacion = datetime.now(timezone.utc) - timedelta(days=dias_atras)
    p = PQRSSolicitud(
        tenant_id=portal.tenant_id,
        tipo=tipo,
        cliente_nombre="Cliente de prueba",
        descripcion="Algo paso",
        estado="en_proceso",
        prioridad=calcular_prioridad(tipo),
        fecha_creacion=creacion,
        fecha_limite_sla=calcular_fecha_limite_sla(tipo, creacion),
    )
    db.add(p)
    db.commit()
    pid = p.id
    db.close()
    return pid


def _con_area(portal, clave, area):
    """Cambia el area de un usuario de prueba."""
    db = portal.Session()
    u = db.get(User, portal.ids[clave])
    u.area = area
    db.commit()
    db.close()


def test_solo_servicio_al_cliente_cierra(entorno, v):
    portal = entorno
    _con_area(portal, "calidad", "Servicio al cliente")
    pid = _crear_pqrs(portal)

    # Alguien de otra area no puede cerrar
    portal.como("logistica")
    r = portal.patch(f"/pqrs/{pid}/estado", data={"estado": "cerrado"})
    v.check("Logistica no puede cerrar -> 403", r.status_code == 403, r.text[:120])
    v.check("el mensaje dice a quien pedirle",
            "Servicio al cliente" in r.json().get("detail", ""), r.json())

    # Pero si puede mover la PQRS a otros estados
    r = portal.patch(f"/pqrs/{pid}/estado", data={"estado": "resuelto"})
    v.check("Logistica si puede marcar 'resuelto'", r.status_code == 200, r.text[:120])

    # Servicio al cliente si cierra
    portal.como("calidad")
    r = portal.patch(f"/pqrs/{pid}/estado", data={"estado": "cerrado"})
    v.check("Servicio al cliente cierra -> 200", r.status_code == 200, r.text[:150])
    v.check("queda con fecha de cierre", r.json()["fecha_cierre"] is not None, r.json())

    # Admin tambien, siempre
    pid2 = _crear_pqrs(portal)
    portal.como("admin")
    v.check("admin tambien puede cerrar",
            portal.patch(f"/pqrs/{pid2}/estado", data={"estado": "cerrado"}).status_code == 200)


def test_reclasificar_tipo(entorno, v):
    portal = entorno
    _con_area(portal, "calidad", "Servicio al cliente")
    # Radicada hace 10 dias como peticion (SLA 15 habiles)
    pid = _crear_pqrs(portal, tipo="peticion", dias_atras=10)

    antes = portal.get(f"/pqrs/{pid}").json()
    v.check("nace como peticion", antes["tipo"] == "peticion", antes["tipo"])
    v.check("con prioridad media", antes["prioridad"] == "media", antes["prioridad"])

    # Quien no es de Servicio al cliente no reclasifica
    portal.como("logistica")
    r = portal.patch(f"/pqrs/{pid}/tipo", data={"tipo": "reclamo", "motivo": "x"})
    v.check("Logistica no puede reclasificar -> 403", r.status_code == 403, r.text[:120])

    portal.como("calidad")
    r = portal.patch(f"/pqrs/{pid}/tipo",
                     data={"tipo": "reclamo", "motivo": "El cliente pide devolucion de dinero"})
    v.check("reclasificar -> 200", r.status_code == 200, r.text[:200])
    despues = r.json()
    v.check("el tipo cambio", despues["tipo"] == "reclamo", despues["tipo"])
    v.check("la prioridad se ajusto sola a alta",
            despues["prioridad"] == "alta", despues["prioridad"])
    v.check("el plazo se recalculo",
            despues["fecha_limite_sla"] != antes["fecha_limite_sla"],
            {"antes": antes["fecha_limite_sla"], "despues": despues["fecha_limite_sla"]})


def test_la_reclasificacion_queda_en_la_trazabilidad(entorno, v):
    portal = entorno
    _con_area(portal, "calidad", "Servicio al cliente")
    pid = _crear_pqrs(portal, tipo="peticion")
    portal.como("calidad")

    portal.patch(f"/pqrs/{pid}/tipo",
                 data={"tipo": "queja", "motivo": "Es una inconformidad con la atencion"})

    seg = portal.get(f"/pqrs/{pid}").json()["seguimientos"]
    reclas = [x for x in seg if x["tipo_evento"] == "reclasificacion"]
    v.check("hay un evento de reclasificacion", len(reclas) == 1, [x["tipo_evento"] for x in seg])
    if reclas:
        texto = reclas[0]["comentario"]
        v.check("dice de que tipo a cual", "peticion -> queja" in texto, texto)
        v.check("registra el cambio de prioridad", "Prioridad" in texto, texto)
        v.check("registra el cambio de fecha limite", "Fecha limite" in texto, texto)
        v.check("guarda el motivo", "inconformidad" in texto, texto)
        v.check("y quien lo hizo", reclas[0]["usuario_nombre"] == "Cali", reclas[0])


def test_la_prioridad_puesta_a_mano_se_respeta(entorno, v):
    portal = entorno
    _con_area(portal, "calidad", "Servicio al cliente")
    pid = _crear_pqrs(portal, tipo="peticion")

    # Alguien la sube a critica por conocer el caso
    db = portal.Session()
    p = db.get(PQRSSolicitud, pid)
    p.prioridad = "critica"
    db.commit()
    db.close()

    portal.como("calidad")
    r = portal.patch(f"/pqrs/{pid}/tipo",
                     data={"tipo": "sugerencia", "motivo": "En realidad es una idea de mejora"})
    v.check("el tipo cambia", r.json()["tipo"] == "sugerencia", r.json()["tipo"])
    v.check("pero la prioridad manual NO se pisa",
            r.json()["prioridad"] == "critica", r.json()["prioridad"])

    seg = portal.get(f"/pqrs/{pid}").json()["seguimientos"]
    texto = next(x["comentario"] for x in seg if x["tipo_evento"] == "reclasificacion")
    v.check("y la trazabilidad lo dice", "sin cambio" in texto, texto)


def test_no_se_reclasifica_una_pqrs_cerrada(entorno, v):
    portal = entorno
    _con_area(portal, "calidad", "Servicio al cliente")
    pid = _crear_pqrs(portal)
    portal.como("calidad")
    portal.patch(f"/pqrs/{pid}/estado", data={"estado": "cerrado"})

    r = portal.patch(f"/pqrs/{pid}/tipo", data={"tipo": "queja", "motivo": "tarde"})
    v.check("reclasificar una cerrada -> 400", r.status_code == 400, r.text[:150])
    v.check("y explica que se hace antes de cerrar",
            "antes de cerrarla" in r.json().get("detail", ""), r.json())


def test_validaciones_de_la_reclasificacion(entorno, v):
    portal = entorno
    _con_area(portal, "calidad", "Servicio al cliente")
    pid = _crear_pqrs(portal, tipo="peticion")
    portal.como("calidad")

    r = portal.patch(f"/pqrs/{pid}/tipo", data={"tipo": "inventado", "motivo": "x"})
    v.check("un tipo invalido -> 400", r.status_code == 400, r.text[:120])

    r = portal.patch(f"/pqrs/{pid}/tipo", data={"tipo": "peticion", "motivo": "x"})
    v.check("reclasificar al mismo tipo -> 400", r.status_code == 400, r.text[:120])

    r = portal.patch(f"/pqrs/{pid}/tipo", data={"tipo": "queja", "motivo": "   "})
    v.check("sin motivo -> 400", r.status_code == 400, r.text[:120])

    r = portal.patch("/pqrs/99999/tipo", data={"tipo": "queja", "motivo": "x"})
    v.check("una PQRS inexistente -> 404", r.status_code == 404, r.status_code)


def test_el_sla_se_recalcula_desde_la_radicacion(entorno, v):
    """
    Lo importante: el plazo nuevo cuenta desde que se radico, no desde hoy.
    Si en realidad era un reclamo, el plazo del reclamo aplicaba desde el
    principio — y puede quedar vencida, que es lo correcto.
    """
    portal = entorno
    _con_area(portal, "calidad", "Servicio al cliente")
    # Radicada hace 20 dias como peticion; como reclamo (8 habiles) ya vencio
    pid = _crear_pqrs(portal, tipo="peticion", dias_atras=20)
    portal.como("calidad")

    r = portal.patch(f"/pqrs/{pid}/tipo",
                     data={"tipo": "reclamo", "motivo": "Es un reclamo por producto"})
    def _aware(iso):
        f = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return f if f.tzinfo else f.replace(tzinfo=timezone.utc)

    limite = _aware(r.json()["fecha_limite_sla"])
    creacion = _aware(r.json()["fecha_creacion"])

    v.check("el limite quedo despues de la radicacion", limite > creacion,
            {"creacion": str(creacion), "limite": str(limite)})
    v.check("y quedo vencida, porque el plazo del reclamo ya paso",
            limite < datetime.now(timezone.utc),
            {"limite": str(limite), "ahora": str(datetime.now(timezone.utc))})


def test_el_sla_de_una_pqrs_nueva_usa_dias_habiles(entorno, v):
    """
    Una queja tiene 5 dias de SLA. En calendario venceria 5 dias despues; en
    habiles siempre es igual o mas, porque se saltan fines de semana y
    festivos.
    """
    portal = entorno
    pid = _crear_pqrs(portal, tipo="queja")

    db = portal.Session()
    p = db.get(PQRSSolicitud, pid)
    from app.modules.pqrs.service import calcular_fecha_limite_sla
    limite = calcular_fecha_limite_sla("queja", p.fecha_creacion)
    calendario = p.fecha_creacion + timedelta(days=5)
    db.close()

    v.check("el plazo en habiles no es menor que en calendario",
            limite.date() >= calendario.date(),
            {"habiles": str(limite.date()), "calendario": str(calendario.date())})
