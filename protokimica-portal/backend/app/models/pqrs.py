from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, func
from sqlalchemy.orm import relationship
from app.core.database import Base


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
    asignado_a = Column(Integer, ForeignKey('users.id'), nullable=True)
    estado = Column(String(20), nullable=False, default='recibido')
    prioridad = Column(String(20), nullable=False, default='media')
    origen_publico = Column(String(20), nullable=False, default='interno')
    fecha_creacion = Column(DateTime(timezone=True), server_default=func.now())
    fecha_limite_sla = Column(DateTime(timezone=True), nullable=True)
    fecha_cierre = Column(DateTime(timezone=True), nullable=True)

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
    seguimientos = relationship('PQRSSeguimiento', back_populates='pqrs', cascade='all, delete-orphan')
    encuesta = relationship('PQRSEncuesta', back_populates='pqrs', uselist=False, cascade='all, delete-orphan')
    adjuntos_solucion = relationship(
        'PQRSAdjuntoSolucion', back_populates='pqrs', cascade='all, delete-orphan',
    )
    productos = relationship(
        'PQRSProducto', back_populates='pqrs', cascade='all, delete-orphan',
        order_by='PQRSProducto.orden',
    )

    @property
    def producto_por_confirmar(self) -> bool:
        """
        Algún producto lo escribió el cliente a mano y falta amarrarlo al
        catálogo. Se DERIVA de los productos, no se guarda aparte: dos
        columnas que dicen lo mismo terminan diciendo cosas distintas.
        """
        return any(p.por_confirmar for p in self.productos)


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
