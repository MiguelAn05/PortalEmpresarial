"""
Modelo User: cada persona entra con el correo que quiera (corporativo o personal)
+ contraseña. No depende de Microsoft Entra ID. Se podría agregar login con
Microsoft más adelante como un método adicional, sin tocar esta tabla.
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    nombre = Column(String(150), nullable=False)
    email = Column(String(180), nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)

    # Rol dentro del tenant: admin | lider | responsable | agente | lectura
    rol = Column(String(40), nullable=False, default="agente")
    area = Column(String(100), nullable=True)  # ej: Comercial, Logística, HSEQ

    activo = Column(Boolean, default=True, nullable=False)
    creado_en = Column(DateTime(timezone=True), server_default=func.now())

    tenant = relationship("Tenant")

    __table_args__ = (
        # Un mismo correo puede repetirse entre tenants distintos, pero no dentro del mismo tenant
        UniqueConstraint("tenant_id", "email", name="uq_user_tenant_email"),
    )
