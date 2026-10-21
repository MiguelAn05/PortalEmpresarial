"""
El informe gerencial de Master Planner (`master_planner/informe.py`).

Lo que se prueba: los compromisos del periodo se juzgan solo cuando ya se
pueden juzgar, las entregas cuentan igual que el indicador, los aplazamientos
salen del historial, finalizados y cancelados van aparte, el área filtra sin
inflar la plata, y cada quien ve el informe de lo que puede ver —la tabla por
persona y el presupuesto incluidos—.
"""
from datetime import date, datetime, timedelta, timezone

from app.models.master_planner import (
    ActividadDiaria, ActividadRegistro, CierreProyecto, HistorialCambio, ItemPresupuesto,
    PagoItem, Proyecto, ProyectoArea, Tarea,
)

# Mediodía en Colombia (17:00 UTC).
def _dia(mes, dia, anio=2026):
    return datetime(anio, mes, dia, 17, 0, tzinfo=timezone.utc)


SEPTIEMBRE = {"desde": "2026-09-01", "hasta": "2026-09-30"}


def _proyecto(entorno, nombre="Portal", area="TICS", lider="tics", estado="en_ejecucion",
              creado=None, inicio=None, fin=None, participantes=(), archivado=False):
    db = entorno.Session()
    p = Proyecto(
        tenant_id=entorno.tenant_id, nombre=nombre, area=area,
        lider_id=entorno.ids[lider] if lider else None, estado=estado, archivado=archivado,
        creado_en=creado or _dia(8, 1), fecha_inicio=inicio, fecha_fin_estimada=fin,
    )
    db.add(p)
    db.flush()
    for a in participantes:
        db.add(ProyectoArea(proyecto_id=p.id, area=a))
    db.commit()
    pid = p.id
    db.close()
    return pid


def _tarea(entorno, proyecto_id, titulo="T", vence=None, entregada=None, asignado="tics",
           area=None, creada=None, horas=None):
    db = entorno.Session()
    t = Tarea(
        proyecto_id=proyecto_id, titulo=titulo, area=area,
        asignado_a=entorno.ids[asignado] if asignado else None,
        estado="completada" if entregada else "en_proceso",
        avance_pct=100 if entregada else 30,
        fecha_fin=vence, fecha_completada=entregada,
        creado_en=creada or _dia(8, 1), horas_estimadas=horas,
    )
    db.add(t)
    db.commit()
    tid = t.id
    db.close()
    return tid


def _agregar(entorno, *objetos):
    db = entorno.Session()
    db.add_all(objetos)
    db.commit()
    db.close()


def _informe(entorno, **params):
    r = entorno.get("/master-planner/informe", params={**SEPTIEMBRE, **params})
    assert r.status_code == 200, r.text
    return r.json()


def _fila(filas, area):
    return next((f for f in filas if f["area"] == area), None)


def test_los_compromisos_se_juzgan_cuando_ya_se_pueden(entorno, v):
    p = _proyecto(entorno)
    _tarea(entorno, p, "A tiempo", vence=_dia(9, 10), entregada=_dia(9, 8))
    _tarea(entorno, p, "Tarde", vence=_dia(9, 12), entregada=_dia(9, 20))
    _tarea(entorno, p, "Vencida", vence=_dia(9, 15))
    _tarea(entorno, p, "De agosto", vence=_dia(8, 15), entregada=_dia(8, 14))
    _tarea(entorno, p, "Entregada en sept., vencía en agosto", vence=_dia(8, 20), entregada=_dia(9, 2))

    c = _informe(entorno)["cumplimiento"]
    v.check("tres compromisos en septiembre", c["total"] == 3, c)
    v.check("uno a tiempo, uno tarde, uno vencido",
            (c["a_tiempo"], c["tarde"], c["vencidas"]) == (1, 1, 1), c)
    v.check("el porcentaje lo da el servidor", c["pct"] == 33.3, c)
    v.check("y se compara con agosto", c["pct_anterior"] == 50.0 and c["variacion_puntos"] == -16.7, c)

    e = _informe(entorno)["entregas"]
    # Como el indicador: lo ENTREGADO en el mes, sin importar cuándo vencía.
    v.check("tres entregas en septiembre", e["total"] == 3, e)
    v.check("una de ellas a tiempo", e["a_tiempo"] == 1 and e["pct"] == 33.3, e)


