"""
Modelos del módulo Master Planner.

Sigue el mismo patrón que PQRS: una entidad principal (Proyecto) con
tablas hijas para desglose (ItemPresupuesto) y trazabilidad
(TareaActualizacion), en vez de un log narrativo tipo Excel.
"""
from sqlalchemy import Boolean, Column, Integer, String, Text, DateTime, ForeignKey, Numeric, func
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
    # Área RESPONSABLE del proyecto: la dueña del presupuesto. Es una sola a
    # propósito — si el presupuesto se repartiera entre varias áreas, los
    # totales por área quedarían inflados. Las demás áreas involucradas van
    # en `areas_participantes` y solo otorgan visibilidad.
    area = Column(String(100), nullable=True)

    # planeacion | en_ejecucion | pausado | cerrado
    estado = Column(String(20), nullable=False, default="planeacion")
    # baja | media | alta | critica
    prioridad = Column(String(20), nullable=False, default="media")

    fecha_inicio = Column(DateTime(timezone=True), nullable=True)
    fecha_fin_estimada = Column(DateTime(timezone=True), nullable=True)
    fecha_fin_real = Column(DateTime(timezone=True), nullable=True)

    # Un proyecto archivado sale de las vistas del día a día pero conserva
    # todo su historial. Es la salida por defecto en vez de borrar, porque
    # el borrado arrastra en cascada tareas, actualizaciones y evidencias.
    archivado = Column(Boolean, nullable=False, default=False, server_default="false")

    creado_en = Column(DateTime(timezone=True), server_default=func.now())

    lider = relationship("User", foreign_keys=[lider_id])
    items_presupuesto = relationship(
        "ItemPresupuesto", back_populates="proyecto", cascade="all, delete-orphan"
    )
    tareas = relationship(
        "Tarea", back_populates="proyecto", cascade="all, delete-orphan"
    )
    # Sin esta cascada, borrar un proyecto revienta contra la llave foránea de
    # mp_historial: sus filas de bitácora siguen apuntando al proyecto.
    historial = relationship(
        "HistorialCambio", back_populates="proyecto", cascade="all, delete-orphan"
    )
    areas_extra = relationship(
        "ProyectoArea", back_populates="proyecto", cascade="all, delete-orphan"
    )

    @property
    def areas_participantes(self) -> list[str]:
        """Áreas adicionales a la responsable. Dan visibilidad, no presupuesto."""
        return sorted(a.area for a in self.areas_extra)

    @property
    def areas_involucradas(self) -> list[str]:
        """La responsable más las participantes — para mostrar en pantalla."""
        todas = set(self.areas_participantes)
        if self.area:
            todas.add(self.area)
        return sorted(todas)

    @property
    def presupuesto_total(self) -> float:
        """Suma de todos los ítems de presupuesto — nunca se escribe a mano."""
        return sum((item.valor_total or 0) for item in self.items_presupuesto)

    @property
    def presupuesto_aprobado(self) -> float:
        return sum(float(i.valor_aprobado or 0) for i in self.items_presupuesto)

    @property
    def presupuesto_pagado(self) -> float:
        return sum(i.valor_pagado for i in self.items_presupuesto)

    @property
    def presupuesto_pendiente(self) -> float:
        """Aprobado que aún no se ha desembolsado."""
        return sum(i.pendiente_de_pago for i in self.items_presupuesto)

    @property
    def pagado_pct(self) -> float:
        """
        Porcentaje pagado sobre lo APROBADO, no sobre lo planeado: es lo que
        de verdad se debe. Lo planeado puede no aprobarse nunca.
        """
        aprobado = self.presupuesto_aprobado
        return round((self.presupuesto_pagado / aprobado) * 100, 1) if aprobado else 0.0

    @property
    def items_por_aprobar(self) -> int:
        return sum(1 for i in self.items_presupuesto if not i.esta_aprobado)

    # Nombre anterior de `presupuesto_pagado`. Se conserva para no romper el
    # indicador automático de ejecución presupuestal, que ya está creado en
    # las bases con esa clave.
    @property
    def presupuesto_ejecutado(self) -> float:
        return self.presupuesto_pagado

    @property
    def _tareas_raiz(self) -> list["Tarea"]:
        return [t for t in self.tareas if t.parent_id is None]

    @property
    def avance_pct(self) -> float:
        """Promedio del avance de las tareas de primer nivel (sin subtareas), redondeado."""
        tareas_raiz = self._tareas_raiz
        if not tareas_raiz:
            return 0
        return round(sum(t.avance_pct for t in tareas_raiz) / len(tareas_raiz), 1)

    @property
    def total_tareas(self) -> int:
        """Solo tareas de primer nivel — es lo que se muestra en la tarjeta del proyecto."""
        return len(self._tareas_raiz)

    @property
    def tareas_completadas(self) -> int:
        return sum(1 for t in self._tareas_raiz if t.estado == "completada")


