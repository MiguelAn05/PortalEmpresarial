"""
Encuestas: plantillas, preguntas y respuestas.

Las preguntas se guardan como DATOS, no en código. Es lo que permite que
mañana Calidad necesite una encuesta de proveedores o de clima laboral sin
que haya que crear una tabla, escribir una migración y desplegar.

La encuesta de PQRS NO vive aquí: sigue en `pqrs_encuestas`, funcionando
como siempre y alimentando sus tres indicadores. El módulo la muestra junto
a estas mediante un adaptador (ver `modules/encuestas/origenes.py`). Migrarla
sería reescribir algo que ya funciona en producción, y no hace falta para
nada de lo que se necesita hoy.
"""
from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, Text,
    UniqueConstraint, func,
)
from sqlalchemy.orm import relationship

from app.core.database import Base

# Tipos de pregunta que el portal sabe pintar y resumir. Deliberadamente
# pocos: cada tipo nuevo obliga a soportarlo en el formulario público, en los
# reportes y en los indicadores.
TIPOS_PREGUNTA = {
    "escala",   # 1 a 5 — la calificación típica; es la que alimenta promedios
    "opcion",   # una de varias (ej. sí / parcialmente / no)
    "si_no",    # binaria; se resume como porcentaje de "sí"
    "texto",    # comentario abierto; no entra en ningún promedio
}


class Plantilla(Base):
    """Una encuesta: qué se pregunta y a quién se le pregunta."""
    __tablename__ = "enc_plantillas"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    nombre = Column(String(200), nullable=False)
    descripcion = Column(Text, nullable=True)

    # Va en la URL pública: /encuesta/<slug>. Se pide corto y estable, porque
    # termina impreso en un QR pegado en un punto de venta: cambiarlo después
    # deja los códigos ya impresos apuntando a nada.
    slug = Column(String(60), nullable=False, index=True)

    # Qué se está calificando: "vendedor", "punto_venta", "proveedor"... Sirve
    # para agrupar los reportes. Vacío = la encuesta no califica a nadie en
    # particular (clima laboral, por ejemplo).
    sujeto_tipo = Column(String(40), nullable=True)

    # La lista cerrada de qué se puede calificar, separada por "|".
    #
    # Existe por limpieza de datos, y no es un detalle menor: si el cliente
    # escribe a mano dónde lo atendieron, "Centro", "centro" y "Sede Centro"
    # entran como tres lugares distintos y el reporte por punto de venta deja
    # de servir. Eso no se arregla después: los datos ya entraron mal.
    #
    # Vacío = el sujeto llega por el enlace (?ref=&nombre=), que es lo más
    # limpio de todo porque el cliente no elige nada.
    sujetos = Column(Text, nullable=True)

    # Texto de agradecimiento al enviar. Cada encuesta cierra distinto.
    mensaje_final = Column(Text, nullable=True)

    activa = Column(Boolean, nullable=False, default=True, server_default="true")
    creado_en = Column(DateTime(timezone=True), server_default=func.now())

    preguntas = relationship(
        "Pregunta", back_populates="plantilla",
        cascade="all, delete-orphan", order_by="Pregunta.orden",
    )
    respuestas = relationship(
        "Respuesta", back_populates="plantilla", cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "slug", name="uq_plantilla_slug"),
    )


class Pregunta(Base):
    __tablename__ = "enc_preguntas"

    id = Column(Integer, primary_key=True, index=True)
    plantilla_id = Column(
        Integer, ForeignKey("enc_plantillas.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    texto = Column(Text, nullable=False)
    ayuda = Column(Text, nullable=True)
    tipo = Column(String(20), nullable=False, default="escala")

    # Las opciones de tipo="opcion", separadas por "|". Un texto y no una
    # tabla aparte: son tres o cuatro etiquetas que solo se leen completas.
    opciones = Column(Text, nullable=True)

    # Nombre estable para referirse a esta pregunta desde un indicador
    # automático ("calificacion_general"). El texto de la pregunta puede
    # reescribirse sin romper el indicador; la clave no.
    clave = Column(String(60), nullable=True)

    obligatoria = Column(Boolean, nullable=False, default=True, server_default="true")
    orden = Column(Integer, nullable=False, default=0, server_default="0")

    plantilla = relationship("Plantilla", back_populates="preguntas")
    items = relationship("RespuestaItem", back_populates="pregunta", cascade="all, delete-orphan")


class Respuesta(Base):
    """Una persona contestando una encuesta, una vez."""
    __tablename__ = "enc_respuestas"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    plantilla_id = Column(
        Integer, ForeignKey("enc_plantillas.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    # A quién califica. El nombre se guarda copiado a propósito: si mañana el
    # vendedor se va de la empresa, el reporte del año pasado tiene que seguir
    # diciendo a quién se calificó.
    sujeto_ref = Column(String(60), nullable=True, index=True)
    sujeto_nombre = Column(String(200), nullable=True)

    respondida_en = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    items = relationship(
        "RespuestaItem", back_populates="respuesta", cascade="all, delete-orphan",
    )
    plantilla = relationship("Plantilla", back_populates="respuestas")


class RespuestaItem(Base):
    """Lo que se contestó en una pregunta."""
    __tablename__ = "enc_items"

    id = Column(Integer, primary_key=True, index=True)
    respuesta_id = Column(
        Integer, ForeignKey("enc_respuestas.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    pregunta_id = Column(
        Integer, ForeignKey("enc_preguntas.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    # Se guardan por separado en vez de en un solo campo de texto: los
    # promedios y porcentajes se calculan en la base sin tener que convertir
    # texto a número en cada consulta.
    valor_numero = Column(Numeric(10, 2), nullable=True)   # escala
    valor_texto = Column(Text, nullable=True)              # texto y opción

    respuesta = relationship("Respuesta", back_populates="items")
    pregunta = relationship("Pregunta", back_populates="items")
