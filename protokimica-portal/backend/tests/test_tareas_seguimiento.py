"""
Lo que le faltaba a una tarea de proyecto para poder seguirla de verdad.

Cuatro observaciones que llegaron de quien usa el módulo:

  - **Cuántas veces se le movió la fecha**, como ya se veía en los proyectos.
    Una tarea que se aplazó cuatro veces no es una tarea que va tarde: es una
    que se planeó mal o que está bloqueada, y eso no se nota en ningún
    semáforo.
  - **Responder un avance.** Preguntar «¿esto incluye la revisión de
    Calidad?» obligaba a escribir OTRO avance, y el historial quedaba con
    conversación mezclada sin decir a cuál contestaba.
  - **Cuántas horas se le va a dedicar**, para ver si a alguien le cabe en la
    semana lo que tiene asignado.
  - **El entregable, al CREARLA.** Escrito después se escribe para justificar
    lo que ya se hizo.
"""
from datetime import datetime, timedelta, timezone

HOY = datetime(2026, 9, 26, 10, tzinfo=timezone.utc)


def _proyecto(portal, nombre="Portal Web"):
    return portal.post("/master-planner/proyectos", json={
        "nombre": nombre, "area": "TICS", "lider_id": portal.ids["admin"],
    }).json()["id"]


def _tarea(portal, proyecto_id, **extra):
    cuerpo = {"titulo": "Migrar base de datos", "area": "TICS"}
    cuerpo.update(extra)
    return portal.post(f"/master-planner/proyectos/{proyecto_id}/tareas", json=cuerpo)


def _mover_fecha(portal, tarea_id, dias):
    return portal.patch(f"/master-planner/tareas/{tarea_id}", json={
        "fecha_fin": (HOY + timedelta(days=dias)).isoformat(),
    })


# ── Entregable y horas, al crear ─────────────────────────────────────

def test_la_tarea_nace_con_entregable_y_horas(entorno, v):
    portal = entorno
    P = _proyecto(portal)

    r = _tarea(portal, P, entregable="El informe de migración firmado",
               horas_estimadas=12.5)
    v.check("se crea", r.status_code == 201, r.text[:250])
    v.check("con su entregable",
            r.json()["entregable"] == "El informe de migración firmado", r.json())
    v.check("y con las horas, con decimales",
            r.json()["horas_estimadas"] == 12.5, r.json())


def test_entregable_y_horas_son_opcionales(entorno, v):
    """Una tarea sin definir todavía no puede quedarse sin crear."""
    portal = entorno
    r = _tarea(portal, _proyecto(portal))
    v.check("se crea igual", r.status_code == 201, r.text[:250])
    v.check("sin entregable", r.json()["entregable"] is None, r.json())
    v.check("y sin horas", r.json()["horas_estimadas"] is None, r.json())


def test_las_horas_no_aceptan_un_dedo_de_mas(entorno, v):
    """Sin tope, «8» se convierte en «800» y la carga de la semana miente."""
    portal = entorno
    P = _proyecto(portal)
    v.check("no acepta 9000 horas", _tarea(portal, P, horas_estimadas=9000).status_code == 422)
    v.check("ni negativas", _tarea(portal, P, horas_estimadas=-3).status_code == 422)
    v.check("cero sí: una tarea de trámite", _tarea(portal, P, horas_estimadas=0).status_code == 201)


def test_cambiar_el_entregable_queda_en_el_historial(entorno, v):
    """
    Cambiarlo es mover la portería: lo que se iba a entregar no es lo que se
    entregó, y eso tiene que quedar dicho con sus dos valores.
    """
    portal = entorno
    P = _proyecto(portal)
    T = _tarea(portal, P, entregable="El informe").json()["id"]

    portal.patch(f"/master-planner/tareas/{T}", json={"entregable": "Un correo con el resumen"})

    historial = portal.get(f"/master-planner/proyectos/{P}/historial").json()
    cambio = next((h for h in historial if h["campo"] == "entregable"), None)
    v.check("quedó registrado", cambio is not None, historial)
    v.check("con el valor anterior", cambio["valor_anterior"] == "El informe", cambio)
    v.check("y el nuevo", cambio["valor_nuevo"] == "Un correo con el resumen", cambio)


