"""
Actividades diarias: lo que se repite y no pertenece a ningún proyecto.

Lo que se defiende aquí es la decisión de fondo del módulo: **las ocurrencias
no se guardan, se deducen**. No hay una fila por día esperando a que alguien
la marque; hay una frecuencia, y contra ella se cuentan los registros. Si esa
deducción se equivoca, el indicador miente y nadie tiene cómo notarlo — no
hay una tabla contra la cual comparar.

Por eso las pruebas de frecuencia van con fechas fijas y no con «hoy»: una
prueba que dependa del día en que se corre pasa el martes y falla el sábado.
"""
from datetime import date, timedelta

from app.models.master_planner import ActividadDiaria
from app.modules.master_planner import actividades as act

# Semana del lunes 5 al domingo 11 de octubre de 2026. El 12 de octubre de
# 2026 cae lunes y es festivo en Colombia (Día de la Raza), así que sirve
# para probar que «días hábiles» lo tiene en cuenta.
LUNES = date(2026, 10, 5)
SABADO = date(2026, 10, 10)
FESTIVO = date(2026, 10, 12)


def _def(**extra):
    """Una definición suelta, sin tocar la base: la regla es pura."""
    base = dict(
        titulo="Revisar el correo del área", frecuencia="diaria",
        solo_dias_habiles=True, desde=date(2026, 1, 1), hasta=None,
        dias_semana=None, dia_mes=None, activa=True,
    )
    base.update(extra)
    return ActividadDiaria(**base)


# ── Qué día tocaba ───────────────────────────────────────────────────

def test_la_diaria_no_cae_en_sabado_ni_en_festivo(v):
    """
    Lo normal en una oficina. Contar el sábado dejaría toda actividad diaria
    con dos incumplimientos por semana que nadie podía evitar.
    """
    diaria = _def()
    v.check("el lunes sí", act.se_espera_el(diaria, LUNES) is True)
    v.check("el sábado no", act.se_espera_el(diaria, SABADO) is False)
    v.check("y el festivo tampoco", act.se_espera_el(diaria, FESTIVO) is False)


def test_si_se_pide_todos_los_dias_el_sabado_cuenta(v):
    """Una ronda de planta sí se hace en fin de semana."""
    todos = _def(solo_dias_habiles=False)
    v.check("el sábado sí", act.se_espera_el(todos, SABADO) is True)
    v.check("y el festivo también", act.se_espera_el(todos, FESTIVO) is True)


def test_la_semanal_solo_toca_los_dias_marcados(v):
    semanal = _def(frecuencia="semanal", dias_semana="1,3")   # lunes y miércoles
    v.check("lunes", act.se_espera_el(semanal, LUNES) is True)
    v.check("martes no", act.se_espera_el(semanal, LUNES + timedelta(days=1)) is False)
    v.check("miércoles", act.se_espera_el(semanal, LUNES + timedelta(days=2)) is True)


def test_la_mensual_de_un_31_se_espera_el_ultimo_dia_del_mes(v):
    """
    Saltarse el mes haría que una actividad mensual desapareciera en febrero
    y en los cuatro meses de treinta días, y nadie lo notaría hasta que el
    indicador diera de más.
    """
    mensual = _def(frecuencia="mensual", dia_mes=31)
    v.check("en noviembre, que tiene 30", act.se_espera_el(mensual, date(2026, 11, 30)) is True)
    v.check("y no el 29", act.se_espera_el(mensual, date(2026, 11, 29)) is False)
    v.check("en febrero, el 28", act.se_espera_el(mensual, date(2026, 2, 28)) is True)
    v.check("en octubre sí el 31", act.se_espera_el(mensual, date(2026, 10, 31)) is True)


def test_antes_de_existir_no_se_esperaba_nada(v):
    """
    Si no, crear una actividad hoy la haría nacer con todo el mes anterior
    incumplido — y el indicador del área caería por algo que no pasó.
    """
    nueva = _def(desde=date(2026, 10, 7))
    v.check("el día anterior no cuenta", act.se_espera_el(nueva, date(2026, 10, 6)) is False)
    v.check("desde su día sí", act.se_espera_el(nueva, date(2026, 10, 7)) is True)


def test_al_desactivarla_deja_de_esperarse(v):
    """Sin `hasta`, apagarla hoy dejaría el resto del mes contándose en rojo."""
    cerrada = _def(hasta=date(2026, 10, 7))
    v.check("hasta ese día sí", act.se_espera_el(cerrada, date(2026, 10, 7)) is True)
    v.check("después ya no", act.se_espera_el(cerrada, date(2026, 10, 8)) is False)


