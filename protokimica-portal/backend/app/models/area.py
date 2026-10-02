"""
Las áreas de cada empresa.

Antes eran una lista en el código (`core/areas.py`), la misma para cualquier
empresa que instalara el portal. Ahora cada empresa tiene las suyas y las
administra en Administración › Áreas.

Las demás tablas guardan el área como TEXTO (`users.area`,
`pqrs_solicitudes.area_responsable`…), no como llave a esta tabla. Es a
propósito: así estaba todo cuando esta tabla llegó, y cambiar once columnas a
llave foránea habría sido una migración de datos enorme sobre lo que más se
usa. El precio es que renombrar un área tiene que reescribir esas columnas;
lo hace `core.areas.renombrar()`, en una sola transacción, y una prueba
verifica que no se le escape ninguna columna nueva.
"""
from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, func,
)

from app.core.database import Base

MAX_NOMBRE_AREA = 100   # el mismo largo que las columnas que guardan el área


class Area(Base):
    __tablename__ = "areas"
    __table_args__ = (UniqueConstraint("tenant_id", "nombre", name="uq_area_tenant_nombre"),)

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"),
                       nullable=False, index=True)
    nombre = Column(String(MAX_NOMBRE_AREA), nullable=False)
    # Desactivar en vez de borrar: lo que ya tiene esa área la conserva, y
    # solo deja de ofrecerse para lo nuevo.
    activa = Column(Boolean, nullable=False, default=True, server_default="true")
    # El área donde trabajan las sedes (en Protokimica, «Puntos de Venta»).
    # Quien está en ella lleva su punto de venta y ve solo las PQRS de su
    # mostrador. Una sola por empresa; la marca viaja con la fila, así que
    # renombrar el área no la pierde.
    es_de_sedes = Column(Boolean, nullable=False, default=False, server_default="false")
    creada_en = Column(DateTime(timezone=True), server_default=func.now())
