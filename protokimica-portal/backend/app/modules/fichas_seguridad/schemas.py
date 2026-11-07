"""
Lo que entra a Fichas de seguridad por JSON.

La subida de una ficha o de una versión va como formulario con archivo
(`multipart`), y sus campos se validan en `service.py` con los mismos topes de
`models/fichas_seguridad.py`; esto es solo la corrección de una ficha.
"""
from datetime import date

from pydantic import BaseModel, Field

from app.models.fichas_seguridad import MAX_CODIGO, MAX_NOMBRE, MAX_OBSERVACIONES, MAX_VERSION


class FichaEditar(BaseModel):
    """
    Lo que se corrige de una ficha. Lo que no se manda no se toca: por eso
    `codigo_producto: null` (o vacío) QUITA el código y omitirlo lo deja igual.
    """
    nombre_producto: str | None = Field(None, max_length=MAX_NOMBRE)
    codigo_producto: str | None = Field(None, max_length=MAX_CODIGO)
    activa: bool | None = None


class VersionEditar(BaseModel):
    """
    Lo que se corrige de una versión ya subida: el número, la fecha y las
    observaciones, que se escriben a mano y con prisa al cargarla. El PDF NO
    se cambia aquí: un documento distinto es una versión nueva, o lo que se
    entregó con esa versión dejaría de ser lo que dice el portal.
    Lo que no se manda no se toca; `observaciones: ""` las quita.
    """
    version: str | None = Field(None, max_length=MAX_VERSION)
    fecha_emision: date | None = None
    observaciones: str | None = Field(None, max_length=MAX_OBSERVACIONES)
