"""
Semáforo, acumulados y armado del tablero.

Todo el cálculo vive aquí y no en el frontend: un indicador que dice 92% en
pantalla tiene que decir 92% en un correo, en un PDF o en un reporte a
gerencia. Si cada consumidor lo recalcula, tarde o temprano dejan de coincidir.
"""
from datetime import date

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.indicadores import (
    HistorialMedicion, Indicador, Medicion, ValorVariable, VariableIndicador,
)
from app.modules.indicadores import formula as formulas
from app.modules.indicadores import fuentes

MESES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]


def _f(v) -> float | None:
    return None if v is None else float(v)


def semaforo(indicador: Indicador, valor: float | None) -> str:
    """
    verde | amarillo | rojo | sin_datos

    Los umbrales se leen según la dirección del indicador: en uno que mejora
    subiendo, verde es "al menos"; en uno que mejora bajando (días de
    respuesta, reclamos), verde es "a lo sumo".

    Si no hay umbrales definidos se cae a la meta: cumple o no cumple. Y si
    tampoco hay meta, no se inventa un juicio.
    """
    if valor is None:
        return "sin_datos"

    verde = _f(indicador.umbral_verde)
    amarillo = _f(indicador.umbral_amarillo)
    meta = _f(indicador.meta)
    hacia_arriba = indicador.direccion == "arriba"

    if verde is None and amarillo is None:
        if meta is None:
            return "sin_datos"
        cumple = valor >= meta if hacia_arriba else valor <= meta
        return "verde" if cumple else "rojo"

    if hacia_arriba:
        if verde is not None and valor >= verde:
            return "verde"
        if amarillo is not None and valor >= amarillo:
            return "amarillo"
        return "rojo"

    if verde is not None and valor <= verde:
        return "verde"
    if amarillo is not None and valor <= amarillo:
        return "amarillo"
    return "rojo"


def acumular(indicador: Indicador, mediciones: list[Medicion]) -> dict:
    """
    Combina varios meses en un solo número, según lo que el indicador mida.

    El caso que importa es `razon`: sumar numeradores y denominadores por
    separado y dividir al final. Promediar los porcentajes mensuales daría un
    número distinto y equivocado — 2/2 (100%) y 50/100 (50%) acumulan 51%, no
    75%.
    """
    modo = indicador.modo_acumulado

    if modo == "formula":
        return _acumular_formula(indicador, mediciones)

    utiles = [m for m in mediciones if m.valor is not None or m.denominador]
    if not utiles:
        return {"valor": None, "numerador": None, "denominador": None, "meses": 0}

    if modo == "razon":
        num = sum(_f(m.numerador) or 0 for m in utiles)
        den = sum(_f(m.denominador) or 0 for m in utiles)
        if not den:
            # Sin numerador/denominador guardados no se puede acumular bien;
            # se promedia y el frontend lo advierte.
            valores = [_f(m.valor) for m in utiles if m.valor is not None]
            valor = round(sum(valores) / len(valores), 2) if valores else None
            return {"valor": valor, "numerador": None, "denominador": None,
                    "meses": len(utiles), "aproximado": True}
        bruto = num / den
        valor = round(bruto * 100, 2) if indicador.unidad == "porcentaje" else round(bruto, 2)
        return {"valor": valor, "numerador": num, "denominador": den, "meses": len(utiles)}

    valores = [_f(m.valor) for m in utiles if m.valor is not None]
    if not valores:
        return {"valor": None, "numerador": None, "denominador": None, "meses": 0}

    if modo == "suma":
        return {"valor": round(sum(valores), 2), "numerador": None,
                "denominador": None, "meses": len(valores)}

    return {"valor": round(sum(valores) / len(valores), 2), "numerador": None,
            "denominador": None, "meses": len(valores), "aproximado": True}


