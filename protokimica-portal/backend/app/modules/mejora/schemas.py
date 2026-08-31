"""Lo que entra y sale del módulo de Oportunidades de Mejora."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ── Acciones ─────────────────────────────────────────────────────────

class AccionCrear(BaseModel):
    descripcion: str = Field(min_length=3, max_length=300)
    responsable_id: int | None = None
    fecha_limite: datetime | None = None


class AccionActualizar(BaseModel):
    descripcion: str | None = Field(default=None, min_length=3, max_length=300)
    responsable_id: int | None = None
    fecha_limite: datetime | None = None
    completada: bool | None = None
    evidencia: str | None = None


class AccionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    descripcion: str
    responsable_id: int | None
    responsable_nombre: str | None
    fecha_limite: datetime | None
    completada: bool
    fecha_completada: datetime | None
    evidencia: str | None


# ── Oportunidad ──────────────────────────────────────────────────────

class OportunidadCrear(BaseModel):
    titulo: str = Field(min_length=5, max_length=200)
    descripcion: str | None = None
    origen: str = "indicador"

    # Cuando nace de un indicador, el periodo es obligatorio en la práctica:
    # sin él no hay contra qué comparar al verificar la eficacia. Se valida
    # en el router para poder explicar el porqué en el mensaje.
    indicador_id: int | None = None
    periodo_anio: int | None = None
    periodo_mes: int | None = Field(default=None, ge=1, le=12)
    valor_inicial: float | None = None
    meta_esperada: float | None = None
    pqrs_id: int | None = None

    area: str | None = None
    responsable_id: int | None = None
    prioridad: str = "media"
    fecha_limite: datetime | None = None


class OportunidadActualizar(BaseModel):
    titulo: str | None = Field(default=None, min_length=5, max_length=200)
    descripcion: str | None = None
    area: str | None = None
    responsable_id: int | None = None
    prioridad: str | None = None
    fecha_limite: datetime | None = None
    causa_raiz: str | None = None
    meta_esperada: float | None = None


class CambioEstado(BaseModel):
    estado: str


class Verificacion(BaseModel):
    eficaz: bool
    nota: str | None = None
    valor_verificado: float | None = None


class OportunidadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    codigo: str | None
    titulo: str
    descripcion: str | None
    origen: str

    indicador_id: int | None
    indicador_nombre: str | None
    periodo_anio: int | None
    periodo_mes: int | None
    valor_inicial: float | None
    meta_esperada: float | None
    pqrs_id: int | None

    area: str | None
    responsable_id: int | None
    responsable_nombre: str | None
    creado_por: int | None
    autor_nombre: str | None

    estado: str
    prioridad: str
    fecha_limite: datetime | None
    causa_raiz: str | None

    eficaz: bool | None
    valor_verificado: float | None
    nota_eficacia: str | None
    fecha_cierre: datetime | None
    creado_en: datetime | None

    total_acciones: int
    acciones_completadas: int
    avance_pct: float


class OportunidadDetalleOut(OportunidadOut):
    acciones: list[AccionOut] = []
