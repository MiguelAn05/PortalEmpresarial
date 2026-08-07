"""
Editar la ficha de un indicador ya creado, y la orientación de la división.

El caso que motivó esto: un indicador de "casos atendidos" quedó con las
etiquetas al revés (30 recibidos arriba, 20 atendidos abajo) y daba 150% en
vez de 67%. El cálculo estaba bien; lo que fallaba era que el formulario
pedía "numerador" y "denominador" y nadie piensa en esos términos.
"""


def _crear_razon(portal, **extra):
    payload = {
        "nombre": "Respuesta mesa de ayuda", "unidad": "porcentaje",
        "tipo_captura": "razon",
        "etiqueta_numerador": "casos atendidos",
        "etiqueta_denominador": "casos recibidos",
        "area": "TICS", "meta": 90, "direccion": "arriba",
        "umbral_verde": 90, "umbral_amarillo": 75,
    }
    payload.update(extra)
    return portal.post("/indicadores", json=payload).json()


def test_la_division_va_en_el_orden_correcto(entorno, v):
    portal = entorno
    ind = _crear_razon(portal)

    # 20 atendidos de 30 recibidos: 20/30 = 66.67%, NO 30/20 = 150%.
    r = portal.post(f"/indicadores/{ind['id']}/mediciones",
                    data={"anio": 2026, "mes": 7, "numerador": 20, "denominador": 30})
    v.check("registrar -> 201", r.status_code == 201, r.text[:150])
    v.check("20 de 30 da 66.67%", round(r.json()["valor"], 2) == 66.67, r.json())
    v.check("y no 150%", r.json()["valor"] != 150, r.json())

    # Al revés da el numero equivocado — asi se veia el problema.
    r = portal.post(f"/indicadores/{ind['id']}/mediciones",
                    data={"anio": 2026, "mes": 6, "numerador": 30, "denominador": 20})
    v.check("invertidos da 150%, que es la señal del error",
            r.json()["valor"] == 150, r.json())


def test_editar_la_ficha_de_un_indicador(entorno, v):
    portal = entorno
    # Se crea con las etiquetas al reves, como paso en la practica.
    ind = _crear_razon(portal,
                       etiqueta_numerador="casos recibidos",
                       etiqueta_denominador="casos atendidos")

    r = portal.patch(f"/indicadores/{ind['id']}", json={
        "etiqueta_numerador": "casos atendidos",
        "etiqueta_denominador": "casos recibidos",
    })
    v.check("corregir las etiquetas -> 200", r.status_code == 200, r.text[:150])
    v.check("quedan en el orden correcto",
            r.json()["etiqueta_numerador"] == "casos atendidos", r.json())

    r = portal.patch(f"/indicadores/{ind['id']}", json={
        "nombre": "Oportunidad mesa de ayuda", "meta": 95,
        "umbral_verde": 95, "umbral_amarillo": 80, "area": "Calidad",
    })
    v.check("se puede cambiar nombre, meta y umbrales", r.status_code == 200, r.text[:150])
    v.check("el nombre cambió", r.json()["nombre"] == "Oportunidad mesa de ayuda", r.json())
    v.check("la meta cambió", r.json()["meta"] == 95, r.json())


def test_editar_no_borra_las_mediciones(entorno, v):
    portal = entorno
    ind = _crear_razon(portal)
    portal.post(f"/indicadores/{ind['id']}/mediciones",
                data={"anio": 2026, "mes": 7, "numerador": 20, "denominador": 30})

    portal.patch(f"/indicadores/{ind['id']}", json={"nombre": "Otro nombre"})
    ficha = portal.get(f"/indicadores/{ind['id']}?anio=2026&mes=7").json()
    v.check("el valor sigue ahí", round(ficha["valor"], 2) == 66.67, ficha)
    v.check("y con su numerador", ficha["numerador"] == 20, ficha)


def test_cambiar_los_umbrales_recalcula_el_semaforo(entorno, v):
    portal = entorno
    ind = _crear_razon(portal)   # verde >= 90
    portal.post(f"/indicadores/{ind['id']}/mediciones",
                data={"anio": 2026, "mes": 7, "numerador": 20, "denominador": 30})

    ficha = portal.get(f"/indicadores/{ind['id']}?anio=2026&mes=7").json()
    v.check("66.67% con umbral 90 no cumple", ficha["semaforo"] == "rojo", ficha["semaforo"])

    # Bajar la exigencia cambia el juicio sin tocar el dato.
    portal.patch(f"/indicadores/{ind['id']}", json={"umbral_verde": 60, "umbral_amarillo": 40})
    ficha = portal.get(f"/indicadores/{ind['id']}?anio=2026&mes=7").json()
    v.check("con umbral 60 sí cumple", ficha["semaforo"] == "verde", ficha["semaforo"])
    v.check("el valor no se tocó", round(ficha["valor"], 2) == 66.67, ficha["valor"])


def test_la_ficha_trae_lo_necesario_para_editarla(entorno, v):
    """
    El formulario de edición se abre desde el detalle. Si la ficha no
    devuelve las etiquetas ni el responsable, editar desde ahí los borraría.
    """
    portal = entorno
    ind = _crear_razon(portal, responsable_id=portal.ids["tics"])
    ficha = portal.get(f"/indicadores/{ind['id']}").json()

    for campo in ("etiqueta_numerador", "etiqueta_denominador", "responsable_id",
                  "orden", "activo", "meta", "umbral_verde", "umbral_amarillo",
                  "direccion", "unidad", "tipo_captura", "area"):
        v.check(f"la ficha trae '{campo}'", campo in ficha, sorted(ficha))

    v.check("con el responsable correcto",
            ficha["responsable_id"] == portal.ids["tics"], ficha.get("responsable_id"))


def test_editar_un_automatico_no_lo_deja_sin_fuente(entorno, v):
    portal = entorno
    ind = portal.post("/indicadores", json={
        "nombre": "Oportunidad PQRS", "unidad": "porcentaje",
        "tipo_captura": "automatico", "fuente_automatica": "pqrs_oportunidad_sla",
    }).json()

    r = portal.patch(f"/indicadores/{ind['id']}", json={"fuente_automatica": "no_existe"})
    v.check("una fuente inválida -> 400", r.status_code == 400, r.text[:150])

    r = portal.patch(f"/indicadores/{ind['id']}", json={"meta": 95})
    v.check("pero sí se puede cambiar la meta", r.status_code == 200, r.text[:150])
    v.check("sin perder la fuente",
            r.json()["fuente_automatica"] == "pqrs_oportunidad_sla", r.json())


def test_gerencia_no_edita_indicadores(entorno, v):
    portal = entorno
    ind = _crear_razon(portal)
    portal.como("gerencia")
    r = portal.patch(f"/indicadores/{ind['id']}", json={"nombre": "X"})
    v.check("gerencia no edita la ficha -> 403", r.status_code == 403, r.status_code)