# ── Cuántas veces se movió la fecha ──────────────────────────────────

def test_cuenta_las_veces_que_se_movio_la_fecha(entorno, v):
    portal = entorno
    P = _proyecto(portal)
    T = _tarea(portal, P, fecha_fin=HOY.isoformat()).json()["id"]

    v.check("arranca en cero",
            portal.get(f"/master-planner/tareas/{T}").json()["veces_aplazada"] == 0)

    _mover_fecha(portal, T, 5)
    _mover_fecha(portal, T, 12)

    v.check("cuenta los dos movimientos",
            portal.get(f"/master-planner/tareas/{T}").json()["veces_aplazada"] == 2)


def test_poner_la_fecha_por_primera_vez_no_es_aplazar(entorno, v):
    """
    Misma regla que en los proyectos: una tarea creada sin fecha a la que
    después se le pone una no se aplazó — no había de qué.
    """
    portal = entorno
    P = _proyecto(portal)
    T = _tarea(portal, P).json()["id"]

    _mover_fecha(portal, T, 5)
    v.check("sigue en cero",
            portal.get(f"/master-planner/tareas/{T}").json()["veces_aplazada"] == 0)

    _mover_fecha(portal, T, 9)
    v.check("y el siguiente sí cuenta",
            portal.get(f"/master-planner/tareas/{T}").json()["veces_aplazada"] == 1)


def test_el_conteo_no_se_contagia_entre_tareas(entorno, v):
    """
    Con el filtro por `entidad_id` mal puesto, una tarea mostraría los
    movimientos de todas — y el número más creíble es el que está mal.
    """
    portal = entorno
    P = _proyecto(portal)
    T1 = _tarea(portal, P, titulo="Una", fecha_fin=HOY.isoformat()).json()["id"]
    T2 = _tarea(portal, P, titulo="Otra", fecha_fin=HOY.isoformat()).json()["id"]

    _mover_fecha(portal, T1, 3)
    _mover_fecha(portal, T1, 6)
    _mover_fecha(portal, T2, 2)

    v.check("cada una cuenta la suya",
            [portal.get(f"/master-planner/tareas/{t}").json()["veces_aplazada"]
             for t in (T1, T2)] == [2, 1])


def test_el_conteo_viaja_tambien_en_la_lista(entorno, v):
    """
    Son siete endpoints los que devuelven tareas. Si el conteo se armara en
    cada uno, el que se olvide devolvería cero sin que nada falle.
    """
    portal = entorno
    P = _proyecto(portal)
    T = _tarea(portal, P, fecha_fin=HOY.isoformat()).json()["id"]
    _mover_fecha(portal, T, 4)

    de_la_lista = portal.get(f"/master-planner/proyectos/{P}/tareas").json()
    v.check("la lista del proyecto lo trae",
            de_la_lista[0]["veces_aplazada"] == 1, de_la_lista[0])

    todas = portal.get("/master-planner/tareas").json()
    v.check("y la lista general también",
            next(t for t in todas if t["id"] == T)["veces_aplazada"] == 1)


# ── Responder un avance ──────────────────────────────────────────────

def _avance(portal, tarea_id, comentario="Voy por la mitad"):
    return portal.post(f"/master-planner/tareas/{tarea_id}/actualizaciones",
                       data={"comentario": comentario})


def test_un_avance_se_puede_responder(entorno, v):
    portal = entorno
    P = _proyecto(portal)
    T = _tarea(portal, P).json()["id"]
    A = _avance(portal, T).json()["id"]

    r = portal.post(
        f"/master-planner/tareas/{T}/actualizaciones/{A}/respuestas",
        json={"comentario": "¿Eso incluye la revisión de Calidad?"},
    )
    v.check("se responde", r.status_code == 201, r.text[:250])
    v.check("con quién preguntó", r.json()["usuario_nombre"] == "Admin", r.json())


