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

    # En qué punto de venta trabaja, por su PREFIJO (`PVG`, `PVC`…). Solo
    # significa algo si `area == "Puntos de Venta"`: acota las PQRS que ve a
    # las de su sede (ver `modules/pqrs/permisos.py`). Vacío en alguien del
    # área = coordina todos los puntos y los ve todos.
    #
    # Se guarda el prefijo y no el nombre del canal porque el prefijo es lo
    # que no cambia: está impreso en el QR pegado en el mostrador.
    punto_venta = Column(String(10), nullable=True)

    activo = Column(Boolean, default=True, nullable=False)
    creado_en = Column(DateTime(timezone=True), server_default=func.now())

    tenant = relationship("Tenant")
    areas_supervisadas = relationship(
        "AreaSupervisada", back_populates="usuario", cascade="all, delete-orphan",
        # Se carga CON el usuario: se consulta en cada filtro por área, y
        # perezosa reventaba si la sesión que lo trajo ya se cerró.
        lazy="selectin",
        order_by="AreaSupervisada.area",
    )

    @property
    def areas_que_supervisa(self) -> list[str]:
        """Solo los nombres, que es lo que se compara en los filtros."""
        return [a.area for a in self.areas_supervisadas]

    __table_args__ = (
        # Un mismo correo puede repetirse entre tenants distintos, pero no dentro del mismo tenant
        UniqueConstraint("tenant_id", "email", name="uq_user_tenant_email"),
    )


class AreaSupervisada(Base):
    """
    Un área que esta persona supervisa, además de la suya.

    Existe porque un director responde por varias áreas —Dirección Técnica
    mira IDI y Salvak— y el filtro del portal es por área EXACTA: sin esto,
    quien está en su propia área de dirección no vería nada de su gente.

    Va en tabla y no en una columna con la lista adentro: se administra desde
    Admin › Usuarios, se consulta con un `IN` en cada módulo, y así agregar
    una jefatura nueva no pide un despliegue.

    **Es de una sola vía a propósito**: el jefe ve hacia abajo, el equipo no
    ve hacia arriba. Quien esté en IDI sigue viendo solo IDI, así que la
    gestión de la dirección no se le muestra.
    """
    __tablename__ = "usuario_areas_supervisadas"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    area = Column(String(100), nullable=False)

    usuario = relationship("User", back_populates="areas_supervisadas")

    __table_args__ = (
        UniqueConstraint("usuario_id", "area", name="uq_area_supervisada"),
    )
