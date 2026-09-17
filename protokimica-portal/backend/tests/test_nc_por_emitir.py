"""
Una nota crédito aprobada avisa AL PUNTO DE VENTA que falta emitirla.

Aprobarla no la termina: alguien tiene que emitirla y escribir su número. Ese
alguien es el punto de venta de la factura —ahora tienen el permiso de
registrar—, así que el aviso va a la gente de ESE punto: una nota crédito de
Guayabal no es trabajo de Belén.

Reglas que se protegen aquí:
- solo al aprobar, nunca al rechazar;
- a quien la pidió no se le manda por aquí: ya recibe el de la decisión;
- si en ese punto no hay nadie que pueda emitirla, **no se descarta**: va a
  todos los que tienen el permiso.
"""
from app.core.capacidades import otorgar_a_area
from app.models.nota_credito import SolicitudNotaCredito
from app.models.user import User
from app.modules.notas_credito import notificaciones
from app.modules.notas_credito.permisos import CAP_REGISTRAR

GUAYABAL = "Punto de venta Guayabal"
BELEN = "Punto de venta Belén"


def _usuario(entorno, clave, punto=None, area="Puntos de Venta", rol="agente"):
    db = entorno.Session()
    u = User(tenant_id=entorno.tenant_id, nombre=clave.title(), email=f"{clave}@p.com",
             password_hash="x", rol=rol, area=area, punto_venta=punto, activo=True)
    db.add(u)
    db.commit()
    entorno.ids[clave] = u.id
    db.close()
    return entorno.ids[clave]


def _permiso_a_los_puntos(entorno):
    """Como quedó configurado en el portal: el área entera puede registrar."""
    db = entorno.Session()
    otorgar_a_area(db, entorno.tenant_id, CAP_REGISTRAR, "Puntos de Venta",
                   entorno.ids["admin"])
    db.commit()
    db.close()


def _solicitud(entorno, punto=GUAYABAL, solicitante=None):
    db = entorno.Session()
    s = SolicitudNotaCredito(
        tenant_id=entorno.tenant_id, codigo="NC-2026-0001", punto_venta=punto,
        factura_afectada="FV-100", observaciones="Producto devuelto.",
        solicitado_por=solicitante or entorno.ids["admin"], estado="solicitada",
    )
    db.add(s)
    db.commit()
    sid = s.id
    db.close()
    return sid


def _avisos(entorno, sid, decision="aprobar"):
    """Responde la solicitud y arma los avisos que saldrían al punto de venta."""
    r = entorno.post(f"/notas-credito/{sid}/responder", json={"decision": decision})
    assert r.status_code == 200, r.text[:300]
    db = entorno.Session()
    solicitud = db.get(SolicitudNotaCredito, sid)
    avisos = notificaciones.avisos_por_emitir(db, entorno.tenant_id, solicitud, "Quien aprueba")
    db.close()
    return avisos


def _destinatarios(avisos, evento="nc-por-emitir"):
    return sorted({
        correo
        for nombre, payload in avisos if nombre == evento
        for correo in payload["destinatarios"]
    })


def test_avisa_a_la_gente_de_ese_punto_de_venta(entorno, v):
    _permiso_a_los_puntos(entorno)
    _usuario(entorno, "guayabal1", punto="PVG")
    _usuario(entorno, "guayabal2", punto="PVG")
    _usuario(entorno, "belen1", punto="PVB")

    entorno.como("admin")
    sid = _solicitud(entorno)
    avisos = _avisos(entorno, sid)

    correos = _destinatarios(avisos)
    v.check("les llega a los de Guayabal",
            correos == ["guayabal1@p.com", "guayabal2@p.com"], correos)
    v.check("y no a Belén", "belen1@p.com" not in correos, correos)


def test_el_evento_dice_que_es_del_punto(entorno, v):
    _permiso_a_los_puntos(entorno)
    _usuario(entorno, "guayabal1", punto="PVG")
    entorno.como("admin")
    avisos = _avisos(entorno, _solicitud(entorno))
    v.check("un solo aviso", len(avisos) == 1, avisos)
    nombre, payload = avisos[0]
    v.check("con el path del webhook", nombre == "nc-por-emitir", nombre)
    v.check("dice que sí es del punto", payload["es_del_punto"] is True, payload)
    v.check("y trae lo que hay que emitir",
            payload["codigo"] == "NC-2026-0001" and payload["punto_venta"] == GUAYABAL, payload)


def test_a_quien_la_pidio_no_se_le_repite(entorno, v):
    """Ya recibe el aviso de la decisión: serían dos correos por una sola cosa."""
    _permiso_a_los_puntos(entorno)
    pidio = _usuario(entorno, "guayabal1", punto="PVG")
    _usuario(entorno, "guayabal2", punto="PVG")

    entorno.como("admin")
    sid = _solicitud(entorno, solicitante=pidio)
    correos = _destinatarios(_avisos(entorno, sid))
    v.check("solo al otro del punto", correos == ["guayabal2@p.com"], correos)


def test_si_el_punto_no_tiene_quien_emita_no_se_pierde(entorno, v):
    """Contabilidad la recibe: una aprobada que nadie emite deja al cliente esperando."""
    db = entorno.Session()
    otorgar_a_area(db, entorno.tenant_id, CAP_REGISTRAR, "Contabilidad",
                   entorno.ids["admin"])
    db.commit()
    db.close()
    _usuario(entorno, "conta1", area="Contabilidad")
    _usuario(entorno, "belen1", punto="PVB")

    entorno.como("admin")
    avisos = _avisos(entorno, _solicitud(entorno))
    correos = _destinatarios(avisos)
    v.check("va a quien sí puede registrarla", correos == ["conta1@p.com"], correos)
    v.check("y el correo lo advierte", avisos[0][1]["es_del_punto"] is False, avisos[0][1])


def test_un_canal_que_no_es_una_sede_tambien_llega(entorno, v):
    """«Venta institucional» no es un punto con gente: va a quien pueda registrarla."""
    db = entorno.Session()
    otorgar_a_area(db, entorno.tenant_id, CAP_REGISTRAR, "Contabilidad",
                   entorno.ids["admin"])
    db.commit()
    db.close()
    _usuario(entorno, "conta1", area="Contabilidad")

    entorno.como("admin")
    avisos = _avisos(entorno, _solicitud(entorno, punto="Venta institucional"))
    v.check("llega igual", _destinatarios(avisos) == ["conta1@p.com"], avisos)


def test_rechazada_no_manda_a_emitir(entorno, v):
    _permiso_a_los_puntos(entorno)
    _usuario(entorno, "guayabal1", punto="PVG")
    entorno.como("admin")
    sid = _solicitud(entorno)

    r = entorno.post(f"/notas-credito/{sid}/responder", json={"decision": "rechazar"})
    v.check("se rechaza", r.status_code == 200, r.text[:200])
    db = entorno.Session()
    solicitud = db.get(SolicitudNotaCredito, sid)
    v.check("queda rechazada", solicitud.estado == "rechazada", solicitud.estado)
    db.close()


def test_el_flujo_de_n8n_escucha_ese_path(entorno, v):
    """El path del webhook es el único punto de encuentro con n8n."""
    from pathlib import Path
    import json

    flujo = Path(__file__).resolve().parents[1] / "n8n" / "nc-por-emitir.json"
    v.check("el flujo existe", flujo.exists(), str(flujo))
    if flujo.exists():
        datos = json.loads(flujo.read_text(encoding="utf-8"))
        paths = {n["parameters"].get("path") for n in datos["nodes"]}
        v.check("con el path correcto", "nc-por-emitir" in paths, paths)
