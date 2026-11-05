"""
Marcaciones: las marcaciones del reloj biométrico (ZKBio Time) y lo que hace
falta para leerlas: quién es cada persona, qué turnos puede tener y qué días
no se trabaja.

**El portal no se conecta a ZKBio.** Un script que corre en el servidor de
ZKBio lee las marcaciones y las EMPUJA al portal con una clave propia
(`CLAVE_MARCACIONES`), igual que el ERP con el catálogo: el portal está
expuesto a internet, así que ahí no puede haber credenciales ni rutas hacia
el reloj. Ver `integraciones/marcaciones/`.

- `mar_marcaciones` guarda cada marcación TAL CUAL llegó, una sola vez
  (`UniqueConstraint`): el script reenvía los últimos días en cada pasada y
  eso tiene que ser inofensivo. La hora llega en la zona de la empresa y se
  guarda en UTC, como el resto del portal.
- `mar_empleados` es la malla: el área, los turnos posibles por día y, si se
  conoce, el correo con el que la persona entra al portal (es lo que deja a un
  agente ver SUS marcaciones y nada más). **No es la tabla de usuarios**: hay
  gente que marca y nunca entra al portal.
- `mar_justificaciones` es lo ÚNICO que se escribe desde la pantalla: lo que
  el líder (o Gestión Humana) explica de una novedad de una persona un día.
  Se guarda aparte y la novedad sigue calculándose igual: justificar no la
  borra, la acompaña con el motivo, quién lo dijo y cuándo.
- **Nada de esto se calcula aquí.** Llegadas tarde, ausencias y excesos de
  descanso salen de `modules/marcaciones/evaluacion.py` al consultar, nunca
  se guardan: cambiar una tolerancia corrige también el pasado y no hay dos
  números distintos para el mismo día.
"""
from sqlalchemy import (
    Boolean, Column, Date, DateTime, ForeignKey, Index, Integer, String, Text,
    UniqueConstraint, func,
)

from app.core.database import Base

# Los topes son los del schema de entrada (`modules/marcaciones/schemas.py`).
MAX_CODIGO = 30
MAX_NOMBRE = 150
MAX_AREA = 100
MAX_TURNOS = 80
MAX_JUSTIFICACION = 500
MIN_JUSTIFICACION = 5


class MarEmpleado(Base):
    __tablename__ = "mar_empleados"
    __table_args__ = (UniqueConstraint("tenant_id", "emp_code", name="uq_mar_empleado_codigo"),)

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    # El código de la persona en ZKBio (la cédula en Protokimica).
    emp_code = Column(String(MAX_CODIGO), nullable=False)
    nombre = Column(String(MAX_NOMBRE), nullable=False)
    # Texto, como en el resto del portal (ver `core/areas.COLUMNAS_CON_AREA`):
    # renombrar un área pasa por `areas.renombrar()`, que también reescribe esta.
    area = Column(String(MAX_AREA), nullable=True)
    correo = Column(String(180), nullable=True)
    # Turnos POSIBLES de cada día: «HH:MM-HH:MM» y, si hay varios, separados
    # por «/». Vacío = no trabaja ese día.
    lun = Column(String(MAX_TURNOS), nullable=False, default="", server_default="")
    mar = Column(String(MAX_TURNOS), nullable=False, default="", server_default="")
    mie = Column(String(MAX_TURNOS), nullable=False, default="", server_default="")
    jue = Column(String(MAX_TURNOS), nullable=False, default="", server_default="")
    vie = Column(String(MAX_TURNOS), nullable=False, default="", server_default="")
    sab = Column(String(MAX_TURNOS), nullable=False, default="", server_default="")
    dom = Column(String(MAX_TURNOS), nullable=False, default="", server_default="")
    # Se desactiva cuando sale de la malla (la persona se fue): sus marcaciones
    # viejas se conservan para el histórico.
    activo = Column(Boolean, nullable=False, default=True, server_default="true")
    actualizado_en = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class MarMarcacion(Base):
    __tablename__ = "mar_marcaciones"
    __table_args__ = (
        UniqueConstraint("tenant_id", "emp_code", "momento", "estado", name="uq_mar_marcacion"),
        Index("ix_mar_marcaciones_tenant_momento", "tenant_id", "momento"),
    )

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    emp_code = Column(String(MAX_CODIGO), nullable=False)
    momento = Column(DateTime(timezone=True), nullable=False)
    # 0 entrada · 1 salida · 2 salida a descanso · 3 regreso de descanso ·
    # 4 y 5 horas extra (se guardan, no se evalúan).
    estado = Column(String(1), nullable=False)
    recibida_en = Column(DateTime(timezone=True), server_default=func.now())


class MarFestivo(Base):
    __tablename__ = "mar_festivos"
    __table_args__ = (UniqueConstraint("tenant_id", "fecha", name="uq_mar_festivo"),)

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    fecha = Column(Date, nullable=False)
    nombre = Column(String(100), nullable=True)


class MarExcepcion(Base):
    """Vacaciones, incapacidad o permiso de UNA persona un día: no se espera su marcación."""
    __tablename__ = "mar_excepciones"
    __table_args__ = (UniqueConstraint("tenant_id", "emp_code", "fecha", name="uq_mar_excepcion"),)

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    emp_code = Column(String(MAX_CODIGO), nullable=False)
    fecha = Column(Date, nullable=False)
    motivo = Column(String(100), nullable=True)


class MarSincronizacion(Base):
    """
    Cada envío del script, incluidos los rechazados.

    El script corre en otro servidor y es la única forma de notar que dejó de
    correr: `GET /marcaciones/estado` lee esta tabla.
    """
    __tablename__ = "mar_sincronizaciones"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    creada_en = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    ok = Column(Boolean, nullable=False, default=True)
    error = Column(Text, nullable=True)
    empleados = Column(Integer, nullable=False, default=0)
    marcaciones_nuevas = Column(Integer, nullable=False, default=0)
    ultima_marcacion = Column(DateTime(timezone=True), nullable=True)


class MarJustificacion(Base):
    """
    El motivo de UNA novedad de UNA persona un día («Cita médica con soporte»).

    La clave es persona + día + tipo de novedad (`constants.NOVEDADES`), no el
    id de la novedad: las novedades no se guardan, se calculan. Si mañana
    cambia una tolerancia y la novedad desaparece, la justificación queda
    guardada y simplemente no se muestra; si vuelve a aparecer, reaparece con
    ella. Quién la escribió se guarda también con su nombre, para que el
    historial no cambie si esa persona se va del portal.
    """
    __tablename__ = "mar_justificaciones"
    __table_args__ = (UniqueConstraint("tenant_id", "emp_code", "fecha", "tipo", name="uq_mar_justificacion"),)

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    emp_code = Column(String(MAX_CODIGO), nullable=False)
    fecha = Column(Date, nullable=False)
    tipo = Column(String(30), nullable=False)
    texto = Column(String(MAX_JUSTIFICACION), nullable=False)
    autor_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    autor_nombre = Column(String(MAX_NOMBRE), nullable=False)
    creada_en = Column(DateTime(timezone=True), server_default=func.now())
    actualizada_en = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
