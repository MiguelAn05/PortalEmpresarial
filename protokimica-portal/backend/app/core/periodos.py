"""
El periodo de un informe: de qué fecha a qué fecha, cuál es el anterior y
cómo se dice en palabras.

Lo usan el informe de PQRS y el de Master Planner. Vivía dentro de PQRS, y
un módulo no importa de otro (ver `tests/test_modularidad.py`): si el
segundo informe lo copiaba, el día que uno cambiara la regla del «día que
empieza a medianoche en Colombia» los dos dirían cosas distintas del mismo
mes.

**El día empieza a medianoche en la hora de la empresa**, no en UTC: si no,
lo que pasa después de las 7 p. m. del 31 contaría para el mes siguiente.
"""
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from app.core.config import settings
from app.core.dias_habiles import contar_habiles, hoy
from app.core.fechas import con_zona

# Un año y un poco: alcanza para comparar un año contra el anterior sin
# pedirle a la base el histórico completo de una vez.
MAX_DIAS_PERIODO = 400
# Hasta dos meses la serie va día por día; más largo, por mes.
MAX_DIAS_SERIE_DIARIA = 62

MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre")


def _zona() -> ZoneInfo:
    return ZoneInfo(settings.ZONA_HORARIA)


def inicio_del_dia(dia: date) -> datetime:
    """Medianoche de ese día en la hora de la empresa, en UTC."""
    return datetime.combine(dia, time.min, tzinfo=_zona()).astimezone(timezone.utc)


def limites(desde: date, hasta: date) -> tuple[datetime, datetime]:
    """
    El periodo como dos instantes UTC: desde la medianoche de `desde`
    (incluida) hasta la de después de `hasta` (excluida).
    """
    return inicio_del_dia(desde), inicio_del_dia(hasta + timedelta(days=1))


def dia_local(momento: datetime) -> date:
    return con_zona(momento).astimezone(_zona()).date()


def dias_habiles_del_periodo(desde: date, hasta: date) -> int:
    """Días hábiles de `desde` a `hasta`, los dos incluidos, sin pasar de hoy."""
    fin = min(hasta, hoy())
    if fin < desde:
        return 0
    # `contar_habiles` no cuenta el día de partida: se parte del anterior.
    return contar_habiles(desde - timedelta(days=1), fin)


TRIMESTRES = ("Primer", "Segundo", "Tercer", "Cuarto")


def _ultimo_del_mes(anio: int, mes: int) -> date:
    return (date(anio + 1, 1, 1) if mes == 12 else date(anio, mes + 1, 1)) - timedelta(days=1)


def etiqueta_periodo(desde: date, hasta: date) -> str:
    """
    Como se dice en un comité: «Septiembre de 2026», «Tercer trimestre de
    2026», «Año 2025». Un rango que no es ninguno de esos va con sus fechas.
    """
    if desde.day == 1 and desde.year == hasta.year and desde.month == hasta.month:
        return f"{MESES[desde.month - 1].capitalize()} de {desde.year}"
    if (desde.day == 1 and desde.month % 3 == 1 and hasta.year == desde.year
            and hasta.month == desde.month + 2 and hasta == _ultimo_del_mes(hasta.year, hasta.month)):
        return f"{TRIMESTRES[desde.month // 3]} trimestre de {desde.year}"
    if desde == date(desde.year, 1, 1) and hasta == date(desde.year, 12, 31):
        return f"Año {desde.year}"
    return f"Del {desde.day} de {MESES[desde.month - 1]} de {desde.year} " \
           f"al {hasta.day} de {MESES[hasta.month - 1]} de {hasta.year}"


def resolver_periodo(desde: date | None, hasta: date | None) -> tuple[date, date]:
    """Sin fechas, el mes en curso hasta hoy."""
    hoy_ = hoy()
    desde = desde or hoy_.replace(day=1)
    hasta = hasta or hoy_
    if desde > hasta:
        raise HTTPException(status_code=400, detail="La fecha inicial es posterior a la final. Revisa el periodo.")
    if (hasta - desde).days > MAX_DIAS_PERIODO:
        raise HTTPException(
            status_code=400,
            detail=f"El periodo puede ser de hasta {MAX_DIAS_PERIODO} días. Pide el informe por partes.",
        )
    return desde, hasta