def _acumular_formula(indicador: Indicador, mediciones: list[Medicion]) -> dict:
    """
    Suma cada variable en todos los meses y aplica la fórmula UNA vez.

    Con `80 × A ÷ B`, enero 9 de 10 y febrero 1 de 90 dan 8 de 100 → 8,
    no el promedio de 72 y 0,89. Un mes al que le falte alguna variable no
    entra: no se puede sumar lo que no se registró.
    """
    letras = [v.letra for v in indicador.variables]
    completos = [m for m in mediciones if letras and set(letras) <= set(m.variables)]
    vacio = {"valor": None, "numerador": None, "denominador": None, "meses": 0, "variables": {}}
    if not completos or not indicador.formula:
        return vacio

    sumas = {letra: sum(m.variables[letra] for m in completos) for letra in letras}
    try:
        valor = round(formulas.evaluar(indicador.formula, sumas), 2)
    except (formulas.DivisionPorCero, formulas.ErrorFormula):
        valor = None
    return {"valor": valor, "numerador": None, "denominador": None,
            "meses": len(completos), "variables": sumas}


def _error_formula(e: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail=str(e))


def preparar_formula(formula: str | None, variables: list[dict]) -> tuple[str, list[dict]]:
    """
    Valida la configuración de un indicador de fórmula y la deja lista para
    guardar: fórmula en su forma canónica y variables limpias.
    """
    if not variables:
        raise HTTPException(
            status_code=400,
            detail="Agrega al menos una variable: son los números que se digitan cada mes.",
        )
    if len(variables) > formulas.MAX_VARIABLES:
        raise HTTPException(
            status_code=400,
            detail=f"Un indicador admite hasta {formulas.MAX_VARIABLES} variables.",
        )

    limpias, letras = [], set()
    for v in variables:
        letra = (v.get("letra") or "").strip().upper()
        etiqueta = (v.get("etiqueta") or "").strip()
        if len(letra) != 1 or letra not in formulas.LETRAS:
            raise HTTPException(status_code=400, detail=f"«{letra}» no es una letra válida para una variable (A–Z).")
        if letra in letras:
            raise HTTPException(status_code=400, detail=f"La letra {letra} está repetida en las variables.")
        if not etiqueta:
            raise HTTPException(
                status_code=400,
                detail=f"La variable {letra} no tiene nombre. Escribe qué se cuenta ahí, por ejemplo «Quejas atendidas».",
            )
        letras.add(letra)
        limpias.append({"letra": letra, "etiqueta": etiqueta})

    try:
        formulas.validar(formula or "", sorted(letras))
        normalizada = formulas.normalizar(formula)
    except formulas.ErrorFormula as e:
        raise _error_formula(e)
    return normalizada, sorted(limpias, key=lambda v: v["letra"])


def aplicar_formula(db: Session, indicador: Indicador, formula: str | None,
                    variables: list[dict] | None, usuario_id: int | None) -> None:
    """
    Guarda la fórmula y las variables de un indicador, cuidando lo ya medido.

    Con mediciones registradas:
    - **no se agregan ni quitan variables**: los meses ya guardados no tienen
      ese dato y el acumulado quedaría calculado con meses incompletos;
    - **sí se renombran**, que no cambia ningún número;
    - **sí se cambia la fórmula**, y entonces se recalcula cada mes con sus
      variables guardadas. El cambio de cada valor queda en el historial,
      porque un número que ya se reportó no puede moverse sin rastro.
    """
    actuales = [{"letra": v.letra, "etiqueta": v.etiqueta} for v in indicador.variables]
    normalizada, limpias = preparar_formula(
        formula if formula is not None else indicador.formula,
        variables if variables is not None else actuales,
    )

    mediciones = indicador.mediciones
    if mediciones and {v["letra"] for v in limpias} != {v["letra"] for v in actuales}:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Este indicador ya tiene {len(mediciones)} mes(es) registrados con sus "
                "variables, así que no se pueden agregar ni quitar variables: esos meses "
                "no tendrían el dato. Puedes cambiarles el nombre o cambiar la fórmula; "
                "si de verdad se mide distinto, crea un indicador nuevo y desactiva este."
            ),
        )

    legible_anterior = indicador.formula_legible
    formula_anterior = indicador.formula

    etiquetas = {v["letra"]: v["etiqueta"] for v in limpias}
    existentes = {v.letra: v for v in indicador.variables}
    for letra, variable in list(existentes.items()):
        if letra not in etiquetas:
            indicador.variables.remove(variable)
    for letra, etiqueta in etiquetas.items():
        if letra in existentes:
            existentes[letra].etiqueta = etiqueta
        else:
            indicador.variables.append(VariableIndicador(letra=letra, etiqueta=etiqueta))
    indicador.formula = normalizada

    if mediciones and formula_anterior and formula_anterior != normalizada:
        motivo = (
            f"Cambió la fórmula: {legible_anterior} → "
            f"{formulas.legible(normalizada, etiquetas)}"
        )
        for m in mediciones:
            if not m.variables:
                continue
            anterior = float(m.valor) if m.valor is not None else None
            try:
                nuevo = formulas.evaluar(normalizada, m.variables)
            except (formulas.DivisionPorCero, formulas.ErrorFormula):
                nuevo = None
            if nuevo != anterior:
                m.valor = nuevo
                db.add(HistorialMedicion(
                    indicador_id=indicador.id, anio=m.anio, mes=m.mes,
                    valor_anterior=anterior, valor_nuevo=nuevo,
                    motivo=motivo, usuario_id=usuario_id,
                ))


