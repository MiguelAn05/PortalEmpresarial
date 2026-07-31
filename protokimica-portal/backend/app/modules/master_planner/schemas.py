from datetime import datetime
from pydantic import BaseModel


# ── Proyecto ────────────────────────────────────────────────────

class ProyectoCreate(BaseModel):
    nombre: str
    objetivo: str | None = None
    alcance: str | None = None
    lider_id: int | None = None
    area: str | None = None
    prioridad: str = "media"
    fecha_inicio: datetime | None = None
    fecha_fin_estimada: datetime | None = None


class ProyectoUpdate(BaseModel):
    nombre: str | None = None
    objetivo: str | None = None
    alcance: str | None = None
    lider_id: int | None = None
    area: str | None = None
    estado: str | None = None
    prioridad: str | None = None
    fecha_inicio: datetime | None = None
    fecha_fin_estimada: datetime | None = None
    fecha_fin_real: datetime | None = None


class ProyectoOut(BaseModel):
    id: int
    nombre: str
    objetivo: str | None
    alcance: str | None
    lider_id: int | None
    lider_nombre: str | None = None
    area: str | None
    estado: str
    prioridad: str
    fecha_inicio: datetime | None
    fecha_fin_estimada: datetime | None
    fecha_fin_real: datetime | None
    presupuesto_total: float
    avance_pct: float
    creado_en: datetime

    class Config:
        from_attributes = True


# ── Ítem de presupuesto ─────────────────────────────────────────

class ItemPresupuestoCreate(BaseModel):
    concepto: str
    detalle: str | None = None
    valor_unitario: float = 0
    cantidad: float = 1
    observaciones: str | None = None


class ItemPresupuestoOut(BaseModel):
    id: int
    concepto: str
    detalle: str | None
    valor_unitario: float
    cantidad: float
    valor_total: float
    observaciones: str | None

    class Config:
        from_attributes = True


# ── Tarea ───────────────────────────────────────────────────────

class TareaCreate(BaseModel):
    titulo: str
    descripcion: str | None = None
    area: str | None = None
    parent_id: int | None = None
    asignado_a: int | None = None
    prioridad: str = "media"
    riesgos: str | None = None
    fecha_inicio: datetime | None = None
    fecha_fin: datetime | None = None


class TareaUpdate(BaseModel):
    titulo: str | None = None
    descripcion: str | None = None
    area: str | None = None
    asignado_a: int | None = None
    estado: str | None = None
    prioridad: str | None = None
    riesgos: str | None = None
    fecha_inicio: datetime | None = None
    fecha_fin: datetime | None = None


class TareaOut(BaseModel):
    id: int
    proyecto_id: int
    parent_id: int | None
    titulo: str
    descripcion: str | None
    area: str | None
    asignado_a: int | None
    asignado_nombre: str | None = None
    estado: str
    prioridad: str
    avance_pct: int
    riesgos: str | None
    fecha_inicio: datetime | None
    fecha_fin: datetime | None
    creado_en: datetime

    class Config:
        from_attributes = True


# ── Actualización de tarea (línea de tiempo) ───────────────────

class TareaActualizacionOut(BaseModel):
    id: int
    usuario_id: int | None
    usuario_nombre: str | None = None
    comentario: str | None
    avance_pct_nuevo: int | None
    adjunto_evidencia: str | None
    fecha: datetime

    class Config:
        from_attributes = True