def test_la_respuesta_viaja_dentro_del_avance_que_contesta(entorno, v):
    """
    Y NO como una entrada suelta de la lista: mostrarla dos veces —una sin
    decir a qué contesta— es exactamente el problema que esto resuelve.
    """
    portal = entorno
    P = _proyecto(portal)
    T = _tarea(portal, P).json()["id"]
    A = _avance(portal, T).json()["id"]
    portal.post(f"/master-planner/tareas/{T}/actualizaciones/{A}/respuestas",
                json={"comentario": "Falta Calidad"})

    lista = portal.get(f"/master-planner/tareas/{T}/actualizaciones").json()
    v.check("la lista trae un solo avance", len(lista) == 1, lista)
    v.check("con su respuesta adentro", len(lista[0]["respuestas"]) == 1, lista[0])
    v.check("y se lee el texto",
            lista[0]["respuestas"][0]["comentario"] == "Falta Calidad", lista[0])


def test_no_se_responde_una_respuesta(entorno, v):
    """Un nivel: esto es «pregúntale al que reportó», no un foro."""
    portal = entorno
    P = _proyecto(portal)
    T = _tarea(portal, P).json()["id"]
    A = _avance(portal, T).json()["id"]
    R = portal.post(f"/master-planner/tareas/{T}/actualizaciones/{A}/respuestas",
                    json={"comentario": "Falta Calidad"}).json()["id"]

    r = portal.post(f"/master-planner/tareas/{T}/actualizaciones/{R}/respuestas",
                    json={"comentario": "Ya se hizo"})
    v.check("no se anida", r.status_code == 400, r.status_code)
    v.check("y dice qué hacer", "hilo" in r.json().get("detail", ""), r.json())


def test_una_respuesta_vacia_no_entra(entorno, v):
    portal = entorno
    P = _proyecto(portal)
    T = _tarea(portal, P).json()["id"]
    A = _avance(portal, T).json()["id"]

    r = portal.post(f"/master-planner/tareas/{T}/actualizaciones/{A}/respuestas",
                    json={"comentario": "   "})
    v.check("no entra", r.status_code == 400, r.status_code)


def test_gerencia_si_puede_preguntar(entorno, v):
    """
    Es el caso que motiva esto: quien lee el avance y necesita una
    aclaración es justamente quien no mueve el avance. Gerencia no escribe
    en el portal, pero comentar sí puede — y preguntar es comentar.
    """
    portal = entorno
    P = _proyecto(portal)
    T = _tarea(portal, P).json()["id"]
    A = _avance(portal, T).json()["id"]

    portal.como("gerencia")
    r = portal.post(f"/master-planner/tareas/{T}/actualizaciones/{A}/respuestas",
                    json={"comentario": "¿Quedó la revisión de Calidad?"})
    v.check("gerencia pregunta", r.status_code == 201, r.text[:250])

    portal.como("lectura")
    r = portal.post(f"/master-planner/tareas/{T}/actualizaciones/{A}/respuestas",
                    json={"comentario": "Yo no debería poder"})
    v.check("pero quien solo lee, no", r.status_code == 403, r.status_code)


def test_responder_un_avance_de_otra_tarea_no_se_puede(entorno, v):
    """El id del avance se valida CONTRA la tarea, no suelto."""
    portal = entorno
    P = _proyecto(portal)
    T1 = _tarea(portal, P, titulo="Una").json()["id"]
    T2 = _tarea(portal, P, titulo="Otra").json()["id"]
    A = _avance(portal, T1).json()["id"]

    r = portal.post(f"/master-planner/tareas/{T2}/actualizaciones/{A}/respuestas",
                    json={"comentario": "Nada que ver"})
    v.check("responde 404", r.status_code == 404, r.status_code)


def test_borrar_el_avance_se_lleva_sus_respuestas(entorno, v):
    """Una respuesta huérfana no se entiende sola."""
    portal = entorno
    P = _proyecto(portal)
    T = _tarea(portal, P).json()["id"]
    A = _avance(portal, T).json()["id"]
    portal.post(f"/master-planner/tareas/{T}/actualizaciones/{A}/respuestas",
                json={"comentario": "Falta Calidad"})

    db = portal.Session()
    from app.models.master_planner import TareaActualizacion
    db.delete(db.get(TareaActualizacion, A))
    db.commit()
    quedan = db.query(TareaActualizacion).filter(
        TareaActualizacion.tarea_id == T).count()
    db.close()

    v.check("no queda ninguna colgando", quedan == 0, quedan)
