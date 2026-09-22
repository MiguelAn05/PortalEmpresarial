from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class PQRSCreate(BaseModel):
    tipo: str  # peticion | queja | reclamo | sugerencia
    cliente_nombre: str
    cliente_email: EmailStr | None = None
    cliente_telefono: str | None = None
    descripcion: str
    area_responsable: str | None = None


class PQRSUpdateEstado(BaseModel):
    estado: str  # recibido | asignado | en_proceso | resuelto | cerrado
    comentario: str | None = None


class PQRSAsignar(BaseModel):
    usuario_id: int
    comentario: str | None = None


class PQRSAsignarArea(BaseModel):
    area: str
    comentario: str | None = None


class PQRSAreaCausante(BaseModel):
    area_causante: str


class SeguimientoOut(BaseModel):
    id: int
    tipo_evento: str
    comentario: str | None
    adjunto_evidencia: str | None = None
    fecha: datetime
    usuario_id: int | None
    usuario_nombre: str | None = None
    usuario_area: str | None = None
    usuario_rol: str | None = None

    class Config:
        from_attributes = True

class PQRSResumenOut(BaseModel):
    """
    Una fila de la lista: exactamente lo que la tabla pinta, y nada más.

    La lista devolvía la PQRS COMPLETA —descripción de hasta cuatro mil
    caracteres, productos, rutas de adjuntos, la solución— para cada una de
    las solicitudes de la empresa, y la pantalla usaba trece campos. Con
    doscientas PQRS no se notaba; el histórico no deja de crecer y esto crece
    con él.

    Los productos, además, se leían con una consulta POR FILA: son una
    relación aparte y el schema los pedía uno a uno. Al no nombrarlos aquí,
    esa consulta deja de existir.

    Los campos son los que usa `PQRSList.jsx` (las columnas de la tabla, la
    búsqueda y los filtros). Si la lista necesita uno nuevo, se agrega aquí —
    no se vuelve a mandar la solicitud entera.
    """
    model_config = ConfigDict(from_attributes=True)

    id: int
    codigo_seguimiento: str | None = None
    radicado_calidad: str | None = None
    tipo: str

    # Con qué se reconoce al cliente en la lista. Ver `nombrePrincipal()`.
    empresa: str | None = None
    nit_cedula: str | None = None
    cliente_nombre: str
    cliente_email: str | None = None

    area_responsable: str | None = None
    estado: str
    prioridad: str

    fecha_creacion: datetime
    fecha_limite_sla: datetime | None = None


class PQRSOut(BaseModel):
    id: int
    codigo_seguimiento: str | None = None
    radicado_calidad: str | None = None
    tipo: str

    empresa: str | None = None
    nit_cedula: str | None = None

    cliente_nombre: str
    cliente_email: str | None = None
    cliente_telefono: str | None = None

    ciudad: str | None = None
    departamento: str | None = None

    # Uno o varios, cada uno con su lote y cantidades. Ver `pqrs/productos.py`.
    productos: list["ProductoOut"] = []
    # Algún producto lo escribió el cliente y falta confirmarlo contra el
    # catálogo. Se deriva de `productos`; se manda ya resuelto.
    producto_por_confirmar: bool = False
    canal_atencion: str | None = None
    factura_numero: str | None = None

    adjunto_producto: str | None = None
    adjunto_factura: str | None = None
    adjunto_video: str | None = None

    descripcion: str
    area_responsable: str | None = None
    area_causante: str | None = None
    asignado_a: int | None = None

    estado: str
    prioridad: str

    fecha_creacion: datetime
    fecha_limite_sla: datetime | None = None
    fecha_cierre: datetime | None = None

    # Qué se le dijo al cliente al marcar "resuelto", y desde cuándo. Ver
    # `pqrs/cierre_automatico.py` para el plazo que sale de `fecha_resuelto`.
    solucion: str | None = None
    fecha_resuelto: datetime | None = None

    class Config:
        from_attributes = True


class AdjuntoSolucionOut(BaseModel):
    id: int
    ruta: str
    creado_en: datetime

    class Config:
        from_attributes = True


class EncuestaOut(BaseModel):
    tipo_solicitud: str | None = None
    calificacion: int | None = None
    solucionada: str | None = None
    calificacion_tiempo_respuesta: str | None = None
    recomendaria: bool | None = None
    comentario: str | None = None
    respondida_en: datetime | None = None
    enviada_en: datetime

    class Config:
        from_attributes = True


