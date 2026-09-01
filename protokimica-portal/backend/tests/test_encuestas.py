"""
Módulo de Encuestas: plantillas, respuesta pública y panel consolidado.

Lo que importa probar aquí no es el CRUD, sino las decisiones: que las
preguntas sean datos y se validen contra la plantilla, que no se pueda
cambiar una encuesta ya respondida, y que la encuesta de PQRS aparezca en el
panel junto a las nuevas sin haberla tocado.
"""
from app.models.pqrs import PQRSEncuesta, PQRSSolicitud
from app.modules.encuestas import service


PLANTILLA_VENDEDORES = {
    "nombre": "Calificación de vendedores",
    "descripcion": "La responde el cliente en el punto de venta.",
    "slug": "vendedores",
    "sujeto_tipo": "vendedor",
    "mensaje_final": "¡Gracias! Tu opinión nos ayuda a mejorar.",
    "preguntas": [
        {"texto": "¿Cómo calificas la atención?", "tipo": "escala",
         "clave": "atencion", "orden": 1},
        {"texto": "¿Encontraste lo que buscabas?", "tipo": "opcion",
         "opciones": "Sí|Parcialmente|No", "orden": 2},
        {"texto": "¿Nos recomendarías?", "tipo": "si_no", "orden": 3},
        {"texto": "¿Algo más que quieras contarnos?", "tipo": "texto",
         "obligatoria": False, "orden": 4},
    ],
}


def _crear_plantilla(portal, datos=None):
    r = portal.post("/encuestas", json=datos or PLANTILLA_VENDEDORES)
    assert r.status_code == 201, r.text
    return r.json()


# ── Plantillas ───────────────────────────────────────────────────────────

def test_crear_una_encuesta_con_sus_preguntas(entorno, v):
    plantilla = _crear_plantilla(entorno)
    v.check("guarda las 4 preguntas", len(plantilla["preguntas"]) == 4, plantilla)
    v.check("respeta el orden",
            [p["texto"] for p in plantilla["preguntas"]][0] == "¿Cómo calificas la atención?",
            plantilla["preguntas"])
    v.check("arranca sin respuestas", plantilla["total_respuestas"] == 0, plantilla)


def test_no_se_repite_la_direccion_web(entorno, v):
    """El slug termina impreso en un QR: dos encuestas no pueden compartirlo."""
    _crear_plantilla(entorno)
    r = entorno.post("/encuestas", json=PLANTILLA_VENDEDORES)
    v.check("la segunda con el mismo slug se rechaza", r.status_code == 400, r.status_code)
    v.check("y dice qué hacer", "Elige otra" in r.json()["detail"], r.json())


def test_un_tipo_de_pregunta_inventado_se_rechaza(entorno, v):
    datos = {**PLANTILLA_VENDEDORES, "slug": "otra",
             "preguntas": [{"texto": "¿?", "tipo": "estrellitas"}]}
    r = entorno.post("/encuestas", json=datos)
    v.check("no se acepta", r.status_code == 400, r.status_code)
    v.check("el error lista los válidos", "escala" in r.json()["detail"], r.json())


# ── Responder, desde el formulario público ───────────────────────────────

def test_el_cliente_ve_y_responde_la_encuesta(entorno, v):
    plantilla = _crear_plantilla(entorno)
    ids = {p["texto"]: p["id"] for p in plantilla["preguntas"]}

    r = entorno.get("/public/encuestas/vendedores")
    v.check("el formulario público responde", r.status_code == 200, r.text[:150])
    v.check("trae las preguntas", len(r.json()["preguntas"]) == 4, r.json())
    v.check("las opciones llegan como lista",
            r.json()["preguntas"][1]["opciones"] == ["Sí", "Parcialmente", "No"],
            r.json()["preguntas"][1])

    r = entorno.post("/public/encuestas/vendedores", json={
        "sujeto_ref": "V-014", "sujeto_nombre": "Andrea Gómez",
        "respuestas": {
            str(ids["¿Cómo calificas la atención?"]): 5,
            str(ids["¿Encontraste lo que buscabas?"]): "Sí",
            str(ids["¿Nos recomendarías?"]): "si",
            str(ids["¿Algo más que quieras contarnos?"]): "Muy amable la atención.",
        },
    })
    v.check("se registra", r.status_code == 200, r.text[:200])
    v.check("responde el mensaje de la encuesta",
            "Gracias" in r.json()["mensaje"], r.json())


