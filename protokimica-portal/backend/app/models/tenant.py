"""
Modelo Tenant: representa una empresa cliente del portal (ej. Protokimica).
Todo lo demás (usuarios, PQRS, indicadores...) cuelga de un tenant_id.
"""
from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, func,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(150), nullable=False)
    slug = Column(String(80), unique=True, nullable=False, index=True)  # ej: "protokimica"
    activo = Column(Boolean, default=True, nullable=False)
    creado_en = Column(DateTime(timezone=True), server_default=func.now())

    # `selectin` y no perezosa: se consulta en cada petición para saber qué
    # módulos abre la empresa, muchas veces con la sesión que trajo al
    # usuario ya cerrada (ver `User.areas_supervisadas`).
    modulos = relationship(
        "TenantModulo", lazy="selectin", cascade="all, delete-orphan",
        back_populates="tenant",
    )

    @property
    def modulos_contratados(self) -> set[str]:
        return {m.modulo for m in self.modulos if m.activo}


class TenantModulo(Base):
    """
    Un módulo que la empresa tiene contratado. Ver `core/modulos.py`.

    Se apaga con `activo` en vez de borrar la fila: así queda desde cuándo lo
    tenía, y volverlo a prender no es crear un contrato nuevo.
    """
    __tablename__ = "tenant_modulos"
    __table_args__ = (UniqueConstraint("tenant_id", "modulo", name="uq_tenant_modulo"),)

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"),
                       nullable=False, index=True)
    modulo = Column(String(40), nullable=False)
    activo = Column(Boolean, nullable=False, default=True, server_default="true")
    desde = Column(DateTime(timezone=True), server_default=func.now())

    tenant = relationship("Tenant", back_populates="modulos")
