"""
Los canales de atención de cada empresa: por dónde entra una PQRS.

Antes eran una lista en el código (`core/canales.py`), igual para cualquier
empresa, con los seis puntos de venta de Protokimica escritos a mano. Ahora
cada empresa tiene los suyos y los administra en Administración › Canales.

Un canal tiene un **tipo**, porque no todos significan lo mismo:

- `sede`: un mostrador físico. Se le asigna a un usuario como su punto de
  venta, acota qué PQRS ve esa persona y es quien emite las notas crédito
  de sus ventas.
- `institucional`: venta a empresas. Sus notas crédito siguen la cadena
  larga (Comercial, Contabilidad ante la DIAN). Antes se reconocía por el
  nombre «Venta institucional».
- `general`: WhatsApp, línea telefónica… Solo dice por dónde entró.

**El prefijo no se cambia nunca.** Es el código del QR impreso y pegado en
la sede, el comienzo del consecutivo de sus PQRS (`PVG0010`) y lo que
`users.punto_venta` guarda como «su punto». Cambiarlo dejaría letreros que
no abren nada y sedes sin su consecutivo. Se puede poner una vez a un canal
que no tenía; editarlo, no.
"""
from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, func,
)

from app.core.database import Base

MAX_NOMBRE_CANAL = 100   # el largo de pqrs_solicitudes.canal_atencion
MAX_PREFIJO = 10         # el largo de users.punto_venta

TIPOS_CANAL = ("sede", "institucional", "general")


class Canal(Base):
    __tablename__ = "canales"
    __table_args__ = (
        UniqueConstraint("tenant_id", "nombre", name="uq_canal_tenant_nombre"),
        UniqueConstraint("tenant_id", "prefijo", name="uq_canal_tenant_prefijo"),
    )

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"),
                       nullable=False, index=True)
    nombre = Column(String(MAX_NOMBRE_CANAL), nullable=False)
    # Sin prefijo, las PQRS del canal van al consecutivo general de la empresa.
    prefijo = Column(String(MAX_PREFIJO), nullable=True)
    tipo = Column(String(20), nullable=False, default="general", server_default="general")
    activo = Column(Boolean, nullable=False, default=True, server_default="true")
    creado_en = Column(DateTime(timezone=True), server_default=func.now())