def test_la_frecuencia_se_dice_en_palabras(v):
    """La redacta el servidor: si la armara la pantalla, agregar una
    frecuencia dejaría un sitio más que actualizar."""
    v.check("diaria hábil",
            act.descripcion_frecuencia(_def()) == "Todos los días hábiles")
    v.check("semanal de un día",
            act.descripcion_frecuencia(_def(frecuencia="semanal", dias_semana="2"))
            == "Cada martes")
    v.check("semanal de varios",
            act.descripcion_frecuencia(_def(frecuencia="semanal", dias_semana="1,3,5"))
            == "Cada lunes, miércoles y viernes")
    v.check("mensual",
            "día 15" in act.descripcion_frecuencia(_def(frecuencia="mensual", dia_mes=15)))


def test_el_mes_en_curso_se_mide_hasta_ayer(v):
    """
    Lo de hoy todavía se puede hacer. Contarlo como incumplido pondría el
    indicador en rojo cada mañana y en verde cada noche.
    """
    hoy = date(2026, 10, 15)
    desde, hasta = act.corte_del_mes(2026, 10, hoy)
    v.check("arranca el primero", desde == date(2026, 10, 1), desde)
    v.check("y corta ayer", hasta == date(2026, 10, 14), hasta)

    # Un mes ya pasado se mide completo.
    _, fin = act.corte_del_mes(2026, 9, hoy)
    v.check("un mes cerrado va entero", fin == date(2026, 9, 30), fin)


# ── Contra la API ────────────────────────────────────────────────────

def _crear(entorno, **extra):
    cuerpo = {"titulo": "Revisar el correo del área", "frecuencia": "diaria"}
    cuerpo.update(extra)
    return entorno.post("/master-planner/actividades", json=cuerpo)


def test_una_actividad_nace_con_responsable_y_area(entorno, v):
    entorno.como("calidad")
    r = _crear(entorno)
    v.check("se crea", r.status_code == 201, r.text[:250])
    v.check("es de quien la creó", r.json()["asignado_nombre"] == "Cali", r.json())
    v.check("y hereda su área", r.json()["area"] == "Calidad", r.json())
    v.check("con la frecuencia en palabras",
            r.json()["frecuencia_texto"] == "Todos los días hábiles", r.json())


def test_no_arranca_antes_de_existir(entorno, v):
    entorno.como("calidad")
    r = _crear(entorno)
    v.check("empieza hoy", r.json()["desde"] == date.today().isoformat(), r.json())


def test_una_semanal_sin_dias_no_le_tocaria_a_nadie(entorno, v):
    entorno.como("calidad")
    r = _crear(entorno, frecuencia="semanal", dias_semana=[])
    v.check("no se crea", r.status_code == 400, r.status_code)
    v.check("y dice qué falta", "día de la semana" in r.json().get("detail", ""), r.json())


def test_una_mensual_sin_dia_tampoco(entorno, v):
    entorno.como("calidad")
    r = _crear(entorno, frecuencia="mensual")
    v.check("no se crea", r.status_code == 400, r.status_code)


def test_se_registra_que_se_hizo_y_no_dos_veces(entorno, v):
    entorno.como("calidad")
    aid = _crear(entorno, solo_dias_habiles=False).json()["id"]

    r = entorno.post(f"/master-planner/actividades/{aid}/registros", json={})
    v.check("se registra", r.status_code == 201, r.text[:250])
    v.check("con quién lo marcó", r.json()["usuario_nombre"] == "Cali", r.json())

    r = entorno.post(f"/master-planner/actividades/{aid}/registros", json={})
    v.check("el mismo día no entra dos veces", r.status_code == 409, r.status_code)


def test_no_se_registra_un_dia_que_no_ha_llegado(entorno, v):
    """Dar por hecho lo que todavía no pasa es dar por cumplido lo que no está."""
    entorno.como("calidad")
    aid = _crear(entorno, solo_dias_habiles=False).json()["id"]

    manana = (date.today() + timedelta(days=1)).isoformat()
    r = entorno.post(f"/master-planner/actividades/{aid}/registros",
                     json={"fecha": manana})
    v.check("no entra", r.status_code == 400, r.status_code)
    v.check("y dice por qué", "todavía no llega" in r.json().get("detail", ""), r.json())


