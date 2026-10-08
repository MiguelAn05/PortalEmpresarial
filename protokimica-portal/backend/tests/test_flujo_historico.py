"""
El flujo real de las PQRS, reconstruido desde el historial
(`pqrs/flujo_historico.py`): primer paso para automatizar el recorrido.

Lo que se prueba: se leen los dos formatos con que el portal ha escrito los
movimientos de área, lo ilegible se cuenta y no se adivina, se reconocen las
idas y vueltas y quién resolvió, y un recorrido solo se propone como ruta
cuando ya es la norma.
"""
from datetime import datetime, timedelta, timezone

from app.models.pqrs import PQRSSeguimiento, PQRSSolicitud
from app.modules.pqrs import asociados
from app.modules.pqrs.flujo_historico import SIN_AREA, analizar, recorrido

INICIO = datetime(2026, 9, 1, 15, 0, tzinfo=timezone.utc)


def _seg(i, comentario, tipo="cambio_estado", estado_nuevo=None):
    return PQRSSeguimiento(id=i, pqrs_id=1, tipo_evento=tipo, comentario=comentario,
                           estado_nuevo=estado_nuevo, fecha=INICIO + timedelta(hours=i))


def _sol(area="Servicio al Cliente", estado="en_proceso"):
    return PQRSSolicitud(id=1, tipo="reclamo", estado=estado, area_responsable=area)


# ── Leer un recorrido ────────────────────────────────────────────────────

def test_lee_el_formato_de_hoy(v):
    r = recorrido(_sol(), [
        _seg(1, "Solicitud radicada por el cliente.", estado_nuevo="recibido"),
        _seg(2, "Área: Servicio al Cliente -> Calidad. Revisar el lote.", "asignacion_area"),
        _seg(3, "Se solicitó autorización: Nota crédito. Área: Calidad -> Contabilidad mientras se responde.",
             "autorizacion_solicitada"),
        _seg(4, "Autorización 'Nota crédito' aprobada. Área: Contabilidad -> Servicio al Cliente.",
             "autorizacion_respondida"),
    ])
    v.check("el recorrido completo, en orden",
            r["ruta"] == ["Servicio al Cliente", "Calidad", "Contabilidad", "Servicio al Cliente"], r)
    v.check("nada ilegible", r["ilegibles"] == 0)


def test_lee_el_formato_viejo_y_completa_el_origen(v):
    r = recorrido(_sol(), [
        _seg(1, "Área: Servicio al Cliente -> Calidad.", "asignacion_area"),
        _seg(2, "Área asignada: Logística.", "asignacion_area"),
    ])
    v.check("el viejo no dice de dónde salió: del área que tenía",
            r["ruta"] == ["Servicio al Cliente", "Calidad", "Logística"], r)


def test_el_area_causante_no_es_un_movimiento(v):
    r = recorrido(_sol(area="Calidad"), [_seg(1, "Área causante: sin definir -> Logística.", "causa")])
    v.check("no mueve el caso", r["ruta"] == ["Calidad"], r)


def test_lo_ilegible_se_cuenta_y_no_se_adivina(v):
    r = recorrido(_sol(), [
        _seg(1, "Área: Servicio al Cliente -> Calidad.", "asignacion_area"),
        _seg(2, "Se la paso a los de bodega", "asignacion_area"),
    ])
    v.check("queda contado", r["ilegibles"] == 1, r)
    v.check("y el recorrido no inventa un destino", r["ruta"] == ["Servicio al Cliente", "Calidad"], r)


def test_sin_movimientos_es_el_area_que_tiene(v):
    r = recorrido(_sol(area="Calidad"), [_seg(1, "Solicitud radicada.", estado_nuevo="recibido")])
    v.check("una sola área", r["ruta"] == ["Calidad"], r)
    r = recorrido(_sol(area=None), [])
    v.check("sin área, se dice", r["ruta"] == [SIN_AREA], r)


def test_quien_la_resolvio(v):
    r = recorrido(_sol(estado="cerrado"), [
        _seg(1, "Área: Servicio al Cliente -> Logística.", "asignacion_area"),
        _seg(2, "Estado: en proceso -> resuelto. Se reenvió.", estado_nuevo="resuelto"),
        _seg(3, "Área: Logística -> Servicio al Cliente.", "asignacion_area"),
    ])
    v.check("el área que la tenía al resolverse, no la última", r["resolvio"] == "Logística", r)

    r = recorrido(_sol(estado="cerrado"), [
        _seg(1, "Estado: recibido -> resuelto.", estado_nuevo="resuelto"),
        _seg(2, "Área: Servicio al Cliente -> Calidad.", "asignacion_area"),
    ])
    v.check("resuelta antes de moverse: el área de nacimiento", r["resolvio"] == "Servicio al Cliente", r)

    r = recorrido(_sol(estado="en_proceso"), [])
    v.check("abierta: nadie la ha resuelto", r["resolvio"] is None, r)


