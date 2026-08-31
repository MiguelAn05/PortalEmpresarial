"""
Oportunidades de Mejora (OMP).

Una OMP es lo que convierte un número malo en trabajo con responsable y
fecha. Nace casi siempre de un indicador que no cumplió su meta, y no se
cierra por decreto: se cierra comparando el indicador DESPUÉS de la acción
contra el que la disparó. Ese es el punto del módulo — el portal ya guarda
las mediciones, así que la eficacia se demuestra con dato, no con acta.

El ciclo es el de ISO 9001 y cada paso pide lo suyo:

    abierta → analisis → ejecucion → verificacion → cerrada
                 ↑                        ↑
          causa raíz              ¿mejoró el indicador?
          obligatoria             eficaz / no eficaz

Si la verificación dice que no fue eficaz, la OMP NO se cierra: vuelve a
análisis. Cerrar en falso es justo lo que busca una auditoría.
"""
from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, Text, func,
)
from sqlalchemy.orm import relationship

from app.core.database import Base

# Los estados del ciclo, en orden. El orden importa: se usa para saber si un
# cambio de estado avanza o retrocede.
ESTADOS = ["abierta", "analisis", "ejecucion", "verificacion", "cerrada"]

# Una OMP que se descarta no es una que se cierra: no cumplió el ciclo y no
# puede contarse como mejora lograda. Va aparte a propósito.
ESTADO_DESCARTADA = "descartada"

ORIGENES = ["indicador", "pqrs", "auditoria", "sugerencia", "otro"]


class Oportunidad(Base):
    """La ficha de la OMP: de dónde salió, qué se va a hacer y si funcionó."""
    __tablename__ = "omp_oportunidades"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    # OMP-2026-0001. Se saca del MÁXIMO existente, nunca de un count():
    # contar da un número ya usado en cuanto alguien borra una del medio.
    codigo = Column(String(20), nullable=True, unique=True, index=True)

    titulo = Column(String(200), nullable=False)
    descripcion = Column(Text, nullable=True)

    # De dónde nació. Es un campo y no una tabla por fuente para que mañana
    # una auditoría o una PQRS reincidente abran una OMP sin migración.
    origen = Column(String(20), nullable=False, default="indicador")

    # El indicador que la disparó y el periodo exacto de la medición que
    # falló: sin el periodo no se sabe contra qué comparar al verificar.
    indicador_id = Column(
        Integer, ForeignKey("ind_indicadores.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    periodo_anio = Column(Integer, nullable=True)
    periodo_mes = Column(Integer, nullable=True)
    # El valor con el que se abrió, congelado. Si alguien corrige la medición
    # después, la comparación de eficacia seguiría teniendo sentido.
    valor_inicial = Column(Numeric(16, 4), nullable=True)
    meta_esperada = Column(Numeric(16, 4), nullable=True)

    pqrs_id = Column(
        Integer, ForeignKey("pqrs_solicitudes.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    area = Column(String(100), nullable=True, index=True)
    responsable_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    estado = Column(String(20), nullable=False, default="abierta", index=True)
    prioridad = Column(String(20), nullable=False, default="media")
    fecha_limite = Column(DateTime(timezone=True), nullable=True)

    # Sin causa raíz no se pasa a ejecución: sin ella las acciones atacan el
    # síntoma y el indicador vuelve a caer el mes siguiente.
    causa_raiz = Column(Text, nullable=True)

    # Resultado de la verificación. `eficaz` en None significa "todavía no se
    # ha verificado", que es distinto de "no funcionó".
    eficaz = Column(Boolean, nullable=True)
    valor_verificado = Column(Numeric(16, 4), nullable=True)
    nota_eficacia = Column(Text, nullable=True)
    fecha_cierre = Column(DateTime(timezone=True), nullable=True)

    creado_por = Column(Integer, ForeignKey("users.id"), nullable=True)
    creado_en = Column(DateTime(timezone=True), server_default=func.now())

    indicador = relationship("Indicador", foreign_keys=[indicador_id])
    responsable = relationship("User", foreign_keys=[responsable_id])
    autor = relationship("User", foreign_keys=[creado_por])
    acciones = relationship(
        "AccionMejora", back_populates="oportunidad",
        cascade="all, delete-orphan", order_by="AccionMejora.id",
    )

    @property
    def responsable_nombre(self):
        return self.responsable.nombre if self.responsable else None

    @property
    def autor_nombre(self):
        """Quién la abrió. En el Excel que usan hoy es una columna: quien
        levanta una OMP responde por ella aunque la ejecute otra área."""
        return self.autor.nombre if self.autor else None

    @property
    def indicador_nombre(self):
        return self.indicador.nombre if self.indicador else None

    @property
    def total_acciones(self) -> int:
        return len(self.acciones)

    @property
    def acciones_completadas(self) -> int:
        return sum(1 for a in self.acciones if a.completada)

    @property
    def avance_pct(self) -> float:
        """Cuánto del plan está hecho. Sin acciones no hay avance que mostrar."""
        if not self.acciones:
            return 0.0
        return round((self.acciones_completadas / len(self.acciones)) * 100, 1)

    @property
    def esta_cerrada(self) -> bool:
        return self.estado in ("cerrada", ESTADO_DESCARTADA)


class AccionMejora(Base):
    """
    Una acción concreta del plan: qué se hace, quién y para cuándo.

    Viven aquí y no como tareas de Master Planner porque una OMP tiene dos o
    tres acciones cortas; colgarlas del planeador obligaría a inventar un
    proyecto contenedor y llenaría el Gantt de ruido.
    """
    __tablename__ = "omp_acciones"

    id = Column(Integer, primary_key=True, index=True)
    omp_id = Column(
        Integer, ForeignKey("omp_oportunidades.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    descripcion = Column(String(300), nullable=False)
    responsable_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    fecha_limite = Column(DateTime(timezone=True), nullable=True)

    completada = Column(Boolean, nullable=False, default=False, server_default="false")
    fecha_completada = Column(DateTime(timezone=True), nullable=True)
    evidencia = Column(String(255), nullable=True)

    creado_en = Column(DateTime(timezone=True), server_default=func.now())

    oportunidad = relationship("Oportunidad", back_populates="acciones")
    responsable = relationship("User", foreign_keys=[responsable_id])

    @property
    def responsable_nombre(self):
        return self.responsable.nombre if self.responsable else None
