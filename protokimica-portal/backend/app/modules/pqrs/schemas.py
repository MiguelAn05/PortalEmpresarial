from datetime import datetime
from pydantic import BaseModel, EmailStr


class PQRSCreate(BaseModel):
    tipo: str  # peticion | queja | reclamo | sugerencia
    cliente_nombre: str
    cliente_email: EmailStr | None = None
    cliente_telefono: str | None = None
    descripcion: str
    area_responsable: str | None = None


class PQRSUpdateEstado(BaseModel):
    estado: str  # recibido | asignado | en_proceso | resuelto | cerrado
    comentario: str | None = None


class PQRSAsignar(BaseModel):
    usuario_id: int
    comentario: str | None = None


class SeguimientoOut(BaseModel):
    id: int
    tipo_evento: str
    comentario: str | None
    fecha: datetime
    usuario_id: int | None

    class Config:
        from_attributes = True


class PQRSOut(BaseModel):
    id: int
    tipo: str
    cliente_nombre: str
    cliente_email: str | None
    cliente_telefono: str | None
    descripcion: str
    area_responsable: str | None
    asignado_a: int | None
    estado: str
    prioridad: str
    fecha_creacion: datetime
    fecha_limite_sla: datetime | None
    fecha_cierre: datetime | None

    class Config:
        from_attributes = True


class PQRSDetailOut(PQRSOut):
    seguimientos: list[SeguimientoOut] = []


class EncuestaCreate(BaseModel):
    calificacion: int  # 1 a 5
    comentario: str | None = None
