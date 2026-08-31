"""
Lo que entra y sale del módulo de Oportunidades de Mejora.

Los `max_length` de aquí tienen su gemelo en `frontend/src/modules/mejora/
constants.js`. Si se amplía uno, hay que subir el otro: un límite que solo
existe en el schema devuelve un 422, y el detalle de un 422 es una lista de
objetos que la pantalla no sabe pintar.
"""
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

# Topes que el formulario también aplica. El del análisis de causas es
# generoso a propósito: en el Excel las descripciones llegan a dos mil
# caracteres y citan numerales de la norma completos.
MAX_TITULO = 200
MAX_ACCION = 300
MAX_TEXTO_LARGO = 4000
MAX_SEGUIMIENTO = 6000
MAX_NOMBRE = 150


# ── Catálogos ────────────────────────────────────────────────────────

class ItemCatalogoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tipo: str
    codigo: str | None
    nombre: str
    orden: int
    activo: bool


class CatalogosOut(BaseModel):
    """Los tres catálogos del formato, listos para llenar los desplegables."""
    proceso: list[ItemCatalogoOut] = []
    fuente: list[ItemCatalogoOut] = []
    tratamiento: list[ItemCatalogoOut] = []


class ItemCatalogoCrear(BaseModel):
    tipo: str
    nombre: str = Field(min_length=2, max_length=120)
    codigo: str | None = Field(default=None, max_length=20)
    orden: int = 0


class ItemCatalogoActualizar(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=120)
    orden: int | None = None
    activo: bool | None = None


# ── Responsables ─────────────────────────────────────────────────────

class ResponsableCrear(BaseModel):
    """
    Uno de los dos: el usuario del portal, o el nombre escrito.

    El nombre suelto no es un descuido: el formato admite «Comité de TIC's»
    como responsable del seguimiento, y un comité no tiene usuario.
    """
    tipo: str = "resolucion"
    usuario_id: int | None = None
    nombre_texto: str | None = Field(default=None, max_length=MAX_NOMBRE)


class ResponsableOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tipo: str
    usuario_id: int | None
    nombre: str | None


# ── Acciones del plan ────────────────────────────────────────────────

class AccionCrear(BaseModel):
    descripcion: str = Field(min_length=3, max_length=MAX_ACCION)
    responsable_id: int | None = None
    fecha_limite: datetime | None = None
    orden: int | None = None


class AccionActualizar(BaseModel):
    descripcion: str | None = Field(default=None, min_length=3, max_length=MAX_ACCION)
    responsable_id: int | None = None
    fecha_limite: datetime | None = None
    estado: str | None = None
    orden: int | None = None
    evidencia: str | None = None


class AccionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    orden: int
    descripcion: str
    responsable_id: int | None
    responsable_nombre: str | None
    fecha_limite: datetime | None
    estado: str
    completada: bool
    fecha_completada: datetime | None
    evidencia: str | None


# ── Seguimientos ─────────────────────────────────────────────────────

class SeguimientoCrear(BaseModel):
    contenido: str = Field(min_length=3, max_length=MAX_SEGUIMIENTO)
    fecha: date | None = None
    adjunto: str | None = Field(default=None, max_length=255)


class SeguimientoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fecha: date
    autor_id: int | None
    autor_nombre: str | None
    contenido: str
    adjunto: str | None
    requiere_revision: bool
    creado_en: datetime | None


# ── Historial ────────────────────────────────────────────────────────

class CambioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campo: str
    valor_anterior: str | None
    valor_nuevo: str | None
    usuario_nombre: str | None
    fecha: datetime | None


# ── Oportunidad ──────────────────────────────────────────────────────

class OportunidadCrear(BaseModel):
    titulo: str = Field(min_length=5, max_length=MAX_TITULO)
    descripcion: str | None = Field(default=None, max_length=MAX_TEXTO_LARGO)
    origen: str = "indicador"
    fecha_registro: date | None = None

    # Los catálogos del formato. Cuando no vienen, el proceso y la fuente se
    # proponen desde el área y el origen — el tratamiento no, porque decide
    # qué campos aplican y esa es una decisión de quien reporta.
    proceso_id: int | None = None
    fuente_id: int | None = None
    tratamiento_id: int | None = None

    clasificacion: str | None = None
    hallazgos_similares: bool = False

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
    prioridad: str = "media"
    fecha_limite: datetime | None = None
    reportado_por_texto: str | None = Field(default=None, max_length=MAX_NOMBRE)

    responsables: list[ResponsableCrear] = []


