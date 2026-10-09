"""
Las bodegas de la empresa: de dónde sale el producto y a quién le toca
confirmarlo. Una sola lista para todo el portal.

Hasta la 0.51 había dos, y no se conocían: la de Notas crédito, escrita en el
código (`Guayabal` y `La 65`, sin el CD), y la de despacho que trajo el flujo
de conceptos de PQRS. Dos listas de lo mismo terminan diciendo cosas
distintas: una bodega nueva aparecía en una pantalla y en la otra no.

- **Cada bodega tiene sus responsables**, que son PERSONAS: en una nota
  crédito institucional son a quienes se les avisa primero y quienes
  confirman que el producto está bien. Antes se marcaba la bodega en cada
  usuario (`users.bodega`); ahora se elige en la bodega, que es donde se
  piensa la pregunta «¿quién responde por esto?».
- **Cada módulo le pone lo suyo encima**, sin que la bodega lo sepa: PQRS le
  asigna el concepto que pide (Logística o Producción) en
  `pqrs_conceptos_bodega`.
- **Notas crédito guarda el NOMBRE** (`nc_solicitudes.bodega`), como guarda
  el canal. Por eso renombrar pasa por `core.bodegas.renombrar()`, que
  reescribe esa columna. PQRS guarda el id, y ahí renombrar no mueve nada.
- **No se borra si alguien la usa**: se desactiva.
"""
from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, func,
)
from sqlalchemy.orm import relationship

from app.core.database import Base

# El largo de `nc_solicitudes.bodega`, que guarda el nombre.
MAX_NOMBRE_BODEGA = 40


class Bodega(Base):
    __tablename__ = "bodegas"
    __table_args__ = (UniqueConstraint("tenant_id", "nombre", name="uq_bodega_tenant_nombre"),)

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    nombre = Column(String(MAX_NOMBRE_BODEGA), nullable=False)
    activo = Column(Boolean, nullable=False, default=True, server_default="true")
    orden = Column(Integer, nullable=False, default=0, server_default="0")
    creada_en = Column(DateTime(timezone=True), server_default=func.now())

    responsables = relationship(
        "BodegaResponsable", back_populates="bodega", cascade="all, delete-orphan", lazy="selectin",
    )


class BodegaResponsable(Base):
    """Una persona que responde por una bodega. Configuración, no trabajo."""
    __tablename__ = "bodega_responsables"
    __table_args__ = (UniqueConstraint("bodega_id", "usuario_id", name="uq_bodega_responsable"),)

    id = Column(Integer, primary_key=True)
    bodega_id = Column(Integer, ForeignKey("bodegas.id", ondelete="CASCADE"), nullable=False, index=True)
    usuario_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    bodega = relationship("Bodega", back_populates="responsables")
