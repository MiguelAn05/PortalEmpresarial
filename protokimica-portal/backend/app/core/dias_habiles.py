"""
Días hábiles y festivos de Colombia.

Los plazos de PQRS son en días hábiles, no calendario: los 15 días de una
petición salen de la Ley 1755 de 2015, que habla de días hábiles. Contarlos
corridos hace que el sistema declare vencido algo que legalmente no lo está.

Hábil = lunes a viernes que no sea festivo. Sábado no cuenta.

Los festivos se calculan, no se listan a mano: una tabla año por año se
queda desactualizada y nadie se entera hasta que un plazo sale mal. Colombia
tiene tres clases de festivo:

  1. Fijos:      siempre el mismo día (1 de enero, 20 de julio...).
  2. Movibles:   dependen de la Pascua (Jueves Santo, Corpus Christi...).
  3. Emiliani:   la Ley 51 de 1983 los corre al lunes siguiente si caen
                 entre martes y domingo.
"""
from datetime import date, datetime, time, timedelta, timezone

# Festivos de fecha fija que NO se mueven.
FIJOS = [
    (1, 1),    # Año Nuevo
    (5, 1),    # Día del Trabajo
    (7, 20),   # Independencia
    (8, 7),    # Batalla de Boyacá
    (12, 8),   # Inmaculada Concepción
    (12, 25),  # Navidad
]

# Fijos que SÍ se corren al lunes siguiente (Ley Emiliani).
FIJOS_EMILIANI = [
    (1, 6),    # Reyes Magos
    (3, 19),   # San José
    (6, 29),   # San Pedro y San Pablo
    (8, 15),   # Asunción de la Virgen
    (10, 12),  # Día de la Raza
    (11, 1),   # Todos los Santos
    (11, 11),  # Independencia de Cartagena
]

# Días contados DESDE el Domingo de Pascua. Los tres primeros caen siempre
# en su día y no se corren; los demás se van al lunes por Ley Emiliani.
PASCUA_FIJOS = [-3, -2]        # Jueves y Viernes Santo
PASCUA_EMILIANI = [43, 64, 71]  # Ascensión, Corpus Christi, Sagrado Corazón


def _domingo_de_pascua(anio: int) -> date:
    """Algoritmo de Butcher (Pascua gregoriana)."""
    a = anio % 19
    b, c = divmod(anio, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    lo = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * lo) // 451
    mes, dia = divmod(h + lo - 7 * m + 114, 31)
    return date(anio, mes, dia + 1)


def _al_lunes(f: date) -> date:
    """Ley Emiliani: si no cae lunes, se corre al lunes siguiente."""
    return f + timedelta(days=(7 - f.weekday()) % 7)


_cache: dict[int, frozenset[date]] = {}


def festivos(anio: int) -> frozenset[date]:
    """Todos los festivos colombianos de un año. Se calcula una sola vez."""
    if anio in _cache:
        return _cache[anio]

    dias = {date(anio, m, d) for m, d in FIJOS}
    dias |= {_al_lunes(date(anio, m, d)) for m, d in FIJOS_EMILIANI}

    pascua = _domingo_de_pascua(anio)
    dias |= {pascua + timedelta(days=n) for n in PASCUA_FIJOS}
    dias |= {_al_lunes(pascua + timedelta(days=n)) for n in PASCUA_EMILIANI}

    _cache[anio] = frozenset(dias)
    return _cache[anio]


def es_habil(f: date) -> bool:
    """Lunes a viernes que no sea festivo."""
    return f.weekday() < 5 and f not in festivos(f.year)


def siguiente_habil(f: date) -> date:
    """El primer día hábil estrictamente después de `f`."""
    siguiente = f + timedelta(days=1)
    while not es_habil(siguiente):
        siguiente += timedelta(days=1)
    return siguiente


def sumar_habiles(desde: date, dias: int) -> date:
    """
    Suma `dias` hábiles a partir de `desde`, sin contar `desde`.

    El plazo arranca el día hábil siguiente a la radicación: una PQRS que
    entra a las 5 p.m. no debe gastar ese día completo.
    """
    if dias <= 0:
        return desde
    actual = desde
    restantes = dias
    while restantes > 0:
        actual = siguiente_habil(actual)
        restantes -= 1
    return actual


def contar_habiles(desde: date, hasta: date) -> int:
    """Días hábiles transcurridos entre dos fechas, sin contar `desde`."""
    if hasta <= desde:
        return 0
    total, actual = 0, desde
    while actual < hasta:
        actual += timedelta(days=1)
        if es_habil(actual):
            total += 1
    return total


# Hora a la que se considera vencido un plazo: el cierre del día hábil.
# Sin esto, algo que vence "el miércoles" quedaría vencido a las 00:00 de ese
# día en vez de al terminarlo.
HORA_CIERRE = time(23, 59, 59)


def limite_en_habiles(desde: datetime, dias: int) -> datetime:
    """
    La fecha y hora límite de un plazo en días hábiles, contando desde la
    radicación. Devuelve el final del día hábil correspondiente, en UTC.
    """
    base = desde.date() if isinstance(desde, datetime) else desde
    vence = sumar_habiles(base, dias)
    return datetime.combine(vence, HORA_CIERRE, tzinfo=timezone.utc)