class OportunidadActualizar(BaseModel):
    titulo: str | None = Field(default=None, min_length=5, max_length=MAX_TITULO)
    descripcion: str | None = Field(default=None, max_length=MAX_TEXTO_LARGO)
    area: str | None = None
    prioridad: str | None = None
    fecha_limite: datetime | None = None
    fecha_registro: date | None = None

    proceso_id: int | None = None
    fuente_id: int | None = None
    tratamiento_id: int | None = None
    clasificacion: str | None = None
    hallazgos_similares: bool | None = None

    # Las 6M. Cada una por separado y no un textarea: el Excel ya venía
    # escribiendo estas etiquetas a mano dentro de la celda.
    causa_efecto: str | None = Field(default=None, max_length=MAX_TEXTO_LARGO)
    causa_metodo: str | None = Field(default=None, max_length=MAX_TEXTO_LARGO)
    causa_mano_obra: str | None = Field(default=None, max_length=MAX_TEXTO_LARGO)
    causa_maquinaria: str | None = Field(default=None, max_length=MAX_TEXTO_LARGO)
    causa_material: str | None = Field(default=None, max_length=MAX_TEXTO_LARGO)
    causa_medidas: str | None = Field(default=None, max_length=MAX_TEXTO_LARGO)
    causa_medio_ambiente: str | None = Field(default=None, max_length=MAX_TEXTO_LARGO)

    causa_raiz: str | None = Field(default=None, max_length=MAX_TEXTO_LARGO)
    correccion: str | None = Field(default=None, max_length=MAX_TEXTO_LARGO)
    beneficio_mejora: str | None = Field(default=None, max_length=MAX_TEXTO_LARGO)
    verificacion_planeada: str | None = Field(default=None, max_length=MAX_TEXTO_LARGO)
    nota_cierre: str | None = Field(default=None, max_length=MAX_TEXTO_LARGO)

    meta_esperada: float | None = None


class CambioEstado(BaseModel):
    estado: str


class Verificacion(BaseModel):
    eficaz: bool
    nota: str | None = Field(default=None, max_length=MAX_TEXTO_LARGO)
    valor_verificado: float | None = None


class ValidacionSGC(BaseModel):
    nota: str | None = Field(default=None, max_length=MAX_TEXTO_LARGO)


class OportunidadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    codigo: str | None
    consecutivo: int | None
    titulo: str
    descripcion: str | None
    origen: str
    fecha_registro: date | None

    proceso_id: int | None
    proceso_nombre: str | None
    fuente_id: int | None
    fuente_nombre: str | None
    tratamiento_id: int | None
    tratamiento_nombre: str | None
    tratamiento_codigo: str | None

    clasificacion: str | None
    hallazgos_similares: bool

    indicador_id: int | None
    indicador_nombre: str | None
    periodo_anio: int | None
    periodo_mes: int | None
    valor_inicial: float | None
    meta_esperada: float | None
    pqrs_id: int | None

    area: str | None
    creado_por: int | None
    autor_nombre: str | None

    estado: str
    prioridad: str
    fecha_limite: datetime | None

    # Qué campos aplican según el tratamiento. Los resuelve el servidor: si
    # la pantalla lo dedujera del nombre del catálogo, renombrarlo desde
    # Admin le escondería un campo obligatorio a media empresa.
    pide_causa: bool
    pide_correccion: bool
    pide_beneficio: bool

    causa_efecto: str | None
    causa_metodo: str | None
    causa_mano_obra: str | None
    causa_maquinaria: str | None
    causa_material: str | None
    causa_medidas: str | None
    causa_medio_ambiente: str | None
    causa_raiz: str | None
    correccion: str | None
    beneficio_mejora: str | None
    verificacion_planeada: str | None

    eficaz: bool | None
    valor_verificado: float | None
    nota_eficacia: str | None
    fecha_cierre: datetime | None
    nota_cierre: str | None

    validado_sgc_por: int | None
    validado_sgc_nombre: str | None
    validado_sgc_en: datetime | None
    nota_sgc: str | None

    requiere_revision: bool
    creado_en: datetime | None

    total_acciones: int
    acciones_completadas: int
    avance_pct: float
    total_seguimientos: int


class OportunidadDetalleOut(OportunidadOut):
    acciones: list[AccionOut] = []
    seguimientos: list[SeguimientoOut] = []
    responsables: list[ResponsableOut] = []
