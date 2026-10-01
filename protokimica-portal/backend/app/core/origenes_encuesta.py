"""
El contrato de un origen de respuestas para el módulo de Encuestas.

Encuestas muestra en una sola lista respuestas que vienen de tablas
distintas: las de sus propias plantillas y la encuesta de satisfacción que
PQRS manda al cerrar una solicitud. Antes Encuestas leía la tabla de PQRS
directamente y no podía instalarse sin él; ahora PQRS declara su origen en
`modules/pqrs/origen_encuesta.py` y Encuestas lo reúne (ver
`core/registro.py`). Aquí vive solo la forma común de una respuesta.

Un módulo declara `ORIGENES = {clave: {"nombre", "descripcion", "fn"}}`,
donde `fn(db, tenant_id)` devuelve una lista de `RespuestaVista`.
"""
from dataclasses import dataclass, field
from datetime import datetime

# Escala común de calificación. La encuesta de PQRS ya venía de 1 a 5, y
# forzar todo a la misma escala es lo que permite comparar y promediar entre
# encuestas distintas sin normalizar en cada consulta.
ESCALA_MAX = 5


@dataclass
class ItemVista:
    pregunta: str
    valor: str | None
    numero: float | None = None


@dataclass
class RespuestaVista:
    """Una respuesta, venga de donde venga, en la forma que el módulo pinta."""
    id: str                       # "pqrs-12" / "enc-45": único entre orígenes
    origen: str                   # clave del origen
    origen_nombre: str
    respondida_en: datetime | None
    calificacion: float | None    # 1..5, o None si esa encuesta no califica
    comentario: str | None = None
    sujeto: str | None = None     # a quién o qué califica
    referencia: str | None = None # de dónde salió (radicado, punto de venta)
    items: list[ItemVista] = field(default_factory=list)
