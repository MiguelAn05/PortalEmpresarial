"""
Semáforo, acumulados y armado del tablero.

Todo el cálculo vive aquí y no en el frontend: un indicador que dice 92% en
pantalla tiene que decir 92% en un correo, en un PDF o en un reporte a
gerencia. Si cada consumidor lo recalcula, tarde o temprano dejan de coincidir.
"""
from datetime import date

from sqlalchemy.orm import Session

from app.models.indicadores import Indicador, Medicion
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
    utiles = [m for m in mediciones if m.valor is not None or m.denominador]
    if not utiles:
        return {"valor": None, "numerador": None, "denominador": None, "meses": 0}

    modo = indicador.modo_acumulado

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
    medicion.observacion = resultado.detalle
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
            "semaforo": semaforo(indicador, valor),
            "observacion": m.observacion if m else None,
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
        "area": indicador.area,
        "responsable_nombre": indicador.responsable_nombre,
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
        "observacion": actual.observacion if actual else None,
        "tiene_evidencia": bool(actual.evidencia) if actual else False,
        "evidencia": actual.evidencia if actual else None,
        "registrado_por": actual.registrado_por_nombre if actual else None,
        "registrado_en": actual.registrado_en if actual else None,

        "valor_mes_anterior": valor_anterior,
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
