from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

# Los topes van aquí y el formulario los repite con la MISMA cifra: el backend
# es la autoridad, pero un `<input>` sin `maxLength` deja que el usuario
# escriba de más y reciba un 422 después de haberlo escrito todo.
MAX_FACTURA = 60
MAX_OBSERVACIONES = 2000
MAX_NUMERO_NC = 60


class MotivoOut(BaseModel):
    id: int
    nombre: str
    activo: bool

    class Config:
        from_attributes = True


class MotivoCreate(BaseModel):
    nombre: str


class ResponderSolicitud(BaseModel):
    decision: str  # aprobada | rechazada
    comentario: str | None = None


class AplicarSolicitud(BaseModel):
    numero_nc: str
    comentario: str | None = None


class AlcanceNotaCredito(BaseModel):
    """
    Qué puede hacer quien está mirando. El frontend no decide permisos: los
    pregunta, y esconde lo que no aplica.
    """
    puede_autorizar: bool
    puede_aplicar: bool


class SolicitudOut(BaseModel):
    id: int
    codigo: str | None = None
    punto_venta: str
    factura_afectada: str
    factura_reemplaza: str | None = None
    valor: Decimal | None = None
    motivo_id: int | None = None
    motivo_nombre: str | None = None
    observaciones: str
    adjunto: str | None = None

    estado: str
    solicitado_por: int
    solicitante_nombre: str | None = None
    creado_en: datetime

    autorizado_por: int | None = None
    autorizador_nombre: str | None = None
    comentario_respuesta: str | None = None
    fecha_respuesta: datetime | None = None

    numero_nc: str | None = None
    ejecutor_nombre: str | None = None
    fecha_aplicacion: datetime | None = None

    class Config:
        from_attributes = True


class SolicitudDetailOut(SolicitudOut):
    alcance: AlcanceNotaCredito | None = None
