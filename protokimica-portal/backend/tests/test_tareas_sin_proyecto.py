"""
Tareas sin proyecto (desde la 0.70).

Una tarea suelta —el cierre contable del mes, un documento que se aprueba— no
tiene por qué inventarse un proyecto. Lo que se prueba:

- sin proyecto el área es obligatoria, y tiene que ser una del catálogo;
- la ven quien la creó, su responsable, quien firma su documento y el líder
  del área (o quien la supervisa); un agente del área, no;
- aparece en la lista, en «mis tareas», en el resumen y en los indicadores
  del área, con el mismo número en todos lados;
- el documento se aprueba igual que el de una tarea con proyecto.
"""
from datetime import datetime, timedelta, timezone

from app.models.user import User


def _lider_de_logistica(portal):
    db = portal.Session()
    u = User(tenant_id=portal.tenant_id, nombre="Lidia", email="lidia@p.com",
             password_hash="x", rol="lider", area="Logística", activo=True)
    otro = User(tenant_id=portal.tenant_id, nombre="Otro", email="otro@p.com",
                password_hash="x", rol="agente", area="Logística", activo=True)
    db.add_all([u, otro])
    db.commit()
    portal.ids["lider_logistica"] = u.id
    portal.ids["otro_logistica"] = otro.id
    db.close()


def _suelta(portal, **extra):
    datos = {"titulo": "Cierre contable de octubre", "area": "Logística",
             "asignado_a": portal.ids["logistica"], **extra}
    return portal.post("/master-planner/tareas", json=datos)


def test_sin_proyecto_el_area_es_obligatoria(entorno, v):
    portal = entorno
    r = portal.post("/master-planner/tareas", json={"titulo": "Sin área"})
    v.check("sin proyecto y sin área responde 400", r.status_code == 400, r.text)
    v.check("y dice por qué", "área" in r.text, r.text)
    r = _suelta(portal, area="Inventada")
    v.check("un área que no existe tampoco", r.status_code == 400, r.text)

    r = _suelta(portal)
    v.check("con área se crea", r.status_code == 201, r.text)
    tarea = r.json()
    v.check("sin proyecto", tarea["proyecto_id"] is None and tarea["proyecto_nombre"] is None, tarea)

    r = portal.patch(f"/master-planner/tareas/{tarea['id']}", json={"area": None})
    v.check("tampoco se le quita el área después", r.status_code == 400, r.text)
    r = portal.patch(f"/master-planner/tareas/{tarea['id']}", json={"titulo": "Cierre de octubre"})
    v.check("lo demás se edita como siempre", r.status_code == 200, r.text)

    sub = portal.post(f"/master-planner/tareas/{tarea['id']}/subtareas", json={"titulo": "Conciliar bancos"})
    v.check("una subtarea hereda que no tiene proyecto",
            sub.status_code == 201 and sub.json()["proyecto_id"] is None, sub.text)
    rep = portal.post(f"/master-planner/tareas/{tarea['id']}/repetir", json={})
    v.check("y se repite sin proyecto", rep.status_code == 201 and rep.json()["proyecto_id"] is None, rep.text)

    # Por la ruta nueva también se crea con proyecto.
    P = portal.post("/master-planner/proyectos", json={"nombre": "Con proyecto"}).json()["id"]
    r = portal.post("/master-planner/tareas", json={"titulo": "Dentro", "proyecto_id": P})
    v.check("con proyecto el área no hace falta", r.status_code == 201 and r.json()["proyecto_id"] == P, r.text)


def test_quien_ve_una_tarea_sin_proyecto(entorno, v):
    portal = entorno
    _lider_de_logistica(portal)
    portal.como("calidad")
    T = _suelta(portal).json()["id"]
    portal.como("admin")
    ajena = _suelta(portal, titulo="De otro", asignado_a=portal.ids["otro_logistica"]).json()["id"]

    def ve(quien, tid):
        portal.como(quien)
        abre = portal.get(f"/master-planner/tareas/{tid}").status_code == 200
        lista = tid in [t["id"] for t in portal.get("/master-planner/tareas").json()]
        assert abre == lista, f"{quien}: abrirla ({abre}) y verla en la lista ({lista}) no coinciden"
        return abre

    v.check("quien la creó la ve, aunque sea de otra área", ve("calidad", T))
    v.check("su responsable la ve", ve("logistica", T))
    v.check("el líder del área la ve", ve("lider_logistica", T))
    v.check("el líder del área ve también la de otro de su equipo", ve("lider_logistica", ajena))
    v.check("un agente del área NO ve la de un compañero", not ve("logistica", ajena))
    v.check("el líder de otra área no", not ve("tics", T))
    v.check("lectura de otra área no", not ve("lectura", T))
    v.check("gerencia ve todas", ve("gerencia", T) and ve("gerencia", ajena))

    portal.como("logistica")
    v.check("le sale en «mis tareas»",
            T in [t["id"] for t in portal.get("/master-planner/tareas/mias").json()])
    v.check("y se puede pedir solo lo que no tiene proyecto",
            all(t["proyecto_id"] is None for t in portal.get("/master-planner/tareas?sin_proyecto=true").json()))


