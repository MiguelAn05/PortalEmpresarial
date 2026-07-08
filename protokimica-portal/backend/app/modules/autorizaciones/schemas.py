from datetime import datetime
from pydantic import BaseModel


class TipoAutorizacionCreate(BaseModel):
    nombre: str
    descripcion: str | None = None
    area_autorizadora: str


class TipoAutorizacionOut(BaseModel):
    id: int
    nombre: str
    descripcion: str | None
    area_autorizadora: str
    activo: bool

    class Config:
        from_attributes = True


class SolicitarAutorizacion(BaseModel):
    tipo_id: int
    comentario_solicitud: str | None = None


class ResponderAutorizacion(BaseModel):
    decision: str  # aprobada | rechazada
    comentario_respuesta: str | None = None


class AutorizacionOut(BaseModel):
    id: int
    pqrs_id: int
    estado: str
    comentario_solicitud: str | None
    comentario_respuesta: str | None
    fecha_solicitud: datetime
    fecha_respuesta: datetime | None
    solicitado_por: int
    autorizado_por: int | None
    tipo: TipoAutorizacionOut

    class Config:
        from_attributes = True