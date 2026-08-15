from datetime import datetime
from pydantic import BaseModel


# ── Proyecto ────────────────────────────────────────────────────

class ProyectoCreate(BaseModel):
    nombre: str
    objetivo: str | None = None
    alcance: str | None = None
    lider_id: int | None = None
    # Area responsable: la duena del presupuesto. Una sola, para que los
    # totales por area no se dupliquen.
    area: str | None = None
    # Areas adicionales que participan. Solo otorgan visibilidad.
    areas_participantes: list[str] = []
    estado: str = "planeacion"
    prioridad: str = "media"
    fecha_inicio: datetime | None = None
    fecha_fin_estimada: datetime | None = None


class ProyectoUpdate(BaseModel):
    nombre: str | None = None
    objetivo: str | None = None
    alcance: str | None = None
    lider_id: int | None = None
    area: str | None = None
    areas_participantes: list[str] | None = None
    estado: str | None = None
    prioridad: str | None = None
    fecha_inicio: datetime | None = None
    fecha_fin_estimada: datetime | None = None
    fecha_fin_real: datetime | None = None
    archivado: bool | None = None


class ProyectoOut(BaseModel):
    id: int
    nombre: str
    objetivo: str | None
    alcance: str | None
    lider_id: int | None
    lider_nombre: str | None = None
    area: str | None
    areas_participantes: list[str] = []
    areas_involucradas: list[str] = []
    estado: str
    prioridad: str
    fecha_inicio: datetime | None
    fecha_fin_estimada: datetime | None
    fecha_fin_real: datetime | None
    archivado: bool
    presupuesto_total: float
    presupuesto_aprobado: float
    presupuesto_pagado: float
    presupuesto_pendiente: float
    pagado_pct: float
    items_por_aprobar: int
    avance_pct: float
    total_tareas: int
    tareas_completadas: int
    creado_en: datetime
    # Cómo terminó, si terminó: "finalizado" o "cancelado". Va aquí para que
    # la lista de proyectos pueda distinguirlos sin pedir el acta de cada uno.
    cierre_tipo: str | None = None

    class Config:
        from_attributes = True


# ── Ítem de presupuesto ─────────────────────────────────────────

class ItemPresupuestoCreate(BaseModel):
    concepto: str
    detalle: str | None = None
    valor_unitario: float = 0
    cantidad: float = 1
    observaciones: str | None = None


class ItemPresupuestoUpdate(BaseModel):
    """El valor aprobado y los pagos NO se tocan aquí: tienen su propio
    endpoint porque cada uno exige un área distinta."""
    concepto: str | None = None
    detalle: str | None = None
    valor_unitario: float | None = None
    cantidad: float | None = None
    observaciones: str | None = None


class AprobacionIn(BaseModel):
    valor_aprobado: float
    nota: str | None = None


class PagoIn(BaseModel):
    valor: float
    fecha: datetime | None = None      # por defecto, hoy
    concepto: str | None = None


class PagoOut(BaseModel):
    id: int
    item_id: int
    valor: float
    fecha: datetime
    concepto: str | None
    soporte: str | None
    registrado_por: int | None
    registrado_por_nombre: str | None = None
    registrado_en: datetime | None

    class Config:
        from_attributes = True


class ItemPresupuestoOut(BaseModel):
    id: int
    proyecto_id: int
    concepto: str
    detalle: str | None
    valor_unitario: float
    cantidad: float
    valor_total: float

    # Aprobación
    valor_aprobado: float | None
    esta_aprobado: bool
    aprobado_por_nombre: str | None = None
    aprobado_en: datetime | None
    nota_aprobacion: str | None

    # Pago
    valor_pagado: float
    pendiente_de_pago: float
    pagado_pct: float
    estado_pago: str
    pagos: list[PagoOut] = []

    disponible: float
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


class SubtareaCreate(BaseModel):
    """El área y el proyecto se heredan del padre, por eso no van aquí."""
    titulo: str
    asignado_a: int | None = None
    prioridad: str = "media"
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


class SubtareaOut(BaseModel):
    """
    Subtarea vista desde su tarea padre. Es plana a propósito: el modelo
    permite anidar más niveles, pero el módulo solo expone uno para que
    la subtarea funcione como checklist y no como un árbol de proyectos.
    """
    id: int
    proyecto_id: int
    parent_id: int | None
    titulo: str
    asignado_a: int | None
    asignado_nombre: str | None = None
    estado: str
    prioridad: str
    avance_pct: int
    fecha_fin: datetime | None

    class Config:
        from_attributes = True


class TareaOut(BaseModel):
    id: int
    proyecto_id: int
    proyecto_nombre: str | None = None
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
    fecha_completada: datetime | None = None
    creado_en: datetime
    subtareas: list[SubtareaOut] = []
    total_subtareas: int = 0
    subtareas_completadas: int = 0

    class Config:
        from_attributes = True


class HistorialCambioOut(BaseModel):
    """
    Una entrada del historial. Los valores vienen como texto ya resuelto
    (nombres, no ids) y las fechas en ISO, para que el frontend solo tenga
    que decidir cómo mostrarlas según `campo`.
    """
    id: int
    entidad: str
    entidad_id: int
    entidad_nombre: str | None
    proyecto_id: int
    campo: str
    valor_anterior: str | None
    valor_nuevo: str | None
    usuario_id: int | None
    usuario_nombre: str | None = None
    fecha: datetime

    class Config:
        from_attributes = True


class UsuarioAsignableOut(BaseModel):
    id: int
    nombre: str
    area: str | None = None

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
