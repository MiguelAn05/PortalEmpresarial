from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, func
from sqlalchemy.orm import relationship
from app.core.database import Base


class TipoAutorizacion(Base):
    """
    Tipos de autorización configurables desde administración.
    Ej: Devolución de dinero, Cambio de producto, Nota crédito
    """
    __tablename__ = "tipos_autorizacion"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    nombre = Column(String(150), nullable=False)
    descripcion = Column(Text, nullable=True)
    area_autorizadora = Column(String(100), nullable=False)  # Área que puede autorizar
    activo = Column(Boolean, default=True, nullable=False)
    creado_en = Column(DateTime(timezone=True), server_default=func.now())

    autorizaciones = relationship("AutorizacionPQRS", back_populates="tipo")


class AutorizacionPQRS(Base):
    """
    Solicitud de autorización para una PQRS específica.
    Bloquea la PQRS hasta que sea aprobada o rechazada.
    """
    __tablename__ = "autorizaciones_pqrs"

    id = Column(Integer, primary_key=True, index=True)
    pqrs_id = Column(Integer, ForeignKey("pqrs_solicitudes.id"), nullable=False, index=True)
    tipo_id = Column(Integer, ForeignKey("tipos_autorizacion.id"), nullable=False)

    # pendiente | aprobada | rechazada
    estado = Column(String(20), nullable=False, default="pendiente")

    solicitado_por = Column(Integer, ForeignKey("users.id"), nullable=False)
    autorizado_por = Column(Integer, ForeignKey("users.id"), nullable=True)

    comentario_solicitud = Column(Text, nullable=True)
    comentario_respuesta = Column(Text, nullable=True)

    # La evidencia con la que se pide y con la que se responde. Antes el
    # soporte (la factura, la foto, el concepto) se mandaba por fuera del
    # portal y la autorización quedaba aprobada sin nada que la sustentara.
    adjunto_solicitud = Column(String(255), nullable=True)
    adjunto_respuesta = Column(String(255), nullable=True)

    fecha_solicitud = Column(DateTime(timezone=True), server_default=func.now())
    fecha_respuesta = Column(DateTime(timezone=True), nullable=True)

    tipo = relationship("TipoAutorizacion", back_populates="autorizaciones")
    solicitante = relationship("User", foreign_keys=[solicitado_por])
    autorizador = relationship("User", foreign_keys=[autorizado_por])

    # El nombre de quien pide y de quien firma, para que la pantalla no tenga
    # que resolver un id contra otra consulta. Mismo patrón que en
    # PQRSSeguimiento.usuario_nombre.
    @property
    def solicitante_nombre(self):
        return self.solicitante.nombre if self.solicitante else None

    @property
    def autorizador_nombre(self):
        return self.autorizador.nombre if self.autorizador else None
