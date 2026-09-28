from datetime import date, datetime
from pydantic import BaseModel, Field

# Topes con gemelo en `frontend/src/modules/masterPlanner/constants.js`, y
# una prueba que los ata. Un límite que solo existe aquí devuelve un 422 en
# la cara de quien ya escribió el texto.
#
# El entregable es una frase —«el informe firmado»—, no el detalle de la
# tarea: para eso está la descripción. 300 es el mismo tope que usa el resto
# del portal para una línea de texto.
MAX_ENTREGABLE = 300
# Un tope alto pero finito: 2.000 horas es un año de trabajo de una persona.
# Sin él, un dedo de más convierte «8» en «800» y la carga de la semana de
# alguien queda diciendo cualquier cosa.
MAX_HORAS = 2000


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
    # Qué tiene que quedar hecho. Se pide aquí, al crear: escrito después se
    # escribe para justificar lo que ya se hizo.
    entregable: str | None = Field(default=None, max_length=MAX_ENTREGABLE)
    horas_estimadas: float | None = Field(default=None, ge=0, le=MAX_HORAS)
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
    entregable: str | None = Field(default=None, max_length=MAX_ENTREGABLE)
    horas_estimadas: float | None = Field(default=None, ge=0, le=MAX_HORAS)
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
    entregable: str | None = None
    horas_estimadas: float | None = None
    fecha_inicio: datetime | None
    fecha_fin: datetime | None
    fecha_completada: datetime | None = None
    # Cuántas veces se movió la fecha de entrega. Lo cuenta el modelo desde el
    # historial (`Tarea.veces_aplazada`), no el router: hay siete endpoints
    # que devuelven tareas y el octavo habría devuelto cero sin fallar.
    veces_aplazada: int = 0
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

class RespuestaActualizacionOut(BaseModel):
    """
    Una respuesta a un avance. Plana a propósito: no lleva `respuestas`
    dentro, porque el servidor solo admite un nivel. Si el schema dejara
    anidar, la pantalla tendría que saber dibujar algo que nunca va a llegar.
    """
    id: int
    usuario_id: int | None
    usuario_nombre: str | None = None
    comentario: str | None
    fecha: datetime

    class Config:
        from_attributes = True


class TareaActualizacionOut(BaseModel):
    id: int
    usuario_id: int | None
    usuario_nombre: str | None = None
    comentario: str | None
    avance_pct_nuevo: int | None
    adjunto_evidencia: str | None
    fecha: datetime
    # Las respuestas viajan DENTRO del avance que contestan, no como entradas
    # sueltas de la lista: es lo que las hace legibles — se ve a qué
    # contestan sin tener que cruzar fechas a ojo.
    respuestas: list[RespuestaActualizacionOut] = []

    class Config:
        from_attributes = True


class RespuestaActualizacionCrear(BaseModel):
    """
    Lo único que lleva una respuesta: el texto.

    No reusa el schema del avance a propósito. Ahí van `avance_pct_nuevo` y la
    evidencia, y una respuesta no mueve el avance ni adjunta nada — dejar esos
    campos aceptaría una petición que después nadie sabría explicar, y la
    pantalla tendría que mandar valores inventados para que el servidor la
    aceptara.
    """
    comentario: str | None = None


# ── Actividades diarias ─────────────────────────────────────────

MAX_TITULO_ACTIVIDAD = 200
MAX_COMENTARIO_REGISTRO = 500


class ActividadCrear(BaseModel):
    """
    Lo mínimo para crear una: título, responsable y frecuencia.

    Una actividad diaria es corta y repetitiva; pedirle siete campos a algo
    que se escribe una vez y se marca todos los días es cómo se consigue que
    nadie la cree. El área NO va aquí: se hereda del responsable en el
    router, que es quien sabe quién es.
    """
    titulo: str = Field(min_length=3, max_length=MAX_TITULO_ACTIVIDAD)
    asignado_a: int | None = None
    frecuencia: str = "diaria"
    # Días ISO (1 = lunes) para la semanal.
    dias_semana: list[int] = []
    dia_mes: int | None = Field(default=None, ge=1, le=31)
    solo_dias_habiles: bool = True
    desde: date | None = None


class ActividadActualizar(BaseModel):
    titulo: str | None = Field(default=None, min_length=3, max_length=MAX_TITULO_ACTIVIDAD)
    asignado_a: int | None = None
    area: str | None = None
    frecuencia: str | None = None
    dias_semana: list[int] | None = None
    dia_mes: int | None = Field(default=None, ge=1, le=31)
    solo_dias_habiles: bool | None = None
    activa: bool | None = None


class RegistroActividadCrear(BaseModel):
    """
    `fecha` vacía es hoy. Se puede mandar otra para registrar lo de ayer:
    quien no alcanzó a marcarlo el viernes lo marca el lunes, y el
    cumplimiento tiene que contarlo en el viernes.
    """
    fecha: date | None = None
    comentario: str | None = Field(default=None, max_length=MAX_COMENTARIO_REGISTRO)


class RegistroActividadOut(BaseModel):
    id: int
    actividad_id: int
    fecha: date
    usuario_id: int | None
    usuario_nombre: str | None = None
    comentario: str | None
    creado_en: datetime

    class Config:
        from_attributes = True


class ActividadOut(BaseModel):
    id: int
    titulo: str
    asignado_a: int | None
    asignado_nombre: str | None = None
    area: str | None
    frecuencia: str
    dias_semana: list[int] = []
    dia_mes: int | None
    solo_dias_habiles: bool
    desde: date
    hasta: date | None
    activa: bool
    creado_en: datetime

    # Redactado por el servidor: «Cada lunes, miércoles y viernes». Si lo
    # armara la pantalla, agregar una frecuencia dejaría un sitio más que
    # actualizar y el que se olvide muestra «undefined».
    frecuencia_texto: str = ""
    # Si tocaba HOY y si ya se registró. Es lo único que la lista necesita
    # para pintar la casilla, y sale de la misma regla que el indicador.
    toca_hoy: bool = False
    registrada_hoy: bool = False

    class Config:
        from_attributes = True


class CumplimientoActividadOut(BaseModel):
    """Cuántas veces tocaba en el periodo y cuántas se registró."""
    esperados: int
    cumplidos: int
    pct: float | None
    pendientes: list[date] = []


class DiaActividadOut(BaseModel):
    """
    Un día del mes, con su estado ya resuelto por el servidor.

    Son CUATRO estados y no dos: `no_aplica` (ese día no tocaba),
    `cumplido`, `pendiente` (es hoy, todavía se puede) y `sin_registrar`.
    Pintar como incumplidos los días en que no tocaba sería mentir, y cobrar
    el de hoy antes de que termine, también.
    """
    fecha: date
    estado: str
    usuario_nombre: str | None = None
    comentario: str | None = None


class MesActividadOut(BaseModel):
    """
    El mes entero de una actividad. Reemplaza la lista de días registrados,
    que crecía sin final: esto siempre son treinta y un cuadros como mucho.
    """
    anio: int
    mes: int
    dias: list[DiaActividadOut]
    # Lo que toca en todo el mes, para saber cuánto falta.
    esperados: int
    cumplidos: int
    # Y lo que ya se podía haber hecho, que es sobre lo que se mide: si no,
    # el primer día del mes toda actividad aparecería con un 5%.
    esperados_hasta_hoy: int
    cumplidos_hasta_hoy: int
    pct: float | None
