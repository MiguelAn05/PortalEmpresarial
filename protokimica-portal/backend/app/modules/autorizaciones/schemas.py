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


class AutorizacionOut(BaseModel):
    id: int
    pqrs_id: int
    estado: str
    comentario_solicitud: str | None
    comentario_respuesta: str | None
    adjunto_solicitud: str | None = None
    adjunto_respuesta: str | None = None
    fecha_solicitud: datetime
    fecha_respuesta: datetime | None
    solicitado_por: int
    solicitante_nombre: str | None = None
    autorizado_por: int | None
    autorizador_nombre: str | None = None
    tipo: TipoAutorizacionOut

    # ¿Puede responderla quien está mirando? Lo decide el servidor con el
    # área del tipo (ver `permisos.puede_responder`). La pantalla lo
    # preguntaba mal —miraba el rol— y por eso un agente del área
    # autorizadora no veía los botones aunque la API sí lo dejaba responder.
    puede_responder: bool = False

    class Config:
        from_attributes = True