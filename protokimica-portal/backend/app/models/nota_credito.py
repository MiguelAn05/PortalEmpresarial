"""
Solicitudes de nota crédito.

Hoy esto se pide por correo: el punto de venta le escribe a Contabilidad
«solicitamos autorización para realizar nota crédito a la factura POS#141824»
y cuenta qué pasó. Funciona hasta que alguien pregunta cuántas notas crédito
se hicieron el mes pasado, o por qué, o si la que se aprobó llegó a existir.
Un correo no responde ninguna de esas tres.

**No es una PQRS.** Comparte el menú con ellas porque es donde la gente ya
entra, pero va en su propia tabla: una PQRS trae el plazo de la Ley 1755, la
encuesta al cliente al cerrarse y el cierre a cargo de Servicio al Cliente, y
nada de eso aplica a un trámite entre el almacén y Contabilidad. Mezclarlas
además metería estas solicitudes en los indicadores de quejas, que es donde
menos deben estar.

El ciclo es: la pide el punto de venta, la autoriza Contabilidad, y se cierra
cuando alguien registra el NÚMERO de la nota crédito que se emitió. Ese último
paso es el que permite auditar la cadena completa y, sobre todo, encontrar las
aprobadas que nunca se ejecutaron — que en un correo son invisibles.
"""
from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, Text, func,
)
from sqlalchemy.orm import relationship

from app.core.database import Base

# Los estados por los que pasa una solicitud. Se declaran aquí para que el
# router, el servicio y las pruebas miren el mismo sitio.
ESTADO_SOLICITADA = "solicitada"
ESTADO_APROBADA = "aprobada"
ESTADO_RECHAZADA = "rechazada"
ESTADO_APLICADA = "aplicada"

ESTADOS = (ESTADO_SOLICITADA, ESTADO_APROBADA, ESTADO_RECHAZADA, ESTADO_APLICADA)

# Una solicitud rechazada o ya aplicada no se vuelve a tocar: son finales.
ESTADOS_ABIERTOS = (ESTADO_SOLICITADA, ESTADO_APROBADA)


class MotivoNotaCredito(Base):
    """
    Por qué se pide la nota crédito.

    Va en TABLA y no en una constante de Python por lo mismo que los catálogos
    de Mejora: la lista la define Contabilidad, no TIC's, y agregar un motivo
    no puede exigir un despliegue. Aquí solo vive la semilla con la que
    arranca; a partir de ahí se administra desde el portal.

    Y va en lista cerrada, no en texto libre, porque es el campo que responde
    «¿por qué estamos haciendo tantas notas crédito?». Escrito a mano, seis
    meses después esa pregunta no tiene respuesta: nadie agrupa «error al
    digitar», «Error digitacion» y «se equivocaron tecleando».
    """
    __tablename__ = "nc_motivos"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    nombre = Column(String(150), nullable=False)
    activo = Column(Boolean, default=True, nullable=False)
    creado_en = Column(DateTime(timezone=True), server_default=func.now())

    solicitudes = relationship("SolicitudNotaCredito", back_populates="motivo")


class SolicitudNotaCredito(Base):
    __tablename__ = "nc_solicitudes"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    # NC-2026-0001. Sale del MÁXIMO y nunca de un count(): con un hueco en el
    # medio —alguien borró una— contar da un número que ya existe, y el commit
    # revienta por unicidad DESPUÉS de haber guardado. Ya mordió dos veces en
    # este portal (código de seguimiento y radicado de Calidad).
    codigo = Column(String(30), nullable=True, index=True)

    # De qué punto de venta o canal viene. Lista cerrada de core/canales.py:
    # escrito a mano, «Itagüí», «itagui» y «Almacén Itagüí» son tres sitios
    # distintos y el informe por almacén deja de servir.
    punto_venta = Column(String(100), nullable=False)

    # La factura sobre la que se pide la nota crédito, y la que la reemplaza
    # cuando el cliente volvió a comprar bien. La segunda es opcional: no
    # siempre hay factura nueva.
    factura_afectada = Column(String(60), nullable=False)
    factura_reemplaza = Column(String(60), nullable=True)

    # Opcionales: hay notas crédito de una factura completa, sin un producto
    # puntual que señalar. Cuando sí lo hay, sale del catálogo del ERP.
    producto_codigo = Column(String(60), nullable=True)
    producto_nombre = Column(String(300), nullable=True)

    # Cuánto se devuelve. Opcional porque no siempre se sabe al pedirla, pero
    # es lo primero que mira quien autoriza.
    valor = Column(Numeric(14, 2), nullable=True)

    motivo_id = Column(Integer, ForeignKey("nc_motivos.id"), nullable=True)

    # El relato de qué pasó, que es lo que hoy va en el cuerpo del correo.
    observaciones = Column(Text, nullable=False)

    # El soporte es opcional: exigirlo dejaría sin radicar a quien lo tiene en
    # papel o no lo tiene todavía.
    adjunto = Column(String(255), nullable=True)

    solicitado_por = Column(Integer, ForeignKey("users.id"), nullable=False)
    estado = Column(String(20), nullable=False, default=ESTADO_SOLICITADA)

    # La firma de Contabilidad.
    autorizado_por = Column(Integer, ForeignKey("users.id"), nullable=True)
    comentario_respuesta = Column(Text, nullable=True)
    fecha_respuesta = Column(DateTime(timezone=True), nullable=True)

    # Lo que cierra el ciclo: el número de la nota crédito que se emitió de
    # verdad. Sin esto, una solicitud aprobada y una ejecutada se ven igual.
    numero_nc = Column(String(60), nullable=True)
    aplicada_por = Column(Integer, ForeignKey("users.id"), nullable=True)
    fecha_aplicacion = Column(DateTime(timezone=True), nullable=True)

    creado_en = Column(DateTime(timezone=True), server_default=func.now())

    motivo = relationship("MotivoNotaCredito", back_populates="solicitudes")
    solicitante = relationship("User", foreign_keys=[solicitado_por])
    autorizador = relationship("User", foreign_keys=[autorizado_por])
    ejecutor = relationship("User", foreign_keys=[aplicada_por])

    # Los nombres a la mano, para que la pantalla no resuelva ids con otra
    # consulta. Mismo patrón que PQRSSeguimiento.usuario_nombre.
    @property
    def solicitante_nombre(self):
        return self.solicitante.nombre if self.solicitante else None

    @property
    def autorizador_nombre(self):
        return self.autorizador.nombre if self.autorizador else None

    @property
    def ejecutor_nombre(self):
        return self.ejecutor.nombre if self.ejecutor else None

    @property
    def motivo_nombre(self):
        return self.motivo.nombre if self.motivo else None