def test_no_se_puede_responder_sin_las_obligatorias(entorno, v):
    plantilla = _crear_plantilla(entorno)
    ids = {p["texto"]: p["id"] for p in plantilla["preguntas"]}

    r = entorno.post("/public/encuestas/vendedores", json={
        "respuestas": {str(ids["¿Cómo calificas la atención?"]): 4},
    })
    v.check("se rechaza", r.status_code == 400, r.status_code)
    v.check("dice cuál falta",
            "¿Encontraste lo que buscabas?" in r.json()["detail"], r.json())


def test_una_calificacion_fuera_de_escala_se_rechaza(entorno, v):
    plantilla = _crear_plantilla(entorno)
    ids = {p["texto"]: p["id"] for p in plantilla["preguntas"]}

    r = entorno.post("/public/encuestas/vendedores", json={
        "respuestas": {
            str(ids["¿Cómo calificas la atención?"]): 9,
            str(ids["¿Encontraste lo que buscabas?"]): "Sí",
            str(ids["¿Nos recomendarías?"]): "si",
        },
    })
    v.check("no se acepta un 9 sobre 5", r.status_code == 400, r.status_code)
    v.check("el mensaje da el rango", "entre 1 y 5" in r.json()["detail"], r.json())


def test_una_opcion_que_no_existe_se_rechaza(entorno, v):
    plantilla = _crear_plantilla(entorno)
    ids = {p["texto"]: p["id"] for p in plantilla["preguntas"]}

    r = entorno.post("/public/encuestas/vendedores", json={
        "respuestas": {
            str(ids["¿Cómo calificas la atención?"]): 4,
            str(ids["¿Encontraste lo que buscabas?"]): "Tal vez",
            str(ids["¿Nos recomendarías?"]): "si",
        },
    })
    v.check("se rechaza", r.status_code == 400, r.status_code)
    v.check("lista las válidas", "Parcialmente" in r.json()["detail"], r.json())


def test_una_encuesta_desactivada_no_recibe_respuestas(entorno, v):
    plantilla = _crear_plantilla(entorno)
    entorno.patch(f"/encuestas/{plantilla['id']}", json={"activa": False})

    r = entorno.get("/public/encuestas/vendedores")
    v.check("el formulario deja de estar disponible", r.status_code == 404, r.status_code)
    v.check("y el mensaje orienta al cliente",
            "Verifique el enlace" in r.json()["detail"], r.json())


# ── No se puede cambiar lo que ya respondieron ───────────────────────────

def test_no_se_cambian_las_preguntas_de_una_encuesta_respondida(entorno, v):
    """
    Cambiarlas dejaría las respuestas contestando algo que ya no se pregunta,
    y cualquier reporte posterior mezclaría cosas distintas.
    """
    plantilla = _crear_plantilla(entorno)
    ids = {p["texto"]: p["id"] for p in plantilla["preguntas"]}
    entorno.post("/public/encuestas/vendedores", json={
        "respuestas": {
            str(ids["¿Cómo calificas la atención?"]): 5,
            str(ids["¿Encontraste lo que buscabas?"]): "Sí",
            str(ids["¿Nos recomendarías?"]): "si",
        },
    })

    r = entorno.patch(f"/encuestas/{plantilla['id']}", json={
        "preguntas": [{"texto": "Otra cosa", "tipo": "escala"}],
    })
    v.check("se bloquea con 409", r.status_code == 409, r.status_code)
    v.check("propone la salida",
            "crea una versión nueva" in r.json()["detail"], r.json())

    # Pero el resto de campos sí se puede editar.
    r = entorno.patch(f"/encuestas/{plantilla['id']}", json={"nombre": "Vendedores 2026"})
    v.check("renombrarla sí se puede", r.status_code == 200, r.text[:150])


def test_no_se_borra_una_encuesta_con_respuestas(entorno, v):
    plantilla = _crear_plantilla(entorno)
    ids = {p["texto"]: p["id"] for p in plantilla["preguntas"]}
    entorno.post("/public/encuestas/vendedores", json={
        "respuestas": {
            str(ids["¿Cómo calificas la atención?"]): 4,
            str(ids["¿Encontraste lo que buscabas?"]): "Sí",
            str(ids["¿Nos recomendarías?"]): "no",
        },
    })

    r = entorno.delete(f"/encuestas/{plantilla['id']}")
    v.check("no se deja borrar", r.status_code == 409, r.status_code)
    v.check("sugiere desactivarla", "Desactívala" in r.json()["detail"], r.json())


