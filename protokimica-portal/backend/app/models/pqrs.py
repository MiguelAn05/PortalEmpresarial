from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func,
)
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.core.dias_habiles import contar_habiles, limite_en_habiles
from app.core.fechas import con_zona

# Regla de negocio: un área no puede tener una PQRS más de 3 días hábiles.
# Aplica a TODAS, también a Servicio al Cliente, y el conteo arranca de cero
# cada vez que el caso llega a un área —incluida la que firma una
# autorización—. Ver `modules/pqrs/tiempo_en_area.py`.
MAX_DIAS_HABILES_EN_AREA = 3

# Atados a `ASOCIADO_*` de `frontend/src/modules/pqrs/constants.js`.
MAX_CODIGO_ASOCIADO = 20
MAX_NOMBRE_ASOCIADO = 150
MAX_GRUPO_ASOCIADO = 60


class PQRSSolicitud(Base):
    __tablename__ = 'pqrs_solicitudes'

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False, index=True)
    codigo_seguimiento = Column(String(30), unique=True, nullable=True, index=True)
    radicado_calidad = Column(String(30), unique=True, nullable=True, index=True)
    tipo = Column(String(20), nullable=False)
    empresa = Column(String(150), nullable=True)
    nit_cedula = Column(String(30), nullable=True)
    cliente_nombre = Column(String(150), nullable=False)
    cliente_email = Column(String(180), nullable=True)
    cliente_telefono = Column(String(40), nullable=True)
    ciudad = Column(String(100), nullable=True)
    departamento = Column(String(100), nullable=True)
    # Los productos (con su lote y cantidades) viven en `pqrs_productos`: un
    # reclamo puede ser por varios. Ver `PQRSProducto`.
    canal_atencion = Column(String(50), nullable=True)
    # La factura es UNA por solicitud: los productos de un mismo reclamo
    # casi siempre vienen de la misma compra.
    factura_numero = Column(String(50), nullable=True)
    adjunto_producto = Column(String(500), nullable=True)
    adjunto_factura = Column(String(500), nullable=True)
    adjunto_video = Column(String(500), nullable=True)
    descripcion = Column(Text, nullable=False)
    area_responsable = Column(String(100), nullable=True)  # área que GESTIONA el caso (asignación operativa)
    area_causante = Column(String(100), nullable=True)  # área CAUSANTE del problema, para indicadores — solo editable internamente
    # «Asociado a»: la causa de la PQRS en el catálogo de la empresa (Mala
    # entrega, Calidad del producto…). Junto con el área causante es «la
    # causa», la marca quien reparte y es obligatoria para cerrar a mano.
    # Ver `modules/pqrs/asociados.py`.
    asociado_id = Column(Integer, ForeignKey('pqrs_asociados.id'), nullable=True, index=True)
    # Desde qué bodega salió el producto (la lista común, `models/bodega.py`).
    # Decide el primer concepto del flujo: Logística o Producción. Ver
    # `modules/pqrs/flujo.py`.
    bodega_despacho_id = Column(Integer, ForeignKey('bodegas.id'), nullable=True)
    asignado_a = Column(Integer, ForeignKey('users.id'), nullable=True)
    estado = Column(String(20), nullable=False, default='recibido')
    prioridad = Column(String(20), nullable=False, default='media')
    origen_publico = Column(String(20), nullable=False, default='interno')
    fecha_creacion = Column(DateTime(timezone=True), server_default=func.now())
    fecha_limite_sla = Column(DateTime(timezone=True), nullable=True)
    fecha_cierre = Column(DateTime(timezone=True), nullable=True)

    # Desde cuándo la tiene su área actual. Vacío cuando no corre el reloj:
    # sin área, o ya respondida (resuelta o cerrada). Lo mantiene
    # `tiempo_en_area.registrar_cambio()`, nunca se escribe a mano; los
    # tramos que ya terminaron quedan en `pqrs_pasos_area`.
    area_desde = Column(DateTime(timezone=True), nullable=True)

    # Qué se le dijo al cliente al marcarla "resuelto": es lo que antes solo
    # vivía en la cabeza de quien atendió, y el cliente nunca llegaba a leer
    # —el correo de cierre solo traía la encuesta—. Obligatoria al entrar a
    # "resuelto" (ver `pqrs/gestion.py`); nullable=True porque las PQRS ya
    # resueltas antes de este cambio no tienen con qué rellenarla.
    solucion = Column(Text, nullable=True)

    # Cuándo entró a "resuelto" por última vez. De aquí sale el plazo de
    # espera antes del cierre automático (3 días hábiles) y se BORRA si se
    # reabre: si no, una PQRS reabierta y vuelta a resolver heredaría el
    # reloj de la primera vez, y podría cerrarse sola con una solución vieja.
    fecha_resuelto = Column(DateTime(timezone=True), nullable=True)

    asignado = relationship('User', foreign_keys=[asignado_a])
    asociado = relationship('PQRSAsociado')
    bodega_despacho = relationship('Bodega')
    # La cadena de conceptos de esta PQRS, en orden. Ver `pqrs/flujo.py`.
    cadena = relationship(
        'PQRSCadenaPaso', back_populates='pqrs', cascade='all, delete-orphan',
        order_by='PQRSCadenaPaso.orden',
    )
    seguimientos = relationship('PQRSSeguimiento', back_populates='pqrs', cascade='all, delete-orphan')
    encuesta = relationship('PQRSEncuesta', back_populates='pqrs', uselist=False, cascade='all, delete-orphan')
    adjuntos_solucion = relationship(
        'PQRSAdjuntoSolucion', back_populates='pqrs', cascade='all, delete-orphan',
    )
    productos = relationship(
        'PQRSProducto', back_populates='pqrs', cascade='all, delete-orphan',
        order_by='PQRSProducto.orden',
    )

    # ── Cuánto lleva en su área (lo calcula el servidor, no la pantalla) ──

    @property
    def area_limite(self) -> datetime | None:
        """Hasta cuándo puede tenerla su área actual."""
        desde = con_zona(self.area_desde)
        return limite_en_habiles(desde, MAX_DIAS_HABILES_EN_AREA) if desde else None

    @property
    def dias_en_area(self) -> int | None:
        """Días hábiles que lleva en su área actual, sin contar el día en que llegó."""
        desde = con_zona(self.area_desde)
        if not desde:
            return None
        return contar_habiles(desde.date(), datetime.now(timezone.utc).date())

    @property
    def area_vencida(self) -> bool:
        """¿Su área actual ya se pasó de los días que tenía?"""
        limite = self.area_limite
        return bool(limite and datetime.now(timezone.utc) > limite)

    @property
    def producto_por_confirmar(self) -> bool:
        """
        Algún producto lo escribió el cliente a mano y falta amarrarlo al
        catálogo. Se DERIVA de los productos, no se guarda aparte: dos
        columnas que dicen lo mismo terminan diciendo cosas distintas.
        """
        return any(p.por_confirmar for p in self.productos)


