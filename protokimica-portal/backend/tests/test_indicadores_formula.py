"""
Indicadores con fórmula personalizada: `80 × A ÷ B`, `(A − B) ÷ A × 100`.

Lo que se protege aquí:
- la fórmula se evalúa con un analizador propio, nunca con `eval`;
- se guardan las variables de cada mes, no solo el resultado;
- el acumulado suma variables y aplica la fórmula una vez (no promedia);
- dividir por cero deja el mes sin registrar, no en cero;
- cambiar la fórmula con meses registrados recalcula y deja rastro.
"""
import json

import pytest

from app.modules.indicadores import formula as f

A, M = 2026, 7


# ── El evaluador, sin base de datos ──────────────────────────────────

@pytest.mark.parametrize("expresion,valores,esperado", [
    ("80 * A / B", {"A": 45, "B": 50}, 72),
    ("(A - B) / A * 100", {"A": 200, "B": 150}, 25),
    ("A + B * 2", {"A": 1, "B": 3}, 7),          # primero × y ÷
    ("(A + B) * 2", {"A": 1, "B": 3}, 8),
    ("-A + 10", {"A": 4}, 6),
    ("2,5 × A ÷ B", {"A": 10, "B": 5}, 5),         # coma decimal y símbolos de pantalla
    ("A / B * 1000", {"A": 3, "B": 1500}, 2),
])
def test_evalua_con_la_precedencia_de_siempre(expresion, valores, esperado):
    assert f.evaluar(expresion, valores) == esperado


@pytest.mark.parametrize("expresion,pista", [
    ("80A", "Falta un operador"),
    ("80 * (A / B", "Falta cerrar"),
    ("A + * B", "dos operadores"),
    ("A * ", "termina en un operador"),
    ("()", "vacíos"),
    ("A ) + B", "Sobra"),
    ("__import__('os')", "no se entiende"),
    ("a + b", "no es una variable"),
    ("", "vacía"),
])
def test_rechaza_lo_que_no_es_una_formula_y_dice_que_corregir(expresion, pista):
    with pytest.raises(f.ErrorFormula) as e:
        f.analizar(expresion)
    assert pista in str(e.value)


def test_dividir_por_cero_no_es_cero():
    with pytest.raises(f.DivisionPorCero):
        f.evaluar("A / B", {"A": 1, "B": 0})


def test_las_variables_deben_coincidir_con_las_declaradas():
    with pytest.raises(f.ErrorFormula, match="no está entre las variables"):
        f.validar("A / C", ["A", "B"])
    with pytest.raises(f.ErrorFormula, match="no se usa"):
        f.validar("A * 2", ["A", "B"])
    f.validar("80 * A / B", ["A", "B"])


def test_se_lee_en_palabras():
    texto = f.legible("80 * A / B", {"A": "Quejas atendidas", "B": "Total de quejas"})
    assert texto == "80 × Quejas atendidas ÷ Total de quejas"


# ── A través de la API ───────────────────────────────────────────────

VARIABLES = [{"letra": "A", "etiqueta": "Quejas atendidas a tiempo"},
             {"letra": "B", "etiqueta": "Total de quejas"}]


def _crear(entorno, **extra):
    cuerpo = {
        "nombre": "Oportunidad ponderada", "unidad": "porcentaje", "tipo_captura": "formula",
        "formula": "80 × A ÷ B", "variables": VARIABLES, "area": "Calidad",
        "meta": 70, "direccion": "arriba",
    }
    cuerpo.update(extra)
    return entorno.post("/indicadores", json=cuerpo)


def _registrar(entorno, iid, mes, valores, **extra):
    return entorno.post(f"/indicadores/{iid}/mediciones", data={
        "anio": A, "mes": mes, "variables": json.dumps(valores),
        "analisis": "Dentro de lo esperado.", **extra,
    })


