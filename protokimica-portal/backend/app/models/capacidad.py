"""
Capacidades otorgadas: quién puede hacer qué, más allá de a qué área
pertenece.

El problema que esto resuelve: hoy "quién autoriza notas crédito" o "quién
cierra una PQRS" vive en una constante de Python (`AREA_AUTORIZADORA`,
`AREA_SGC`...) repetida en cinco módulos. Mientras el área coincida con quién
hace el trabajo, funciona. El día que no —Aseguramiento también tramita notas
crédito, no solo Contabilidad— la única salida es cambiarle el área a esa
persona, y con eso le das también todo lo demás que esa área decide en otros
módulos.

**Una capacidad se otorga a un ÁREA (lo normal, se hereda solo cuando entra
gente nueva) o a una PERSONA (la excepción, explícita y visible).** Nunca a
un rol: el rol decide a qué MÓDULO entras (ver `core/modulos.py`), no qué
puedes hacer dentro. Mezclar las dos cosas es cómo se termina con un sistema
de roles paralelo que nadie entiende.

**El catálogo de capacidades vive en código (`core/capacidades.py`), no en
esta tabla.** Una capacidad sin un `if` en algún módulo que la compruebe es
una promesa vacía: alguien la otorgaría creyendo que protege algo, y no
protegería nada. Esta tabla solo dice A QUIÉN se le dio una capacidad que el
código ya sabe comprobar — el mismo principio que ya usa
`TipoAutorizacion.area_autorizadora`, generalizado a todo el portal.
"""
from sqlalchemy import (
    CheckConstraint, Column, DateTime, ForeignKey, Integer, String, func,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class CapacidadOtorgada(Base):
    __tablename__ = "capacidades_otorgadas"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    # La clave del catálogo en core/capacidades.CAPACIDADES, ej.
    # "notas_credito.autorizar". No es una FK a una tabla de catálogo a
    # propósito: el catálogo es código, así que no hay tabla que referenciar.
    capacidad = Column(String(60), nullable=False, index=True)

    # Exactamente uno de los dos va lleno — nunca los dos, nunca ninguno.
    # Otorgar a un área es lo normal: se hereda sola cuando entra gente nueva
    # y se pierde sola cuando alguien cambia de área. Otorgar a una persona es
    # la excepción explícita para cuando el área no alcanza.
    area = Column(String(100), nullable=True)
    usuario_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Quién la otorgó y cuándo. Sin esto, una capacidad otorgada a una persona
    # es una puerta abierta sin firma: nadie puede explicar después por qué
    # Silvana puede autorizar notas crédito si no es de Contabilidad.
    otorgada_por = Column(Integer, ForeignKey("users.id"), nullable=False)
    otorgada_en = Column(DateTime(timezone=True), server_default=func.now())

    # Revocar NO borra la fila — la marca. Un borrado no se distingue de
    # "esto nunca se otorgó", y la siembra que deja la tabla al día con las
    # reglas de hoy (`sembrar_capacidades_iniciales`) le devolvería a
    # Contabilidad, en el próximo arranque, una capacidad que un
    # administrador le quitó a propósito. NULL = vigente.
    revocada_en = Column(DateTime(timezone=True), nullable=True)

    usuario = relationship("User", foreign_keys=[usuario_id])
    otorgante = relationship("User", foreign_keys=[otorgada_por])

    __table_args__ = (
        CheckConstraint(
            "(area IS NOT NULL) != (usuario_id IS NOT NULL)",
            name="ck_capacidad_area_xor_usuario",
        ),
    )

    @property
    def usuario_nombre(self):
        return self.usuario.nombre if self.usuario else None

    @property
    def otorgante_nombre(self):
        return self.otorgante.nombre if self.otorgante else None