class PQRSAsociado(Base):
    """
    «Asociado a»: el catálogo de causas de una PQRS (Mala entrega, Calidad
    del producto, Toma de pedido…). Es la lista con la que Calidad ya sacaba
    sus informes en Excel, y de la que salen las OMP y la ruta del caso.

    **Es tabla y no una lista en el código** porque la cambia la empresa sin
    desplegar, igual que las áreas y los canales. Se siembra sola la primera
    vez que se pide (`asociados.del_tenant`). No se borra: se desactiva, y
    las PQRS que ya lo tenían lo conservan.

    El `codigo` (`ME`, `TP-PV`…) NO es único: el formato oficial repite `ME`
    para la mala entrega del CEDI y la del punto de venta, y `N` para tres
    novedades del cliente. La identidad es el id; lo único es el nombre.
    """
    __tablename__ = 'pqrs_asociados'
    __table_args__ = (
        UniqueConstraint('tenant_id', 'nombre', name='uq_pqrs_asociado_tenant_nombre'),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'),
                       nullable=False, index=True)
    codigo = Column(String(MAX_CODIGO_ASOCIADO), nullable=False)
    nombre = Column(String(MAX_NOMBRE_ASOCIADO), nullable=False)
    # Para agrupar la lista y que no sean veinte opciones seguidas.
    grupo = Column(String(MAX_GRUPO_ASOCIADO), nullable=False)
    # El área causante que se propone al elegirlo. Solo se PROPONE: quien
    # clasifica la cambia si en ese caso fue otra.
    area_sugerida = Column(String(100), nullable=True)
    # «(S) Servicio (puede volverse OMP)»: una marca del catálogo, no del
    # nombre, para que renombrarlo no apague la regla.
    sugiere_omp = Column(Boolean, nullable=False, default=False, server_default='false')
    # Si es la variante de un tipo de canal (`sede` o `institucional`):
    # «Mala Entrega (Pventa)», «Novedad del cliente (VInst)». La pantalla la
    # pone primero cuando la PQRS entró por ese tipo de canal. Vacío: aplica
    # a cualquiera.
    aplica_a = Column(String(20), nullable=True)
    # El concepto técnico que pide el flujo cuando la PQRS es de esta causa
    # (Calidad del producto → Área Técnica). Vacío: la causa no pide uno.
    concepto_tecnico_id = Column(Integer, ForeignKey('tipos_autorizacion.id'), nullable=True)
    orden = Column(Integer, nullable=False, default=0, server_default='0')
    activo = Column(Boolean, nullable=False, default=True, server_default='true')
    creado_en = Column(DateTime(timezone=True), server_default=func.now())


