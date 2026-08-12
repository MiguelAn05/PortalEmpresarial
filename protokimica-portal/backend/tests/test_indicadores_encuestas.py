"""
Indicadores automáticos que salen de las encuestas.

Estas fuentes no se pueden escribir de antemano como las de PQRS o Master
Planner: las encuestas se crean desde la interfaz, así que el catálogo se
arma leyendo las que existan. Lo que se prueba aquí es justamente eso — que
una encuesta nueva aparezca sola como fuente y que sus números salgan bien.
"""
from datetime import datetime, timezone

from app.modules.indicadores import fuentes

PLANTILLA = {
    "nombre": "Atención en punto de venta",
    "slug": "puntos",
    "sujeto_tipo": "punto de venta",
    "sujetos": "Sede Centro|Sede Norte",
    "preguntas": [{"texto": "¿Cómo fue la atención?", "tipo": "escala", "orden": 1}],
}


def _encuesta_con_notas(portal, notas):
    """Crea la encuesta y le mete una respuesta por cada nota de la lista."""
    r = portal.post("/encuestas", json=PLANTILLA)
    assert r.status_code == 201, r.text
    plantilla = r.json()
    pid = plantilla["preguntas"][0]["id"]

    for nota in notas:
        resp = portal.post("/public/encuestas/puntos", json={
            "sujeto_nombre": "Sede Centro", "respuestas": {str(pid): nota},
        })
        assert resp.status_code == 200, resp.text
    return plantilla


def test_una_encuesta_nueva_aparece_sola_en_el_catalogo(entorno, v):
    portal = entorno
    v.check("antes no está",
            not any(f["clave"].startswith("encuesta:puntos")
                    for f in portal.get("/indicadores/catalogo").json()))

    _encuesta_con_notas(portal, [5])

    catalogo = portal.get("/indicadores/catalogo").json()
    claves = [f["clave"] for f in catalogo]
    v.check("aparece el promedio", "encuesta:puntos:promedio" in claves, claves[-5:])
    v.check("los insatisfechos", "encuesta:puntos:detractores" in claves, claves[-5:])
    v.check("y el volumen", "encuesta:puntos:respuestas" in claves, claves[-5:])

    ficha = next(f for f in catalogo if f["clave"] == "encuesta:puntos:promedio")
    v.check("se agrupa bajo Encuestas", ficha["modulo"] == "Encuestas", ficha)
    v.check("lleva el nombre de la encuesta",
            "Atención en punto de venta" in ficha["nombre"], ficha)


def test_el_promedio_del_mes_sale_correcto(entorno, v):
    portal = entorno
    _encuesta_con_notas(portal, [5, 4, 3])

    hoy = datetime.now(timezone.utc)
    r = fuentes.calcular("encuesta:puntos:promedio", portal.Session(),
                         portal.tenant_id, hoy.year, hoy.month)
    v.check("promedia las tres notas", r.valor == 4.0, r)
    v.check("y dice de cuántas sale", "3 respuesta" in r.detalle, r.detalle)


def test_los_insatisfechos_son_los_de_1_y_2(entorno, v):
    portal = entorno
    _encuesta_con_notas(portal, [5, 5, 2, 1])

    hoy = datetime.now(timezone.utc)
    r = fuentes.calcular("encuesta:puntos:detractores", portal.Session(),
                         portal.tenant_id, hoy.year, hoy.month)
    v.check("2 de 4 son detractores", r.valor == 50.0, r)
    # Guardar numerador y denominador es lo que permite que el acumulado
    # trimestral sea correcto en vez de promediar porcentajes.
    v.check("guarda numerador y denominador",
            r.numerador == 2 and r.denominador == 4, r)


def test_un_mes_sin_respuestas_no_es_un_cero(entorno, v):
    """
    Que nadie respondiera no significa calificación cero: eso hundiría el
    indicador por falta de datos, que es un problema distinto.
    """
    portal = entorno
    _encuesta_con_notas(portal, [5])

    r = fuentes.calcular("encuesta:puntos:promedio", portal.Session(),
                         portal.tenant_id, 2020, 1)   # un mes sin nada
    v.check("el valor es None, no 0", r.valor is None, r)
    v.check("y lo explica", "Sin respuestas" in r.detalle, r.detalle)


def test_se_puede_crear_un_indicador_apuntando_a_una_encuesta(entorno, v):
    portal = entorno
    _encuesta_con_notas(portal, [4, 4])

    r = portal.post("/indicadores", json={
        "nombre": "Satisfacción en punto de venta", "unidad": "razon",
        "tipo_captura": "automatico", "fuente_automatica": "encuesta:puntos:promedio",
        "area": "Comercial", "meta": 4.5, "direccion": "arriba",
        "umbral_verde": 4.5, "umbral_amarillo": 4,
    })
    v.check("el indicador se crea", r.status_code == 201, r.text[:200])

    hoy = datetime.now(timezone.utc)
    calculo = portal.post(f"/indicadores/{r.json()['id']}/calcular",
                          params={"anio": hoy.year, "mes": hoy.month})
    v.check("y se calcula solo", calculo.status_code == 200, calculo.text[:200])
    v.check("con el promedio real", float(calculo.json()["valor"]) == 4.0, calculo.json())


def test_una_fuente_de_encuesta_inventada_se_rechaza(entorno, v):
    r = entorno.post("/indicadores", json={
        "nombre": "Inventado", "unidad": "razon", "tipo_captura": "automatico",
        "fuente_automatica": "encuesta:no-existe:promedio",
        "meta": 4, "direccion": "arriba",
    })
    v.check("no deja crearlo", r.status_code == 400, r.status_code)


def test_una_metrica_inventada_se_rechaza(entorno, v):
    portal = entorno
    _encuesta_con_notas(portal, [5])
    r = portal.post("/indicadores", json={
        "nombre": "Inventado", "unidad": "razon", "tipo_captura": "automatico",
        "fuente_automatica": "encuesta:puntos:loquesea",
        "meta": 4, "direccion": "arriba",
    })
    v.check("no deja crearlo", r.status_code == 400, r.status_code)