def test_lo_que_vence_mas_adelante_no_se_cobra(entorno, v):
    ahora = datetime.now(timezone.utc)
    p = _proyecto(entorno)
    _tarea(entorno, p, "Vence en tres días", vence=ahora + timedelta(days=3))
    _tarea(entorno, p, "Venció ayer", vence=ahora - timedelta(days=1))
    hoy = date.today()
    c = _informe(entorno, desde=(hoy - timedelta(days=10)).isoformat(),
                 hasta=(hoy + timedelta(days=10)).isoformat())["cumplimiento"]
    v.check("la que vence después queda pendiente", c["pendientes"] == 1, c)
    v.check("y no baja el porcentaje", c["juzgadas"] == 1 and c["pct"] == 0.0, c)


def test_aplazamientos_salen_del_historial(entorno, v):
    p = _proyecto(entorno)
    t = _tarea(entorno, p, "Movida", vence=_dia(9, 25))
    _agregar(
        entorno,
        HistorialCambio(entidad="tarea", entidad_id=t, proyecto_id=p, campo="fecha_fin",
                        valor_anterior=_dia(9, 5).isoformat(), valor_nuevo=_dia(9, 25).isoformat(),
                        fecha=_dia(9, 4)),
        # Poner la fecha por primera vez no es aplazar.
        HistorialCambio(entidad="tarea", entidad_id=t, proyecto_id=p, campo="fecha_fin",
                        valor_anterior=None, valor_nuevo=_dia(9, 5).isoformat(), fecha=_dia(9, 1)),
        HistorialCambio(entidad="proyecto", entidad_id=p, proyecto_id=p, campo="fecha_fin_estimada",
                        valor_anterior=_dia(10, 1).isoformat(), valor_nuevo=_dia(11, 1).isoformat(),
                        fecha=_dia(9, 10)),
    )
    inf = _informe(entorno)
    a = inf["aplazamientos"]
    v.check("un aplazamiento de tarea, de 20 días", a["tareas"] == 1 and a["dias_tareas"] == 20, a)
    v.check("uno de proyecto, de 31 días", a["proyectos"] == 1 and a["dias_proyectos"] == 31, a)
    v.check("el proyecto encabeza los más aplazados",
            a["mas_aplazados"][0]["id"] == p and a["mas_aplazados"][0]["veces"] == 2, a)
    v.check("el compromiso dice que se movió", inf["cumplimiento"]["aplazadas"] == 1, inf["cumplimiento"])


def test_finalizados_y_cancelados_van_aparte(entorno, v):
    hecho = _proyecto(entorno, "Hecho", estado="cerrado", archivado=True, fin=_dia(9, 30))
    caido = _proyecto(entorno, "Caído", estado="cancelado", archivado=True)
    _agregar(
        entorno,
        CierreProyecto(proyecto_id=hecho, tipo="finalizado", entregables="El portal en línea",
                       cerrado_en=_dia(9, 20)),
        CierreProyecto(proyecto_id=caido, tipo="cancelado", motivo="Sin presupuesto",
                       cerrado_en=_dia(9, 22)),
    )
    inf = _informe(entorno)
    r = inf["resumen"]
    v.check("uno finalizado y uno cancelado", (r["finalizados"], r["cancelados"]) == (1, 1), r)
    v.check("el finalizado se entregó en plazo", r["finalizados_en_plazo"] == 1, r)
    textos = {c["nombre"]: c["texto"] for c in inf["cierres"]}
    v.check("cada cierre dice qué quedó o por qué se cayó",
            textos == {"Hecho": "El portal en línea", "Caído": "Sin presupuesto"}, textos)
    v.check("los cerrados no cuentan como activos", r["proyectos_activos"] == 0, r)


