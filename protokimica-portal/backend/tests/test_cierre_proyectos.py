"""
Cierre de proyectos: finalizar, cancelar y retomar.

Lo que se prueba son las decisiones, no el CRUD: que cancelar exija un
motivo, que los números del acta queden congelados, que cancelar no borre
nada y que retomar deje rastro de lo que pasó.
"""


def _crear_proyecto(portal, nombre="Planta nueva", lider=None):
    payload = {"nombre": nombre, "area": "TICS", "estado": "en_ejecucion"}
    if lider is not None:
        payload["lider_id"] = lider
    r = portal.post("/master-planner/proyectos", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def _cerrar(portal, proyecto_id, **datos):
    return portal.post(f"/master-planner/proyectos/{proyecto_id}/cerrar", data=datos)


# ── Finalizar ────────────────────────────────────────────────────────────

def test_finalizar_deja_acta_con_entregables(entorno, v):
    portal = entorno
    p = _crear_proyecto(portal)

    r = _cerrar(portal, p["id"], tipo="finalizado",
                entregables="Manual de operación y capacitación al personal",
                observaciones="Quedó pendiente la señalización")
    v.check("responde 200", r.status_code == 200, r.text[:200])

    acta = r.json()
    v.check("el acta es de finalización", acta["tipo"] == "finalizado", acta)
    v.check("guarda los entregables",
            "Manual de operación" in acta["entregables"], acta)
    v.check("y las observaciones",
            "señalización" in acta["observaciones"], acta)
    v.check("registra quién cerró", acta["cerrado_por_nombre"] is not None, acta)
    v.check("nace vigente", acta["vigente"] is True, acta)


def test_al_finalizar_el_proyecto_queda_cerrado_y_archivado(entorno, v):
    portal = entorno
    p = _crear_proyecto(portal)
    _cerrar(portal, p["id"], tipo="finalizado", entregables="Listo")

    r = portal.get(f"/master-planner/proyectos/{p['id']}").json()
    v.check("el estado es cerrado", r["estado"] == "cerrado", r["estado"])
    v.check("se archiva: sale de las vistas del día a día",
            r["archivado"] is True, r["archivado"])
    v.check("se sella la fecha de fin", r["fecha_fin_real"] is not None, r)
    v.check("y se puede saber cómo terminó",
            r["cierre_tipo"] == "finalizado", r.get("cierre_tipo"))


def test_el_acta_congela_los_numeros(entorno, v):
    """
    Un acta dice lo que era verdad el día que se firmó. Si los números se
    recalcularan, corregir un pago viejo cambiaría un acta de hace un año.
    """
    portal = entorno
    p = _crear_proyecto(portal)

    portal.post(f"/master-planner/proyectos/{p['id']}/presupuesto", json={
        "concepto": "Equipos", "valor_unitario": 1000000, "cantidad": 2,
    })
    portal.post(f"/master-planner/proyectos/{p['id']}/tareas", json={"titulo": "Comprar"})

    acta = _cerrar(portal, p["id"], tipo="finalizado", entregables="ok").json()
    v.check("guarda el presupuesto planeado del momento",
            acta["resumen"]["presupuesto_planeado"] == 2000000, acta["resumen"])
    v.check("y el conteo de tareas",
            acta["resumen"]["tareas_total"] == 1, acta["resumen"])

    # Se agrega presupuesto DESPUÉS de cerrar: el acta no puede moverse.
    portal.post(f"/master-planner/proyectos/{p['id']}/presupuesto", json={
        "concepto": "Extra", "valor_unitario": 500000, "cantidad": 1,
    })
    actas = portal.get(f"/master-planner/proyectos/{p['id']}/cierres").json()
    v.check("el acta sigue diciendo lo mismo",
            actas[0]["resumen"]["presupuesto_planeado"] == 2000000,
            actas[0]["resumen"])


# ── Cancelar ─────────────────────────────────────────────────────────────

def test_cancelar_exige_motivo(entorno, v):
    portal = entorno
    p = _crear_proyecto(portal)

    r = _cerrar(portal, p["id"], tipo="cancelado")
    v.check("sin motivo se rechaza", r.status_code == 400, r.status_code)
    v.check("y explica por qué hace falta",
            "explicar por qué" in r.json()["detail"], r.json())

    r = _cerrar(portal, p["id"], tipo="cancelado",
                motivo="El proveedor incumplió y no hay presupuesto para reemplazarlo")
    v.check("con motivo sí se cancela", r.status_code == 200, r.text[:200])
    v.check("el motivo queda guardado",
            "proveedor incumplió" in r.json()["motivo"], r.json())


def test_cancelar_no_borra_nada(entorno, v):
    portal = entorno
    p = _crear_proyecto(portal)
    portal.post(f"/master-planner/proyectos/{p['id']}/tareas", json={"titulo": "Algo"})

    _cerrar(portal, p["id"], tipo="cancelado", motivo="Se cayó el negocio")

    r = portal.get(f"/master-planner/proyectos/{p['id']}")
    v.check("el proyecto sigue existiendo", r.status_code == 200, r.status_code)
    v.check("marcado como cancelado", r.json()["estado"] == "cancelado", r.json()["estado"])

    tareas = portal.get(f"/master-planner/proyectos/{p['id']}/tareas").json()
    v.check("y sus tareas siguen ahí", len(tareas) == 1, tareas)


def test_un_cancelado_no_aparece_en_la_lista_del_dia_a_dia(entorno, v):
    portal = entorno
    activo = _crear_proyecto(portal, "Sigue vivo")
    muerto = _crear_proyecto(portal, "Se cayó")
    _cerrar(portal, muerto["id"], tipo="cancelado", motivo="Sin presupuesto")

    visibles = [p["nombre"] for p in portal.get("/master-planner/proyectos").json()]
    v.check("el activo sí está", activo["nombre"] in visibles, visibles)
    v.check("el cancelado no", muerto["nombre"] not in visibles, visibles)

    archivados = [p["nombre"] for p in
                  portal.get("/master-planner/proyectos", params={"archivados": True}).json()]
    v.check("pero se encuentra en archivados", muerto["nombre"] in archivados, archivados)


# ── Retomar ──────────────────────────────────────────────────────────────

def test_retomar_devuelve_el_proyecto_y_anula_el_acta(entorno, v):
    portal = entorno
    p = _crear_proyecto(portal)
    _cerrar(portal, p["id"], tipo="cancelado", motivo="Se aplazó para el otro año")

    r = portal.post(f"/master-planner/proyectos/{p['id']}/retomar")
    v.check("se puede retomar", r.status_code == 200, r.text[:200])

    proyecto = portal.get(f"/master-planner/proyectos/{p['id']}").json()
    v.check("vuelve a ejecución", proyecto["estado"] == "en_ejecucion", proyecto["estado"])
    v.check("y a las vistas del día a día", proyecto["archivado"] is False, proyecto)
    v.check("sin fecha de fin", proyecto["fecha_fin_real"] is None, proyecto)
    v.check("ya no figura cómo terminó", proyecto["cierre_tipo"] is None, proyecto)


def test_retomar_conserva_el_acta_como_historia(entorno, v):
    """
    Es justo lo que alguien busca cuando pregunta "¿este proyecto no se
    había caído?". Borrarla dejaría la pregunta sin respuesta.
    """
    portal = entorno
    p = _crear_proyecto(portal)
    _cerrar(portal, p["id"], tipo="cancelado", motivo="El proveedor se retiró")
    portal.post(f"/master-planner/proyectos/{p['id']}/retomar")

    actas = portal.get(f"/master-planner/proyectos/{p['id']}/cierres").json()
    v.check("el acta sigue existiendo", len(actas) == 1, actas)
    v.check("con su motivo intacto", "proveedor se retiró" in actas[0]["motivo"], actas[0])
    v.check("pero anulada", actas[0]["vigente"] is False, actas[0])
    v.check("y consta quién la anuló",
            actas[0]["anulado_por_nombre"] is not None, actas[0])


def test_no_se_puede_cerrar_dos_veces(entorno, v):
    portal = entorno
    p = _crear_proyecto(portal)
    _cerrar(portal, p["id"], tipo="finalizado", entregables="ok")

    r = _cerrar(portal, p["id"], tipo="finalizado", entregables="otra vez")
    v.check("el segundo cierre se rechaza", r.status_code == 400, r.status_code)
    v.check("y dice qué hacer", "Retomar" in r.json()["detail"], r.json())


def test_no_se_retoma_algo_que_no_esta_cerrado(entorno, v):
    portal = entorno
    p = _crear_proyecto(portal)
    r = portal.post(f"/master-planner/proyectos/{p['id']}/retomar")
    v.check("se rechaza", r.status_code == 400, r.status_code)
    v.check("y lo explica", "no está cerrado" in r.json()["detail"], r.json())


def test_cerrar_y_volver_a_cerrar_deja_las_dos_actas(entorno, v):
    portal = entorno
    p = _crear_proyecto(portal)
    _cerrar(portal, p["id"], tipo="cancelado", motivo="Primera caída")
    portal.post(f"/master-planner/proyectos/{p['id']}/retomar")
    _cerrar(portal, p["id"], tipo="finalizado", entregables="Al final sí salió")

    actas = portal.get(f"/master-planner/proyectos/{p['id']}/cierres").json()
    v.check("quedan las dos", len(actas) == 2, len(actas))
    vigentes = [a for a in actas if a["vigente"]]
    v.check("solo una vigente", len(vigentes) == 1, actas)
    v.check("y es la de finalización", vigentes[0]["tipo"] == "finalizado", vigentes[0])


# ── Permisos ─────────────────────────────────────────────────────────────

def test_quien_ve_el_proyecto_pero_no_lo_lidera_no_puede_cerrarlo(entorno, v):
    """
    Cerrar es afirmar que se cumplió. Le compete a quien responde por el
    proyecto, no a cualquiera que pueda editarlo.

    El proyecto va sin líder y del área de quien prueba: así se ve, se puede
    editar, y aun así el cierre queda fuera de su alcance.
    """
    portal = entorno
    p = _crear_proyecto(portal)          # área TICS, sin líder asignado

    portal.como("tics")                  # es de su área: lo ve y lo edita
    v.check("lo puede ver",
            portal.get(f"/master-planner/proyectos/{p['id']}").status_code == 200)

    r = _cerrar(portal, p["id"], tipo="finalizado", entregables="ok")
    v.check("pero no cerrarlo", r.status_code == 403, r.status_code)
    v.check("y el mensaje dice a quién pedirle",
            "líder del proyecto" in r.json()["detail"], r.json())


def test_el_lider_del_proyecto_si_lo_cierra(entorno, v):
    portal = entorno
    p = _crear_proyecto(portal, lider=portal.ids["tics"])
    portal.como("tics")
    r = _cerrar(portal, p["id"], tipo="finalizado", entregables="ok")
    v.check("su líder sí puede", r.status_code == 200, r.text[:200])


def test_un_lider_de_otra_area_ni_siquiera_lo_encuentra(entorno, v):
    """
    Responde 404 y no 403, como en todo Master Planner: un 403 confirmaría
    que el proyecto existe a quien no debería ni saberlo.
    """
    portal = entorno
    p = _crear_proyecto(portal, lider=portal.ids["tics"])   # área TICS

    portal.como("calidad")
    r = _cerrar(portal, p["id"], tipo="finalizado", entregables="ok")
    v.check("responde 404, no 403", r.status_code == 404, r.status_code)


def test_admin_puede_cerrar_cualquiera(entorno, v):
    portal = entorno
    p = _crear_proyecto(portal, lider=portal.ids["tics"])
    portal.como("admin")
    r = _cerrar(portal, p["id"], tipo="finalizado", entregables="ok")
    v.check("admin cierra proyectos ajenos", r.status_code == 200, r.text[:200])


def test_lectura_no_puede_cerrar(entorno, v):
    portal = entorno
    p = _crear_proyecto(portal)
    portal.como("lectura")
    r = _cerrar(portal, p["id"], tipo="finalizado", entregables="ok")
    v.check("no escribe nada, tampoco cierra", r.status_code == 403, r.status_code)