class PQRSProducto(Base):
    """
    Un producto dentro de una PQRS, con SU lote y SUS cantidades.

    Antes la PQRS tenía un solo producto en columnas propias, y un reclamo
    por tres productos de la misma compra obligaba a radicar tres PQRS —con
    tres plazos, tres correos y tres encuestas para un solo problema— o a
    meter los otros dos en la descripción, donde ningún informe los ve. Cada
    producto trae lote y cantidades distintos, así que va en su propia fila.
    """
    __tablename__ = 'pqrs_productos'

    id = Column(Integer, primary_key=True, index=True)
    pqrs_id = Column(
        Integer, ForeignKey('pqrs_solicitudes.id', ondelete='CASCADE'),
        nullable=False, index=True,
    )
    # En qué orden los escribió quien radicó: así se muestran siempre igual.
    orden = Column(Integer, nullable=False, default=0)

    producto_codigo = Column(String(50), nullable=True)
    # 300 y no 200: es el mismo largo que `cat_productos.nombre`. Un producto
    # del catálogo con nombre largo no cabía y se truncaba al radicar.
    producto_nombre = Column(String(300), nullable=True)

    # El cliente no encontró este producto en el buscador y lo escribió.
    #
    # Existe porque la salida no puede ser dejarlo sin radicar: quien tiene un
    # reclamo tiene que poder ponerlo. Pero un nombre escrito a mano no sirve
    # para un informe —«Hipoclorito», «hipoclorito 13» y «HIPOCLORITO x20L»
    # son tres productos distintos para un reporte— así que queda MARCADO y
    # Servicio al Cliente lo corrige contra el catálogo antes de cerrar.
    # Se DEDUCE («hay nombre y no hay código»), nunca se recibe.
    por_confirmar = Column(Boolean, nullable=False, default=False, server_default="false")

    presentacion = Column(String(30), nullable=True)  # unidad | kilo | gramo | litro | mililitro
    cantidad_presentacion = Column(String(20), nullable=True)  # ej: "5"
    lote = Column(String(50), nullable=True)
    cantidad_factura = Column(String(20), nullable=True)
    cantidad_reclamo = Column(String(20), nullable=True)

    pqrs = relationship('PQRSSolicitud', back_populates='productos')


class PQRSSeguimiento(Base):
    __tablename__ = 'pqrs_seguimientos'

    id = Column(Integer, primary_key=True, index=True)
    pqrs_id = Column(Integer, ForeignKey('pqrs_solicitudes.id'), nullable=False, index=True)
    usuario_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    tipo_evento = Column(String(30), nullable=False)
    comentario = Column(Text, nullable=True)

    # A qué estado pasó la solicitud, cuando el evento es un cambio de estado.
    #
    # Existe para que la consulta pública pueda redactar el movimiento sin
    # usar el comentario: ahí es donde el área escribe sus notas internas, y
    # eso no le corresponde al cliente. Con el estado aparte, el texto que ve
    # se genera aquí y siempre dice lo mismo.
    estado_nuevo = Column(String(20), nullable=True)
    adjunto_evidencia = Column(String(255), nullable=True)
    fecha = Column(DateTime(timezone=True), server_default=func.now())

    pqrs = relationship('PQRSSolicitud', back_populates='seguimientos')
    usuario = relationship('User')

    @property
    def usuario_nombre(self):
        return self.usuario.nombre if self.usuario else None

    @property
    def usuario_area(self):
        return self.usuario.area if self.usuario else None

    @property
    def usuario_rol(self):
        return self.usuario.rol if self.usuario else None