class AlcancePQRS(BaseModel):
    """
    Qué puede hacer ESTA persona con ESTA PQRS.

    El frontend no decide permisos, los pregunta: si repitiera las reglas de
    `permisos.py` para saber a quién mostrarle qué, tarde o temprano la
    pantalla ofrecería un botón que el servidor rechaza, o escondería uno que
    sí estaba permitido. Aquí llegan ya resueltas y la interfaz solo esconde
    lo que no aplica.
    """
    # Escribir cualquier cosa: comentario, estado o evidencia. Es falso para
    # 'lectura' y 'gerencia', que no escriben nada en el portal.
    puede_gestionar: bool
    # Mover el área responsable. Es de Servicio al Cliente, que reparte.
    puede_cambiar_area: bool
    # Cerrar dispara la encuesta al cliente y congela la PQRS para los
    # indicadores; por eso va aparte de gestionar.
    puede_cerrar: bool
    # Corregir lo que el cliente escribió mal al radicar: el tipo y el
    # producto. Es la misma regla y el mismo dueño para los dos.
    puede_reclasificar: bool
    # Corregir los datos del cliente, de la factura y los adjuntos. Es de
    # quien gestiona el caso —quien llama al cliente es quien descubre que el
    # correo estaba mal—, y no con la PQRS cerrada. Ver `pqrs/edicion.py`.
    puede_editar_datos: bool = False


class PQRSDetailOut(PQRSOut):
    seguimientos: list[SeguimientoOut] = []
    encuesta: EncuestaOut | None = None
    alcance: AlcancePQRS | None = None
    adjuntos_solucion: list[AdjuntoSolucionOut] = []
    # Cuándo se cierra sola si el cliente no contesta. Solo tiene sentido
    # con `estado == "resuelto"`; se calcula en el router porque depende de
    # una función (`cierre_automatico.plazo_confirmacion`), no de una
    # columna.
    plazo_confirmacion: datetime | None = None


class PQRSEditarDatos(BaseModel):
    """
    Corrección de los datos de una PQRS radicada. Todo es opcional: solo se
    toca lo que llega (`exclude_unset`), y un campo vacío es «bórralo».

    Los `max_length` son los de las columnas de `pqrs_solicitudes`, y
    `frontend/src/modules/pqrs/constants.js` los repite en el `maxLength` de
    cada input: un límite sin su tope en pantalla es un 422 esperando pasar.
    """
    empresa: str | None = Field(None, max_length=150)
    nit_cedula: str | None = Field(None, max_length=30)
    cliente_nombre: str | None = Field(None, max_length=150)
    cliente_email: str | None = Field(None, max_length=180)
    cliente_telefono: str | None = Field(None, max_length=40)
    ciudad: str | None = Field(None, max_length=100)
    departamento: str | None = Field(None, max_length=100)
    factura_numero: str | None = Field(None, max_length=50)


class ProductoIn(BaseModel):
    """
    Un producto nuevo en una PQRS ya radicada. Los topes son los de
    `pqrs_productos` y `LIMITES_PRODUCTO` en el frontend los repite.
    """
    producto_codigo: str | None = Field(None, max_length=50)
    producto_nombre: str | None = Field(None, max_length=300)
    presentacion: str | None = Field(None, max_length=30)
    cantidad_presentacion: str | None = Field(None, max_length=20)
    lote: str | None = Field(None, max_length=50)
    cantidad_factura: str | None = Field(None, max_length=20)
    cantidad_reclamo: str | None = Field(None, max_length=20)


class ProductoCorregir(BaseModel):
    """Lo que se corrige de un producto: el código y el nombre van por el catálogo."""
    presentacion: str | None = Field(None, max_length=30)
    cantidad_presentacion: str | None = Field(None, max_length=20)
    lote: str | None = Field(None, max_length=50)
    cantidad_factura: str | None = Field(None, max_length=20)
    cantidad_reclamo: str | None = Field(None, max_length=20)


class ProductoOut(BaseModel):
    id: int
    producto_codigo: str | None = None
    producto_nombre: str | None = None
    por_confirmar: bool = False
    presentacion: str | None = None
    cantidad_presentacion: str | None = None
    lote: str | None = None
    cantidad_factura: str | None = None
    cantidad_reclamo: str | None = None

    class Config:
        from_attributes = True


# `PQRSOut` nombra a `ProductoOut` antes de que exista: se resuelve aquí.
PQRSOut.model_rebuild()
PQRSDetailOut.model_rebuild()


class PuntoVentaOut(BaseModel):
    canal: str
    prefijo: str


class VisibilidadPQRS(BaseModel):
    """
    Qué parte de las PQRS ve quien está mirando. La pantalla lo usa para
    decir «estás viendo las de Guayabal» en vez de dejar que alguien crea que
    no hay más PQRS en la empresa, y para no ofrecer filtros por puntos que
    no ve.
    """
    # False = ve todas las PQRS de la empresa.
    restringida: bool
    # Los puntos de venta que ve. Uno solo = una sede; varios = coordinador.
    puntos: list[PuntoVentaOut] = []


class EncuestaCreate(BaseModel):
    tipo_solicitud: str  # peticion | queja | reclamo | sugerencia | felicitacion
    calificacion: int  # calificación de la atención, 1 a 5
    solucionada: str  # si | parcial | no
    calificacion_tiempo_respuesta: str  # excelente | bueno | regular | malo
    recomendaria: bool
    comentario: str | None = None
