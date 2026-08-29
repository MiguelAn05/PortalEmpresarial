"""
Quién puede responder una autorización.

Manda el ÁREA, no el cargo. Quien trabaja en Aseguramiento autoriza lo de
Aseguramiento, sea líder o agente. Amarrarlo al rol dejaba fuera a la gente
que hace el trabajo y obligaba a cambiarle el cargo a alguien solo para que
pudiera firmar.
"""
from app.models.autorizacion import TipoAutorizacion
from app.models.pqrs import PQRSSolicitud
from app.models.user import User
from app.modules.autorizaciones.permisos import puede_responder


def _usuario(rol, area):
    u = User()
    u.rol, u.area = rol, area
    return u


# ── La regla, sin pasar por la API ───────────────────────────────────────

def test_un_agente_del_area_si_puede(v):
    v.check("el agente de Aseguramiento autoriza lo de Aseguramiento",
            puede_responder(_usuario("agente", "Aseguramiento"), "Aseguramiento"))


def test_un_lider_de_otra_area_no_puede(v):
    v.check("el líder de Calidad no autoriza lo de Aseguramiento",
            puede_responder(_usuario("lider", "Calidad"), "Aseguramiento") is False)


def test_admin_siempre_puede(v):
    """Es quien destraba cuando el responsable está de vacaciones."""
    v.check("aunque su área sea otra",
            puede_responder(_usuario("admin", "TICS"), "Aseguramiento"))


def test_un_tipo_sin_area_solo_lo_responde_admin(v):
    """Una firma sin dueño no la puede dar cualquiera."""
    v.check("nadie del común", puede_responder(_usuario("lider", "Calidad"), None) is False)
    v.check("solo admin", puede_responder(_usuario("admin", "TICS"), None))


# ── Contra la API real ───────────────────────────────────────────────────

def _preparar(portal, area_autorizadora="Calidad"):
    db = portal.Session()
    tipo = TipoAutorizacion(
        tenant_id=portal.tenant_id, nombre="Nota crédito",
        descripcion="Autoriza la nota", area_autorizadora=area_autorizadora,
    )
    db.add(tipo)
    solicitud = PQRSSolicitud(
        tenant_id=portal.tenant_id, tipo="reclamo", cliente_nombre="Cliente",
        descripcion="algo", estado="en_proceso", prioridad="media",
        origen_publico="publico",
    )
    db.add(solicitud)
    db.commit()
    ids = (solicitud.id, tipo.id)
    db.close()

    portal.como("admin")
    r = portal.post(f"/autorizaciones/pqrs/{ids[0]}/solicitar",
                    json={"tipo_id": ids[1], "comentario_solicitud": "Se requiere"})
    assert r.status_code == 201, r.text
    return ids[0], r.json()["id"]


def test_el_agente_del_area_autorizadora_puede_responder(entorno, v):
    """Antes no podía: se exigía rol de líder aunque fuera su área."""
    portal = entorno
    pqrs_id, aut_id = _preparar(portal, area_autorizadora="Logística")

    portal.como("logistica")   # rol agente, área Logística
    r = portal.post(f"/autorizaciones/pqrs/{pqrs_id}/{aut_id}/responder",
                    json={"decision": "aprobada", "comentario_respuesta": "Va"})
    v.check("un agente de esa área sí autoriza", r.status_code == 200, r.text[:250])
    v.check("y queda aprobada", r.json()["estado"] == "aprobada", r.json())


def test_un_lider_de_otra_area_recibe_403_con_instruccion(entorno, v):
    portal = entorno
    pqrs_id, aut_id = _preparar(portal, area_autorizadora="Calidad")

    portal.como("tics")   # líder, pero de TICS
    r = portal.post(f"/autorizaciones/pqrs/{pqrs_id}/{aut_id}/responder",
                    json={"decision": "aprobada"})
    v.check("no puede", r.status_code == 403, r.status_code)
    v.check("y el mensaje dice a quién pedirle",
            "Calidad" in r.json()["detail"], r.json())


def test_lectura_no_autoriza_aunque_sea_su_area(entorno, v):
    """`lectura` no escribe nada en el portal; esto no es la excepción."""
    portal = entorno
    pqrs_id, aut_id = _preparar(portal, area_autorizadora="TICS")

    portal.como("lectura")   # rol lectura, área TICS
    r = portal.post(f"/autorizaciones/pqrs/{pqrs_id}/{aut_id}/responder",
                    json={"decision": "aprobada"})
    v.check("se bloquea", r.status_code == 403, r.status_code)


def test_gerencia_tampoco_autoriza(entorno, v):
    """Gerencia ve todo y no modifica nada: solo comenta."""
    portal = entorno
    pqrs_id, aut_id = _preparar(portal, area_autorizadora="Calidad")

    portal.como("gerencia")
    r = portal.post(f"/autorizaciones/pqrs/{pqrs_id}/{aut_id}/responder",
                    json={"decision": "aprobada"})
    v.check("se bloquea", r.status_code == 403, r.status_code)