def test_el_area_filtra_sin_inflar_la_plata(entorno, v):
    p = _proyecto(entorno, "Compartido", area="TICS", participantes=["Calidad"],
                  inicio=_dia(8, 1), fin=_dia(12, 1))
    _tarea(entorno, p, "De Calidad", vence=_dia(9, 10), entregada=_dia(9, 9), area="Calidad", asignado="calidad")
    _tarea(entorno, p, "De TICS", vence=_dia(9, 11), asignado="tics")
    db = entorno.Session()
    item = ItemPresupuesto(proyecto_id=p, concepto="Licencias", valor_unitario=1000, cantidad=1,
                           valor_aprobado=1000, aprobado_en=_dia(9, 3))
    db.add(item)
    db.flush()
    db.add(PagoItem(item_id=item.id, valor=400, fecha=_dia(9, 5)))
    db.commit()
    db.close()

    inf = _informe(entorno)
    tics, calidad = _fila(inf["por_area"], "TICS"), _fila(inf["por_area"], "Calidad")
    v.check("TICS lo tiene como responsable", tics["proyectos_responsable"] == 1, tics)
    v.check("Calidad como participante", calidad["proyectos_participa"] == 1, calidad)
    v.check("cada área responde por sus compromisos",
            calidad["compromisos"]["a_tiempo"] == 1 and tics["compromisos"]["vencidas"] == 1,
            inf["por_area"])
    pres = inf["presupuesto"]
    v.check("la plata va solo al área responsable",
            [f["area"] for f in pres["por_area"]] == ["TICS"], pres["por_area"])
    v.check("y cuenta lo pagado en el periodo", pres["pagado_periodo"] == 400.0, pres)

    solo_calidad = _informe(entorno, area="Calidad")
    v.check("filtrar por Calidad trae el proyecto donde participa",
            solo_calidad["resumen"]["proyectos_activos"] == 1, solo_calidad["resumen"])
    v.check("y la tabla muestra solo Calidad",
            [f["area"] for f in solo_calidad["por_area"]] == ["Calidad"], solo_calidad["por_area"])
    v.check("el selector sigue ofreciendo las dos",
            solo_calidad["alcance"]["areas_disponibles"] == ["Calidad", "TICS"], solo_calidad["alcance"])


def test_cada_quien_ve_lo_suyo(entorno, v):
    suyo = _proyecto(entorno, "Con Logi", area="TICS")
    _tarea(entorno, suyo, "De Logi", vence=_dia(9, 10), asignado="logistica")
    _tarea(entorno, suyo, "De Tico", vence=_dia(9, 10), asignado="tics")
    ajeno = _proyecto(entorno, "De Calidad", area="Calidad", lider="calidad")
    _tarea(entorno, ajeno, "De Cali", vence=_dia(9, 10), asignado="calidad")
    _agregar(entorno, ItemPresupuesto(proyecto_id=suyo, concepto="X", valor_unitario=500, cantidad=1))

    entorno.como("gerencia")
    inf = _informe(entorno)
    v.check("gerencia ve toda la empresa", inf["alcance"]["toda_empresa"]
            and inf["resumen"]["proyectos_activos"] == 2, inf["alcance"])
    v.check("y a todas las personas",
            {p["nombre"] for p in inf["personas"]} == {"Logi", "Tico", "Cali"}, inf["personas"])

    entorno.como("logistica")
    inf = _informe(entorno)
    v.check("un agente ve solo donde participa", inf["resumen"]["proyectos_activos"] == 1, inf["resumen"])
    v.check("sin la tabla por persona", inf["personas"] is None and not inf["alcance"]["ve_personas"],
            inf["alcance"])
    v.check("ni la plata de un proyecto que no lidera", inf["presupuesto"] is None, inf["presupuesto"])

    entorno.como("tics")
    inf = _informe(entorno)
    v.check("un líder ve la tabla de su gente, no la de otras áreas",
            {p["nombre"] for p in inf["personas"]} == {"Tico"}, inf["personas"])
    v.check("y la plata del proyecto que lidera", inf["presupuesto"]["planeado"] == 500.0, inf["presupuesto"])


def test_proyectos_quietos_y_en_riesgo(entorno, v):
    quieto = _proyecto(entorno, "Quieto", creado=_dia(7, 1), inicio=_dia(7, 1), fin=_dia(9, 1))
    _tarea(entorno, quieto, "Vieja", creada=_dia(7, 1))
    nuevo = _proyecto(entorno, "Nuevo", creado=_dia(9, 15))

    inf = _informe(entorno)
    v.check("el que no se movió en el periodo sale como quieto",
            [q["id"] for q in inf["quietos"]] == [quieto], inf["quietos"])
    v.check("el creado en el periodo no", nuevo not in [q["id"] for q in inf["quietos"]])
    v.check("cuenta como nuevo", inf["resumen"]["nuevos"] == 1, inf["resumen"])
    riesgo = next((r for r in inf["en_riesgo"] if r["id"] == quieto), None)
    v.check("vencido y quieto: en riesgo alto", riesgo and riesgo["salud"] == "rojo", inf["en_riesgo"])
    v.check("con los motivos escritos por el servidor",
            riesgo and any("Debía entregarse" in m for m in riesgo["motivos"])
            and "Sin movimiento en el periodo" in riesgo["motivos"], riesgo)


