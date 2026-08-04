"""
Proyectos, tareas, subtareas, archivar y presupuesto.

Corre contra la API real con TestClient. El fixture `entorno` monta un portal
limpio con usuarios de todos los roles; `v` acumula las comprobaciones y las
reporta todas juntas si algo falla.
"""
from datetime import datetime, timedelta, timezone

from app.models.pqrs import PQRSSolicitud  # noqa: F401
from app.models.user import User  # noqa: F401


def test_master_planner(entorno, v):
    portal = entorno
    # ── Proyectos ──
    r = portal.post("/master-planner/proyectos", json={
        "nombre": "Portal Web", "objetivo": "Digitalizar", "area": "TICS",
        "lider_id": portal.ids["admin"], "prioridad": "alta",
    })
    v.check("crear proyecto -> 201", r.status_code == 201, r.text)
    P = r.json()["id"]
    v.check("archivado arranca en False", r.json()["archivado"] is False, r.json())
    v.check("total_tareas=0 al crear", r.json()["total_tareas"] == 0, r.json())

    v.check("estado enviado al crear se respeta", portal.post("/master-planner/proyectos", json={
        "nombre": "Con estado", "estado": "en_ejecucion",
    }).json()["estado"] == "en_ejecucion")

    r = portal.post("/master-planner/proyectos", json={"nombre": "Proyecto vacio"})
    P_VACIO = r.json()["id"]
    v.check("estado por defecto es planeacion", r.json()["estado"] == "planeacion", r.json())

    r = portal.get("/master-planner/proyectos")
    v.check("listar activos devuelve 3", len(r.json()) == 3, r.json())

    # ── Tareas y subtareas ──
    hoy = datetime.now(timezone.utc)
    r = portal.post(f"/master-planner/proyectos/{P}/tareas", json={
        "titulo": "Migrar base de datos", "area": "TICS", "asignado_a": portal.ids["calidad"],
        "prioridad": "critica",
        "fecha_inicio": hoy.isoformat(),
        "fecha_fin": (hoy + timedelta(days=4, hours=3)).isoformat(),
    })
    v.check("crear tarea -> 201", r.status_code == 201, r.text)
    T = r.json()["id"]
    v.check("asignado_nombre resuelto", r.json()["asignado_nombre"] == "Cali", r.json())
    v.check("subtareas vacio al crear", r.json()["subtareas"] == [], r.json())
    v.check("hora conservada en fecha_fin", r.json()["fecha_fin"][11:16] == (hoy + timedelta(days=4, hours=3)).strftime("%H:%M"), r.json()["fecha_fin"])

    r = portal.post(f"/master-planner/tareas/{T}/subtareas", json={
        "titulo": "Respaldar datos", "asignado_a": portal.ids["admin"], "prioridad": "alta",
    })
    v.check("crear subtarea -> 201", r.status_code == 201, r.text)
    S = r.json()["id"]
    v.check("subtarea hereda proyecto", r.json()["proyecto_id"] == P, r.json())
    v.check("subtarea hereda area del padre", r.json()["area"] == "TICS", r.json())
    v.check("subtarea tiene parent_id", r.json()["parent_id"] == T, r.json())

    r = portal.post(f"/master-planner/tareas/{S}/subtareas", json={"titulo": "Nieta"})
    v.check("subtarea de subtarea -> 400", r.status_code == 400, r.text)

    r = portal.get("/master-planner/tareas")
    v.check("tablero global excluye subtareas", [t["id"] for t in r.json()] == [T], r.json())
    tarea = r.json()[0]
    v.check("padre expone su subtarea", [s["id"] for s in tarea["subtareas"]] == [S], tarea)
    v.check("contador total_subtareas", tarea["total_subtareas"] == 1, tarea)
    v.check("contador subtareas_completadas", tarea["subtareas_completadas"] == 0, tarea)

    r = portal.get("/master-planner/tareas?incluir_subtareas=true")
    v.check("incluir_subtareas=true las trae", sorted(t["id"] for t in r.json()) == sorted([T, S]), r.json())

    r = portal.get(f"/master-planner/proyectos/{P}/tareas")
    v.check("tareas del proyecto excluye subtareas", [t["id"] for t in r.json()] == [T], r.json())

    r = portal.get("/master-planner/tareas/mias")
    v.check("mis tareas incluye subtareas asignadas a mi", [t["id"] for t in r.json()] == [S], r.json())

    # /tareas/mias tiene que ganarle a /tareas/{id}: si el orden de rutas se
    # rompiera, FastAPI intentaría convertir "mias" a int y devolvería 422.
    v.check("ruta /tareas/mias no la captura /tareas/{id}", r.status_code == 200, r.status_code)

    r = portal.get(f"/master-planner/tareas/{T}")
    v.check("obtener tarea por id -> 200", r.status_code == 200, r.text)
    v.check("obtener tarea trae sus subtareas", [s["id"] for s in r.json()["subtareas"]] == [S], r.json())
    v.check("obtener tarea inexistente -> 404", portal.get("/master-planner/tareas/99999").status_code == 404)

    # ── Avance del proyecto ──
    portal.patch(f"/master-planner/tareas/{S}", json={"estado": "completada", "avance_pct": 100})
    r = portal.get(f"/master-planner/tareas?proyecto_id={P}")
    v.check("subtarea completada no cambia avance del padre", r.json()[0]["avance_pct"] == 0, r.json())
    r = portal.get(f"/master-planner/proyectos/{P}")
    v.check("avance del proyecto ignora subtareas", r.json()["avance_pct"] == 0, r.json())
    v.check("total_tareas cuenta solo raiz", r.json()["total_tareas"] == 1, r.json())

    fd = {"comentario": "Avanzando", "avance_pct_nuevo": "50"}
    r = portal.post(f"/master-planner/tareas/{T}/actualizaciones", data=fd)
    v.check("actualizacion sube avance -> 201", r.status_code == 201, r.text)
    r = portal.get(f"/master-planner/proyectos/{P}")
    v.check("avance del proyecto = 50", r.json()["avance_pct"] == 50, r.json())

    # ── Borrar / archivar ──
    r = portal.delete(f"/master-planner/proyectos/{P}")
    v.check("borrar proyecto con tareas -> 409", r.status_code == 409, r.text)
    v.check("mensaje 409 dice cuantas tareas", "2 tarea" in r.json()["detail"], r.json())

    r = portal.delete(f"/master-planner/proyectos/{P_VACIO}")
    v.check("borrar proyecto vacio -> 204", r.status_code == 204, r.text)
    v.check("proyecto vacio ya no existe", portal.get(f"/master-planner/proyectos/{P_VACIO}").status_code == 404)

    r = portal.patch(f"/master-planner/proyectos/{P}", json={"archivado": True})
    v.check("archivar -> 200", r.status_code == 200 and r.json()["archivado"] is True, r.text)

    r = portal.get("/master-planner/proyectos")
    v.check("archivado sale de la lista activa", P not in [p["id"] for p in r.json()], r.json())
    r = portal.get("/master-planner/proyectos?archivados=true")
    v.check("archivado aparece en el archivo", [p["id"] for p in r.json()] == [P], r.json())
    r = portal.get("/master-planner/tareas")
    v.check("tareas de archivado salen del tablero", r.json() == [], r.json())
    r = portal.get("/master-planner/tareas/mias")
    v.check("tareas de archivado salen de mis tareas", r.json() == [], r.json())
    r = portal.get("/master-planner/tareas?incluir_archivados=true")
    v.check("incluir_archivados=true las devuelve", [t["id"] for t in r.json()] == [T], r.json())

    r = portal.patch(f"/master-planner/proyectos/{P}", json={"archivado": False})
    v.check("desarchivar", r.json()["archivado"] is False, r.text)
    v.check("vuelve a la lista activa", P in [p["id"] for p in portal.get("/master-planner/proyectos").json()])

    # ── Borrado en cascada de subtareas ──
    r = portal.delete(f"/master-planner/tareas/{T}")
    v.check("borrar padre -> 204", r.status_code == 204, r.text)
    r = portal.get("/master-planner/tareas?incluir_subtareas=true")
    v.check("subtarea se fue con el padre", r.json() == [], r.json())


