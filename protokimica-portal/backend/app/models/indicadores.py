"""
Modelos del módulo de Indicadores.

Un Indicador es la DEFINICIÓN (qué se mide, con qué fórmula, cuál es la meta)
y una Medicion es el VALOR de ese indicador en un mes concreto. Separarlos es
lo que permite ver tendencia, comparar periodos y calcular acumulados.

Decisión central: los indicadores de porcentaje guardan numerador y
denominador, no el porcentaje ya calculado. Sin eso, el acumulado trimestral
sería el promedio de los porcentajes mensuales, que es aritméticamente
incorrecto (2/2 y 50/100 no dan 75%, dan 51%).
"""
from sqlalchemy import (
    Boolean, Column, Integer, String, Text, DateTime, ForeignKey, Numeric,
    UniqueConstraint, func,
)
from sqlalchemy.orm import relationship

from app.core.database import Base

# Cómo se obtiene el valor de cada periodo.
#   automatico → lo calcula el sistema desde PQRS o Master Planner
#   valor      → alguien digita un número
#   razon      → alguien digita numerador y denominador
TIPOS_CAPTURA = {"automatico", "valor", "razon"}

# Qué significa el número, y de paso cómo se formatea y se acumula.
UNIDADES = {"porcentaje", "moneda", "dias", "cantidad", "razon"}

# Si el indicador mejora subiendo (satisfacción) o bajando (días de respuesta).
DIRECCIONES = {"arriba", "abajo"}


class Indicador(Base):
    """La ficha del indicador: qué mide, cómo se calcula y contra qué se juzga."""
    __tablename__ = "ind_indicadores"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    nombre = Column(String(200), nullable=False)
    descripcion = Column(Text, nullable=True)       # qué mide, en una frase
    formula_texto = Column(Text, nullable=True)     # la fórmula tal como la escribe Calidad

    unidad = Column(String(20), nullable=False, default="porcentaje")
    tipo_captura = Column(String(20), nullable=False, default="valor")
    # Solo para tipo_captura='automatico': clave del calculador registrado.
    fuente_automatica = Column(String(60), nullable=True)

    # Etiquetas de los dos números cuando se captura como razón, para que el
    # formulario diga "PQRS cerradas a tiempo" y no "numerador".
    etiqueta_numerador = Column(String(120), nullable=True)
    etiqueta_denominador = Column(String(120), nullable=True)

    area = Column(String(100), nullable=True)
    responsable_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    meta = Column(Numeric(14, 2), nullable=True)
    direccion = Column(String(10), nullable=False, default="arriba")
    # Dos cortes que definen el semáforo. Se interpretan según `direccion`:
    # con "arriba", verde es >= umbral_verde; con "abajo", verde es <=.
    umbral_verde = Column(Numeric(14, 2), nullable=True)
    umbral_amarillo = Column(Numeric(14, 2), nullable=True)

    requiere_evidencia = Column(Boolean, nullable=False, default=False, server_default="false")
    activo = Column(Boolean, nullable=False, default=True, server_default="true")
    orden = Column(Integer, nullable=False, default=0, server_default="0")

    creado_en = Column(DateTime(timezone=True), server_default=func.now())

    responsable = relationship("User", foreign_keys=[responsable_id])
    mediciones = relationship(
        "Medicion", back_populates="indicador",
        cascade="all, delete-orphan", order_by="Medicion.anio, Medicion.mes",
    )

    @property
    def responsable_nombre(self):
        return self.responsable.nombre if self.responsable else None

    @property
    def es_automatico(self) -> bool:
        return self.tipo_captura == "automatico"

    @property
    def modo_acumulado(self) -> str:
        """
        Cómo se combinan varios meses en un trimestre o un año.

        - razon:    suma numeradores y denominadores, luego divide. Es el único
                    correcto para porcentajes.
        - suma:     dinero y conteos se suman.
        - promedio: para valores que no son ni razón ni acumulables (días
                    promedio, calificaciones). Es una aproximación y así se
                    advierte en la interfaz.
        """
        if self.tipo_captura == "razon" or self.unidad == "porcentaje":
            return "razon"
        if self.unidad in ("moneda", "cantidad"):
            return "suma"
        return "promedio"


class Medicion(Base):
    """El valor de un indicador en un mes. Un registro por indicador y mes."""
    __tablename__ = "ind_mediciones"

    id = Column(Integer, primary_key=True, index=True)
    indicador_id = Column(
        Integer, ForeignKey("ind_indicadores.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    anio = Column(Integer, nullable=False)
    mes = Column(Integer, nullable=False)   # 1-12

    # `valor` siempre viene resuelto, incluso en los de tipo razón, para no
    # tener que recalcularlo en cada consulta del tablero.
    valor = Column(Numeric(16, 4), nullable=True)
    numerador = Column(Numeric(16, 4), nullable=True)
    denominador = Column(Numeric(16, 4), nullable=True)

    observacion = Column(Text, nullable=True)
    evidencia = Column(String(255), nullable=True)

    registrado_por = Column(Integer, ForeignKey("users.id"), nullable=True)
    registrado_en = Column(DateTime(timezone=True), server_default=func.now())

    # Costura para un futuro flujo de aprobación: hoy nadie las escribe, pero
    # existir desde el inicio evita una migración el día que se pida validar
    # los valores antes de publicarlos.
    validado_por = Column(Integer, ForeignKey("users.id"), nullable=True)
    validado_en = Column(DateTime(timezone=True), nullable=True)

    indicador = relationship("Indicador", back_populates="mediciones")
    registrador = relationship("User", foreign_keys=[registrado_por])
    validador = relationship("User", foreign_keys=[validado_por])

    __table_args__ = (
        UniqueConstraint("indicador_id", "anio", "mes", name="uq_medicion_periodo"),
    )

    @property
    def registrado_por_nombre(self):
        return self.registrador.nombre if self.registrador else None

    @property
    def validado_por_nombre(self):
        return self.validador.nombre if self.validador else None

    @property
    def periodo(self) -> str:
        return f"{self.anio}-{self.mes:02d}"


class HistorialMedicion(Base):
    """
    Quién cambió el valor de una medición y de cuánto a cuánto. Mismo criterio
    que en Master Planner: un número que se reporta a gerencia no puede
    cambiar sin dejar rastro.
    """
    __tablename__ = "ind_historial"

    id = Column(Integer, primary_key=True, index=True)
    indicador_id = Column(
        Integer, ForeignKey("ind_indicadores.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    anio = Column(Integer, nullable=False)
    mes = Column(Integer, nullable=False)

    valor_anterior = Column(Numeric(16, 4), nullable=True)
    valor_nuevo = Column(Numeric(16, 4), nullable=True)
    motivo = Column(Text, nullable=True)

    usuario_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    fecha = Column(DateTime(timezone=True), server_default=func.now())

    usuario = relationship("User")

    @property
    def usuario_nombre(self):
        return self.usuario.nombre if self.usuario else None