def test_no_se_registra_un_dia_en_que_no_tocaba(entorno, v):
    entorno.como("calidad")
    # Solo los lunes; se intenta registrar un día que no es lunes.
    aid = _crear(entorno, frecuencia="semanal", dias_semana=[1]).json()["id"]
    hoy = date.today()
    no_lunes = hoy - timedelta(days=1) if hoy.isoweekday() == 1 else hoy

    r = entorno.post(f"/master-planner/actividades/{aid}/registros",
                     json={"fecha": no_lunes.isoformat()})
    if no_lunes.isoweekday() != 1:
        v.check("no entra", r.status_code == 400, r.status_code)
        v.check("y dice cuándo toca", "cada lunes" in r.json().get("detail", "").lower(),
                r.json())


def test_la_lista_dice_si_toca_hoy_y_si_ya_se_registro(entorno, v):
    """Es lo único que la pantalla necesita para pintar la casilla."""
    entorno.como("calidad")
    aid = _crear(entorno, solo_dias_habiles=False).json()["id"]

    fila = entorno.get("/master-planner/actividades").json()[0]
    v.check("toca hoy", fila["toca_hoy"] is True, fila)
    v.check("y todavía no se registró", fila["registrada_hoy"] is False, fila)

    entorno.post(f"/master-planner/actividades/{aid}/registros", json={})
    fila = entorno.get("/master-planner/actividades").json()[0]
    v.check("ahora sí", fila["registrada_hoy"] is True, fila)


def test_desactivarla_cierra_su_periodo(entorno, v):
    entorno.como("calidad")
    aid = _crear(entorno).json()["id"]

    r = entorno.patch(f"/master-planner/actividades/{aid}", json={"activa": False})
    v.check("se desactiva", r.status_code == 200, r.text[:250])
    v.check("y queda con fecha de cierre", r.json()["hasta"] == date.today().isoformat(),
            r.json())

    r = entorno.patch(f"/master-planner/actividades/{aid}", json={"activa": True})
    v.check("al reactivarla se vuelve a abrir", r.json()["hasta"] is None, r.json())


def test_una_actividad_con_registros_no_se_borra(entorno, v):
    """
    Es la constancia de que alguien hizo su trabajo. Lo que se necesita ahí
    es desactivarla, y el 409 tiene que decirlo.
    """
    entorno.como("calidad")
    aid = _crear(entorno, solo_dias_habiles=False).json()["id"]
    entorno.post(f"/master-planner/actividades/{aid}/registros", json={})

    r = entorno.delete(f"/master-planner/actividades/{aid}")
    v.check("no se borra", r.status_code == 409, r.status_code)
    v.check("y ofrece desactivarla", "esactí" in r.json().get("detail", "")
            or "esactiv" in r.json().get("detail", ""), r.json())


def test_una_creada_por_error_si_se_borra(entorno, v):
    entorno.como("calidad")
    aid = _crear(entorno, titulo="Me equivoqué al crearla").json()["id"]
    v.check("se borra", entorno.delete(f"/master-planner/actividades/{aid}").status_code == 204)


def test_un_agente_no_le_pone_actividades_a_otro(entorno, v):
    """Uno crea las suyas; un líder crea para su área."""
    entorno.como("logistica")   # agente
    r = _crear(entorno, asignado_a=entorno.ids["tics"])
    v.check("no puede", r.status_code == 403, r.status_code)
    v.check("y dice a quién pedírselo", "líder" in r.json().get("detail", ""), r.json())


def test_un_lider_si_le_pone_actividades_a_su_area(entorno, v):
    entorno.como("tics")   # líder de TICS
    r = _crear(entorno, asignado_a=entorno.ids["lectura"])   # lectura está en TICS
    v.check("puede", r.status_code == 201, r.text[:250])
    v.check("y queda a nombre de esa persona", r.json()["asignado_nombre"] == "Lector",
            r.json())


def test_lo_ajeno_no_aparece(entorno, v):
    entorno.como("calidad")
    _crear(entorno, titulo="Cosa de Calidad")

    entorno.como("logistica")
    titulos = [a["titulo"] for a in entorno.get("/master-planner/actividades").json()]
    v.check("no ve la de otra área", "Cosa de Calidad" not in titulos, titulos)


# ── El indicador ─────────────────────────────────────────────────────