class PQRSAdjuntoSolucion(Base):
    """
    El soporte de la solución: pueden ser varias imágenes y/o un PDF, así
    que va en tabla propia y no en una columna de texto — una sola columna
    solo alcanza para un archivo, y aquí el agente puede tener que mostrar
    el antes y el después, o la factura de la nota crédito junto con la foto
    del producto cambiado.
    """
    __tablename__ = 'pqrs_adjuntos_solucion'

    id = Column(Integer, primary_key=True, index=True)
    pqrs_id = Column(Integer, ForeignKey('pqrs_solicitudes.id'), nullable=False, index=True)
    ruta = Column(String(500), nullable=False)
    creado_en = Column(DateTime(timezone=True), server_default=func.now())

    pqrs = relationship('PQRSSolicitud', back_populates='adjuntos_solucion')


class PQRSEncuesta(Base):
    __tablename__ = 'pqrs_encuestas'

    id = Column(Integer, primary_key=True, index=True)
    pqrs_id = Column(Integer, ForeignKey('pqrs_solicitudes.id'), nullable=False, unique=True)

    tipo_solicitud = Column(String(20), nullable=True)  # peticion | queja | reclamo | sugerencia | felicitacion
    calificacion = Column(Integer, nullable=True)  # calificación de la atención, 1 a 5
    solucionada = Column(String(20), nullable=True)  # si | parcial | no
    calificacion_tiempo_respuesta = Column(String(20), nullable=True)  # excelente | bueno | regular | malo
    recomendaria = Column(Boolean, nullable=True)
    comentario = Column(Text, nullable=True)

    respondida_en = Column(DateTime(timezone=True), nullable=True)
    enviada_en = Column(DateTime(timezone=True), server_default=func.now())

    pqrs = relationship('PQRSSolicitud', back_populates='encuesta')

    @property
    def respondida(self) -> bool:
        return self.respondida_en is not None


class PQRSPasoArea(Base):
    """
    Un tramo terminado de una PQRS en un área: quién la tuvo, desde cuándo,
    hasta cuándo y si se pasó de los días.

    Es lo que permite medir después —un indicador, un informe de «qué área se
    demora más»— sin reconstruirlo del historial de texto. El tramo que está
    corriendo no está aquí: es el `area_responsable` y el `area_desde` de la
    PQRS, y se guarda aquí cuando termina.
    """
    __tablename__ = "pqrs_pasos_area"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    pqrs_id = Column(Integer, ForeignKey("pqrs_solicitudes.id", ondelete="CASCADE"),
                     nullable=False, index=True)
    area = Column(String(100), nullable=False, index=True)
    desde = Column(DateTime(timezone=True), nullable=False)
    hasta = Column(DateTime(timezone=True), nullable=False)
    dias_habiles = Column(Integer, nullable=False)
    excedio = Column(Boolean, nullable=False, default=False)



# ── El flujo de conceptos ──────────────────────────────────────────────
# Ver `modules/pqrs/flujo.py`: por qué es una cadena de conceptos y no una
# ruta de áreas, y cómo avanza sola.

# Las clases de paso de un flujo. `concepto` es un tipo de autorización fijo;
# los otros dos se resuelven con los datos de cada PQRS.
CLASES_PASO = ("concepto", "bodega", "tecnico")

# Los tipos de PQRS. Una plantilla de flujo dice para cuáles sirve: un
# reclamo por producto no recorre lo mismo que una queja por la atención, y
# una felicitación no pide conceptos.
TIPOS_PQRS = ("peticion", "queja", "reclamo", "sugerencia", "felicitacion")

# Cómo va cada paso de la cadena de una PQRS.
ESTADOS_PASO = ("pendiente", "en_curso", "aprobado", "rechazado", "devuelto")