# ── El panel: todo junto ─────────────────────────────────────────────────

def test_el_panel_junta_las_encuestas_nuevas_con_las_de_pqrs(entorno, v):
    """
    La encuesta de PQRS vive en su propia tabla desde antes y no se tocó.
    El panel la muestra igual, gracias al adaptador de orígenes.
    """
    portal = entorno
    plantilla = _crear_plantilla(portal)
    ids = {p["texto"]: p["id"] for p in plantilla["preguntas"]}
    portal.post("/public/encuestas/vendedores", json={
        "sujeto_ref": "V-014", "sujeto_nombre": "Andrea Gómez",
        "respuestas": {
            str(ids["¿Cómo calificas la atención?"]): 5,
            str(ids["¿Encontraste lo que buscabas?"]): "Sí",
            str(ids["¿Nos recomendarías?"]): "si",
        },
    })

    # Una encuesta de PQRS respondida, escrita directo como la crea el módulo.
    from datetime import datetime, timezone
    db = portal.Session()
    sol = PQRSSolicitud(
        tenant_id=portal.tenant_id, tipo="reclamo", cliente_nombre="Cliente X",
        descripcion="algo", estado="cerrado", prioridad="media",
        origen_publico="publico", codigo_seguimiento="PK-001",
        area_responsable="Servicio al Cliente",
    )
    db.add(sol)
    db.commit()
    db.add(PQRSEncuesta(
        pqrs_id=sol.id, calificacion=3, solucionada="parcial",
        comentario="Demoraron mucho", recomendaria=False,
        respondida_en=datetime.now(timezone.utc),
    ))
    db.commit()
    db.close()

    datos = portal.get("/encuestas/panel").json()

    v.check("hay dos respuestas en total", datos["resumen"]["total"] == 2, datos["resumen"])
    origenes = {r["origen"] for r in datos["respuestas"]}
    v.check("de los dos orígenes", origenes == {"vendedores", "pqrs"}, origenes)
    v.check("el promedio junta ambas", datos["resumen"]["promedio"] == 4.0, datos["resumen"])
    v.check("un 3 no es detractor: detractor es 1 o 2",
            datos["resumen"]["detractores"] == 0, datos["resumen"])

    # El filtro por origen deja ver una sola encuesta.
    solo = portal.get("/encuestas/panel", params={"origen": "vendedores"}).json()
    v.check("filtrar por origen funciona", solo["resumen"]["total"] == 1, solo["resumen"])


# ── Lista cerrada de qué se califica ─────────────────────────────────────

PLANTILLA_PUNTOS = {
    "nombre": "Atención en punto de venta",
    "slug": "puntos",
    "sujeto_tipo": "punto de venta",
    "sujetos": "Sede Centro|Sede Norte|Sede Sur",
    "preguntas": [
        {"texto": "¿Cómo fue la atención?", "tipo": "escala", "orden": 1},
    ],
}


def test_con_lista_cerrada_hay_que_elegir_de_la_lista(entorno, v):
    """
    El texto libre rompe el reporte: "Centro", "centro" y "Sede Centro"
    entrarían como tres puntos distintos y ninguno tendría datos suficientes.
    """
    portal = entorno
    plantilla = _crear_plantilla(portal, PLANTILLA_PUNTOS)
    pid = plantilla["preguntas"][0]["id"]

    r = portal.get("/public/encuestas/puntos")
    v.check("el formulario trae las opciones",
            r.json()["sujetos"] == ["Sede Centro", "Sede Norte", "Sede Sur"], r.json())

    # Inventarse un punto que no está en la lista.
    r = portal.post("/public/encuestas/puntos", json={
        "sujeto_nombre": "centro", "respuestas": {str(pid): 5},
    })
    v.check("se rechaza lo que no está en la lista", r.status_code == 400, r.status_code)
    v.check("y el error dice cuáles valen",
            "Sede Centro" in r.json()["detail"], r.json())

    # No elegir nada.
    r = portal.post("/public/encuestas/puntos", json={"respuestas": {str(pid): 5}})
    v.check("tampoco se puede omitir", r.status_code == 400, r.status_code)

    # Elegir bien.
    r = portal.post("/public/encuestas/puntos", json={
        "sujeto_nombre": "Sede Norte", "respuestas": {str(pid): 4},
    })
    v.check("una opción de la lista sí entra", r.status_code == 200, r.text[:150])


