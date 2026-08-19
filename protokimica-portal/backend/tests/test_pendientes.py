"""
Los endpoints que alimentan los recordatorios automáticos.

Todos devuelven lo mismo en forma: destinatarios con su correo y SOLO lo
suyo. Un correo que dice "tienes 3 pendientes" se atiende; uno con la lista
de toda la empresa se archiva sin abrir.

Lo que se prueba: que cada quien reciba lo propio, que lo huérfano no se
pierda, y que el plazo de PQRS se cuente en días hábiles.
"""
from datetime import datetime, timedelta, timezone

from app.models.pqrs import PQRSSolicitud
from app.modules.pqrs.pendientes import dias_habiles_restantes


def _hoy():
    return datetime.now(timezone.utc)


# ── PQRS por vencer ──────────────────────────────────────────────────────

def _pqrs(portal, asignado_a=None, dias_limite=1, estado="asignado"):
    db = portal.Session()
    s = PQRSSolicitud(
        tenant_id=portal.tenant_id, tipo="peticion", cliente_nombre="Cliente",
        descripcion="algo", estado=estado, prioridad="media",
        origen_publico="publico", asignado_a=asignado_a,
        fecha_limite_sla=_hoy() + timedelta(days=dias_limite),
    )
    db.add(s)
    db.commit()
    sid = s.id
    db.close()
    return sid


def test_cada_quien_recibe_solo_sus_pqrs(entorno, v):
    portal = entorno
    _pqrs(portal, asignado_a=portal.ids["tics"], dias_limite=1)
    _pqrs(portal, asignado_a=portal.ids["tics"], dias_limite=0)
    _pqrs(portal, asignado_a=portal.ids["calidad"], dias_limite=1)

    datos = portal.get("/pqrs/por-vencer", params={"dias": 5}).json()
    porcorreo = {d["email"]: d for d in datos["destinatarios"]}

    v.check("hay dos destinatarios", len(datos["destinatarios"]) == 2, porcorreo.keys())
    v.check("al de TICS le tocan sus dos", porcorreo["tics@p.com"]["total"] == 2, porcorreo)
    v.check("al de Calidad solo la suya", porcorreo["calidad@p.com"]["total"] == 1, porcorreo)


def test_las_que_no_tienen_responsable_no_se_pierden(entorno, v):
    """Son las más peligrosas: el reloj corre y no hay quién responda."""
    portal = entorno
    _pqrs(portal, asignado_a=None, dias_limite=1)

    datos = portal.get("/pqrs/por-vencer", params={"dias": 5}).json()
    v.check("salen aparte", len(datos["sin_responsable"]) == 1, datos["sin_responsable"])
    v.check("y cuentan en el total", datos["total"] == 1, datos["total"])


def test_una_pqrs_cerrada_ya_no_vence(entorno, v):
    portal = entorno
    _pqrs(portal, asignado_a=portal.ids["tics"], dias_limite=0, estado="cerrado")
    _pqrs(portal, asignado_a=portal.ids["tics"], dias_limite=0, estado="resuelto")

    datos = portal.get("/pqrs/por-vencer", params={"dias": 5}).json()
    v.check("no aparecen", datos["total"] == 0, datos)


def test_solo_avisa_de_las_que_estan_cerca(entorno, v):
    portal = entorno
    _pqrs(portal, asignado_a=portal.ids["tics"], dias_limite=40)   # lejísimos

    datos = portal.get("/pqrs/por-vencer", params={"dias": 2}).json()
    v.check("una que vence en 40 días no molesta hoy", datos["total"] == 0, datos)


def test_el_plazo_se_cuenta_en_dias_habiles_y_respeta_festivos(v):
    """
    Contarlo en días corridos declararía vencido lo que sigue en término:
    los plazos de PQRS son hábiles por la Ley 1755.

    El ejemplo es real y vale por sí solo: del viernes 14 de agosto de 2026
    al martes 18 hay UN día hábil, no cuatro. En el medio quedan sábado,
    domingo y el lunes 17, que es festivo porque la Asunción cae sábado y la
    Ley Emiliani la corre al lunes.
    """
    class Falsa:
        pass

    viernes = datetime(2026, 8, 14, 8, 0, tzinfo=timezone.utc)

    s = Falsa()
    s.fecha_limite_sla = datetime(2026, 8, 18, 17, 0, tzinfo=timezone.utc)
    v.check("de viernes a martes queda 1 día hábil, no 4",
            dias_habiles_restantes(s, viernes) == 1,
            dias_habiles_restantes(s, viernes))

    # El lunes es festivo: vencer "el lunes" desde el viernes no deja margen.
    s.fecha_limite_sla = datetime(2026, 8, 17, 17, 0, tzinfo=timezone.utc)
    v.check("el lunes festivo no cuenta como día hábil",
            dias_habiles_restantes(s, viernes) == 0,
            dias_habiles_restantes(s, viernes))


