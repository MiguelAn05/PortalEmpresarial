"""
Visibilidad por area, proyectos multi-area y el rol de gerencia.

Corre contra la API real con TestClient. El fixture `entorno` monta un portal
limpio con usuarios de todos los roles; `v` acumula las comprobaciones y las
reporta todas juntas si algo falla.
"""
from datetime import datetime, timedelta, timezone

from app.models.pqrs import PQRSSolicitud  # noqa: F401
from app.models.user import User  # noqa: F401


def test_permisos(entorno, v):
    portal = entorno
    hoy = datetime.now(timezone.utc)
    def en(d): return (hoy + timedelta(days=d)).isoformat()

    # ── Datos base, creados como admin ────────────────────────────
    portal.como("admin")
    P_TI = portal.post("/master-planner/proyectos", json={
        "nombre": "Portal Web", "area": "TICS", "fecha_inicio": en(-10), "fecha_fin_estimada": en(20),
    }).json()["id"]
    P_CAL = portal.post("/master-planner/proyectos", json={"nombre": "Auditoría ISO", "area": "Calidad"}).json()["id"]
    P_MIXTO = portal.post("/master-planner/proyectos", json={
        "nombre": "ERP Fase 2", "area": "TICS", "areas_participantes": ["Calidad", "Logística"],
    }).json()
    P_MIX = P_MIXTO["id"]
    P_SIN = portal.post("/master-planner/proyectos", json={"nombre": "Sin clasificar"}).json()["id"]

    portal.post(f"/master-planner/proyectos/{P_TI}/presupuesto", json={
        "concepto": "Licencias", "valor_unitario": 1000000, "cantidad": 4, "valor_ejecutado": 1000000,
    })
    portal.post(f"/master-planner/proyectos/{P_CAL}/presupuesto", json={
        "concepto": "Consultoría", "valor_unitario": 2000000, "cantidad": 1,
    })

    # ── Proyectos multi-área ──
    v.check("guarda las áreas participantes",
          P_MIXTO["areas_participantes"] == ["Calidad", "Logística"], P_MIXTO)
    v.check("areas_involucradas incluye la responsable",
          P_MIXTO["areas_involucradas"] == ["Calidad", "Logística", "TICS"], P_MIXTO)
    v.check("el área responsable sigue siendo una sola", P_MIXTO["area"] == "TICS", P_MIXTO)

    r = portal.patch(f"/master-planner/proyectos/{P_MIX}", json={"areas_participantes": ["Calidad"]}).json()
    v.check("se pueden quitar áreas participantes", r["areas_participantes"] == ["Calidad"], r)
    r = portal.patch(f"/master-planner/proyectos/{P_MIX}", json={"areas_participantes": ["Calidad", "Logística", "TICS"]}).json()
    v.check("el área responsable no se duplica en las participantes",
          r["areas_participantes"] == ["Calidad", "Logística"], r)

    # ── Visibilidad: depende del rol ──
    # Un LÍDER responde por su área: ve lo de su gente aunque no participe
    # personalmente. Un AGENTE solo ve donde le asignaron trabajo.
    portal.como("tics")
    vistos = {p["nombre"] for p in portal.get("/master-planner/proyectos").json()}
    v.check("el líder ve los proyectos de su área", "Portal Web" in vistos, vistos)
    v.check("y aquellos donde su área participa", "ERP Fase 2" in vistos, vistos)
    v.check("pero no un proyecto sin área que no toca nadie de su equipo",
          "Sin clasificar" not in vistos, vistos)
    v.check("ni el de otra área", "Auditoría ISO" not in vistos, vistos)

    # El caso que motivó esto: a alguien que no es jefe le encargan liderar un
    # proyecto de otra área. Su jefe tiene que poder mirarlo.
    portal.como("admin")
    portal.patch(f"/master-planner/proyectos/{P_SIN}",
                 json={"lider_id": portal.ids["logistica"]})
    portal.como("logistica")
    v.check("quien lo lidera lo ve, aunque no sea jefe",
          "Sin clasificar" in {p["nombre"] for p in
                               portal.get("/master-planner/proyectos").json()})

    portal.como("calidad")
    vistos = {p["nombre"] for p in portal.get("/master-planner/proyectos").json()}
    v.check("cada líder ve lo suyo", "Auditoría ISO" in vistos, vistos)
    v.check("y no lo de la otra área", "Portal Web" not in vistos, vistos)

    # ── Acceso directo a un proyecto ajeno ──
    portal.como("calidad")
    v.check("abrir un proyecto de otra área da 404",
          portal.get(f"/master-planner/proyectos/{P_TI}").status_code == 404)
    v.check("su historial también da 404",
          portal.get(f"/master-planner/proyectos/{P_TI}/historial").status_code == 404)
    v.check("sus tareas también dan 404",
          portal.get(f"/master-planner/proyectos/{P_TI}/tareas").status_code == 404)
    v.check("y su presupuesto también",
          portal.get(f"/master-planner/proyectos/{P_TI}/presupuesto").status_code == 404)
    v.check("no puede editarlo",
          portal.patch(f"/master-planner/proyectos/{P_TI}", json={"nombre": "Hackeado"}).status_code == 404)

    # ── Tarea asignada fuera de tu área ──
    portal.como("admin")
    T_CAL = portal.post(f"/master-planner/proyectos/{P_CAL}/tareas", json={
        "titulo": "Revisar hallazgos", "asignado_a": portal.ids["tics"], "fecha_fin": en(5),
    }).json()["id"]

    portal.como("tics")
    vistos = {p["nombre"] for p in portal.get("/master-planner/proyectos").json()}
    v.check("ahora TICS SÍ ve el proyecto de Calidad donde le asignaron algo",
          "Auditoría ISO" in vistos, vistos)
    v.check("puede abrir la tarea asignada",
          portal.get(f"/master-planner/tareas/{T_CAL}").status_code == 200)
    v.check("aparece en sus tareas",
          any(t["id"] == T_CAL for t in portal.get("/master-planner/tareas/mias").json()))
    # Pero el dinero de un área ajena sigue siendo privado
    r = portal.get(f"/master-planner/proyectos/{P_CAL}/presupuesto")
    v.check("pero NO puede ver el presupuesto de ese proyecto ajeno -> 403",
          r.status_code == 403, f"{r.status_code} {r.text[:80]}")

    portal.como("logistica")
    v.check("alguien sin relación con ese proyecto sigue sin verlo",
          portal.get(f"/master-planner/tareas/{T_CAL}").status_code == 404)

    # ── El líder ve su proyecto aunque sea de otra área ──
    portal.como("admin")
    portal.patch(f"/master-planner/proyectos/{P_CAL}", json={"lider_id": portal.ids["logistica"]})
    portal.como("logistica")
    v.check("el líder ve el proyecto que lidera",
          portal.get(f"/master-planner/proyectos/{P_CAL}").status_code == 200)
    v.check("y sí ve su presupuesto",
          portal.get(f"/master-planner/proyectos/{P_CAL}/presupuesto").status_code == 200)

    # ── Rol gerencia: ve todo ──
    portal.como("gerencia")
    vistos = {p["nombre"] for p in portal.get("/master-planner/proyectos").json()}
    v.check("gerencia ve los 4 proyectos", len(vistos) == 4, vistos)
    v.check("gerencia entra a cualquier proyecto",
          portal.get(f"/master-planner/proyectos/{P_CAL}").status_code == 200)
    v.check("gerencia ve cualquier presupuesto",
          portal.get(f"/master-planner/proyectos/{P_TI}/presupuesto").status_code == 200)
    res = portal.get("/master-planner/resumen")
    v.check("gerencia ve el resumen completo", res.status_code == 200 and res.json()["kpis"]["proyectos_total"] == 4,
          res.json().get("kpis"))
    v.check("con el presupuesto de todas las áreas",
          res.json()["presupuesto"]["planeado"] == 6000000, res.json()["presupuesto"])
    v.check("gerencia lee el historial", portal.get("/master-planner/historial").status_code == 200)

    # ── Rol gerencia: no toca nada ──
    v.check("no crea proyectos",
          portal.post("/master-planner/proyectos", json={"nombre": "X"}).status_code == 403)
    v.check("no edita proyectos",
          portal.patch(f"/master-planner/proyectos/{P_TI}", json={"nombre": "X"}).status_code == 403)
    v.check("no borra proyectos",
          portal.delete(f"/master-planner/proyectos/{P_SIN}").status_code == 403)
    v.check("no crea tareas",
          portal.post(f"/master-planner/proyectos/{P_TI}/tareas", json={"titulo": "X"}).status_code == 403)
    v.check("no edita tareas",
          portal.patch(f"/master-planner/tareas/{T_CAL}", json={"estado": "completada"}).status_code == 403)
    v.check("no borra tareas",
          portal.delete(f"/master-planner/tareas/{T_CAL}").status_code == 403)
    v.check("no toca el presupuesto",
          portal.post(f"/master-planner/proyectos/{P_TI}/presupuesto", json={"concepto": "X"}).status_code == 403)
    r = portal.get(f"/master-planner/proyectos/{P_TI}/presupuesto").json()
    v.check("ni registra ejecución",
          portal.patch(f"/master-planner/presupuesto/{r[0]['id']}", json={"valor_ejecutado": 9}).status_code == 403)

    # ── Rol gerencia: sí puede comentar ──
    r = portal.post(f"/master-planner/tareas/{T_CAL}/actualizaciones", data={"comentario": "¿Cómo va esto?"})
    v.check("gerencia sí publica un comentario -> 201", r.status_code == 201, r.text[:120])
    v.check("queda con su nombre", r.json()["usuario_nombre"] == "Gerente", r.json())
    r = portal.post(f"/master-planner/tareas/{T_CAL}/actualizaciones", data={"avance_pct_nuevo": "80"})
    v.check("pero NO puede mover el avance -> 403", r.status_code == 403, r.text[:120])

    # ── Rol lectura: nada de nada ──
    portal.como("lectura")
    v.check("lectura sí consulta", portal.get("/master-planner/proyectos").status_code == 200)
    v.check("pero no comenta",
          portal.post(f"/master-planner/tareas/{T_CAL}/actualizaciones", data={"comentario": "hola"}).status_code == 403)
    v.check("ni edita", portal.patch(f"/master-planner/proyectos/{P_TI}", json={"nombre": "X"}).status_code == 403)
    vistos = {p["nombre"] for p in portal.get("/master-planner/proyectos").json()}
    v.check("y lectura también está limitado a su área", "Auditoría ISO" not in vistos, vistos)

    # ── El resumen respeta la misma regla que el listado ──
    portal.como("calidad")
    res = portal.get("/master-planner/resumen").json()
    nombres = {p["nombre"] for p in res["proyectos"]}
    v.check("el resumen del líder trae lo de su área",
          nombres == {"Auditoría ISO"}, nombres)
    v.check("con el presupuesto de su área",
          res["presupuesto"]["planeado"] == 2000000, res["presupuesto"])

    # A TICS le entregan el liderazgo de Portal Web. Hasta aquí no lo veía
    # —ser del área ya no basta—; desde aquí sí, y con su presupuesto.
    portal.como("admin")
    portal.patch(f"/master-planner/proyectos/{P_TI}", json={"lider_id": portal.ids["tics"]})

    portal.como("tics")
    res = portal.get("/master-planner/resumen").json()
    # TICS ve el proyecto de Calidad porque le asignaron una tarea, pero su
    # presupuesto no debe entrar en los totales ni mostrarse en la fila:
    # trabajar en un proyecto no da acceso a su plata.
    v.check("TICS ve el proyecto de Calidad en el resumen",
          any(p["nombre"] == "Auditoría ISO" for p in res["proyectos"]),
          {p["nombre"] for p in res["proyectos"]})
    fila = next(p for p in res["proyectos"] if p["nombre"] == "Auditoría ISO")
    v.check("y la fila marca el presupuesto como no visible",
          fila["presupuesto_visible"] is False and fila["planeado"] is None, fila)
    v.check("en los totales solo entra la plata de lo que lidera",
          res["presupuesto"]["planeado"] == 4000000, res["presupuesto"])
    propio = next(p for p in res["proyectos"] if p["nombre"] == "Portal Web")
    v.check("su propio proyecto sí muestra la plata",
          propio["presupuesto_visible"] is True and propio["planeado"] == 4000000, propio)
    v.check("Calidad no aparece en el desglose por área de TICS",
          "Calidad" not in {a["area"] for a in res["presupuesto_por_area"]},
          [a["area"] for a in res["presupuesto_por_area"]])

    # ── El tablero global también filtra ──
    portal.como("logistica")
    tareas = portal.get("/master-planner/tareas").json()
    v.check("Logística no ve tareas de proyectos ajenos",
          all(t["proyecto_id"] in (P_MIX, P_CAL, P_SIN) for t in tareas),
          [(t["titulo"], t["proyecto_id"]) for t in tareas])


