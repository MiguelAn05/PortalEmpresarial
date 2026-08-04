"""
Indicadores: definicion, mediciones, semaforo, acumulados y tablero.

Corre contra la API real con TestClient. El fixture `entorno` monta un portal
limpio con usuarios de todos los roles; `v` acumula las comprobaciones y las
reporta todas juntas si algo falla.
"""
from datetime import datetime, timedelta, timezone

from app.models.pqrs import PQRSSolicitud  # noqa: F401
from app.models.user import User  # noqa: F401


def test_indicadores(entorno, v):
    portal = entorno
    A, M = 2026, 7

    # ── Catalogo y rutas ──
    r = portal.get("/indicadores/catalogo")
    v.check("el catalogo responde 200", r.status_code == 200, r.text[:100])
    v.check("trae las 11 fuentes", len(r.json()) == 11, len(r.json()))
    v.check("/catalogo no lo captura /{id}", r.status_code != 422)
    v.check("/tablero tampoco", portal.get("/indicadores/tablero").status_code == 200)

    # ── Crear indicadores ──
    # Manual de razon (porcentaje)
    r = portal.post("/indicadores", json={
        "nombre": "Cumplimiento de capacitaciones", "unidad": "porcentaje",
        "tipo_captura": "razon", "etiqueta_numerador": "Capacitaciones realizadas",
        "etiqueta_denominador": "Capacitaciones programadas", "area": "Gestión humana",
        "meta": 90, "direccion": "arriba", "umbral_verde": 90, "umbral_amarillo": 75,
        "requiere_evidencia": False,
    })
    v.check("crear indicador de razon -> 201", r.status_code == 201, r.text[:150])
    I_RAZON = r.json()["id"]
    v.check("modo de acumulado = razon", r.json()["modo_acumulado"] == "razon", r.json())

    # Manual de valor directo, mejor hacia abajo
    r = portal.post("/indicadores", json={
        "nombre": "Accidentes de trabajo", "unidad": "cantidad", "tipo_captura": "valor",
        "area": "Gestión humana", "meta": 0, "direccion": "abajo",
        "umbral_verde": 0, "umbral_amarillo": 1,
    })
    I_ACC = r.json()["id"]
    v.check("cantidad se acumula sumando", r.json()["modo_acumulado"] == "suma", r.json())

    # Automatico
    r = portal.post("/indicadores", json={
        "nombre": "Oportunidad PQRS", "unidad": "porcentaje", "tipo_captura": "automatico",
        "fuente_automatica": "pqrs_oportunidad_sla", "area": "Calidad",
        "meta": 90, "direccion": "arriba", "umbral_verde": 90, "umbral_amarillo": 75,
    })
    v.check("crear indicador automatico -> 201", r.status_code == 201, r.text[:150])
    I_AUTO = r.json()["id"]
    v.check("queda marcado como automatico", r.json()["es_automatico"] is True, r.json())

    r = portal.post("/indicadores", json={"nombre": "X", "tipo_captura": "automatico"})
    v.check("automatico sin fuente -> 400", r.status_code == 400, r.text[:100])
    r = portal.post("/indicadores", json={"nombre": "X", "tipo_captura": "automatico",
                                     "fuente_automatica": "no_existe"})
    v.check("fuente inexistente -> 400", r.status_code == 400, r.text[:100])
    r = portal.post("/indicadores", json={"nombre": "X", "unidad": "kilos"})
    v.check("unidad invalida -> 422", r.status_code == 422, r.status_code)

    # ── Registrar mediciones ──
    r = portal.post(f"/indicadores/{I_RAZON}/mediciones",
               data={"anio": A, "mes": M, "numerador": 18, "denominador": 20})
    v.check("registrar razon -> 201", r.status_code == 201, r.text[:150])
    v.check("calcula el porcentaje solo", r.json()["valor"] == 90.0, r.json())

    r = portal.post(f"/indicadores/{I_RAZON}/mediciones", data={"anio": A, "mes": M, "valor": 50})
    v.check("faltando num/den -> 400", r.status_code == 400, r.text[:120])
    r = portal.post(f"/indicadores/{I_RAZON}/mediciones",
               data={"anio": A, "mes": M, "numerador": 5, "denominador": 0})
    v.check("denominador cero -> 400", r.status_code == 400, r.text[:120])
    r = portal.post(f"/indicadores/{I_RAZON}/mediciones", data={"anio": A, "mes": 13, "numerador": 1, "denominador": 2})
    v.check("mes invalido -> 400", r.status_code == 400, r.text[:100])

    r = portal.post(f"/indicadores/{I_AUTO}/mediciones", data={"anio": A, "mes": M, "valor": 99})
    v.check("no se puede digitar un automatico -> 400", r.status_code == 400, r.text[:120])

    portal.post(f"/indicadores/{I_ACC}/mediciones", data={"anio": A, "mes": M, "valor": 2})

    # ── Correccion y historial ──
    v.check("sin cambios aun, historial vacio",
          portal.get(f"/indicadores/{I_RAZON}/historial").json() == [])
    r = portal.post(f"/indicadores/{I_RAZON}/mediciones",
               data={"anio": A, "mes": M, "numerador": 19, "denominador": 20,
                     "motivo": "Faltaba registrar una capacitacion"})
    v.check("corregir el valor -> 201", r.status_code == 201, r.text[:120])
    v.check("el valor quedo actualizado", r.json()["valor"] == 95.0, r.json())
    h = portal.get(f"/indicadores/{I_RAZON}/historial").json()
    v.check("la correccion quedo en el historial", len(h) == 1, h)
    v.check("con el valor anterior", h[0]["valor_anterior"] == 90.0, h[0])
    v.check("y el nuevo", h[0]["valor_nuevo"] == 95.0, h[0])
    v.check("y el motivo", "capacitacion" in (h[0]["motivo"] or ""), h[0])
    v.check("y quien lo hizo", h[0]["usuario_nombre"] == "Admin", h[0])

    # Volver a guardar lo mismo no debe ensuciar el historial
    portal.post(f"/indicadores/{I_RAZON}/mediciones", data={"anio": A, "mes": M, "numerador": 19, "denominador": 20})
    v.check("reguardar el mismo valor no genera historial",
          len(portal.get(f"/indicadores/{I_RAZON}/historial").json()) == 1)

    # Un solo registro por mes
    v.check("no se duplican mediciones del mismo mes",
          len([m for m in portal.get(f"/indicadores/{I_RAZON}").json()["serie"] if m["valor"] is not None]) == 1)

    # ── Semaforo ──
    def semaforo_de(iid, anio=A, mes=M):
        return portal.get(f"/indicadores/{iid}?anio={anio}&mes={mes}").json()["semaforo"]
    v.check("95% con umbral 90 = verde", semaforo_de(I_RAZON) == "verde", semaforo_de(I_RAZON))
    # Accidentes: mejor hacia abajo, verde<=0, amarillo<=1; hay 2 => rojo
    v.check("2 accidentes con meta 0 = rojo", semaforo_de(I_ACC) == "rojo", semaforo_de(I_ACC))
    portal.post(f"/indicadores/{I_ACC}/mediciones", data={"anio": A, "mes": 6, "valor": 1})
    v.check("1 accidente = amarillo", semaforo_de(I_ACC, mes=6) == "amarillo", semaforo_de(I_ACC, mes=6))
    portal.post(f"/indicadores/{I_ACC}/mediciones", data={"anio": A, "mes": 5, "valor": 0})
    v.check("0 accidentes = verde", semaforo_de(I_ACC, mes=5) == "verde", semaforo_de(I_ACC, mes=5))
    v.check("un mes sin registrar = sin_datos", semaforo_de(I_RAZON, mes=2) == "sin_datos")

    # ── Acumulados ──
    # Junio 2/2 (100%) y Julio 19/20 (95%): el acumulado correcto es 21/22 = 95.45,
    # NO el promedio 97.5.
    portal.post(f"/indicadores/{I_RAZON}/mediciones", data={"anio": A, "mes": 6, "numerador": 2, "denominador": 2})
    ficha = portal.get(f"/indicadores/{I_RAZON}?anio={A}&mes={M}").json()
    anual = ficha["acumulado_anio"]
    v.check("el acumulado suma num y den, no promedia porcentajes",
          anual["valor"] == 95.45, anual)
    v.check("y guarda de donde sale", anual["numerador"] == 21 and anual["denominador"] == 22, anual)
    v.check("el promedio ingenuo (97.5) NO es el resultado", anual["valor"] != 97.5, anual)
    # Julio cae en el tercer trimestre; junio en el segundo.
    tri = ficha["acumulado_trimestre"]
    v.check("el trimestre solo abarca sus propios meses",
          ficha["trimestre"] == 3 and tri["denominador"] == 20, {"tri": ficha["trimestre"], "acc": tri})

    acc = portal.get(f"/indicadores/{I_ACC}?anio={A}&mes={M}").json()
    v.check("las cantidades se acumulan sumando",
          acc["acumulado_anio"]["valor"] == 3, acc["acumulado_anio"])

    # ── Comparaciones ──
    ficha = portal.get(f"/indicadores/{I_RAZON}?anio={A}&mes={M}").json()
    v.check("trae el valor del mes anterior", ficha["valor_mes_anterior"] == 100.0, ficha["valor_mes_anterior"])
    v.check("y la variacion contra el mes anterior", ficha["variacion_mes"] == -5.0, ficha["variacion_mes"])
    v.check("sin dato del año pasado, la variacion es None", ficha["variacion_anio"] is None, ficha)
    v.check("la serie trae los 12 meses", len(ficha["serie"]) == 12, len(ficha["serie"]))
    v.check("los meses sin dato vienen en null",
          ficha["serie"][0]["valor"] is None, ficha["serie"][0])

    # ── Indicadores automaticos ──
    d = lambda dia: datetime(A, M, dia, 12, tzinfo=timezone.utc)
    s = portal.Session()
    s.add_all([
        PQRSSolicitud(tenant_id=portal.tenant_id, tipo="reclamo", cliente_nombre="C1", descripcion="x",
                      fecha_creacion=d(1), fecha_limite_sla=d(9), fecha_cierre=d(5)),
        PQRSSolicitud(tenant_id=portal.tenant_id, tipo="queja", cliente_nombre="C2", descripcion="x",
                      fecha_creacion=d(2), fecha_limite_sla=d(6), fecha_cierre=d(15)),
    ])
    s.commit(); s.close()

    r = portal.post(f"/indicadores/{I_AUTO}/calcular?anio={A}&mes={M}")
    v.check("recalcular -> 200", r.status_code == 200, r.text[:150])
    v.check("calcula 1 de 2 = 50%", r.json()["valor"] == 50.0, r.json())
    v.check("guarda numerador y denominador", r.json()["numerador"] == 1 and r.json()["denominador"] == 2, r.json())
    v.check("y explica de donde sale", "de 2" in (r.json()["observacion"] or ""), r.json())

    r = portal.post(f"/indicadores/{I_AUTO}/calcular?anio={A}&mes={M}")
    v.check("recalcular es idempotente", r.status_code == 200 and r.json()["valor"] == 50.0)
    v.check("no duplica la medicion",
          len([m for m in portal.get(f"/indicadores/{I_AUTO}").json()["serie"] if m["valor"] is not None]) == 1)

    r = portal.post(f"/indicadores/{I_RAZON}/calcular?anio={A}&mes={M}")
    v.check("no se puede recalcular un manual -> 400", r.status_code == 400, r.text[:120])

    r = portal.post(f"/indicadores/calcular-periodo?anio={A}&mes={M}")
    v.check("calcular todo el periodo -> 200", r.status_code == 200, r.text[:120])
    v.check("calculo el unico automatico", len(r.json()["calculados"]) == 1, r.json())
    v.check("sin errores", r.json()["errores"] == [], r.json())

    # ── Tablero ──
    tab = portal.get(f"/indicadores/tablero?anio={A}&mes={M}").json()
    v.check("trae los 3 indicadores", tab["resumen"]["total"] == 3, tab["resumen"])
    v.check("nombra el mes", tab["mes_nombre"] == "Julio", tab["mes_nombre"])
    v.check("cuenta verdes y rojos",
          tab["resumen"]["verde"] == 1 and tab["resumen"]["rojo"] == 2, tab["resumen"])
    v.check("cumplimiento = 1 de 3 = 33.3%", tab["resumen"]["cumplimiento_pct"] == 33.3, tab["resumen"])
    v.check("agrupa por area", {a["area"] for a in tab["por_area"]} == {"Gestión humana", "Calidad"},
          [a["area"] for a in tab["por_area"]])
    v.check("ofrece las areas para filtrar",
          set(tab["areas_disponibles"]) == {"Gestión humana", "Calidad"}, tab["areas_disponibles"])
    v.check("cada indicador trae su serie", all("serie" in i for i in tab["indicadores"]))

    tab_th = portal.get(f"/indicadores/tablero?anio={A}&mes={M}&area=Gestión humana").json()
    v.check("filtra por area", tab_th["resumen"]["total"] == 2, tab_th["resumen"])

    # Pendientes de registro: un manual sin valor en el periodo
    portal.post("/indicadores", json={"nombre": "Rotacion de personal", "unidad": "porcentaje",
                                 "tipo_captura": "valor", "area": "Gestión humana", "meta": 5,
                                 "direccion": "abajo"})
    tab = portal.get(f"/indicadores/tablero?anio={A}&mes={M}").json()
    v.check("avisa cuales faltan por registrar", tab["resumen"]["pendientes_registro"] == 1, tab["resumen"])
    v.check("y dice cuales son", tab["pendientes"][0]["nombre"] == "Rotacion de personal", tab["pendientes"])
    v.check("los sin datos no bajan el cumplimiento",
          tab["resumen"]["cumplimiento_pct"] == 33.3, tab["resumen"])

    # ── Borrar vs desactivar ──
    r = portal.delete(f"/indicadores/{I_RAZON}")
    v.check("borrar uno con historico -> 409", r.status_code == 409, r.text[:130])
    v.check("y sugiere desactivarlo", "esact" in r.json()["detail"], r.json())
    vacio = portal.post("/indicadores", json={"nombre": "Desechable"}).json()["id"]
    v.check("borrar uno sin mediciones -> 204", portal.delete(f"/indicadores/{vacio}").status_code == 204)

    portal.patch(f"/indicadores/{I_ACC}", json={"activo": False})
    tab = portal.get(f"/indicadores/tablero?anio={A}&mes={M}").json()
    v.check("desactivar lo saca del tablero",
          all(i["id"] != I_ACC for i in tab["indicadores"]), [i["id"] for i in tab["indicadores"]])
    v.check("pero el indicador sigue existiendo",
          portal.get(f"/indicadores/{I_ACC}").status_code == 200)
    portal.patch(f"/indicadores/{I_ACC}", json={"activo": True})

    # ── Permisos ──
    portal.como("gerencia")
    v.check("gerencia ve el tablero", portal.get(f"/indicadores/tablero?anio={A}&mes={M}").status_code == 200)
    v.check("gerencia ve el detalle", portal.get(f"/indicadores/{I_RAZON}").status_code == 200)
    v.check("gerencia NO crea indicadores",
          portal.post("/indicadores", json={"nombre": "X"}).status_code == 403)
    v.check("gerencia NO registra mediciones",
          portal.post(f"/indicadores/{I_RAZON}/mediciones",
                 data={"anio": A, "mes": 3, "numerador": 1, "denominador": 2}).status_code == 403)
    v.check("gerencia NO recalcula",
          portal.post(f"/indicadores/{I_AUTO}/calcular?anio={A}&mes={M}").status_code == 403)
    v.check("gerencia NO edita la ficha",
          portal.patch(f"/indicadores/{I_RAZON}", json={"meta": 10}).status_code == 403)


