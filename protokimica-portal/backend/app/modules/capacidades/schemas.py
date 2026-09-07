from datetime import datetime

from pydantic import BaseModel, model_validator


class OtorgamientoOut(BaseModel):
    id: int
    area: str | None = None
    usuario_id: int | None = None
    usuario_nombre: str | None = None
    otorgada_por: int
    otorgante_nombre: str | None = None
    otorgada_en: datetime

    class Config:
        from_attributes = True


class CapacidadOut(BaseModel):
    """
    Una fila del catálogo (`core/capacidades.CAPACIDADES`) con quién la tiene
    hoy. Va junta y no en dos llamadas — es exactamente la vista que responde
    «¿quién puede autorizar notas crédito?» sin tener que cruzar nada.
    """
    clave: str
    descripcion: str
    otorgamientos: list[OtorgamientoOut]


class OtorgarCapacidad(BaseModel):
    """
    Exactamente uno de los dos: a un área (lo normal) o a una persona
    (la excepción). Los dos juntos, o ninguno, no dicen a quién se otorga.
    """
    area: str | None = None
    usuario_id: int | None = None

    @model_validator(mode="after")
    def _uno_solo(self):
        if bool(self.area) == bool(self.usuario_id):
            raise ValueError(
                "Manda exactamente uno: 'area' para otorgarla a toda un área, "
                "o 'usuario_id' para otorgarla a una persona."
            )
        return self
