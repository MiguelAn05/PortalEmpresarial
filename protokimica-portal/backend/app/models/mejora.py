"""
Oportunidades de Mejora (OMP) — el formato RCN-F-13 del SGC.

Este módulo reemplaza el Excel `REPORTE PLAN DE ACCIÓN - OMP` que hoy lleva
cada proceso por separado, sin perder ninguna de sus 23 columnas. El proceso
pasa a ser un campo: un solo registro para toda la empresa en vez de
diecisiete archivos que nadie puede cruzar.

Lo que el portal agrega sobre el Excel es lo que hace que el registro sirva
para una auditoría en vez de ser una lista de tareas con otro nombre:

    abierta → analisis → ejecucion → verificacion → cerrada
                 ↑                        ↑
        causa raíz (OMP/AC)        ¿mejoró el indicador?
        beneficio (AM)             eficaz / no eficaz

Si la verificación dice que no fue eficaz, la OMP NO se cierra: vuelve a
análisis. Cerrar en falso es justo lo que busca una auditoría.

**El tratamiento decide qué campos aplican** (§5 del formato): una Acción
Correctiva pide corrección, una Acción de Mejora pide beneficio, y solo
OMP y AC piden análisis de causas. Esa regla se resuelve por el CÓDIGO del
tratamiento, nunca por su nombre — el histórico ya trae el mismo tratamiento
escrito de tres formas distintas.
"""
from sqlalchemy import (
    Boolean, Column, Date, DateTime, ForeignKey, Integer, Numeric, String,
    Text, UniqueConstraint, func,
)
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.modules.mejora.catalogos import (
    TRATAMIENTO_AC, TRATAMIENTO_AM, TRATAMIENTOS_CON_CAUSA,
)

# Los estados del ciclo, en orden. El orden importa: se usa para saber si un
# cambio de estado avanza o retrocede.
ESTADOS = ["abierta", "analisis", "ejecucion", "verificacion", "cerrada"]

# Una OMP que se descarta no es una que se cierra: no cumplió el ciclo y no
# puede contarse como mejora lograda. Va aparte a propósito.
ESTADO_DESCARTADA = "descartada"

ORIGENES = ["indicador", "pqrs", "auditoria", "sugerencia", "otro"]

# El Excel solo conoce «Abierto» y «Cerrado». El ciclo del portal es más
# fino, así que al exportar se colapsa a esos dos — sin perder el estado
# real, que sigue guardado.
ESTADO_EXPORTADO = {
    "abierta": "Abierto",
    "analisis": "Abierto",
    "ejecucion": "Abierto",
    "verificacion": "Abierto",
    "cerrada": "Cerrado",
    ESTADO_DESCARTADA: "Cerrado",
}

# Riesgo u oportunidad (columna K). No está en la hoja `Listado` del Excel
# pero es una lista cerrada de hecho, así que va como enum y no como
# catálogo editable: cambiarla no sería parametrizar, sería cambiar la norma.
CLASIFICACIONES = ["riesgo", "oportunidad"]

# Estados de una tarea del plan de acción. El Excel no los tiene —ahí el
# plan es un textarea— pero sin ellos no hay avance que calcular.
ESTADOS_ACCION = ["pendiente", "en_curso", "cumplida"]

# Los dos papeles de las columnas E y F del formato.
TIPOS_RESPONSABLE = ["resolucion", "seguimiento"]