def valor_por_formula(indicador: Indicador, valores: dict) -> tuple[float, dict[str, float]]:
    """
    El valor de un mes a partir de lo que se digitó en cada variable.

    Dividir por cero se rechaza con el mismo criterio que el denominador en
    cero de la razón: si en el periodo no hubo casos, el mes se deja sin
    registrar — un cero bajaría el semáforo por algo que no pasó.
    """
    etiquetas = indicador.etiquetas_variables
    limpios = {}
    for letra, etiqueta in etiquetas.items():
        crudo = valores.get(letra)
        if crudo is None or crudo == "":
            raise HTTPException(status_code=400, detail=f"Falta el valor de «{etiqueta}».")
        try:
            limpios[letra] = float(str(crudo).replace(",", "."))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"«{etiqueta}» debe ser un número.")
    try:
        return formulas.evaluar(indicador.formula, limpios), limpios
    except formulas.DivisionPorCero:
        raise HTTPException(
            status_code=400,
            detail=(
                "Con esos valores la fórmula divide por cero. Si en el periodo no "
                "hubo casos, deja el mes sin registrar."
            ),
        )
    except formulas.ErrorFormula as e:
        raise _error_formula(e)


def guardar_variables(medicion: Medicion, valores: dict[str, float]) -> None:
    """Reemplaza lo digitado de cada variable en el mes."""
    existentes = {v.letra: v for v in medicion.valores_variables}
    for letra, valor in valores.items():
        if letra in existentes:
            existentes[letra].valor = valor
        else:
            medicion.valores_variables.append(ValorVariable(letra=letra, valor=valor))
    for letra, fila in existentes.items():
        if letra not in valores:
            medicion.valores_variables.remove(fila)


def calcular_automatico(db: Session, indicador: Indicador, tenant_id: int,
                        anio: int, mes: int) -> Medicion:
    """
    Recalcula y guarda el valor de un indicador automático. Es idempotente:
    volver a calcular el mismo mes actualiza el registro, no crea otro.
    """
    resultado = fuentes.calcular(indicador.fuente_automatica, db, tenant_id, anio, mes)

    medicion = (
        db.query(Medicion)
        .filter(Medicion.indicador_id == indicador.id,
                Medicion.anio == anio, Medicion.mes == mes)
        .first()
    )
    if not medicion:
        medicion = Medicion(indicador_id=indicador.id, anio=anio, mes=mes)
        db.add(medicion)

    medicion.valor = resultado.valor
    medicion.numerador = resultado.numerador
    medicion.denominador = resultado.denominador
    medicion.analisis = resultado.detalle
    return medicion


def _mes_anterior(anio: int, mes: int) -> tuple[int, int]:
    return (anio - 1, 12) if mes == 1 else (anio, mes - 1)


