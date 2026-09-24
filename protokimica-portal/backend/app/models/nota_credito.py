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

**Hay dos ciclos, según quién la pida** (la cadena vive en
`modules/notas_credito/flujo.py`):

- **Un punto de venta**: la autoriza Contabilidad y la emite el punto. Es el
  ciclo de siempre y no cambió.
- **Ventas Institucionales**: pasa por Comercial y después por Contabilidad,
  que verifica ante la DIAN si la factura tiene saldo a favor; y si el motivo
  implica producto, antes que nadie la bodega confirma que llegó y en qué
  estado. La emite quien tenga la capacidad de registrar.

Las dos se cierran igual: cuando alguien registra el NÚMERO de la nota crédito
que se emitió. Ese paso es el que permite auditar la cadena completa y, sobre
todo, encontrar las aprobadas que nunca se ejecutaron — que en un correo son
invisibles.
"""
from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, Text, func,
)
from sqlalchemy.orm import relationship

from app.core.database import Base

# Los estados por los que pasa una solicitud. Se declaran aquí para que el
# router, el servicio y las pruebas miren el mismo sitio.
#
# `solicitada` es una ETAPA HISTÓRICA: era el turno en que Contabilidad
# autorizaba las del mostrador, un paso que ya no existe (ver
# `notas_credito/flujo.py`). No está en `ESTADOS` porque ninguna solicitud
# viva puede estar ahí, pero la constante se queda: `nc_historial` guarda esa
# etapa en las que sí pasaron por ella, y el historial es lo que se audita.
ESTADO_SOLICITADA = "solicitada"
ESTADO_APROBADA = "aprobada"
ESTADO_RECHAZADA = "rechazada"
ESTADO_APLICADA = "aplicada"

# ── Las etapas de la cadena institucional ───────────────────────────
#
# Una venta institucional no la autoriza Contabilidad de una: primero la
# bodega confirma que el producto llegó (solo si el motivo implica producto),
# después Comercial decide si la devolución procede, y al final Contabilidad
# verifica ante la DIAN que la factura tenga saldo a favor. Ver
# `modules/notas_credito/flujo.py`, que es donde vive la cadena.
#
# **El estado dice de quién es el turno.** Se escogió así, y no un campo
# `etapa` aparte, porque dos columnas que describen lo mismo terminan
# diciendo cosas distintas — y porque los cuatro estados de siempre siguen
# significando exactamente lo que significaban, así que las solicitudes que
# ya existen no se mueven de sitio.
ESTADO_EN_BODEGA = "en_bodega"
ESTADO_EN_COMERCIAL = "en_comercial"
ESTADO_EN_CONTABILIDAD = "en_contabilidad"

# Devuelta al solicitante para que corrija. NO es un rechazo: el rechazo
# cierra el caso y la devolución lo deja vivo en manos de quien lo pidió.
# Sin este estado, «corrígelo y vuelve a mandarlo» obliga a radicar otra
# desde cero: se gasta un consecutivo, se pierde por qué murió la primera y
# el mismo caso se cuenta dos veces en el informe.
ESTADO_DEVUELTA = "devuelta"

# La cancela QUIEN LA PIDIÓ, cuando al revisar resulta que no procede. Es
# distinto de que se la hayan rechazado y en el informe tiene que verse
# distinto: una que el vendedor retira no es un caso que la empresa negó.
ESTADO_CANCELADA = "cancelada"

ESTADOS = (
    ESTADO_EN_BODEGA, ESTADO_EN_COMERCIAL,
    ESTADO_EN_CONTABILIDAD, ESTADO_APROBADA, ESTADO_DEVUELTA,
    ESTADO_RECHAZADA, ESTADO_APLICADA, ESTADO_CANCELADA,
)

# Una rechazada, aplicada o cancelada no se vuelve a tocar: son finales.
# Una devuelta SÍ está abierta — está esperando a que el solicitante la
# corrija, que es trabajo pendiente como cualquier otro.
ESTADOS_ABIERTOS = (
    ESTADO_EN_BODEGA, ESTADO_EN_COMERCIAL,
    ESTADO_EN_CONTABILIDAD, ESTADO_APROBADA, ESTADO_DEVUELTA,
)


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

    # ¿Este motivo implica que vuelve producto físico?
    #
    # Va en el MOTIVO y no como una pregunta suelta del formulario porque es
    # una propiedad del motivo, no del caso: «devolución de mercancía» siempre
    # trae producto y «error al digitar el NIT» nunca. Preguntándolo cada vez,
    # la respuesta dependería de quién radica; aquí la define Contabilidad una
    # sola vez, desde el portal y sin desplegar.
    requiere_bodega = Column(Boolean, default=False, nullable=False)

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

    # NO hay producto a propósito. Una factura trae varios renglones, así que
    # un solo campo de producto miente más de lo que ayuda: o se llena con uno
    # de los tres que venían, o se deja vacío y estorba. Lo que sí identifica
    # el caso es la factura, y eso ya está arriba.

    # El valor de la factura. Opcional porque no siempre se sabe al pedirla,
    # pero es lo primero que mira quien autoriza.
    valor = Column(Numeric(14, 2), nullable=True)

    motivo_id = Column(Integer, ForeignKey("nc_motivos.id"), nullable=True)

    # A qué bodega entró el producto devuelto: «Guayabal» o «La 65» de
    # `core/bodegas.py`. Solo se llena cuando el motivo lo exige, y de ella
    # sale a quién le toca confirmar. Nula en todo lo que no mueve producto,
    # que es la mayoría.
    bodega = Column(String(40), nullable=True)

    # El relato de qué pasó, que es lo que hoy va en el cuerpo del correo.
    observaciones = Column(Text, nullable=False)

    # El soporte es opcional: exigirlo dejaría sin radicar a quien lo tiene en
    # papel o no lo tiene todavía.
    adjunto = Column(String(255), nullable=True)

    solicitado_por = Column(Integer, ForeignKey("users.id"), nullable=False)
    # Toda solicitud empieza por Comercial, venga del mostrador o de una
    # venta institucional. El router lo pone explícito con
    # `flujo.estado_inicial()`; esto es solo el respaldo del modelo.
    estado = Column(String(20), nullable=False, default=ESTADO_EN_COMERCIAL)

    # La firma que la dejó lista para emitir: Contabilidad en la rama del
    # punto de venta, y la verificación ante la DIAN en la institucional. Es
    # la ÚLTIMA firma, no todas — las intermedias viven en `nc_historial`,
    # porque una cadena de cuatro manos no cabe en tres columnas.
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
    historial = relationship(
        "HistorialNotaCredito", back_populates="solicitud",
        cascade="all, delete-orphan", order_by="HistorialNotaCredito.creado_en",
    )
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


class HistorialNotaCredito(Base):
    """
    Cada mano por la que pasó la solicitud.

    Con una sola firma bastaban tres columnas en la solicitud. Con una cadena
    de cuatro etapas —bodega, comercial, DIAN, emisión— y la posibilidad de
    devolverla para corregir, no: una solicitud puede pasar dos veces por la
    misma etapa, y eso no cabe en columnas. Es además lo que hace auditable la
    cadena, que es la razón de que el módulo exista.

    Se guarda el NOMBRE junto al id, como en los seguimientos de PQRS: el día
    que alguien se va de la empresa y su usuario se desactiva, el historial
    tiene que seguir diciendo quién aprobó.
    """
    __tablename__ = "nc_historial"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    solicitud_id = Column(
        Integer, ForeignKey("nc_solicitudes.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    # En qué etapa estaba cuando se actuó, y qué se hizo. La etapa se guarda
    # y no se deduce del estado siguiente: devolver desde Comercial y
    # devolver desde la DIAN dejan el mismo estado y no son lo mismo.
    etapa = Column(String(20), nullable=False)
    accion = Column(String(20), nullable=False)

    usuario_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    usuario_nombre = Column(String(150), nullable=True)
    comentario = Column(Text, nullable=True)
    creado_en = Column(DateTime(timezone=True), server_default=func.now())

    solicitud = relationship("SolicitudNotaCredito", back_populates="historial")