def test_crear_un_indicador_de_formula(entorno, v):
    r = _crear(entorno)
    v.check("201", r.status_code == 201, r.text[:300])
    datos = r.json()
    v.check("guarda la forma canónica", datos["formula"] == "80 * A / B", datos)
    v.check("y la dice en palabras",
            datos["formula_legible"] == "80 × Quejas atendidas a tiempo ÷ Total de quejas", datos)
    v.check("con sus variables", [x["letra"] for x in datos["variables"]] == ["A", "B"], datos)
    v.check("acumula por fórmula", datos["modo_acumulado"] == "formula", datos)


def test_una_formula_mal_armada_no_se_guarda(entorno, v):
    r = _crear(entorno, formula="80 * A /")
    v.check("400", r.status_code == 400, r.text[:300])
    v.check("dice qué corregir", "operador" in r.json()["detail"], r.json())

    r = _crear(entorno, formula="80 * A")
    v.check("variable sin usar: 400", r.status_code == 400, r.text[:300])

    r = _crear(entorno, variables=[{"letra": "A", "etiqueta": " "}, VARIABLES[1]])
    v.check("variable sin nombre: 400", r.status_code == 400, r.text[:300])


def test_registrar_un_mes_calcula_y_guarda_las_variables(entorno, v):
    iid = _crear(entorno).json()["id"]
    r = _registrar(entorno, iid, M, {"A": 45, "B": 50})
    v.check("201", r.status_code == 201, r.text[:300])
    v.check("valor calculado por el servidor", r.json()["valor"] == 72, r.json())
    v.check("guarda los números de base", r.json()["variables"] == {"A": 45, "B": 50}, r.json())

    ficha = entorno.get(f"/indicadores/{iid}", params={"anio": A, "mes": M}).json()
    v.check("la ficha trae las variables del mes", ficha["valores_variables"] == {"A": 45, "B": 50}, ficha)
    v.check("y el semáforo", ficha["semaforo"] == "verde", ficha["semaforo"])


def test_no_se_puede_mandar_el_valor_a_mano(entorno, v):
    """El valor lo calcula el servidor: un `valor` en el formulario se ignora."""
    iid = _crear(entorno).json()["id"]
    r = _registrar(entorno, iid, M, {"A": 45, "B": 50}, valor=99)
    v.check("se ignora el valor enviado", r.json()["valor"] == 72, r.json())


def test_falta_una_variable(entorno, v):
    iid = _crear(entorno).json()["id"]
    r = _registrar(entorno, iid, M, {"A": 45})
    v.check("400", r.status_code == 400, r.text[:300])
    v.check("dice cuál", "Total de quejas" in r.json()["detail"], r.json())


def test_dividir_por_cero_deja_el_mes_sin_registrar(entorno, v):
    iid = _crear(entorno).json()["id"]
    r = _registrar(entorno, iid, M, {"A": 0, "B": 0})
    v.check("400", r.status_code == 400, r.text[:300])
    v.check("explica qué hacer", "sin registrar" in r.json()["detail"], r.json())


def test_el_acumulado_suma_variables_no_promedia(entorno, v):
    """
    Julio 9 de 10 (72) y agosto 1 de 90 (0,89). Promediar daría 36,4; la
    cuenta correcta es 80 × 10 ÷ 100 = 8.
    """
    iid = _crear(entorno).json()["id"]
    _registrar(entorno, iid, 7, {"A": 9, "B": 10})
    _registrar(entorno, iid, 8, {"A": 1, "B": 90})
    ficha = entorno.get(f"/indicadores/{iid}", params={"anio": A, "mes": 8}).json()
    acumulado = ficha["acumulado_anio"]
    v.check("80 × 10 ÷ 100 = 8", acumulado["valor"] == 8, acumulado)
    v.check("con las sumas", acumulado["variables"] == {"A": 10, "B": 100}, acumulado)


