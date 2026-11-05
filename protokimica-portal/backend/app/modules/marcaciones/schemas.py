"""
Lo que manda el script del servidor de ZKBio.

Los topes son los de las columnas (`models/marcaciones.py`): un valor más
largo rechaza el lote entero con un 422 que dice cuál, en vez de reventar en
el commit con un error de Postgres.

Las horas llegan «de pared», en la zona de la empresa
(`AAAA-MM-DD HH:MM:SS`): es como las guarda ZKBio y como las lee quien mira
el reloj. El servicio las convierte a UTC para guardarlas.
"""
import re
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

from app.models.marcaciones import MAX_AREA, MAX_CODIGO, MAX_NOMBRE, MAX_TURNOS
from app.modules.marcaciones.constants import ESTADOS_VALIDOS

_TURNO = re.compile(r"^([01]\d|2[0-3]):[0-5]\d-([01]\d|2[0-3]):[0-5]\d$")


def _validar_turnos(valor: str) -> str:
    """«HH:MM-HH:MM», y varios separados por «/». Vacío = no trabaja ese día."""
    valor = (valor or "").strip()
    if not valor:
        return ""
    for tramo in valor.split("/"):
        if not _TURNO.match(tramo.strip()):
            raise ValueError(
                f"«{tramo.strip()}» no es un turno válido. Se escribe HH:MM-HH:MM, "
                "y varios turnos posibles se separan con «/» (por ejemplo 06:00-14:00/14:00-22:00)."
            )
    return "/".join(t.strip() for t in valor.split("/"))


class EmpleadoIn(BaseModel):
    emp_code: str = Field(min_length=1, max_length=MAX_CODIGO)
    nombre: str = Field(min_length=1, max_length=MAX_NOMBRE)
    area: str | None = Field(None, max_length=MAX_AREA)
    correo: str | None = Field(None, max_length=180)
    lun: str = Field("", max_length=MAX_TURNOS)
    mar: str = Field("", max_length=MAX_TURNOS)
    mie: str = Field("", max_length=MAX_TURNOS)
    jue: str = Field("", max_length=MAX_TURNOS)
    vie: str = Field("", max_length=MAX_TURNOS)
    sab: str = Field("", max_length=MAX_TURNOS)
    dom: str = Field("", max_length=MAX_TURNOS)

    @field_validator("lun", "mar", "mie", "jue", "vie", "sab", "dom")
    @classmethod
    def _turnos(cls, v: str) -> str:
        return _validar_turnos(v)


class MarcacionIn(BaseModel):
    emp_code: str = Field(min_length=1, max_length=MAX_CODIGO)
    # Hora de pared, sin zona.
    momento: datetime
    estado: str = Field(max_length=1)

    @field_validator("estado")
    @classmethod
    def _estado(cls, v: str) -> str:
        if v not in ESTADOS_VALIDOS:
            raise ValueError(
                f"Estado «{v}» desconocido. Los de ZKBio son 0 entrada, 1 salida, "
                "2 salida a descanso, 3 regreso de descanso, 4 y 5 horas extra."
            )
        return v

    @field_validator("momento")
    @classmethod
    def _sin_zona(cls, v: datetime) -> datetime:
        # La hora llega ya en la zona de la empresa; una con zona se pasaría
        # por UTC sin que nadie lo notara. Se rechaza para que no ocurra.
        if v.tzinfo is not None:
            raise ValueError("La hora de la marcación va sin zona (AAAA-MM-DD HH:MM:SS), en la hora local de la empresa.")
        return v


class FestivoIn(BaseModel):
    fecha: date
    nombre: str | None = Field(None, max_length=100)


class ExcepcionIn(BaseModel):
    emp_code: str = Field(min_length=1, max_length=MAX_CODIGO)
    fecha: date
    motivo: str | None = Field(None, max_length=100)


class SincronizacionIn(BaseModel):
    # Cada lista es independiente: el script de marcaciones manda las
    # marcaciones cada pasada y la malla/festivos/excepciones cuando cambian.
    # Ausente (None) = no tocar; la lista de empleados reemplaza la malla.
    empleados: list[EmpleadoIn] | None = None
    marcaciones: list[MarcacionIn] | None = None
    festivos: list[FestivoIn] | None = None
    excepciones: list[ExcepcionIn] | None = None
