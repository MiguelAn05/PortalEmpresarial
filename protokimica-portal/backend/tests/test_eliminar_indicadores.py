"""
Eliminar indicadores.

El borrado por defecto protege el histórico: si el indicador tiene
mediciones, responde 409 y no borra nada. Perder años de serie histórica por
un clic no debería ser posible.

Para lo que sí hay que eliminar de verdad —los indicadores de prueba antes de
salir a producción— existe `incluir_mediciones=true`, que hay que pedir
explícitamente.
"""


def _indicador(portal, nombre="Disponibilidad"):
    r = portal.post("/indicadores", json={
        "nombre": nombre, "unidad": "porcentaje", "tipo_captura": "valor",
        "area": "TICS", "meta": 90, "direccion": "arriba",
        "umbral_verde": 90, "umbral_amarillo": 75,
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _medir(portal, ind, anio=2026, mes=7, valor=95):
    r = portal.post(f"/indicadores/{ind}/mediciones",
                    data={"anio": anio, "mes": mes, "valor": valor})
    assert r.status_code in (200, 201), r.text


def test_uno_sin_mediciones_se_borra_sin_ceremonia(entorno, v):
    portal = entorno
    ind = _indicador(portal)

    r = portal.delete(f"/indicadores/{ind}")
    v.check("responde 204", r.status_code == 204, r.status_code)
    v.check("y ya no existe",
            portal.get(f"/indicadores/{ind}").status_code == 404)


def test_con_mediciones_no_se_borra_por_accidente(entorno, v):
    portal = entorno
    ind = _indicador(portal)
    _medir(portal, ind)

    r = portal.delete(f"/indicadores/{ind}")
    v.check("se bloquea con 409", r.status_code == 409, r.status_code)
    v.check("dice cuántas mediciones hay", "1 medición" in r.json()["detail"], r.json())
    v.check("y ofrece las dos salidas",
            "Desactívalo" in r.json()["detail"] and "datos de prueba" in r.json()["detail"],
            r.json())
    v.check("el indicador sigue vivo",
            portal.get(f"/indicadores/{ind}").status_code == 200)


def test_se_puede_borrar_con_todo_si_se_pide_a_proposito(entorno, v):
    """El caso real: limpiar los indicadores de prueba antes de producción."""
    portal = entorno
    ind = _indicador(portal, "Indicador de prueba")
    _medir(portal, ind, mes=6)
    _medir(portal, ind, mes=7)

    r = portal.delete(f"/indicadores/{ind}", params={"incluir_mediciones": True})
    v.check("ahora sí borra", r.status_code == 204, r.text[:200])
    v.check("y desaparece",
            portal.get(f"/indicadores/{ind}").status_code == 404)


def test_borrar_uno_no_toca_los_demas(entorno, v):
    portal = entorno
    victima = _indicador(portal, "El que sobra")
    sobreviviente = _indicador(portal, "El que se queda")
    _medir(portal, victima)
    _medir(portal, sobreviviente)

    portal.delete(f"/indicadores/{victima}", params={"incluir_mediciones": True})

    r = portal.get(f"/indicadores/{sobreviviente}")
    v.check("el otro sigue ahí", r.status_code == 200, r.status_code)
    tablero = portal.get("/indicadores/tablero", params={"anio": 2026, "mes": 7}).json()
    v.check("y conserva su medición",
            tablero["indicadores"][0]["valor"] == 95, tablero["indicadores"][0])


def test_desactivar_es_la_otra_salida(entorno, v):
    """
    Para un indicador de verdad que dejó de usarse, lo correcto es
    desactivarlo: sale del tablero y el histórico queda.
    """
    portal = entorno
    ind = _indicador(portal)
    _medir(portal, ind)

    r = portal.patch(f"/indicadores/{ind}", json={"activo": False})
    v.check("se desactiva", r.status_code == 200, r.text[:150])

    tablero = portal.get("/indicadores/tablero", params={"anio": 2026, "mes": 7}).json()
    v.check("sale del tablero", tablero["resumen"]["total"] == 0, tablero["resumen"])
    v.check("pero el indicador existe",
            portal.get(f"/indicadores/{ind}").status_code == 200)


def test_lectura_no_puede_eliminar(entorno, v):
    portal = entorno
    ind = _indicador(portal)
    portal.como("lectura")
    r = portal.delete(f"/indicadores/{ind}")
    v.check("se bloquea", r.status_code == 403, r.status_code)