def test_cuenta_en_el_resumen_y_en_los_indicadores_del_area(entorno, v):
    from app.modules.master_planner import fuentes_indicador as fi

    portal = entorno
    ayer = datetime.now(timezone.utc) - timedelta(days=1)
    T = _suelta(portal, fecha_fin=ayer.isoformat()).json()["id"]

    resumen = portal.get("/master-planner/resumen?area=Logística").json()["kpis"]
    v.check("vencida, cuenta en el resumen de su área", resumen["tareas_vencidas"] == 1, resumen)
    v.check("y no en el de otra", portal.get("/master-planner/resumen?area=TICS").json()["kpis"]["tareas_vencidas"] == 0)

    portal.patch(f"/master-planner/tareas/{T}", json={"estado": "completada"})
    hoy = datetime.now(timezone.utc)
    db = portal.Session()
    r = fi.mp_cumplimiento_fechas(db, portal.tenant_id, hoy.year, hoy.month, area="Logística")
    v.check("completada tarde, cuenta en el cumplimiento de su área",
            (r.numerador, r.denominador) == (0, 1), r)
    r = fi.mp_cumplimiento_fechas(db, portal.tenant_id, hoy.year, hoy.month, area="TICS")
    v.check("y no en el de otra área", r.denominador == 0, r)
    db.close()

    informe = portal.get("/master-planner/informe").json()
    v.check("el informe la trae", informe is not None)


def test_el_documento_de_una_tarea_sin_proyecto_se_aprueba_igual(entorno, tmp_path, monkeypatch, v):
    from app.core.config import settings

    monkeypatch.setattr(settings, "DOCUMENTOS_DIR", str(tmp_path))
    portal = entorno
    plantilla = next(p for p in portal.get("/master-planner/plantillas-revision").json()
                     if p["nombre"] == "Revisión contable")
    r = _suelta(portal, fecha_fin=datetime.now(timezone.utc).isoformat(), revision={
        "plantilla_id": plantilla["id"], "revisores": [portal.ids["calidad"], portal.ids["tics"]],
    })
    v.check("nace sin proyecto y con su flujo", r.status_code == 201 and r.json()["requiere_revision"], r.text)
    T = r.json()["id"]

    portal.como("tics")
    v.check("quien firma la abre aunque no sea de su área",
            portal.get(f"/master-planner/tareas/{T}").status_code == 200)

    portal.como("logistica")
    portal.post(f"/master-planner/tareas/{T}/documentos",
                files={"archivo": ("estados.pdf", b"%PDF-1.4\n%%EOF\n", "application/pdf")})
    vid = portal.post(f"/master-planner/tareas/{T}/documentos/enviar", json={}).json()["versiones"][0]["id"]

    portal.como("admin")
    grupos = {g["email"]: g for g in portal.get("/master-planner/revisiones/por-vencer").json()["destinatarios"]}
    v.check("el recordatorio la trae, a quien firma",
            [d["tarea_id"] for d in grupos.get("calidad@p.com", {}).get("documentos", [])] == [T], grupos)

    for quien in ("calidad", "tics"):
        portal.como(quien)
        v.check(f"{quien} encuentra el documento en su bandeja",
                vid in [f["version"]["id"] for f in portal.get("/master-planner/revisiones/pendientes").json()["por_revisar"]])
        r = portal.post(f"/master-planner/documentos/{vid}/responder", json={"decision": "aprobar"})
        v.check(f"{quien} firma", r.status_code == 200, r.text)
    portal.como("admin")
    v.check("con la última firma queda cumplida",
            portal.get(f"/master-planner/tareas/{T}").json()["estado"] == "completada")