class ItemCatalogo(Base):
    """
    Un valor de los catálogos del formato: proceso, fuente o tratamiento.

    Una sola tabla con discriminador en vez de tres: las tres se administran
    igual, se piden juntas al abrir el formulario y ninguna tiene campos
    propios. Tres tablas idénticas serían tres migraciones y tres pantallas
    de Admin para el mismo trabajo.

    `codigo` solo lo usan los tratamientos (`OMP`/`AC`/`AM`), que es donde
    hay lógica colgando. Los procesos y las fuentes son rótulos.
    """
    __tablename__ = "omp_catalogos"
    __table_args__ = (
        UniqueConstraint("tenant_id", "tipo", "nombre", name="uq_omp_catalogo"),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    tipo = Column(String(20), nullable=False, index=True)   # proceso|fuente|tratamiento
    codigo = Column(String(20), nullable=True)
    nombre = Column(String(120), nullable=False)
    orden = Column(Integer, nullable=False, default=0, server_default="0")

    # Un catálogo no se borra, se desactiva: las OMP viejas lo siguen
    # apuntando y el reporte tiene que poder decir de qué proceso eran.
    activo = Column(Boolean, nullable=False, default=True, server_default="true")


class Oportunidad(Base):
    """La ficha de la OMP: de dónde salió, qué se va a hacer y si funcionó."""
    __tablename__ = "omp_oportunidades"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    # OMP-2026-0001. Se saca del MÁXIMO existente, nunca de un count():
    # contar da un número ya usado en cuanto alguien borra una del medio.
    codigo = Column(String(20), nullable=True, unique=True, index=True)

    # El número que el SGC conoce: 1, 2, 3… DENTRO de cada proceso, porque
    # hasta hoy cada proceso llevaba su propio archivo y los auditores citan
    # «la 6 de TIC's». Se guarda en vez de renumerar al exportar: si se
    # recalculara, descartar una fila correría todas las siguientes y una
    # referencia de auditoría dejaría de apuntar a lo mismo.
    consecutivo = Column(Integer, nullable=True)

    titulo = Column(String(200), nullable=False)
    descripcion = Column(Text, nullable=True)

    # La fecha que va en el formato. Es distinta de `creado_en`: al importar
    # el histórico, la acción se registró en 2022 aunque la fila se creara
    # hoy, y el reporte tiene que decir 2022.
    fecha_registro = Column(Date, nullable=True)

    # De dónde nació DENTRO del portal: a qué registro está amarrada. No es
    # lo mismo que la fuente del SGC —«auditoría interna» y «externa» no se
    # distinguen aquí— pero casi siempre la propone.
    origen = Column(String(20), nullable=False, default="indicador")

    # ── Los catálogos del formato ────────────────────────────────────
    proceso_id = Column(
        Integer, ForeignKey("omp_catalogos.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    fuente_id = Column(
        Integer, ForeignKey("omp_catalogos.id", ondelete="SET NULL"), nullable=True,
    )
    tratamiento_id = Column(
        Integer, ForeignKey("omp_catalogos.id", ondelete="SET NULL"), nullable=True,
    )

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

    estado = Column(String(20), nullable=False, default="abierta", index=True)
    prioridad = Column(String(20), nullable=False, default="media")
    fecha_limite = Column(DateTime(timezone=True), nullable=True)

    # ¿Riesgo u oportunidad? (columna K)
    clasificacion = Column(String(20), nullable=True)

    # ¿Existen hallazgos similares? (columna J). Cuando es verdadero se
    # esperan OMP relacionadas en `omp_relaciones`.
    hallazgos_similares = Column(
        Boolean, nullable=False, default=False, server_default="false",
    )

    # ── Análisis de causas, en 6M (columna L) ────────────────────────
    # Siete campos en vez de un textarea: el Excel ya venía escribiendo
    # «Método: … / Mano de Obra: …» a mano dentro de la celda, así que la
    # estructura existe, solo que sin que nada la garantice. Al exportar se
    # reconstruye el bloque de texto con estas mismas etiquetas y en este
    # orden, para que el formato impreso no cambie.
    causa_efecto = Column(Text, nullable=True)
    causa_metodo = Column(Text, nullable=True)
    causa_mano_obra = Column(Text, nullable=True)
    causa_maquinaria = Column(Text, nullable=True)
    causa_material = Column(Text, nullable=True)
    causa_medidas = Column(Text, nullable=True)
    causa_medio_ambiente = Column(Text, nullable=True)

    # Sin causa raíz no se pasa a ejecución: sin ella las acciones atacan el
    # síntoma y el indicador vuelve a caer el mes siguiente. Aplica a OMP y
    # a AC; una Acción de Mejora no tiene causa, tiene beneficio.
    causa_raiz = Column(Text, nullable=True)

    # Lo que se hace para tapar el hueco YA, antes de atacar la causa. Solo
    # aplica a Acción Correctiva (columna N).
    correccion = Column(Text, nullable=True)

    # Por qué vale la pena. Solo aplica a Acción de Mejora (columna O).
    beneficio_mejora = Column(Text, nullable=True)

    # Qué se va a hacer para comprobar que sirvió, escrito ANTES (columna Q).
    # Es distinto del resultado: esto es el plan de verificación, `eficaz`
    # es lo que pasó. Ponerlo por adelantado evita el clásico «se verificó
    # revisando que ya no se presentó», que no dice cómo se revisó.
    verificacion_planeada = Column(Text, nullable=True)

    # ── Resultado de la verificación ─────────────────────────────────
    # `eficaz` en None significa «todavía no se ha verificado», que es
    # distinto de «no funcionó».
    eficaz = Column(Boolean, nullable=True)
    valor_verificado = Column(Numeric(16, 4), nullable=True)
    nota_eficacia = Column(Text, nullable=True)
    fecha_cierre = Column(DateTime(timezone=True), nullable=True)
    # Lo que el Excel metía dentro de la celda de la fecha de cierre: el
    # comentario con el que el SGC dio por cerrada la acción. Separado,
    # porque una fecha con texto adentro no se puede ordenar ni filtrar.
    nota_cierre = Column(Text, nullable=True)

    # ── Validación del SGC ───────────────────────────────────────────
    # Cerrar no es solo llenar la fecha: los cierres reales del formato
    # dicen «se validó con el SGC y se puede dar por cerrada». Es un paso de
    # aprobación con nombre y fecha, no un campo de texto — si no queda
    # quién lo aprobó, vuelve a ser el campo de texto que ya existía.
    validado_sgc_por = Column(Integer, ForeignKey("users.id"), nullable=True)
    validado_sgc_en = Column(DateTime(timezone=True), nullable=True)
    nota_sgc = Column(Text, nullable=True)

    # Quien reportó el hallazgo. Se guarda el usuario cuando lo hay y el
    # texto cuando no: el histórico trae nombres con el cargo entre
    # paréntesis y gente que ya no trabaja aquí, y perder eso al importar
    # sería perder de quién salió cada acción.
    reportado_por_texto = Column(String(150), nullable=True)
    creado_por = Column(Integer, ForeignKey("users.id"), nullable=True)
    creado_en = Column(DateTime(timezone=True), server_default=func.now())

    # Marca del importador: la fila entró pero algo no se pudo interpretar
    # (una fecha que decía «Agosto de 2022», seguimientos sin fecha al
    # inicio). Se importa igual y se marca, en vez de perder el texto.
    requiere_revision = Column(
        Boolean, nullable=False, default=False, server_default="false",
    )

    indicador = relationship("Indicador", foreign_keys=[indicador_id])
    autor = relationship("User", foreign_keys=[creado_por])
    validador_sgc = relationship("User", foreign_keys=[validado_sgc_por])

    proceso = relationship("ItemCatalogo", foreign_keys=[proceso_id])
    fuente = relationship("ItemCatalogo", foreign_keys=[fuente_id])
    tratamiento = relationship("ItemCatalogo", foreign_keys=[tratamiento_id])

    acciones = relationship(
        "AccionMejora", back_populates="oportunidad",
        cascade="all, delete-orphan", order_by="AccionMejora.orden, AccionMejora.id",
    )
    seguimientos = relationship(
        "SeguimientoMejora", back_populates="oportunidad",
        cascade="all, delete-orphan",
        order_by="SeguimientoMejora.fecha, SeguimientoMejora.id",
    )
    responsables = relationship(
        "ResponsableMejora", back_populates="oportunidad",
        cascade="all, delete-orphan", order_by="ResponsableMejora.id",
    )

    # ── Lo que se muestra ya resuelto ────────────────────────────────

    @property
    def autor_nombre(self):
        """Quién la abrió. En el formato es la columna C: quien levanta una
        OMP responde por ella aunque la ejecute otro proceso."""
        if self.autor:
            return self.autor.nombre
        return self.reportado_por_texto

    @property
    def indicador_nombre(self):
        return self.indicador.nombre if self.indicador else None

    @property
    def proceso_nombre(self):
        return self.proceso.nombre if self.proceso else None

    @property
    def fuente_nombre(self):
        return self.fuente.nombre if self.fuente else None

    @property
    def tratamiento_nombre(self):
        return self.tratamiento.nombre if self.tratamiento else None

    @property
    def tratamiento_codigo(self):
        """`OMP`, `AC` o `AM`. Es la llave de la que cuelga qué campos
        aplican; el nombre puede renombrarse desde Admin, el código no."""
        return self.tratamiento.codigo if self.tratamiento else None

    @property
    def validado_sgc_nombre(self):
        return self.validador_sgc.nombre if self.validador_sgc else None

    @property
    def pide_causa(self) -> bool:
        """
        ¿Esta acción tiene que explicar por qué pasó?

        Sí para OMP y AC. Una Acción de Mejora no corrige nada —nadie
        falló— así que exigirle causa raíz obligaba a escribir «no aplica»
        para poder avanzar, que es como se le enseña a la gente a mentirle a
        un formulario. Sin tratamiento elegido todavía se pide, que es el
        comportamiento que el módulo tenía antes.
        """
        codigo = self.tratamiento_codigo
        return codigo is None or codigo in TRATAMIENTOS_CON_CAUSA

    @property
    def pide_correccion(self) -> bool:
        return self.tratamiento_codigo == TRATAMIENTO_AC

    @property
    def pide_beneficio(self) -> bool:
        return self.tratamiento_codigo == TRATAMIENTO_AM

    @property
    def responsables_resolucion(self):
        return [r for r in self.responsables if r.tipo == "resolucion"]

    @property
    def responsables_seguimiento(self):
        return [r for r in self.responsables if r.tipo == "seguimiento"]

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
    def total_seguimientos(self) -> int:
        return len(self.seguimientos)

    @property
    def esta_cerrada(self) -> bool:
        return self.estado in ("cerrada", ESTADO_DESCARTADA)

    @property
    def estado_formato(self) -> str:
        """Cómo se rotula en el .xlsx del SGC, que solo conoce dos estados."""
        return ESTADO_EXPORTADO.get(self.estado, "Abierto")


class ResponsableMejora(Base):
    """
    Quién resuelve el hallazgo y quién le hace seguimiento (columnas E y F).

    Son varios a propósito: en el Excel van separados por saltos de línea
    dentro de la misma celda, y el seguimiento a veces lo lleva un comité
    entero. Por eso se admite `nombre_texto` sin usuario — un «Comité de
    TIC's» no tiene correo ni entra al portal, pero es quien responde.
    """
    __tablename__ = "omp_responsables"

    id = Column(Integer, primary_key=True, index=True)
    omp_id = Column(
        Integer, ForeignKey("omp_oportunidades.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    tipo = Column(String(20), nullable=False)   # resolucion | seguimiento
    usuario_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    # Para comités y para gente que ya no es usuario del portal.
    nombre_texto = Column(String(150), nullable=True)

    oportunidad = relationship("Oportunidad", back_populates="responsables")
    usuario = relationship("User", foreign_keys=[usuario_id])

    @property
    def nombre(self):
        return self.usuario.nombre if self.usuario else self.nombre_texto


class AccionMejora(Base):
    """
    Una tarea concreta del plan de acción (columna P): qué se hace, quién y
    para cuándo.

    En el Excel esto es un textarea con líneas numeradas, y por eso hoy es
    imposible saber cuánto lleva una acción: el avance porcentual solo
    existe si las tareas son filas. Al exportar se serializan de vuelta como
    `N. tarea / responsable / fecha`, una por línea.

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

    # El número que la tarea lleva en el plan. El Excel las numera a mano y
    # el orden importa: unas dependen de otras.
    orden = Column(Integer, nullable=False, default=0, server_default="0")

    descripcion = Column(String(300), nullable=False)
    responsable_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    fecha_limite = Column(DateTime(timezone=True), nullable=True)

    # Tres estados y no un booleano: «en curso» es la respuesta honesta a
    # «¿ya?» durante la mayor parte de la vida de una tarea, y sin ella la
    # gente marca cumplido antes de tiempo para que el avance se mueva.
    estado = Column(
        String(20), nullable=False, default="pendiente", server_default="pendiente",
    )
    fecha_completada = Column(DateTime(timezone=True), nullable=True)
    evidencia = Column(String(255), nullable=True)

    creado_en = Column(DateTime(timezone=True), server_default=func.now())

    oportunidad = relationship("Oportunidad", back_populates="acciones")
    responsable = relationship("User", foreign_keys=[responsable_id])

    @property
    def responsable_nombre(self):
        return self.responsable.nombre if self.responsable else None

    @property
    def completada(self) -> bool:
        """Derivado del estado, no un campo aparte: dos columnas que dicen
        lo mismo terminan diciendo cosas distintas."""
        return self.estado == "cumplida"


class SeguimientoMejora(Base):
    """
    Una entrada del seguimiento (columnas S, T y U del Excel).

    Son tres columnas para lo mismo: el formato se quedó sin espacio y
    fueron agregando `SEGUIMIENTO 2` y `SEGUIMIENTO 3`, con hasta veinticinco
    entradas concatenadas dentro de una sola celda de seis mil caracteres.
    Aquí es una fila por entrada, que es lo que siempre fue.

    Al exportar se reparten cronológicamente entre S, T y U para no romperle
    el formato al SGC.
    """
    __tablename__ = "omp_seguimientos"

    id = Column(Integer, primary_key=True, index=True)
    omp_id = Column(
        Integer, ForeignKey("omp_oportunidades.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    fecha = Column(Date, nullable=False)
    autor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    # El histórico trae el autor escrito al final de la celda y en
    # mayúsculas; conservarlo es la única forma de saber quién hizo el
    # seguimiento de 2022.
    autor_texto = Column(String(150), nullable=True)

    contenido = Column(Text, nullable=False)
    adjunto = Column(String(255), nullable=True)

    # El importador no pudo separar la fecha del texto y metió el bloque
    # entero. Se marca para que alguien lo revise, en vez de perderlo.
    requiere_revision = Column(
        Boolean, nullable=False, default=False, server_default="false",
    )

    creado_en = Column(DateTime(timezone=True), server_default=func.now())

    oportunidad = relationship("Oportunidad", back_populates="seguimientos")
    autor = relationship("User", foreign_keys=[autor_id])

    @property
    def autor_nombre(self):
        return self.autor.nombre if self.autor else self.autor_texto


class RelacionMejora(Base):
    """
    «¿Existen hallazgos similares?» (columna J) respondido con nombres.

    En el Excel es un Sí/No que no lleva a ninguna parte: dice que hay otros
    casos pero no cuáles, así que nadie puede revisar si ya se intentó algo
    parecido. Aquí el Sí apunta a las OMP concretas.
    """
    __tablename__ = "omp_relaciones"
    __table_args__ = (
        UniqueConstraint("omp_id", "relacionada_id", name="uq_omp_relacion"),
    )

    id = Column(Integer, primary_key=True, index=True)
    omp_id = Column(
        Integer, ForeignKey("omp_oportunidades.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    relacionada_id = Column(
        Integer, ForeignKey("omp_oportunidades.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    creado_en = Column(DateTime(timezone=True), server_default=func.now())


class CambioMejora(Base):
    """
    Quién cambió qué y cuándo: la trazabilidad que el Excel no tiene.

    Mismo patrón que `mp_historial` de Master Planner: los valores se
    guardan como texto ya resuelto —el nombre del responsable, no su id—
    para que el historial siga siendo legible aunque después se desactive un
    usuario o se renombre un catálogo. Es lo que permite responder «¿por qué
    esta acción se aplazó tres veces?» sin depender de la memoria de nadie.
    """
    __tablename__ = "omp_historial"

    id = Column(Integer, primary_key=True, index=True)
    omp_id = Column(
        Integer, ForeignKey("omp_oportunidades.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    campo = Column(String(50), nullable=False)
    valor_anterior = Column(Text, nullable=True)
    valor_nuevo = Column(Text, nullable=True)

    usuario_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    fecha = Column(DateTime(timezone=True), server_default=func.now())

    usuario = relationship("User")

    @property
    def usuario_nombre(self):
        return self.usuario.nombre if self.usuario else None
