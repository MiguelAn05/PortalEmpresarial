"""
Fechas con zona horaria, en un solo sitio.

Postgres devuelve las fechas con zona y SQLite (el de las pruebas) sin ella,
y restar una de cada tipo revienta. Esta función vivía copiada en siete
módulos; ahora es la única.

Para «qué día es hoy» para una persona, ver `dias_habiles.hoy()`: eso es otra
pregunta y depende de `settings.ZONA_HORARIA`.
"""
from datetime import date, datetime, time, timezone


def con_zona(valor: datetime | date | None) -> datetime | None:
    """
    La fecha con zona horaria; si no traía, se asume UTC, que es como se guarda.

    Una fecha sin hora (`date`) se toma como el inicio de ese día en UTC.
    """
    if valor is None:
        return None
    if isinstance(valor, datetime):
        return valor if valor.tzinfo else valor.replace(tzinfo=timezone.utc)
    return datetime.combine(valor, time.min, tzinfo=timezone.utc)
