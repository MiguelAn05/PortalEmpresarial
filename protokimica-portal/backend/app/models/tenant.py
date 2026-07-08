"""
Modelo Tenant: representa una empresa cliente del portal (ej. Protokimica).
Todo lo demás (usuarios, PQRS, indicadores...) cuelga de un tenant_id.
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, func

from app.core.database import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(150), nullable=False)
    slug = Column(String(80), unique=True, nullable=False, index=True)  # ej: "protokimica"
    activo = Column(Boolean, default=True, nullable=False)
    creado_en = Column(DateTime(timezone=True), server_default=func.now())
