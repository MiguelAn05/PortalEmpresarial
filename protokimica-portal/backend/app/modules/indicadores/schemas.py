from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.indicadores import TIPOS_CAPTURA, UNIDADES, DIRECCIONES


class VariableIn(BaseModel):
    """Una variable de un indicador de fórmula: `A` = «Quejas atendidas a tiempo»."""
    letra: str = Field(..., min_length=1, max_length=1)
    etiqueta: str = Field(..., max_length=120)


class VariableOut(VariableIn):
    class Config:
        from_attributes = True


class IndicadorBase(BaseModel):
    nombre: str
    descripcion: str | None = None
    formula_texto: str | None = None
    unidad: str = "porcentaje"
    tipo_captura: str = "valor"
    fuente_automatica: str | None = None
    etiqueta_numerador: str | None = None
    etiqueta_denominador: str | None = None
    # Solo para tipo_captura="formula". Ver `indicadores/formula.py`.
    formula: str | None = Field(None, max_length=300)
    variables: list[VariableIn] = []
    area: str | None = None
    responsable_id: int | None = None
    meta: float | None = None
    direccion: str = "arriba"
    umbral_verde: float | None = None
    umbral_amarillo: float | None = None
    requiere_evidencia: bool = False
    orden: int = 0

    @field_validator("unidad")
    @classmethod
    def _unidad_valida(cls, v):
        if v not in UNIDADES:
            raise ValueError(f"Unidad inválida. Usa una de: {', '.join(sorted(UNIDADES))}.")
        return v

    @field_validator("tipo_captura")
    @classmethod
    def _captura_valida(cls, v):
        if v not in TIPOS_CAPTURA:
            raise ValueError(f"Tipo de captura inválido. Usa uno de: {', '.join(sorted(TIPOS_CAPTURA))}.")
        return v

    @field_validator("direccion")
    @classmethod
    def _direccion_valida(cls, v):
        if v not in DIRECCIONES:
            raise ValueError("La dirección debe ser 'arriba' o 'abajo'.")
        return v


class IndicadorCreate(IndicadorBase):
    pass


class IndicadorUpdate(BaseModel):
    """Todo opcional; los mismos validadores aplican cuando el campo viene."""
    nombre: str | None = None
    descripcion: str | None = None
    formula_texto: str | None = None
    unidad: str | None = None
    tipo_captura: str | None = None
    fuente_automatica: str | None = None
    etiqueta_numerador: str | None = None
    etiqueta_denominador: str | None = None
    formula: str | None = Field(None, max_length=300)
    variables: list[VariableIn] | None = None
    area: str | None = None
    responsable_id: int | None = None
    meta: float | None = None
    direccion: str | None = None
    umbral_verde: float | None = None
    umbral_amarillo: float | None = None
    requiere_evidencia: bool | None = None
    activo: bool | None = None
    orden: int | None = None

    @field_validator("unidad")
    @classmethod
    def _unidad_valida(cls, v):
        if v is not None and v not in UNIDADES:
            raise ValueError(f"Unidad inválida. Usa una de: {', '.join(sorted(UNIDADES))}.")
        return v

    @field_validator("tipo_captura")
    @classmethod
    def _captura_valida(cls, v):
        if v is not None and v not in TIPOS_CAPTURA:
            raise ValueError(f"Tipo de captura inválido. Usa uno de: {', '.join(sorted(TIPOS_CAPTURA))}.")
        return v

    @field_validator("direccion")
    @classmethod
    def _direccion_valida(cls, v):
        if v is not None and v not in DIRECCIONES:
            raise ValueError("La dirección debe ser 'arriba' o 'abajo'.")
        return v


class IndicadorOut(IndicadorBase):
    id: int
    variables: list[VariableOut] = []
    formula_legible: str | None = None
    activo: bool
    responsable_nombre: str | None = None
    es_automatico: bool
    modo_acumulado: str
    creado_en: datetime

    class Config:
        from_attributes = True


class MedicionOut(BaseModel):
    id: int
    indicador_id: int
    anio: int
    mes: int
    valor: float | None
    numerador: float | None
    denominador: float | None
    # Lo que se digitó de cada variable en un indicador de fórmula.
    variables: dict[str, float] = {}
    analisis: str | None
    evidencia: str | None
    registrado_por: int | None
    registrado_por_nombre: str | None = None
    registrado_en: datetime | None
    validado_por_nombre: str | None = None
    validado_en: datetime | None

    class Config:
        from_attributes = True


class HistorialOut(BaseModel):
    id: int
    anio: int
    mes: int
    valor_anterior: float | None
    valor_nuevo: float | None
    motivo: str | None
    usuario_nombre: str | None = None
    fecha: datetime

    class Config:
        from_attributes = True


class FormulaPrueba(BaseModel):
    """
    Una fórmula a medio armar, para validarla y probarla antes de guardar.

    La pantalla la manda mientras se arma el indicador y mientras se digita
    un mes: así el resultado que se ve es el que calcula el servidor, y no una
    segunda implementación en el navegador que tarde o temprano diga otra cosa.
    """
    formula: str = Field("", max_length=300)
    variables: list[VariableIn] = []
    valores: dict[str, float | None] = {}


class FormulaResultado(BaseModel):
    valida: bool
    error: str | None = None
    legible: str | None = None
    # None si faltan valores o si con ellos se divide por cero.
    resultado: float | None = None
    divide_por_cero: bool = False