# ── El análisis de toda la empresa ───────────────────────────────────────

def _radicar(entorno, tipo, movimientos, asociado=None, estado="cerrado", codigo=None):
    db = entorno.Session()
    p = PQRSSolicitud(tenant_id=entorno.tenant_id, tipo=tipo, cliente_nombre="C", descripcion="x",
                      estado=estado, prioridad="media", origen_publico="publico",
                      area_responsable=movimientos[-1] if movimientos else "Servicio al Cliente",
                      asociado_id=asociado, codigo_seguimiento=codigo, fecha_creacion=INICIO)
    db.add(p)
    db.flush()
    for i, (a, b) in enumerate(zip(movimientos, movimientos[1:])):
        db.add(PQRSSeguimiento(pqrs_id=p.id, tipo_evento="asignacion_area",
                               comentario=f"Área: {a} -> {b}.", fecha=INICIO + timedelta(hours=i)))
    db.commit()
    db.close()


def test_propone_una_ruta_solo_cuando_ya_es_la_norma(entorno, v):
    sc, cal, log = "Servicio al Cliente", "Calidad", "Logística"
    for _ in range(3):
        _radicar(entorno, "reclamo", [sc, log, sc])
    _radicar(entorno, "reclamo", [sc, cal])
    _radicar(entorno, "queja", [sc, cal])
    _radicar(entorno, "queja", [sc, log])
    _radicar(entorno, "queja", [sc])

    db = entorno.Session()
    r = analizar(db, entorno.tenant_id)
    db.close()

    reclamo = next(g for g in r["por_tipo"] if g["grupo"] == "Reclamo")
    v.check("reclamos: 3 de 4 van a Logística y vuelven, eso es la norma",
            reclamo["patron"]["hay_patron"] and reclamo["patron"]["ruta"] == [sc, log, sc]
            and reclamo["patron"]["pct"] == 75.0, reclamo["patron"])
    queja = next(g for g in r["por_tipo"] if g["grupo"] == "Queja")
    v.check("quejas: ninguno pasa de un tercio, no hay patrón", queja["patron"]["hay_patron"] is False,
            queja["patron"])

    v.check("las idas y vueltas se cuentan", r["resumen"]["idas_y_vueltas"] == 3, r["resumen"])
    v.check("Servicio al Cliente aparece en todas",
            next(a for a in r["areas"] if a["area"] == sc)["pqrs"] == 7, r["areas"])
    v.check("la transición más común: a Logística (3 reclamos + 1 queja)",
            r["transiciones"][0] == {"de": sc, "a": log, "n": 4}, r["transiciones"])


def test_agrupa_por_causa(entorno, v):
    db = entorno.Session()
    me = next(a for a in asociados.del_tenant(db, entorno.tenant_id) if a.nombre == "Mala Entrega (CEDI)")
    me_id = me.id
    db.close()
    for _ in range(3):
        _radicar(entorno, "reclamo", ["Servicio al Cliente", "Logística"], asociado=me_id)

    db = entorno.Session()
    r = analizar(db, entorno.tenant_id)
    db.close()
    grupo = r["por_asociado"][0]
    v.check("con el nombre del asociado", grupo["grupo"] == "(ME) Mala Entrega (CEDI)", grupo)
    v.check("y su ruta", grupo["patron"]["hay_patron"]
            and grupo["patron"]["ruta"] == ["Servicio al Cliente", "Logística"], grupo["patron"])
    v.check("cuenta las clasificadas", r["resumen"]["con_causa"] == 3, r["resumen"])


def test_pocos_casos_no_son_un_patron(entorno, v):
    _radicar(entorno, "sugerencia", ["Servicio al Cliente", "Mercadeo"])
    db = entorno.Session()
    r = analizar(db, entorno.tenant_id)
    db.close()
    sugerencia = r["por_tipo"][0]
    v.check("uno solo no decide nada", sugerencia["patron"]["hay_patron"] is False
            and "pocos" in sugerencia["patron"]["motivo"], sugerencia["patron"])


def test_sin_pqrs_no_revienta(entorno, v):
    db = entorno.Session()
    r = analizar(db, entorno.tenant_id)
    db.close()
    v.check("resumen en cero", r["resumen"]["pqrs"] == 0 and r["recorridos"] == [], r["resumen"])