def test_cambiar_la_formula_recalcula_y_deja_rastro(entorno, v):
    iid = _crear(entorno).json()["id"]
    _registrar(entorno, iid, M, {"A": 45, "B": 50})

    r = entorno.patch(f"/indicadores/{iid}", json={"formula": "A / B * 100"})
    v.check("se acepta", r.status_code == 200, r.text[:300])
    ficha = entorno.get(f"/indicadores/{iid}", params={"anio": A, "mes": M}).json()
    v.check("el mes se recalculó", ficha["valor"] == 90, ficha["valor"])

    historial = entorno.get(f"/indicadores/{iid}/historial").json()
    v.check("queda en el historial", len(historial) == 1, historial)
    v.check("con antes y después", historial[0]["valor_anterior"] == 72
            and historial[0]["valor_nuevo"] == 90, historial)
    v.check("y el motivo dice la fórmula", "Cambió la fórmula" in (historial[0]["motivo"] or ""), historial)


def test_renombrar_variables_con_meses_registrados_si_se_puede(entorno, v):
    iid = _crear(entorno).json()["id"]
    _registrar(entorno, iid, M, {"A": 45, "B": 50})
    r = entorno.patch(f"/indicadores/{iid}", json={"variables": [
        {"letra": "A", "etiqueta": "Quejas cerradas en plazo"}, VARIABLES[1]]})
    v.check("200", r.status_code == 200, r.text[:300])
    v.check("nombre nuevo", r.json()["variables"][0]["etiqueta"] == "Quejas cerradas en plazo")


def test_agregar_variables_con_meses_registrados_no(entorno, v):
    iid = _crear(entorno).json()["id"]
    _registrar(entorno, iid, M, {"A": 45, "B": 50})
    r = entorno.patch(f"/indicadores/{iid}", json={
        "formula": "80 * A / (B + C)",
        "variables": VARIABLES + [{"letra": "C", "etiqueta": "Reabiertas"}],
    })
    v.check("409", r.status_code == 409, r.text[:300])
    v.check("explica la salida", "indicador nuevo" in r.json()["detail"], r.json())


def test_cambiar_a_otro_tipo_con_meses_registrados_no(entorno, v):
    iid = _crear(entorno).json()["id"]
    _registrar(entorno, iid, M, {"A": 45, "B": 50})
    r = entorno.patch(f"/indicadores/{iid}", json={"tipo_captura": "valor"})
    v.check("409", r.status_code == 409, r.text[:300])


def test_sin_meses_se_puede_rearmar_todo(entorno, v):
    iid = _crear(entorno).json()["id"]
    r = entorno.patch(f"/indicadores/{iid}", json={
        "formula": "(A + B) / C * 100",
        "variables": VARIABLES + [{"letra": "C", "etiqueta": "Total del periodo"}],
    })
    v.check("200", r.status_code == 200, r.text[:300])
    v.check("tres variables", len(r.json()["variables"]) == 3, r.json())


def test_probar_formula_sin_guardar(entorno, v):
    r = entorno.post("/indicadores/formula/probar", json={
        "formula": "80 * A / B", "variables": VARIABLES, "valores": {"A": 45, "B": 50},
    })
    v.check("válida con resultado", r.json() == {
        "valida": True, "error": None,
        "legible": "80 × Quejas atendidas a tiempo ÷ Total de quejas",
        "resultado": 72.0, "divide_por_cero": False,
    }, r.json())

    r = entorno.post("/indicadores/formula/probar", json={"formula": "80 *", "variables": VARIABLES})
    v.check("inválida con explicación", r.json()["valida"] is False and r.json()["error"], r.json())

    r = entorno.post("/indicadores/formula/probar", json={
        "formula": "A / B", "variables": VARIABLES, "valores": {"A": 1, "B": 0}})
    v.check("avisa la división por cero", r.json()["divide_por_cero"] is True, r.json())


def test_borrar_con_mediciones_se_lleva_las_variables(entorno, v):
    iid = _crear(entorno).json()["id"]
    _registrar(entorno, iid, M, {"A": 45, "B": 50})
    r = entorno.delete(f"/indicadores/{iid}", params={"incluir_mediciones": True})
    v.check("204", r.status_code == 204, r.text[:300])


def test_quien_no_entra_al_modulo_no_prueba_formulas(entorno, v):
    entorno.como("logistica")   # agente: no abre Indicadores
    r = entorno.post("/indicadores/formula/probar", json={"formula": "A", "variables": []})
    v.check("403", r.status_code == 403, r.text[:300])