def test_una_pqrs_vencida_sale_con_dias_negativos(entorno, v):
    """Distinguir «le quedan 0 días» de «venció hace 3» cambia el mensaje."""
    portal = entorno
    db = portal.Session()
    s = PQRSSolicitud(
        tenant_id=portal.tenant_id, tipo="peticion", cliente_nombre="Cliente",
        descripcion="algo", estado="asignado", prioridad="media",
        origen_publico="publico", asignado_a=portal.ids["tics"],
        fecha_limite_sla=_hoy() - timedelta(days=10),
    )
    db.add(s)
    db.commit()
    db.close()

    datos = portal.get("/pqrs/por-vencer", params={"dias": 2}).json()
    caso = datos["destinatarios"][0]["casos"][0]
    v.check("va marcada como vencida", caso["vencida"] is True, caso)
    v.check("con los días en negativo", caso["dias_restantes"] < 0, caso)


# ── Indicadores sin registrar ────────────────────────────────────────────

def _indicador(portal, nombre, responsable_id=None):
    r = portal.post("/indicadores", json={
        "nombre": nombre, "unidad": "porcentaje", "tipo_captura": "valor",
        "area": "TICS", "meta": 90, "direccion": "arriba",
        "umbral_verde": 90, "umbral_amarillo": 75,
        **({"responsable_id": responsable_id} if responsable_id else {}),
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_a_cada_responsable_le_llegan_solo_sus_indicadores(entorno, v):
    portal = entorno
    _indicador(portal, "Disponibilidad", portal.ids["tics"])
    _indicador(portal, "Backups", portal.ids["tics"])
    _indicador(portal, "Auditorías", portal.ids["calidad"])

    datos = portal.get("/indicadores/pendientes-de-registro",
                       params={"anio": 2026, "mes": 7}).json()
    porcorreo = {d["email"]: d["total"] for d in datos["destinatarios"]}

    v.check("faltan los tres", datos["total"] == 3, datos["total"])
    v.check("al de TICS le tocan dos", porcorreo.get("tics@p.com") == 2, porcorreo)
    v.check("al de Calidad uno", porcorreo.get("calidad@p.com") == 1, porcorreo)


def test_un_indicador_sin_responsable_sale_aparte(entorno, v):
    """Si nadie lo reclama, nadie lo registra."""
    portal = entorno
    _indicador(portal, "Huérfano")

    datos = portal.get("/indicadores/pendientes-de-registro",
                       params={"anio": 2026, "mes": 7}).json()
    v.check("no se pierde", len(datos["sin_responsable"]) == 1, datos["sin_responsable"])


def test_lo_ya_registrado_no_se_recuerda(entorno, v):
    portal = entorno
    ind = _indicador(portal, "Disponibilidad", portal.ids["tics"])
    portal.post(f"/indicadores/{ind}/mediciones", data={"anio": 2026, "mes": 7, "valor": 95})

    datos = portal.get("/indicadores/pendientes-de-registro",
                       params={"anio": 2026, "mes": 7}).json()
    v.check("ya no aparece", datos["total"] == 0, datos)


# ── Tareas vencidas ──────────────────────────────────────────────────────

def _proyecto_con_tarea(portal, dias_fin, asignado_a, archivado=False):
    p = portal.post("/master-planner/proyectos",
                    json={"nombre": f"P{dias_fin}", "area": "TICS"}).json()
    portal.post(f"/master-planner/proyectos/{p['id']}/tareas", json={
        "titulo": "Pendiente", "asignado_a": asignado_a,
        "fecha_fin": (_hoy() + timedelta(days=dias_fin)).isoformat(),
    })
    if archivado:
        portal.patch(f"/master-planner/proyectos/{p['id']}", json={"archivado": True})
    return p


def test_avisa_de_lo_vencido_y_de_lo_que_esta_por_vencer(entorno, v):
    portal = entorno
    _proyecto_con_tarea(portal, -5, portal.ids["tics"])   # vencida
    _proyecto_con_tarea(portal, 2, portal.ids["tics"])    # vence pronto
    _proyecto_con_tarea(portal, 30, portal.ids["tics"])   # lejos

    datos = portal.get("/master-planner/tareas-vencidas-por-persona").json()
    persona = datos["destinatarios"][0]

    v.check("una vencida", persona["vencidas"] == 1, persona)
    v.check("una por vencer", persona["por_vencer"] == 1, persona)
    v.check("la de dentro de un mes no molesta", len(persona["tareas"]) == 2, persona)
    v.check("la vencida va primero", persona["tareas"][0]["vencida"] is True, persona["tareas"])


def test_un_proyecto_archivado_no_genera_pendientes(entorno, v):
    """Un proyecto cerrado o cancelado no puede seguir reclamándole a nadie."""
    portal = entorno
    _proyecto_con_tarea(portal, -5, portal.ids["tics"], archivado=True)

    datos = portal.get("/master-planner/tareas-vencidas-por-persona").json()
    v.check("nadie recibe nada", datos["total_personas"] == 0, datos)


def test_las_tareas_completadas_no_cuentan(entorno, v):
    portal = entorno
    p = _proyecto_con_tarea(portal, -5, portal.ids["tics"])
    tareas = portal.get(f"/master-planner/proyectos/{p['id']}/tareas").json()
    portal.patch(f"/master-planner/tareas/{tareas[0]['id']}", json={"estado": "completada"})

    datos = portal.get("/master-planner/tareas-vencidas-por-persona").json()
    v.check("no quedan pendientes", datos["total_personas"] == 0, datos)
