"""
Catálogo de productos: una copia local de lo que vive en el ERP.

No se consulta Oracle en vivo. Un proceso del lado del ERP manda el catálogo
cada cierto tiempo y aquí queda una copia. Eso es deliberado:

  - El portal está expuesto a internet. Si algún día lo comprometen, aquí no
    hay credenciales ni rutas hacia la base del ERP: no existe la conexión.
  - Las búsquedas salen de Postgres en milisegundos, sin depender de que el
    ERP esté arriba ni de la latencia de la red.
  - Un buscador público que consultara el ERP con cada tecla podría generar
    bloqueos sobre las tablas donde la empresa factura.

Solo se copia lo que hace falta para identificar un producto. Nada de
precios, costos ni existencias: si no está aquí, no se puede filtrar.
"""
from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, func,
)

from app.core.database import Base


class ProductoCatalogo(Base):
    __tablename__ = "cat_productos"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    # El código del ERP. Es la identidad del producto y lo que se guarda en
    # la PQRS, así que no cambia aunque le renombren la descripción.
    codigo = Column(String(60), nullable=False, index=True)
    nombre = Column(String(300), nullable=False)
    presentacion = Column(String(60), nullable=True)

    # Un producto que deja de venir en la sincronización se marca inactivo en
    # vez de borrarse: deja de aparecer en el buscador, pero si mañana vuelve
    # al catálogo no se pierde nada y las PQRS viejas siguen teniendo sentido.
    activo = Column(Boolean, nullable=False, default=True, server_default="true")

    actualizado_en = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "codigo", name="uq_producto_codigo"),
    )
