"""
Los números del inicio que alimentan la portada de gerencia.

Todo esto se calcula en el servidor a propósito: si el frontend sumara los
pagos por mes, tarde o temprano la gráfica del portal y el reporte de
Tesorería dirían cosas distintas.
"""
from datetime import datetime, timedelta, timezone

from app.models.master_planner import ItemPresupuesto, PagoItem, Proyecto
from app.modules.inicio.service import (
    MESES_SERIE, _meses_hacia_atras, _proyectos_al_frente, _serie_presupuesto,
)


def _proyecto(db, tenant_id, nombre="Proyecto", estado="en_ejecucion", fin=None):
    p = Proyecto(tenant_id=tenant_id, nombre=nombre, estado=estado,
                 fecha_fin_estimada=fin)
    db.add(p)
    db.commit()
    return p


def test_la_serie_trae_un_punto_por_mes(entorno):
    db = entorno.Session()
    serie = _serie_presupuesto(db, [])

    assert len(serie) == MESES_SERIE
    assert all(p["etiqueta"] and "anio" in p and "mes" in p for p in serie)
    # Del más viejo al más nuevo: una gráfica que va al revés se lee al revés.
    assert serie[-1]["mes"] == datetime.now(timezone.utc).month
    db.close()


def test_sin_proyectos_la_serie_va_en_ceros_pero_existe(entorno):
    """Sin datos la gráfica se dibuja vacía; no desaparece ni revienta."""
    db = entorno.Session()
    serie = _serie_presupuesto(db, [])
    assert all(p["pagado"] == 0 and p["aprobado"] == 0 for p in serie)
    db.close()


def test_los_pagos_caen_en_el_mes_que_les_toca(entorno):
    db = entorno.Session()
    p = _proyecto(db, entorno.tenant_id)
    item = ItemPresupuesto(proyecto_id=p.id, concepto="Equipos",
                           valor_unitario=1000, cantidad=1)
    db.add(item)
    db.commit()

    ahora = datetime.now(timezone.utc)
    db.add(PagoItem(item_id=item.id, valor=500, fecha=ahora))
    db.commit()

    serie = _serie_presupuesto(db, [p.id])
    assert serie[-1]["pagado"] == 500, serie[-1]
    assert sum(x["pagado"] for x in serie[:-1]) == 0
    db.close()


def test_lo_pagado_hace_mucho_no_entra_en_la_ventana(entorno):
    """La gráfica es de los últimos meses, no de toda la historia."""
    db = entorno.Session()
    p = _proyecto(db, entorno.tenant_id)
    item = ItemPresupuesto(proyecto_id=p.id, concepto="Viejo",
                           valor_unitario=1000, cantidad=1)
    db.add(item)
    db.commit()

    hace_dos_anios = datetime.now(timezone.utc) - timedelta(days=730)
    db.add(PagoItem(item_id=item.id, valor=999, fecha=hace_dos_anios))
    db.commit()

    serie = _serie_presupuesto(db, [p.id])
    assert sum(x["pagado"] for x in serie) == 0
    db.close()


def test_los_meses_cruzan_el_cambio_de_ano():
    periodos = _meses_hacia_atras(14)
    assert len(periodos) == 14
    assert len(set(periodos)) == 14, "hay meses repetidos"
    assert all(1 <= mes <= 12 for _, mes in periodos)


def test_al_frente_van_los_que_vencen_primero(entorno):
    db = entorno.Session()
    ahora = datetime.now(timezone.utc)
    tarde = _proyecto(db, entorno.tenant_id, "Vence tarde", fin=ahora + timedelta(days=90))
    pronto = _proyecto(db, entorno.tenant_id, "Vence pronto", fin=ahora + timedelta(days=5))
    sin_fecha = _proyecto(db, entorno.tenant_id, "Sin fecha", fin=None)

    nombres = [p["nombre"] for p in _proyectos_al_frente([tarde, pronto, sin_fecha])]

    assert nombres[0] == "Vence pronto"
    assert nombres[-1] == "Sin fecha", "sin plazo no hay urgencia: va al final"
    db.close()


def test_los_proyectos_terminados_no_ocupan_la_portada(entorno):
    db = entorno.Session()
    activo = _proyecto(db, entorno.tenant_id, "Activo", estado="en_ejecucion")
    cerrado = _proyecto(db, entorno.tenant_id, "Cerrado", estado="cerrado")
    cancelado = _proyecto(db, entorno.tenant_id, "Cancelado", estado="cancelado")

    nombres = [p["nombre"] for p in _proyectos_al_frente([activo, cerrado, cancelado])]

    assert nombres == ["Activo"]
    db.close()


def test_gerencia_recibe_todo_lo_que_pinta_la_portada(entorno):
    """La prueba de verdad: contra la API, con el usuario que la usa."""
    entorno.como("gerencia")
    datos = entorno.get("/inicio").json()["empresa"]

    for campo in ["proyectos_activos", "proyectos_nuevos_mes", "proyectos",
                  "pqrs_abiertas", "pqrs_cerradas_mes", "serie_presupuesto",
                  "presupuesto_aprobado", "pagado_pct_aprobado"]:
        assert campo in datos, f"falta {campo} en el resumen de empresa"

    assert len(datos["serie_presupuesto"]) == MESES_SERIE
