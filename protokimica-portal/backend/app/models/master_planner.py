"""
Modelos del módulo Master Planner.

Sigue el mismo patrón que PQRS: una entidad principal (Proyecto) con
tablas hijas para desglose (ItemPresupuesto) y trazabilidad
(TareaActualizacion), en vez de un log narrativo tipo Excel.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Numeric, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class Proyecto(Base):
    __tablename__ = "mp_proyectos"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    nombre = Column(String(200), nullable=False)
    objetivo = Column(Text, nullable=True)
    alcance = Column(Text, nullable=True)

    lider_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    area = Column(String(100), nullable=True)

    # planeacion | en_ejecucion | pausado | cerrado
    estado = Column(String(20), nullable=False, default="planeacion")
    # baja | media | alta | critica
    prioridad = Column(String(20), nullable=False, default="media")

    fecha_inicio = Column(DateTime(timezone=True), nullable=True)
    fecha_fin_estimada = Column(DateTime(timezone=True), nullable=True)
    fecha_fin_real = Column(DateTime(timezone=True), nullable=True)

    creado_en = Column(DateTime(timezone=True), server_default=func.now())

    lider = relationship("User", foreign_keys=[lider_id])
    items_presupuesto = relationship(
        "ItemPresupuesto", back_populates="proyecto", cascade="all, delete-orphan"
    )
    tareas = relationship(
        "Tarea", back_populates="proyecto", cascade="all, delete-orphan"
    )

    @property
    def presupuesto_total(self) -> float:
        """Suma de todos los ítems de presupuesto — nunca se escribe a mano."""
        return sum((item.valor_total or 0) for item in self.items_presupuesto)

    @property
    def avance_pct(self) -> float:
        """Promedio del avance de las tareas de primer nivel (sin subtareas), redondeado."""
        tareas_raiz = [t for t in self.tareas if t.parent_id is None]
        if not tareas_raiz:
            return 0
        return round(sum(t.avance_pct for t in tareas_raiz) / len(tareas_raiz), 1)


class ItemPresupuesto(Base):
    """Equivale a una fila de la hoja 'Presupuesto' del Excel DE-F-10."""
    __tablename__ = "mp_items_presupuesto"

    id = Column(Integer, primary_key=True, index=True)
    proyecto_id = Column(Integer, ForeignKey("mp_proyectos.id"), nullable=False, index=True)

    concepto = Column(String(200), nullable=False)
    detalle = Column(String(300), nullable=True)
    valor_unitario = Column(Numeric(14, 2), nullable=False, default=0)
    cantidad = Column(Numeric(10, 2), nullable=False, default=1)
    observaciones = Column(Text, nullable=True)

    creado_en = Column(DateTime(timezone=True), server_default=func.now())

    proyecto = relationship("Proyecto", back_populates="items_presupuesto")

    @property
    def valor_total(self) -> float:
        return float(self.valor_unitario or 0) * float(self.cantidad or 0)


class Tarea(Base):
    """
    Equivale a una 'Actividad' o 'Entregable/Tarea' del Excel — mismo
    modelo para ambos niveles, diferenciados por parent_id (permite
    subtareas si algún proyecto las necesita, sin forzarlo).
    """
    __tablename__ = "mp_tareas"

    id = Column(Integer, primary_key=True, index=True)
    proyecto_id = Column(Integer, ForeignKey("mp_proyectos.id"), nullable=False, index=True)
    parent_id = Column(Integer, ForeignKey("mp_tareas.id"), nullable=True, index=True)

    titulo = Column(String(200), nullable=False)
    descripcion = Column(Text, nullable=True)
    area = Column(String(100), nullable=True)

    asignado_a = Column(Integer, ForeignKey("users.id"), nullable=True)

    # pendiente | en_proceso | bloqueada | completada — controla la columna del Kanban
    estado = Column(String(20), nullable=False, default="pendiente")
    prioridad = Column(String(20), nullable=False, default="media")
    avance_pct = Column(Integer, nullable=False, default=0)
    riesgos = Column(Text, nullable=True)

    fecha_inicio = Column(DateTime(timezone=True), nullable=True)
    fecha_fin = Column(DateTime(timezone=True), nullable=True)

    creado_en = Column(DateTime(timezone=True), server_default=func.now())

    proyecto = relationship("Proyecto", back_populates="tareas")
    asignado = relationship("User", foreign_keys=[asignado_a])
    subtareas = relationship("Tarea", cascade="all, delete-orphan")
    actualizaciones = relationship(
        "TareaActualizacion", back_populates="tarea",
        cascade="all, delete-orphan", order_by="TareaActualizacion.fecha.desc()",
    )

    @property
    def asignado_nombre(self):
        return self.asignado.nombre if self.asignado else None


class TareaActualizacion(Base):
    """
    Reemplaza el log narrativo mensual del Excel: una entrada por
    actualización de avance, con comentario, % nuevo (opcional) y
    evidencia adjunta (opcional) — mismo patrón que pqrs_seguimientos.
    """
    __tablename__ = "mp_tarea_actualizaciones"

    id = Column(Integer, primary_key=True, index=True)
    tarea_id = Column(Integer, ForeignKey("mp_tareas.id"), nullable=False, index=True)
    usuario_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    comentario = Column(Text, nullable=True)
    avance_pct_nuevo = Column(Integer, nullable=True)
    adjunto_evidencia = Column(String(255), nullable=True)

    fecha = Column(DateTime(timezone=True), server_default=func.now())

    tarea = relationship("Tarea", back_populates="actualizaciones")
    usuario = relationship("User")

    @property
    def usuario_nombre(self):
        return self.usuario.nombre if self.usuario else None
