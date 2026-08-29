from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, func
from sqlalchemy.orm import relationship
from app.core.database import Base


class PQRSSolicitud(Base):
    __tablename__ = 'pqrs_solicitudes'

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False, index=True)
    codigo_seguimiento = Column(String(30), unique=True, nullable=True, index=True)
    radicado_calidad = Column(String(30), unique=True, nullable=True, index=True)
    tipo = Column(String(20), nullable=False)
    empresa = Column(String(150), nullable=True)
    nit_cedula = Column(String(30), nullable=True)
    cliente_nombre = Column(String(150), nullable=False)
    cliente_email = Column(String(180), nullable=True)
    cliente_telefono = Column(String(40), nullable=True)
    ciudad = Column(String(100), nullable=True)
    departamento = Column(String(100), nullable=True)
    producto_codigo = Column(String(50), nullable=True)
    producto_nombre = Column(String(200), nullable=True)
    presentacion = Column(String(30), nullable=True)  # unidad | kilo | gramo | litro | mililitro
    cantidad_presentacion = Column(String(20), nullable=True)  # cantidad asociada a la presentación, ej: "5"
    canal_atencion = Column(String(50), nullable=True)
    lote = Column(String(50), nullable=True)
    factura_numero = Column(String(50), nullable=True)
    cantidad_factura = Column(String(20), nullable=True)
    cantidad_reclamo = Column(String(20), nullable=True)
    adjunto_producto = Column(String(500), nullable=True)
    adjunto_factura = Column(String(500), nullable=True)
    adjunto_video = Column(String(500), nullable=True)
    descripcion = Column(Text, nullable=False)
    area_responsable = Column(String(100), nullable=True)  # área que GESTIONA el caso (asignación operativa)
    area_causante = Column(String(100), nullable=True)  # área CAUSANTE del problema, para indicadores — solo editable internamente
    asignado_a = Column(Integer, ForeignKey('users.id'), nullable=True)
    estado = Column(String(20), nullable=False, default='recibido')
    prioridad = Column(String(20), nullable=False, default='media')
    origen_publico = Column(String(20), nullable=False, default='interno')
    fecha_creacion = Column(DateTime(timezone=True), server_default=func.now())
    fecha_limite_sla = Column(DateTime(timezone=True), nullable=True)
    fecha_cierre = Column(DateTime(timezone=True), nullable=True)

    asignado = relationship('User', foreign_keys=[asignado_a])
    seguimientos = relationship('PQRSSeguimiento', back_populates='pqrs', cascade='all, delete-orphan')
    encuesta = relationship('PQRSEncuesta', back_populates='pqrs', uselist=False, cascade='all, delete-orphan')


class PQRSSeguimiento(Base):
    __tablename__ = 'pqrs_seguimientos'

    id = Column(Integer, primary_key=True, index=True)
    pqrs_id = Column(Integer, ForeignKey('pqrs_solicitudes.id'), nullable=False, index=True)
    usuario_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    tipo_evento = Column(String(30), nullable=False)
    comentario = Column(Text, nullable=True)

    # A qué estado pasó la solicitud, cuando el evento es un cambio de estado.
    #
    # Existe para que la consulta pública pueda redactar el movimiento sin
    # usar el comentario: ahí es donde el área escribe sus notas internas, y
    # eso no le corresponde al cliente. Con el estado aparte, el texto que ve
    # se genera aquí y siempre dice lo mismo.
    estado_nuevo = Column(String(20), nullable=True)
    adjunto_evidencia = Column(String(255), nullable=True)
    fecha = Column(DateTime(timezone=True), server_default=func.now())

    pqrs = relationship('PQRSSolicitud', back_populates='seguimientos')
    usuario = relationship('User')

    @property
    def usuario_nombre(self):
        return self.usuario.nombre if self.usuario else None

    @property
    def usuario_area(self):
        return self.usuario.area if self.usuario else None

    @property
    def usuario_rol(self):
        return self.usuario.rol if self.usuario else None


class PQRSEncuesta(Base):
    __tablename__ = 'pqrs_encuestas'

    id = Column(Integer, primary_key=True, index=True)
    pqrs_id = Column(Integer, ForeignKey('pqrs_solicitudes.id'), nullable=False, unique=True)

    tipo_solicitud = Column(String(20), nullable=True)  # peticion | queja | reclamo | sugerencia | felicitacion
    calificacion = Column(Integer, nullable=True)  # calificación de la atención, 1 a 5
    solucionada = Column(String(20), nullable=True)  # si | parcial | no
    calificacion_tiempo_respuesta = Column(String(20), nullable=True)  # excelente | bueno | regular | malo
    recomendaria = Column(Boolean, nullable=True)
    comentario = Column(Text, nullable=True)

    respondida_en = Column(DateTime(timezone=True), nullable=True)
    enviada_en = Column(DateTime(timezone=True), server_default=func.now())

    pqrs = relationship('PQRSSolicitud', back_populates='encuesta')

    @property
    def respondida(self) -> bool:
        return self.respondida_en is not None
