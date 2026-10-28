"""
Corregir el texto de un avance o de una respuesta de una tarea.

Uno se equivoca escribiendo, y sin esto la única salida era otro avance que
dijera «donde dice X léase Y». Lo que se prueba: solo lo corrige quien lo
escribió, solo cambia el texto, la entrada queda marcada como editada y el
texto anterior queda en el historial de la tarea, y no puede quedar vacía.
Se prueba con lo que de verdad manda la pantalla: `{"comentario": ...}`.
"""


def _tarea(portal):
    P = portal.post("/master-planner/proyectos", json={
        "nombre": "Portal Web", "area": "TICS", "lider_id": portal.ids["admin"],
    }).json()["id"]
    return portal.post(f"/master-planner/proyectos/{P}/tareas", json={
        "titulo": "Migrar base de datos", "area": "TICS", "asignado_a": portal.ids["tics"],
    }).json()["id"]


def _avance(portal, tarea_id, comentario="Voy por la mitda", avance=None):
    datos = {"comentario": comentario} if comentario else {}
    if avance is not None:
        datos["avance_pct_nuevo"] = str(avance)
    r = portal.post(f"/master-planner/tareas/{tarea_id}/actualizaciones", data=datos)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _corregir(portal, tarea_id, entrada_id, comentario):
    return portal.patch(f"/master-planner/tareas/{tarea_id}/actualizaciones/{entrada_id}",
                        json={"comentario": comentario})


def _lista(portal, tarea_id):
    return portal.get(f"/master-planner/tareas/{tarea_id}/actualizaciones").json()


def test_quien_lo_escribio_lo_corrige(entorno, v):
    portal = entorno
    T = _tarea(portal)
    portal.como("tics")
    A = _avance(portal, T, avance=50)

    v.check("la lista le dice que lo puede corregir", _lista(portal, T)[0]["puede_corregir"] is True)
    r = _corregir(portal, T, A, "Voy por la mitad")
    v.check("corregir responde 200", r.status_code == 200, r.text)
    avance = _lista(portal, T)[0]
    v.check("el texto cambió", avance["comentario"] == "Voy por la mitad", avance)
    v.check("queda marcado como editado", avance["editado_en"] is not None, avance)
    v.check("el porcentaje no se toca", avance["avance_pct_nuevo"] == 50, avance)

    historial = portal.get(f"/master-planner/tareas/{T}/historial").json()
    corregido = next((h for h in historial if h["campo"] == "avance_corregido"), None)
    v.check("el historial guarda el texto anterior y el nuevo",
            corregido and corregido["valor_anterior"] == "Voy por la mitda"
            and corregido["valor_nuevo"] == "Voy por la mitad", historial)


def test_lo_de_otro_no_se_corrige(entorno, v):
    portal = entorno
    T = _tarea(portal)
    portal.como("tics")
    A = _avance(portal, T)

    for quien in ("admin", "gerencia"):
        portal.como(quien)
        v.check(f"{quien}: la lista no le ofrece corregirlo", _lista(portal, T)[0]["puede_corregir"] is False)
        r = _corregir(portal, T, A, "Otra cosa")
        v.check(f"{quien}: 403 diciendo qué hacer", r.status_code == 403 and "respóndele" in r.json()["detail"], r.text)
    portal.como("tics")
    v.check("el texto sigue siendo el suyo", _lista(portal, T)[0]["comentario"] == "Voy por la mitda")


def test_las_respuestas_tambien_se_corrigen(entorno, v):
    portal = entorno
    T = _tarea(portal)
    portal.como("tics")
    A = _avance(portal, T)
    portal.como("gerencia")
    R = portal.post(f"/master-planner/tareas/{T}/actualizaciones/{A}/respuestas",
                    json={"comentario": "¿Incluye la revison?"}).json()["id"]

    respuesta = _lista(portal, T)[0]["respuestas"][0]
    v.check("gerencia corrige su propia pregunta", respuesta["puede_corregir"] is True, respuesta)
    r = _corregir(portal, T, R, "¿Incluye la revisión de Calidad?")
    v.check("y la corrección entra", r.status_code == 200, r.text)
    respuesta = _lista(portal, T)[0]["respuestas"][0]
    v.check("la respuesta queda corregida y marcada",
            respuesta["comentario"] == "¿Incluye la revisión de Calidad?" and respuesta["editado_en"], respuesta)
    historial = portal.get(f"/master-planner/tareas/{T}/historial").json()
    v.check("en el historial dice que fue una respuesta",
            any(h["campo"] == "respuesta_corregida" for h in historial), historial)


def test_no_queda_vacia(entorno, v):
    portal = entorno
    T = _tarea(portal)
    portal.como("tics")
    solo_texto = _avance(portal, T)
    r = _corregir(portal, T, solo_texto, "   ")
    v.check("un avance que era solo texto no se vacía", r.status_code == 400, r.text)

    con_porcentaje = _avance(portal, T, comentario="Texto de más", avance=70)
    r = _corregir(portal, T, con_porcentaje, "")
    v.check("uno con porcentaje sí puede quedar sin texto", r.status_code == 200, r.text)


def test_sin_cambios_no_ensucia_el_historial(entorno, v):
    portal = entorno
    T = _tarea(portal)
    portal.como("tics")
    A = _avance(portal, T, comentario="Listo")
    _corregir(portal, T, A, "  Listo ")
    v.check("guardar lo mismo no lo marca editado", _lista(portal, T)[0]["editado_en"] is None)
    historial = portal.get(f"/master-planner/tareas/{T}/historial").json()
    v.check("ni deja renglón", not any(h["campo"] == "avance_corregido" for h in historial))


def test_un_avance_de_otra_tarea_no_se_corrige_desde_esta(entorno, v):
    portal = entorno
    T1, T2 = _tarea(portal), _tarea(portal)
    portal.como("tics")
    A = _avance(portal, T1)
    r = _corregir(portal, T2, A, "Cambiado")
    v.check("404", r.status_code == 404, r.text)


def test_lectura_no_corrige(entorno, v):
    portal = entorno
    T = _tarea(portal)
    A = _avance(portal, T)
    portal.como("lectura")
    v.check("403", _corregir(portal, T, A, "x").status_code == 403)
