from datetime import datetime

from pydantic import BaseModel

from app.models.encuestas import TIPOS_PREGUNTA


class PreguntaCreate(BaseModel):
    texto: str
    ayuda: str | None = None
    tipo: str = "escala"
    # Separadas por "|", solo para tipo "opcion".
    opciones: str | None = None
    clave: str | None = None
    obligatoria: bool = True
    orden: int = 0


class PreguntaOut(PreguntaCreate):
    id: int

    class Config:
        from_attributes = True


class PlantillaCreate(BaseModel):
    nombre: str
    descripcion: str | None = None
    slug: str
    sujeto_tipo: str | None = None
    mensaje_final: str | None = None
    activa: bool = True
    preguntas: list[PreguntaCreate] = []


class PlantillaUpdate(BaseModel):
    nombre: str | None = None
    descripcion: str | None = None
    sujeto_tipo: str | None = None
    mensaje_final: str | None = None
    activa: bool | None = None
    # Si viene, reemplaza TODAS las preguntas. Editar una encuesta que ya
    # tiene respuestas se bloquea en el router: cambiarle las preguntas
    # dejaría respuestas apuntando a algo que ya no se preguntó.
    preguntas: list[PreguntaCreate] | None = None


class PlantillaOut(BaseModel):
    id: int
    nombre: str
    descripcion: str | None
    slug: str
    sujeto_tipo: str | None
    mensaje_final: str | None
    activa: bool
    creado_en: datetime | None
    preguntas: list[PreguntaOut] = []
    total_respuestas: int = 0

    class Config:
        from_attributes = True


class RespuestaCreate(BaseModel):
    """
    Lo que envía el formulario público.

    `respuestas` es {id_de_pregunta: valor}. No se declara pregunta por
    pregunta porque las preguntas son datos: un esquema fijo obligaría a
    desplegar cada vez que alguien agrega una.
    """
    sujeto_ref: str | None = None
    sujeto_nombre: str | None = None
    respuestas: dict[str, str | int | float | None] = {}


def validar_tipo_pregunta(tipo: str) -> None:
    if tipo not in TIPOS_PREGUNTA:
        raise ValueError(
            f"Tipo de pregunta inválido: «{tipo}». "
            f"Usa uno de: {', '.join(sorted(TIPOS_PREGUNTA))}."
        )