def test_actividades_diarias_del_periodo(entorno, v):
    db = entorno.Session()
    a = ActividadDiaria(tenant_id=entorno.tenant_id, titulo="Ronda", asignado_a=entorno.ids["tics"],
                        area="TICS", frecuencia="semanal", dias_semana="1", desde=date(2026, 9, 1))
    db.add(a)
    db.flush()
    # Lunes de septiembre de 2026: 7, 14, 21 y 28. Se registraron dos.
    db.add_all([ActividadRegistro(actividad_id=a.id, fecha=date(2026, 9, 7)),
                ActividadRegistro(actividad_id=a.id, fecha=date(2026, 9, 21))])
    db.commit()
    db.close()

    inf = _informe(entorno)
    act = inf["actividades"]
    v.check("cuatro esperadas, dos registradas", (act["esperados"], act["cumplidos"]) == (4, 2), act)
    v.check("la lista de las menos cumplidas la trae", act["menos_cumplidas"][0]["pct"] == 50.0, act)
    v.check("y la tabla por área la suma", _fila(inf["por_area"], "TICS")["actividades_pct"] == 50.0,
            inf["por_area"])


def test_periodo_invalido_dice_que_hacer(entorno, v):
    r = entorno.get("/master-planner/informe", params={"desde": "2026-09-30", "hasta": "2026-09-01"})
    v.check("400 con el motivo", r.status_code == 400 and "Revisa el periodo" in r.json()["detail"], r.text)


def test_el_periodo_se_nombra_como_en_un_comite(entorno, v):
    from app.core.periodos import etiqueta_periodo
    v.check("un mes", etiqueta_periodo(date(2026, 9, 1), date(2026, 9, 30)) == "Septiembre de 2026")
    v.check("un trimestre cerrado", etiqueta_periodo(date(2026, 7, 1), date(2026, 9, 30)) == "Tercer trimestre de 2026")
    v.check("el cuarto", etiqueta_periodo(date(2025, 10, 1), date(2025, 12, 31)) == "Cuarto trimestre de 2025")
    v.check("un año", etiqueta_periodo(date(2025, 1, 1), date(2025, 12, 31)) == "Año 2025")
    v.check("lo demás, con fechas",
            etiqueta_periodo(date(2026, 7, 1), date(2026, 9, 29)).startswith("Del 1 de julio"))
    inf = _informe(entorno, desde="2026-07-01", hasta="2026-09-30")
    v.check("y se compara con el trimestre anterior, no con los mismos días hacia atrás",
            inf["periodo"]["anterior"]["etiqueta"] == "Segundo trimestre de 2026", inf["periodo"])


def test_contra_que_se_compara(entorno, v):
    from app.core.periodos import periodo_anterior as ant
    d = date
    v.check("septiembre contra agosto completo", ant(d(2026, 9, 1), d(2026, 9, 30)) == (d(2026, 8, 1), d(2026, 8, 31)))
    v.check("marzo contra febrero completo", ant(d(2026, 3, 1), d(2026, 3, 31)) == (d(2026, 2, 1), d(2026, 2, 28)))
    v.check("lo que va de octubre contra el mismo tramo de septiembre",
            ant(d(2026, 10, 1), d(2026, 10, 21)) == (d(2026, 9, 1), d(2026, 9, 21)))
    v.check("del 1 al 31 de marzo en curso no inventa el 31 de febrero",
            ant(d(2026, 3, 1), d(2026, 3, 30)) == (d(2026, 2, 1), d(2026, 2, 28)))
    v.check("el tercer trimestre contra el segundo", ant(d(2026, 7, 1), d(2026, 9, 30)) == (d(2026, 4, 1), d(2026, 6, 30)))
    v.check("lo que va del cuarto contra el mismo tramo del tercero",
            ant(d(2026, 10, 1), d(2026, 11, 15)) == (d(2026, 7, 1), d(2026, 8, 15)))
    v.check("el primer trimestre contra el cuarto del año pasado",
            ant(d(2026, 1, 1), d(2026, 3, 31)) == (d(2025, 10, 1), d(2025, 12, 31)))
    v.check("un año contra el anterior", ant(d(2026, 1, 1), d(2026, 12, 31)) == (d(2025, 1, 1), d(2025, 12, 31)))
    v.check("lo que va del año contra el mismo tramo del anterior",
            ant(d(2026, 1, 1), d(2026, 10, 21)) == (d(2025, 1, 1), d(2025, 10, 21)))
    v.check("un rango suelto, con el del mismo largo pegado antes",
            ant(d(2026, 9, 10), d(2026, 9, 23)) == (d(2026, 8, 27), d(2026, 9, 9)))