def serie_del_anio(indicador: Indicador, anio: int) -> list[dict]:
    """Los 12 meses del año, incluidos los que aún no tienen dato."""
    por_mes = {m.mes: m for m in indicador.mediciones if m.anio == anio}
    serie = []
    for mes in range(1, 13):
        m = por_mes.get(mes)
        valor = _f(m.valor) if m else None
        serie.append({
            "mes": mes,
            "etiqueta": MESES[mes - 1][:3],
            "valor": valor,
            "numerador": _f(m.numerador) if m else None,
            "denominador": _f(m.denominador) if m else None,
            "variables": m.variables if m else {},
            "semaforo": semaforo(indicador, valor),
            "analisis": m.analisis if m else None,
            "tiene_evidencia": bool(m.evidencia) if m else False,
            "registrado_por": m.registrado_por_nombre if m else None,
        })
    return serie


def _acumulado_meses(indicador: Indicador, anio: int, meses: list[int]) -> dict:
    seleccion = [m for m in indicador.mediciones if m.anio == anio and m.mes in meses]
    resultado = acumular(indicador, seleccion)
    resultado["semaforo"] = semaforo(indicador, resultado["valor"])
    return resultado


def resumen_indicador(indicador: Indicador, anio: int, mes: int) -> dict:
    """
    La ficha del indicador en un corte de tiempo: valor del mes, comparación
    con el mes anterior y con el mismo mes del año pasado, acumulados, y la
    serie completa para la gráfica de tendencia.
    """
    por_periodo = {(m.anio, m.mes): m for m in indicador.mediciones}

    actual = por_periodo.get((anio, mes))
    valor_actual = _f(actual.valor) if actual else None

    anio_ant, mes_ant = _mes_anterior(anio, mes)
    anterior = por_periodo.get((anio_ant, mes_ant))
    valor_anterior = _f(anterior.valor) if anterior else None

    hace_un_anio = por_periodo.get((anio - 1, mes))
    valor_hace_un_anio = _f(hace_un_anio.valor) if hace_un_anio else None

    def variacion(contra: float | None) -> float | None:
        if valor_actual is None or contra is None:
            return None
        return round(valor_actual - contra, 2)

    trimestre = ((mes - 1) // 3) + 1
    meses_trimestre = list(range((trimestre - 1) * 3 + 1, trimestre * 3 + 1))

    return {
        "id": indicador.id,
        "nombre": indicador.nombre,
        "descripcion": indicador.descripcion,
        "formula_texto": indicador.formula_texto,
        "unidad": indicador.unidad,
        "tipo_captura": indicador.tipo_captura,
        "fuente_automatica": indicador.fuente_automatica,
        "es_automatico": indicador.es_automatico,
        # Las etiquetas y el responsable van aquí para que el formulario de
        # edición pueda abrirse desde el detalle sin perder esos campos.
        "etiqueta_numerador": indicador.etiqueta_numerador,
        "etiqueta_denominador": indicador.etiqueta_denominador,
        "formula": indicador.formula,
        "formula_legible": indicador.formula_legible,
        "variables": [{"letra": v.letra, "etiqueta": v.etiqueta} for v in indicador.variables],
        "area": indicador.area,
        "responsable_id": indicador.responsable_id,
        "responsable_nombre": indicador.responsable_nombre,
        "orden": indicador.orden,
        "activo": indicador.activo,
        "meta": _f(indicador.meta),
        "direccion": indicador.direccion,
        "umbral_verde": _f(indicador.umbral_verde),
        "umbral_amarillo": _f(indicador.umbral_amarillo),
        "requiere_evidencia": indicador.requiere_evidencia,
        "modo_acumulado": indicador.modo_acumulado,

        "valor": valor_actual,
        "semaforo": semaforo(indicador, valor_actual),
        "numerador": _f(actual.numerador) if actual else None,
        "denominador": _f(actual.denominador) if actual else None,
        "valores_variables": actual.variables if actual else {},
        "analisis": actual.analisis if actual else None,
        "tiene_evidencia": bool(actual.evidencia) if actual else False,
        "evidencia": actual.evidencia if actual else None,
        "registrado_por": actual.registrado_por_nombre if actual else None,
        "registrado_en": actual.registrado_en if actual else None,

        "valor_mes_anterior": valor_anterior,
        # El semáforo del mes pasado se resuelve aquí y no en quien consume la
        # ficha: comparar estados es lo que permite decir "esto empeoró", y
        # recalcularlo afuera significaría repetir la regla de los umbrales.
        "semaforo_mes_anterior": semaforo(indicador, valor_anterior),
        "variacion_mes": variacion(valor_anterior),
        "valor_anio_anterior": valor_hace_un_anio,
        "variacion_anio": variacion(valor_hace_un_anio),

        "acumulado_trimestre": _acumulado_meses(indicador, anio, meses_trimestre),
        "acumulado_anio": _acumulado_meses(indicador, anio, list(range(1, mes + 1))),
        "trimestre": trimestre,

        "serie": serie_del_anio(indicador, anio),
    }


def construir_tablero(db: Session, tenant_id: int, anio: int, mes: int,
                      area: str | None = None) -> dict:
    """El tablero completo de un periodo, listo para pintar."""
    query = db.query(Indicador).filter(
        Indicador.tenant_id == tenant_id, Indicador.activo.is_(True),
    )
    if area:
        query = query.filter(Indicador.area == area)
    indicadores = query.order_by(Indicador.orden, Indicador.nombre).all()

    fichas = [resumen_indicador(i, anio, mes) for i in indicadores]

    conteo = {"verde": 0, "amarillo": 0, "rojo": 0, "sin_datos": 0}
    for f in fichas:
        conteo[f["semaforo"]] += 1

    con_juicio = conteo["verde"] + conteo["amarillo"] + conteo["rojo"]

    # Pendientes de registro: manuales sin valor en el periodo. Es el número
    # que le dice a Calidad qué falta antes del comité.
    pendientes = [
        {"id": f["id"], "nombre": f["nombre"], "area": f["area"],
         "responsable_nombre": f["responsable_nombre"]}
        for f in fichas if not f["es_automatico"] and f["valor"] is None
    ]

    # Por área, para la comparación lado a lado.
    por_area: dict[str, dict] = {}
    for f in fichas:
        clave = f["area"] or "Sin área"
        fila = por_area.setdefault(clave, {
            "area": clave, "total": 0, "verde": 0, "amarillo": 0, "rojo": 0, "sin_datos": 0,
        })
        fila["total"] += 1
        fila[f["semaforo"]] += 1
    for fila in por_area.values():
        juzgados = fila["verde"] + fila["amarillo"] + fila["rojo"]
        fila["cumplimiento_pct"] = round((fila["verde"] / juzgados) * 100, 1) if juzgados else None

    return {
        "anio": anio,
        "mes": mes,
        "mes_nombre": MESES[mes - 1],
        "resumen": {
            **conteo,
            "total": len(fichas),
            # Solo cuentan los que tienen un juicio posible: incluir los
            # "sin datos" haría bajar el cumplimiento por falta de registro,
            # que es un problema distinto y se muestra aparte.
            "cumplimiento_pct": round((conteo["verde"] / con_juicio) * 100, 1) if con_juicio else None,
            "pendientes_registro": len(pendientes),
        },
        "indicadores": fichas,
        "por_area": sorted(por_area.values(), key=lambda a: -a["total"]),
        "pendientes": pendientes,
        "areas_disponibles": sorted({
            i.area for i in db.query(Indicador).filter(
                Indicador.tenant_id == tenant_id, Indicador.activo.is_(True),
            ).all() if i.area
        }),
    }


def periodo_por_defecto() -> tuple[int, int]:
    """
    El mes anterior al actual. Un indicador del mes en curso está incompleto
    por definición, así que abrir el tablero en el mes cerrado es lo que
    espera quien lo consulta.
    """
    hoy = date.today()
    return _mes_anterior(hoy.year, hoy.month)