def _meses_atras(dia: date, meses: int) -> date:
    """El mismo día `meses` atrás; si ese mes es más corto, su último día."""
    anio, mes = divmod(dia.year * 12 + dia.month - 1 - meses, 12)
    ultimo = _ultimo_del_mes(anio, mes + 1)
    return ultimo.replace(day=min(dia.day, ultimo.day))


def periodo_anterior(desde: date, hasta: date) -> tuple[date, date]:
    """
    Contra qué se compara. **Un periodo de calendario se compara con el de
    calendario anterior**: septiembre contra agosto completo, el tercer
    trimestre contra el segundo, 2026 contra 2025. Contar «los mismos días
    hacia atrás» comparaba el tercer trimestre con «del 31 de marzo al 30 de
    junio», que no es nada que alguien presente en un comité.

    Lo que va en curso se compara con el mismo tramo del anterior: del 1 al
    21 de octubre contra del 1 al 21 de septiembre (o hasta el último día, si
    el mes anterior es más corto). Cualquier otro rango, con el del mismo
    largo pegado antes: «estas dos semanas contra las dos de antes».
    """
    if desde.day == 1:
        meses = None
        if desde.month == 1 and hasta <= date(desde.year, 12, 31) and hasta.month > 3:
            meses = 12                                  # el año, o lo que va de él
        elif desde.month % 3 == 1 and hasta.year == desde.year and desde.month < hasta.month <= desde.month + 2:
            meses = 3                                   # el trimestre, o lo que va de él
        elif hasta.year == desde.year and hasta.month == desde.month:
            meses = 1                                   # el mes, o lo que va de él
        if meses:
            ant_desde = _meses_atras(desde, meses)
            # Un periodo que llega al último día de su mes se compara con el
            # anterior también completo (febrero termina el 28, no el 30).
            if hasta == _ultimo_del_mes(hasta.year, hasta.month):
                fin_mes = _meses_atras(hasta.replace(day=1), meses)
                return ant_desde, _ultimo_del_mes(fin_mes.year, fin_mes.month)
            return ant_desde, _meses_atras(hasta, meses)

    largo = (hasta - desde).days + 1
    ant_hasta = desde - timedelta(days=1)
    return ant_hasta - timedelta(days=largo - 1), ant_hasta


def describir(desde: date, hasta: date, generado: datetime) -> dict:
    """El bloque `periodo` que llevan los informes, con su anterior."""
    ant_desde, ant_hasta = periodo_anterior(desde, hasta)
    return {
        "desde": desde.isoformat(), "hasta": hasta.isoformat(),
        "etiqueta": etiqueta_periodo(desde, hasta),
        "anterior": {"desde": ant_desde.isoformat(), "hasta": ant_hasta.isoformat(),
                     "etiqueta": etiqueta_periodo(ant_desde, ant_hasta)},
        "generado": generado.isoformat(),
    }


def serie(por_dia: Counter, desde: date, hasta: date) -> dict:
    """
    Una serie en el tiempo a partir de un conteo por día local: día por día
    hasta dos meses, por mes si es más largo. Los días sin nada van en cero,
    no se saltan: una columna que falta se lee como un día que no existió.
    """
    dias = (hasta - desde).days + 1
    if dias <= MAX_DIAS_SERIE_DIARIA:
        puntos = []
        for i in range(dias):
            d = desde + timedelta(days=i)
            puntos.append({"clave": d.isoformat(), "etiqueta": str(d.day), "n": por_dia.get(d, 0)})
        return {"escala": "dia", "puntos": puntos}

    por_mes = Counter()
    for d, n in por_dia.items():
        por_mes[(d.year, d.month)] += n
    puntos = []
    anio, mes = desde.year, desde.month
    while (anio, mes) <= (hasta.year, hasta.month):
        puntos.append({"clave": f"{anio}-{mes:02d}", "etiqueta": f"{MESES[mes - 1][:3]} {anio}",
                       "n": por_mes.get((anio, mes), 0)})
        anio, mes = (anio + 1, 1) if mes == 12 else (anio, mes + 1)
    return {"escala": "mes", "puntos": puntos}
