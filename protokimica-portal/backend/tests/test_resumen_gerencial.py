"""
Historial de cambios, presupuesto ejecutado y resumen gerencial.

Corre contra la API real con TestClient. El fixture `entorno` monta un portal
limpio con usuarios de todos los roles; `v` acumula las comprobaciones y las
reporta todas juntas si algo falla.
"""
from datetime import datetime, timedelta, timezone

from app.models.pqrs import PQRSSolicitud  # noqa: F401
from app.models.user import User  # noqa: F401


def test_resumen_gerencial(entorno, v):
    portal = entorno
    hoy = datetime.now(timezone.utc)
    def en(dias, horas=0):
        return (hoy + timedelta(days=dias, hours=horas)).isoformat()

    # ── Historial de proyecto ──
    P = portal.post("/master-planner/proyectos", json={
        "nombre": "Portal Web", "area": "TICS", "lider_id": portal.ids["admin"],
        "fecha_inicio": en(-30), "fecha_fin_estimada": en(30),
    }).json()["id"]

    h = portal.get(f"/master-planner/proyectos/{P}/historial").json()
    v.check("crear proyecto no genera historial", h == [], h)

    portal.patch(f"/master-planner/proyectos/{P}", json={"fecha_fin_estimada": en(60)})
    h = portal.get(f"/master-planner/proyectos/{P}/historial").json()
    v.check("mover la fecha deja registro", len(h) == 1, h)
    e = h[0]
    v.check("registra el campo correcto", e["campo"] == "fecha_fin_estimada", e)
    v.check("guarda el valor anterior", e["valor_anterior"] is not None, e)
    v.check("guarda el valor nuevo", e["valor_nuevo"] is not None, e)
    v.check("registra quién lo hizo", e["usuario_nombre"] == "Admin", e)
    v.check("guarda el nombre de la entidad", e["entidad_nombre"] == "Portal Web", e)
    v.check("marca la entidad como proyecto", e["entidad"] == "proyecto", e)

    portal.patch(f"/master-planner/proyectos/{P}", json={"nombre": "Portal Web"})
    v.check("guardar sin cambios reales no ensucia el historial",
          len(portal.get(f"/master-planner/proyectos/{P}/historial").json()) == 1)

    portal.patch(f"/master-planner/proyectos/{P}", json={"lider_id": portal.ids["calidad"], "prioridad": "alta"})
    h = portal.get(f"/master-planner/proyectos/{P}/historial").json()
    v.check("dos cambios a la vez dejan dos registros", len(h) == 3, len(h))
    lider = next(x for x in h if x["campo"] == "lider_id")
    v.check("el responsable se guarda por nombre, no por id", lider["valor_nuevo"] == "Cali", lider)
    v.check("y el anterior también", lider["valor_anterior"] == "Admin", lider)

    portal.patch(f"/master-planner/proyectos/{P}", json={"objetivo": "Un objetivo bastante largo " * 20})
    texto = next(x for x in portal.get(f"/master-planner/proyectos/{P}/historial").json()
                 if x["campo"] == "objetivo")
    v.check("los textos largos se registran sin volcar el contenido",
          texto["valor_nuevo"] is None and texto["valor_anterior"] is None, texto)

    # ── Historial de tarea ──
    T = portal.post(f"/master-planner/proyectos/{P}/tareas", json={
        "titulo": "Migrar base de datos", "asignado_a": portal.ids["calidad"], "fecha_fin": en(5),
    }).json()["id"]

    portal.patch(f"/master-planner/tareas/{T}", json={"fecha_fin": en(20), "estado": "en_proceso"})
    ht = portal.get(f"/master-planner/tareas/{T}/historial").json()
    v.check("la tarea registra sus cambios", len(ht) == 2, ht)
    v.check("todos apuntan a la tarea", all(x["entidad"] == "tarea" and x["entidad_id"] == T for x in ht), ht)

    hp = portal.get(f"/master-planner/proyectos/{P}/historial").json()
    v.check("el historial del proyecto incluye el de sus tareas",
          any(x["entidad"] == "tarea" for x in hp), [x["entidad"] for x in hp])
    hp_solo = portal.get(f"/master-planner/proyectos/{P}/historial?solo_proyecto=true").json()
    v.check("solo_proyecto=true excluye las tareas",
          all(x["entidad"] == "proyecto" for x in hp_solo), [x["entidad"] for x in hp_solo])

    # ── fecha_completada y cumplimiento ──
    tarea = portal.get(f"/master-planner/tareas/{T}").json()
    v.check("una tarea abierta no tiene fecha de cierre", tarea["fecha_completada"] is None, tarea)

    portal.patch(f"/master-planner/tareas/{T}", json={"estado": "completada"})
    tarea = portal.get(f"/master-planner/tareas/{T}").json()
    v.check("completar sella la fecha de cierre", tarea["fecha_completada"] is not None, tarea)

    portal.patch(f"/master-planner/tareas/{T}", json={"estado": "en_proceso"})
    v.check("reabrir limpia la fecha de cierre",
          portal.get(f"/master-planner/tareas/{T}").json()["fecha_completada"] is None)
    portal.patch(f"/master-planner/tareas/{T}", json={"estado": "completada"})

    # Llegar al 100% desde una actualización también debe cerrar y quedar en historial
    T2 = portal.post(f"/master-planner/proyectos/{P}/tareas", json={
        "titulo": "Pruebas QA", "asignado_a": portal.ids["calidad"], "fecha_fin": en(-3),
    }).json()["id"]
    portal.post(f"/master-planner/tareas/{T2}/actualizaciones", data={"avance_pct_nuevo": "100"})
    t2 = portal.get(f"/master-planner/tareas/{T2}").json()
    v.check("llegar al 100% completa la tarea", t2["estado"] == "completada", t2)
    v.check("y sella la fecha de cierre", t2["fecha_completada"] is not None, t2)
    v.check("y queda registrado en el historial",
          any(x["campo"] == "estado" for x in portal.get(f"/master-planner/tareas/{T2}/historial").json()))

    # ── Presupuesto: aprobar y pagar ──
    # El flujo detallado se prueba en test_pagos.py; aqui solo lo necesario
    # para que el resumen tenga cifras de plata que agregar.
    I = portal.post(f"/master-planner/proyectos/{P}/presupuesto", json={
        "concepto": "Licencias", "valor_unitario": 1000000, "cantidad": 4,
    }).json()
    v.check("crear ítem calcula el total", I["valor_total"] == 4000000, I)
    v.check("arranca sin aprobar", I["esta_aprobado"] is False, I)
    v.check("y sin pagar", I["valor_pagado"] == 0, I)

    r = portal.patch(f"/master-planner/presupuesto/{I['id']}/aprobar",
                     json={"valor_aprobado": 4000000})
    v.check("aprobar -> 200", r.status_code == 200, r.text[:150])

    r = portal.post(f"/master-planner/presupuesto/{I['id']}/pagos", data={"valor": 2500000})
    v.check("registrar pago -> 201", r.status_code == 201, r.text[:150])

    proy = portal.get(f"/master-planner/proyectos/{P}").json()
    v.check("el proyecto suma lo planeado", proy["presupuesto_total"] == 4000000, proy)
    v.check("el proyecto suma lo pagado", proy["presupuesto_pagado"] == 2500000, proy)
    v.check("y lo que queda pendiente", proy["presupuesto_pendiente"] == 1500000, proy)

    hpres = [x for x in portal.get(f"/master-planner/proyectos/{P}/historial").json()
             if "presupuesto" in x["campo"] or "pago" in x["campo"]]
    v.check("agregar, aprobar y pagar quedan en el historial", len(hpres) == 3, hpres)

    # ── Resumen gerencial ──
    # Segundo proyecto, otra área, atrasado
    P2 = portal.post("/master-planner/proyectos", json={
        "nombre": "Auditoría ISO", "area": "Calidad", "estado": "en_ejecucion",
        "fecha_inicio": en(-80), "fecha_fin_estimada": en(-10),
    }).json()["id"]
    I2 = portal.post(f"/master-planner/proyectos/{P2}/presupuesto", json={
        "concepto": "Consultoría", "valor_unitario": 2000000, "cantidad": 1,
    }).json()["id"]
    portal.patch(f"/master-planner/presupuesto/{I2}/aprobar", json={"valor_aprobado": 2000000})
    portal.post(f"/master-planner/presupuesto/{I2}/pagos", data={"valor": 500000})
    T3 = portal.post(f"/master-planner/proyectos/{P2}/tareas", json={
        "titulo": "Levantar hallazgos", "asignado_a": portal.ids["calidad"], "prioridad": "critica", "fecha_fin": en(-2),
    }).json()["id"]
    portal.post(f"/master-planner/proyectos/{P2}/tareas", json={"titulo": "Sin responsable"})
    portal.post(f"/master-planner/tareas/{T3}/subtareas", json={
        "titulo": "Revisar procedimiento", "asignado_a": portal.ids["calidad"], "fecha_fin": en(-1),
    })

    res = portal.get("/master-planner/resumen")
    v.check("el resumen responde 200", res.status_code == 200, res.text)
    res = res.json()

    k = res["kpis"]
    v.check("cuenta los proyectos", k["proyectos_total"] == 2, k)
    v.check("cuenta las tareas abiertas", k["tareas_abiertas"] == 2, k)
    v.check("cuenta alta prioridad", k["tareas_alta_prioridad"] == 1, k)
    v.check("cuenta las vencidas", k["tareas_vencidas"] == 1, k)
    v.check("cuenta las sin asignar", k["tareas_sin_asignar"] == 1, k)
    v.check("las subtareas no inflan el conteo de tareas", k["tareas_total"] == 4, k)
    v.check("ni el de vencidas", k["tareas_vencidas"] == 1, k)

    p = res["presupuesto"]
    v.check("suma el planeado de todos los proyectos", p["planeado"] == 6000000, p)
    v.check("suma el ejecutado", p["ejecutado"] == 3000000, p)
    v.check("calcula el disponible", p["disponible"] == 3000000, p)
    v.check("calcula el % de ejecución", p["ejecucion_pct"] == 50.0, p)

    areas = {a["area"]: a for a in res["presupuesto_por_area"]}
    v.check("desglosa por área", set(areas) == {"TICS", "Calidad"}, list(areas))
    v.check("TI planeado correcto", areas["TICS"]["planeado"] == 4000000, areas["TICS"])
    v.check("Calidad ejecución 25%", areas["Calidad"]["ejecucion_pct"] == 25.0, areas["Calidad"])
    v.check("marca si un área se pasó", areas["TICS"]["sobrepasado"] is False, areas["TICS"])
    v.check("las áreas vienen de mayor a menor", [a["area"] for a in res["presupuesto_por_area"]] == ["TICS", "Calidad"])
    v.check("la participación suma 100", round(sum(a["participacion_pct"] for a in res["presupuesto_por_area"])) == 100)

    proyectos = {x["nombre"]: x for x in res["proyectos"]}
    iso = proyectos["Auditoría ISO"]
    v.check("el proyecto con plazo vencido sale en rojo", iso["salud"] == "rojo", iso)
    v.check("calcula el plazo consumido", iso["plazo_consumido_pct"] > 100, iso)
    v.check("cuenta las tareas vencidas del proyecto", iso["tareas_vencidas"] == 1, iso)
    web = proyectos["Portal Web"]
    v.check("cuenta las replanificaciones", web["replanificaciones"] == 1, web)
    v.check("cuenta los días aplazados", web["dias_aplazados"] == 30, web)
    v.check("los proyectos en riesgo van primero", res["proyectos"][0]["salud"] in ("rojo", "amarillo"))
    v.check("el KPI de riesgo concuerda con la tabla",
          k["proyectos_en_riesgo"] == sum(1 for x in res["proyectos"] if x["salud"] in ("rojo", "amarillo")), k)

    carga = {x["nombre"]: x for x in res["carga_por_persona"]}
    v.check("Ana aparece en la carga", "Cali" in carga, list(carga))
    v.check("cuenta sus tareas activas sin contar subtareas",
          carga["Cali"]["activas"] == 1, carga.get("Cali"))
    v.check("cuenta sus vencidas", carga["Cali"]["vencidas"] == 1, carga.get("Cali"))
    v.check("las sin asignar no entran en la carga de nadie",
          sum(x["activas"] for x in res["carga_por_persona"]) == k["tareas_abiertas"] - k["tareas_sin_asignar"])

    cumpl = {x["area"]: x for x in res["cumplimiento_por_area"]}
    v.check("hay cumplimiento por área", len(cumpl) >= 1, list(cumpl))
    v.check("T2 se cerró tarde y cuenta como tarde",
          sum(x["tarde"] for x in res["cumplimiento_por_area"]) == 1, res["cumplimiento_por_area"])
    v.check("T se cerró a tiempo",
          sum(x["a_tiempo"] for x in res["cumplimiento_por_area"]) == 1, res["cumplimiento_por_area"])
    v.check("el cumplimiento global es 50%", k["cumplimiento_pct"] == 50.0, k)

    # ── Filtro por área y proyectos archivados ──
    solo_ti = portal.get("/master-planner/resumen?area=TICS").json()
    v.check("filtrar por área deja un solo proyecto", solo_ti["kpis"]["proyectos_total"] == 1, solo_ti["kpis"])
    v.check("y solo su presupuesto", solo_ti["presupuesto"]["planeado"] == 4000000, solo_ti["presupuesto"])
    v.check("las áreas disponibles no se filtran", set(solo_ti["areas_disponibles"]) == {"TICS", "Calidad"}, solo_ti["areas_disponibles"])

    portal.patch(f"/master-planner/proyectos/{P2}", json={"archivado": True})
    res2 = portal.get("/master-planner/resumen").json()
    v.check("un proyecto archivado sale del resumen", res2["kpis"]["proyectos_total"] == 1, res2["kpis"])
    v.check("y su presupuesto también", res2["presupuesto"]["planeado"] == 4000000, res2["presupuesto"])
    portal.patch(f"/master-planner/proyectos/{P2}", json={"archivado": False})

    # ── Actividad reciente y borrado ──
    g = portal.get("/master-planner/historial?limite=5").json()
    v.check("la actividad reciente responde", len(g) == 5, len(g))
    v.check("viene de la más nueva a la más vieja",
          [x["fecha"] for x in g] == sorted([x["fecha"] for x in g], reverse=True))
    v.check("se puede filtrar por campo",
          all(x["campo"] == "fecha_fin_estimada"
              for x in portal.get("/master-planner/historial?campo=fecha_fin_estimada").json()))

    # Borrar un proyecto con historial no debe reventar contra la llave foránea
    PV = portal.post("/master-planner/proyectos", json={"nombre": "Desechable"}).json()["id"]
    portal.patch(f"/master-planner/proyectos/{PV}", json={"prioridad": "alta"})
    v.check("el proyecto desechable tiene historial",
          len(portal.get(f"/master-planner/proyectos/{PV}/historial").json()) == 1)
    r = portal.delete(f"/master-planner/proyectos/{PV}")
    v.check("borrar un proyecto con historial funciona -> 204", r.status_code == 204, r.text)

    # Borrar una tarea no debe borrar su rastro del proyecto
    antes_h = len(portal.get(f"/master-planner/proyectos/{P}/historial").json())
    portal.delete(f"/master-planner/tareas/{T2}")
    despues_h = portal.get(f"/master-planner/proyectos/{P}/historial").json()
    v.check("el historial de una tarea borrada sobrevive en el proyecto",
          len(despues_h) == antes_h, f"{antes_h} -> {len(despues_h)}")
    v.check("y conserva el nombre que tenía la tarea",
          any(x["entidad_nombre"] == "Pruebas QA" for x in despues_h))