class PQRSConceptoBodega(Base):
    """
    Qué concepto pide el flujo de una PQRS cuando el producto salió de esta
    bodega: en Protokimica, el CD y La 65 piden a Logística y Guayabal a
    Producción. La bodega es la lista común del portal (`models/bodega.py`);
    esto es solo lo que PQRS le pone encima, y por eso vive aquí.
    """
    __tablename__ = 'pqrs_conceptos_bodega'
    __table_args__ = (
        UniqueConstraint('bodega_id', name='uq_pqrs_concepto_bodega'),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    bodega_id = Column(Integer, ForeignKey('bodegas.id', ondelete='CASCADE'), nullable=False)
    tipo_autorizacion_id = Column(Integer, ForeignKey('tipos_autorizacion.id'), nullable=True)


class PQRSFlujo(Base):
    """
    Una plantilla de conceptos: qué se pide, en qué orden, para las PQRS de
    unos TIPOS (reclamo, queja…) y un tipo de canal. Se edita en
    Administración sin desplegar. Cuál le toca a cada PQRS lo decide
    `flujo.plantilla_para()`: la más específica.
    """
    __tablename__ = 'pqrs_flujos'

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    nombre = Column(String(MAX_NOMBRE_ASOCIADO), nullable=False)
    # `sede`, `institucional`, `general`, o vacío: cualquier canal.
    aplica_a = Column(String(20), nullable=True)
    # Los tipos de PQRS para los que sirve, separados por coma y en el orden
    # de `TIPOS_PQRS`; vacío: cualquier tipo. Se lee con `.tipos`.
    tipos_pqrs = Column(String(100), nullable=True)
    activo = Column(Boolean, nullable=False, default=True, server_default='true')
    creado_en = Column(DateTime(timezone=True), server_default=func.now())

    @property
    def tipos(self) -> list[str]:
        return [t for t in (self.tipos_pqrs or "").split(",") if t]

    @tipos.setter
    def tipos(self, valores) -> None:
        elegidos = set(valores or ())
        self.tipos_pqrs = ",".join(t for t in TIPOS_PQRS if t in elegidos) or None

    pasos = relationship(
        'PQRSFlujoPaso', back_populates='flujo', cascade='all, delete-orphan',
        order_by='PQRSFlujoPaso.orden',
    )


class PQRSFlujoPaso(Base):
    __tablename__ = 'pqrs_flujo_pasos'

    id = Column(Integer, primary_key=True, index=True)
    flujo_id = Column(Integer, ForeignKey('pqrs_flujos.id', ondelete='CASCADE'), nullable=False, index=True)
    orden = Column(Integer, nullable=False, default=0)
    clase = Column(String(20), nullable=False, default='concepto')
    # Solo para `concepto`: los otros se resuelven por bodega y por causa.
    tipo_autorizacion_id = Column(Integer, ForeignKey('tipos_autorizacion.id'), nullable=True)

    flujo = relationship('PQRSFlujo', back_populates='pasos')


class PQRSCadenaPaso(Base):
    """
    Un paso de la cadena de conceptos de UNA PQRS, ya resuelto a un tipo de
    autorización concreto. Se copian de la plantilla al iniciar: cambiar la
    plantilla después no le mueve los pasos a las PQRS que ya van en camino.
    """
    __tablename__ = 'pqrs_cadena_pasos'

    id = Column(Integer, primary_key=True, index=True)
    pqrs_id = Column(Integer, ForeignKey('pqrs_solicitudes.id', ondelete='CASCADE'), nullable=False, index=True)
    orden = Column(Integer, nullable=False, default=0)
    tipo_autorizacion_id = Column(Integer, ForeignKey('tipos_autorizacion.id'), nullable=False)
    # De dónde salió: `concepto`, `bodega`, `tecnico` (de la plantilla) o
    # `agregado` (lo puso Servicio al Cliente a mano).
    origen = Column(String(20), nullable=False, default='concepto')
    estado = Column(String(20), nullable=False, default='pendiente')
    autorizacion_id = Column(Integer, ForeignKey('autorizaciones_pqrs.id'), nullable=True)
    # Quien inició o agregó el paso: a su nombre se pide la autorización
    # cuando el flujo la pide solo.
    creado_por = Column(Integer, ForeignKey('users.id'), nullable=True)
    creado_en = Column(DateTime(timezone=True), server_default=func.now())

    pqrs = relationship('PQRSSolicitud', back_populates='cadena')
    tipo = relationship('TipoAutorizacion')
