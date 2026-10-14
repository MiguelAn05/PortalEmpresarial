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
    JSON, Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Text,
    UniqueConstraint, func,
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
    # El grupo del ERP («QUIMICOS GRAV. 19%»). Sirve para agrupar las PQRS
    # por familia de producto en un informe.
    grupo = Column(String(60), nullable=True)
    # Lo vendido hace poco sale primero en el buscador. No se usa para
    # esconder nada: un producto que no se vende hace dos años también se
    # puede reclamar, y para lo raro está «no encuentro mi producto».
    fecha_ultima_venta = Column(Date, nullable=True)

    # Código, nombre y presentación en minúscula y sin tildes. Se arma al
    # sincronizar (`service.texto_de_busqueda`) para que «acido» encuentre
    # «Ácido» sin depender de una extensión de Postgres, y en producción
    # lleva un índice de trigramas para que buscar no recorra la tabla.
    texto_busqueda = Column(String(500), nullable=True)

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


class HuellaClienteERP(Base):
    """
    Un cliente del ERP, reducido a una huella que no se puede leer.

    Sirve para UNA pregunta: «¿este NIT es cliente nuestro?». No se copian
    clientes —ni el nombre, ni la ciudad, ni el NIT—: el script de MORFEO
    calcula un HMAC-SHA256 de cada NIT con `CLAVE_HUELLA_NIT` y solo manda
    eso. Los NIT nunca salen de la red interna, y quien se llevara esta
    tabla tendría una lista de números de 64 cifras sin la clave para
    compararlos.
    """
    __tablename__ = "cat_clientes_huella"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    huella = Column(String(64), nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "huella", name="uq_cliente_huella"),
    )


class SincronizacionERP(Base):
    """
    Cada vez que el ERP mandó algo, y qué pasó.

    El script corre de madrugada en otro servidor: si deja de llegar, lo
    único que lo delata es que aquí la última fecha se quedó quieta.
    """
    __tablename__ = "cat_sincronizaciones"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    # 'productos' | 'clientes'
    tipo = Column(String(20), nullable=False)
    fecha = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    exitosa = Column(Boolean, nullable=False)
    # Lo que devolvió la sincronización (nuevos, actualizados…).
    resumen = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