def test_el_indicador_cuenta_lo_registrado_sobre_lo_que_tocaba(entorno, v):
    from app.modules.indicadores import fuentes

    entorno.como("calidad")
    aid = _crear(entorno, solo_dias_habiles=False).json()["id"]
    entorno.post(f"/master-planner/actividades/{aid}/registros", json={})

    hoy = date.today()
    db = entorno.Session()
    # Se mide el mes en curso: como el corte es «hasta ayer», el registro de
    # hoy no entra todavía — justamente lo que la regla dice.
    r = fuentes.calcular("mp_actividades_diarias", db, entorno.tenant_id,
                         hoy.year, hoy.month, area="Calidad")
    db.close()

    v.check("da un resultado", r is not None)
    v.check("y guarda los dos números, no solo el porcentaje",
            r.numerador is not None and r.denominador is not None, r)


def test_sin_actividades_programadas_no_hay_incumplimiento(entorno, v):
    """Un 0% diría que nadie cumplió; lo cierto es que no había qué cumplir."""
    from app.modules.indicadores import fuentes

    db = entorno.Session()
    r = fuentes.calcular("mp_actividades_diarias", db, entorno.tenant_id,
                         2020, 1, area="Calidad")
    db.close()

    v.check("sin dato, no cero", r.valor is None, r)
    v.check("y lo explica", "No había" in (r.detalle or ""), r)


# ── El mes, día por día ──────────────────────────────────────────────

def test_el_mes_distingue_cuatro_estados(entorno, v):
    """
    Pintar como incumplidos los días en que no tocaba sería mentir, y cobrar
    el de hoy antes de que termine, también. Son cuatro cosas distintas.
    """
    entorno.como("calidad")
    aid = _crear(entorno, frecuencia="semanal", dias_semana=[date.today().isoweekday()]).json()["id"]
    entorno.post(f"/master-planner/actividades/{aid}/registros", json={})

    hoy = date.today()
    mes = entorno.get(f"/master-planner/actividades/{aid}/mes").json()
    por_fecha = {d["fecha"]: d["estado"] for d in mes["dias"]}

    v.check("trae el mes entero", len(mes["dias"]) >= 28, len(mes["dias"]))
    v.check("hoy quedó cumplido", por_fecha[hoy.isoformat()] == "cumplido", por_fecha[hoy.isoformat()])

    # Un día de otro día de la semana no aplica.
    otro = next(
        (d for d in mes["dias"]
         if date.fromisoformat(d["fecha"]).isoweekday() != hoy.isoweekday()),
        None,
    )
    v.check("los días que no tocan no cuentan como incumplidos",
            otro and otro["estado"] == "no_aplica", otro)


def test_el_mes_no_juzga_lo_que_todavia_no_llega(entorno, v):
    entorno.como("calidad")
    aid = _crear(entorno, solo_dias_habiles=False).json()["id"]

    mes = entorno.get(f"/master-planner/actividades/{aid}/mes").json()
    hoy = date.today()
    futuros = [d for d in mes["dias"] if date.fromisoformat(d["fecha"]) > hoy]

    v.check("ningún día futuro sale sin registrar",
            all(d["estado"] != "sin_registrar" for d in futuros),
            [d for d in futuros if d["estado"] == "sin_registrar"][:3])


def test_el_porcentaje_se_mide_sobre_lo_que_ya_se_podia_hacer(entorno, v):
    """
    Si se midiera sobre el mes entero, el primer día de octubre toda
    actividad diaria aparecería con un 5% de cumplimiento por los días que
    todavía no han llegado.
    """
    entorno.como("calidad")
    aid = _crear(entorno, solo_dias_habiles=False).json()["id"]
    mes = entorno.get(f"/master-planner/actividades/{aid}/mes").json()

    v.check("lo del mes entero es mayor o igual a lo de hasta hoy",
            mes["esperados"] >= mes["esperados_hasta_hoy"], mes)
    v.check("y son dos números distintos, no uno repetido",
            "esperados_hasta_hoy" in mes and "esperados" in mes, mes)


def test_el_mes_se_puede_mirar_hacia_atras(entorno, v):
    """Sin esto, el registro solo existiría para el mes en curso."""
    entorno.como("calidad")
    aid = _crear(entorno, solo_dias_habiles=False).json()["id"]

    r = entorno.get(f"/master-planner/actividades/{aid}/mes",
                    params={"anio": 2026, "mes": 1})
    v.check("responde", r.status_code == 200, r.text[:200])
    v.check("con los 31 días de enero", len(r.json()["dias"]) == 31, len(r.json()["dias"]))
    v.check("y sin nada esperado: la actividad no existía",
            r.json()["esperados"] == 0, r.json()["esperados"])