def test_sin_lista_el_sujeto_llega_por_el_enlace(entorno, v):
    """Un QR por punto: el cliente no elige nada y el dato entra limpio igual."""
    portal = entorno
    plantilla = _crear_plantilla(portal)
    ids = {p["texto"]: p["id"] for p in plantilla["preguntas"]}

    r = portal.post("/public/encuestas/vendedores", json={
        "sujeto_ref": "PV-03", "sujeto_nombre": "Sede Sur",
        "respuestas": {
            str(ids["¿Cómo calificas la atención?"]): 5,
            str(ids["¿Encontraste lo que buscabas?"]): "Sí",
            str(ids["¿Nos recomendarías?"]): "si",
        },
    })
    v.check("se acepta sin lista", r.status_code == 200, r.text[:150])

    datos = portal.get("/encuestas/panel").json()
    v.check("y queda amarrada al punto",
            datos["por_sujeto"][0]["sujeto"] == "Sede Sur", datos["por_sujeto"])


def test_se_pueden_agregar_puntos_a_una_encuesta_ya_respondida(entorno, v):
    """
    Abrir una sede nueva no puede obligar a rehacer la encuesta: agregar
    opciones no invalida ninguna respuesta anterior.
    """
    portal = entorno
    plantilla = _crear_plantilla(portal, PLANTILLA_PUNTOS)
    pid = plantilla["preguntas"][0]["id"]
    portal.post("/public/encuestas/puntos", json={
        "sujeto_nombre": "Sede Centro", "respuestas": {str(pid): 5},
    })

    r = portal.patch(f"/encuestas/{plantilla['id']}", json={
        "sujetos": "Sede Centro|Sede Norte|Sede Sur|Sede Occidente",
    })
    v.check("agregar una sede sí se puede", r.status_code == 200, r.text[:200])

    r = portal.post("/public/encuestas/puntos", json={
        "sujeto_nombre": "Sede Occidente", "respuestas": {str(pid): 3},
    })
    v.check("y la nueva ya recibe respuestas", r.status_code == 200, r.text[:150])


def test_el_ranking_pone_primero_al_peor_calificado(v):
    """Un ranking sirve para actuar sobre la cola, no para felicitar al primero."""
    from app.modules.encuestas.origenes import RespuestaVista

    respuestas = [
        RespuestaVista(id="1", origen="v", origen_nombre="V", respondida_en=None,
                       calificacion=5.0, sujeto="Andrea"),
        RespuestaVista(id="2", origen="v", origen_nombre="V", respondida_en=None,
                       calificacion=2.0, sujeto="Carlos"),
        RespuestaVista(id="3", origen="v", origen_nombre="V", respondida_en=None,
                       calificacion=4.0, sujeto="Carlos"),
    ]
    ranking = service.resumir_por_sujeto(respuestas)

    v.check("Carlos va primero", ranking[0]["sujeto"] == "Carlos", ranking)
    v.check("con el promedio de sus dos notas", ranking[0]["promedio"] == 3.0, ranking)
    v.check("y se ve de cuántas sale", ranking[0]["respuestas"] == 2, ranking)


def test_la_distribucion_distingue_dos_promedios_iguales(v):
    """
    Un 3.0 de puros treses y un 3.0 de mitad cincos y mitad unos son
    problemas distintos. El promedio solo los muestra iguales.
    """
    from app.modules.encuestas.origenes import RespuestaVista

    def con_notas(notas):
        return [RespuestaVista(id=str(i), origen="v", origen_nombre="V",
                               respondida_en=None, calificacion=n)
                for i, n in enumerate(notas)]

    parejo = service.resumir(con_notas([3, 3, 3, 3]))
    polarizado = service.resumir(con_notas([5, 5, 1, 1]))

    v.check("los dos promedian 3.0",
            parejo["promedio"] == 3.0 and polarizado["promedio"] == 3.0,
            (parejo["promedio"], polarizado["promedio"]))
    v.check("pero solo uno tiene detractores",
            parejo["detractores"] == 0 and polarizado["detractores"] == 2,
            (parejo["detractores"], polarizado["detractores"]))