class ProyectoArea(Base):
    """
    Área adicional que participa en un proyecto. Existe para el caso real de
    proyectos que involucran a dos o más áreas: cualquiera de ellas ve el
    proyecto, pero el presupuesto se le sigue atribuyendo solo al área
    responsable (`Proyecto.area`).
    """
    __tablename__ = "mp_proyecto_areas"

    id = Column(Integer, primary_key=True, index=True)
    proyecto_id = Column(
        Integer, ForeignKey("mp_proyectos.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    area = Column(String(100), nullable=False, index=True)

    proyecto = relationship("Proyecto", back_populates="areas_extra")


class ItemPresupuesto(Base):
    """Equivale a una fila de la hoja 'Presupuesto' del Excel DE-F-10."""
    __tablename__ = "mp_items_presupuesto"

    id = Column(Integer, primary_key=True, index=True)
    proyecto_id = Column(Integer, ForeignKey("mp_proyectos.id"), nullable=False, index=True)

    concepto = Column(String(200), nullable=False)
    detalle = Column(String(300), nullable=True)
    valor_unitario = Column(Numeric(14, 2), nullable=False, default=0)
    cantidad = Column(Numeric(10, 2), nullable=False, default=1)

    # El dinero recorre tres etapas: planeado -> aprobado -> pagado.
    #   planeado: valor_unitario × cantidad, lo que se presupuestó.
    #   aprobado: lo que Administración autorizó desembolsar. En NULL mientras
    #             nadie lo haya aprobado — distinto de aprobar cero.
    #   pagado:   la suma de los abonos que registró Tesorería.
    valor_aprobado = Column(Numeric(14, 2), nullable=True)
    aprobado_por = Column(Integer, ForeignKey("users.id"), nullable=True)
    aprobado_en = Column(DateTime(timezone=True), nullable=True)
    nota_aprobacion = Column(Text, nullable=True)

    observaciones = Column(Text, nullable=True)

    creado_en = Column(DateTime(timezone=True), server_default=func.now())

    proyecto = relationship("Proyecto", back_populates="items_presupuesto")
    aprobador = relationship("User", foreign_keys=[aprobado_por])
    pagos = relationship(
        "PagoItem", back_populates="item",
        cascade="all, delete-orphan", order_by="PagoItem.fecha",
    )

    @property
    def valor_total(self) -> float:
        """Valor planeado del ítem."""
        return float(self.valor_unitario or 0) * float(self.cantidad or 0)

    @property
    def esta_aprobado(self) -> bool:
        return self.valor_aprobado is not None

    @property
    def aprobado_por_nombre(self):
        return self.aprobador.nombre if self.aprobador else None

    @property
    def valor_pagado(self) -> float:
        """
        Suma de los abonos. Se deriva y no se guarda aparte: un campo que se
        actualiza a mano en paralelo a los abonos termina desincronizado.
        """
        return sum(float(p.valor or 0) for p in self.pagos)

    @property
    def pendiente_de_pago(self) -> float:
        """
        Lo aprobado que aún no se ha desembolsado. Sin aprobación no hay nada
        pendiente: todavía no es una obligación.
        """
        if not self.esta_aprobado:
            return 0.0
        return float(self.valor_aprobado) - self.valor_pagado

    @property
    def pagado_pct(self) -> float:
        aprobado = float(self.valor_aprobado or 0)
        return round((self.valor_pagado / aprobado) * 100, 1) if aprobado else 0.0

    @property
    def estado_pago(self) -> str:
        """por_aprobar | aprobado | parcial | pagado"""
        if not self.esta_aprobado:
            return "por_aprobar"
        pagado = self.valor_pagado
        if pagado <= 0:
            return "aprobado"
        # Se compara con tolerancia de un peso: los decimales de un abono
        # calculado como porcentaje no tienen por qué cuadrar al centavo.
        if pagado + 1 >= float(self.valor_aprobado):
            return "pagado"
        return "parcial"

    @property
    def disponible(self) -> float:
        """Puede ser negativo: es la señal de que el ítem se pasó del presupuesto."""
        return self.valor_total - self.valor_pagado


class PagoItem(Base):
    """
    Un abono contra un ítem de presupuesto.

    Se guardan los abonos en vez de un solo campo "pagado" porque los pagos
    reales van por partes: anticipo, contra entrega, saldo. Con el detalle se
    puede responder cuándo se pagó cada cosa y con qué soporte; con un solo
    número, no.
    """
    __tablename__ = "mp_pagos"

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(
        Integer, ForeignKey("mp_items_presupuesto.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    valor = Column(Numeric(14, 2), nullable=False)
    fecha = Column(DateTime(timezone=True), nullable=False)
    concepto = Column(String(200), nullable=True)   # "Anticipo 50%", "Saldo"...
    soporte = Column(String(255), nullable=True)    # comprobante adjunto

    registrado_por = Column(Integer, ForeignKey("users.id"), nullable=True)
    registrado_en = Column(DateTime(timezone=True), server_default=func.now())

    item = relationship("ItemPresupuesto", back_populates="pagos")
    registrador = relationship("User", foreign_keys=[registrado_por])

    @property
    def registrado_por_nombre(self):
        return self.registrador.nombre if self.registrador else None


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
    # Momento en que la tarea pasó a "completada". Es lo que permite medir
    # cumplimiento: sin esto solo se sabe que está hecha, no si llegó a tiempo.
    fecha_completada = Column(DateTime(timezone=True), nullable=True)

    # Id del evento en el calendario de Outlook, si se sincronizó. Sin esto
    # no se puede distinguir "crear" de "actualizar": cada cambio de fecha
    # dejaría un evento nuevo en la agenda de la persona en vez de mover el
    # que ya estaba. Vacío = esa tarea no tiene evento (o Graph está apagado).
    outlook_evento_id = Column(String(255), nullable=True)

    creado_en = Column(DateTime(timezone=True), server_default=func.now())

    proyecto = relationship("Proyecto", back_populates="tareas")
    asignado = relationship("User", foreign_keys=[asignado_a])
    subtareas = relationship(
        "Tarea", back_populates="parent",
        cascade="all, delete-orphan", order_by="Tarea.creado_en.asc()",
    )
    parent = relationship("Tarea", back_populates="subtareas", remote_side=[id])
    actualizaciones = relationship(
        "TareaActualizacion", back_populates="tarea",
        cascade="all, delete-orphan", order_by="TareaActualizacion.fecha.desc()",
    )

    @property
    def asignado_nombre(self):
        return self.asignado.nombre if self.asignado else None

    @property
    def proyecto_nombre(self):
        return self.proyecto.nombre if self.proyecto else None

    @property
    def total_subtareas(self) -> int:
        return len(self.subtareas)

    @property
    def subtareas_completadas(self) -> int:
        return sum(1 for s in self.subtareas if s.estado == "completada")


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


class HistorialCambio(Base):  # noqa: E303
    """
    Bitácora de cambios de proyectos y tareas: quién cambió qué, cuándo, y de
    qué valor a cuál. Es lo que permite responder "¿por qué esta entrega se
    corrió tres veces?" sin depender de la memoria de nadie.

    Los valores se guardan como texto ya resuelto (el nombre del responsable,
    no su id) para que el historial siga siendo legible aunque después se
    desactive un usuario o se renombre algo.
    """
    __tablename__ = "mp_historial"

    id = Column(Integer, primary_key=True, index=True)

    entidad = Column(String(20), nullable=False)   # proyecto | tarea
    entidad_id = Column(Integer, nullable=False)
    # Cómo se llamaba en ese momento. Denormalizado para que el historial
    # siga siendo legible si después se renombra o se borra la tarea.
    entidad_nombre = Column(String(200), nullable=True)
    # Siempre presente, incluso para tareas: permite filtrar todo el historial
    # de un proyecto (el suyo y el de sus tareas) con una sola consulta.
    proyecto_id = Column(Integer, ForeignKey("mp_proyectos.id"), nullable=False, index=True)

    campo = Column(String(50), nullable=False)
    valor_anterior = Column(Text, nullable=True)
    valor_nuevo = Column(Text, nullable=True)

    usuario_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    fecha = Column(DateTime(timezone=True), server_default=func.now())

    usuario = relationship("User")
    proyecto = relationship("Proyecto", back_populates="historial")

    @property
    def usuario_nombre(self):
        return self.usuario.nombre if self.usuario else None
