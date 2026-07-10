from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func
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
    canal_atencion = Column(String(50), nullable=True)
    lote = Column(String(50), nullable=True)
    factura_numero = Column(String(50), nullable=True)
    cantidad_factura = Column(String(20), nullable=True)
    cantidad_reclamo = Column(String(20), nullable=True)
    adjunto_producto = Column(String(500), nullable=True)
    adjunto_factura = Column(String(500), nullable=True)
    descripcion = Column(Text, nullable=False)
    area_responsable = Column(String(100), nullable=True)
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
    fecha = Column(DateTime(timezone=True), server_default=func.now())

    pqrs = relationship('PQRSSolicitud', back_populates='seguimientos')
    usuario = relationship('User')


class PQRSEncuesta(Base):
    __tablename__ = 'pqrs_encuestas'

    id = Column(Integer, primary_key=True, index=True)
    pqrs_id = Column(Integer, ForeignKey('pqrs_solicitudes.id'), nullable=False, unique=True)
    calificacion = Column(Integer, nullable=True)
    comentario = Column(Text, nullable=True)
    respondida_en = Column(DateTime(timezone=True), nullable=True)
    enviada_en = Column(DateTime(timezone=True), server_default=func.now())

    pqrs = relationship('PQRSSolicitud', back_populates='encuesta')
