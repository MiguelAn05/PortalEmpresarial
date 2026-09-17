from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

# Los topes van aquí y el formulario los repite con la MISMA cifra: el backend
# es la autoridad, pero un `<input>` sin `maxLength` deja que el usuario
# escriba de más y reciba un 422 después de haberlo escrito todo.
MAX_FACTURA = 60
MAX_OBSERVACIONES = 2000
MAX_NUMERO_NC = 60


class MotivoOut(BaseModel):
    id: int
    nombre: str
    activo: bool
    # Si este motivo implica producto devuelto y, por tanto, confirmación de
    # la bodega antes de que nadie apruebe nada.
    requiere_bodega: bool = False

    class Config:
        from_attributes = True


class MotivoCreate(BaseModel):
    nombre: str
    requiere_bodega: bool = False


class ResponderSolicitud(BaseModel):
    # aprobar | rechazar | devolver — ver `flujo.ACCIONES`. «Aprobar» pasa al
    # siguiente paso de la cadena, no termina el trámite.
    decision: str
    comentario: str | None = None


class ComentarioOpcional(BaseModel):
    """
    Lo único que llevan reenviar y cancelar.

    NO reusan `ResponderSolicitud`: ahí `decision` es obligatoria y en estas
    dos no significa nada, así que la pantalla tendría que inventarse un valor
    para que el servidor la aceptara — y el día que se le olvide, el 422 no
    dice nada parecido a lo que de verdad pasa.
    """
    comentario: str | None = None


class HistorialOut(BaseModel):
    """Una mano de la cadena, para la línea de tiempo del detalle."""
    etapa: str
    accion: str
    usuario_nombre: str | None = None
    comentario: str | None = None
    creado_en: datetime

    class Config:
        from_attributes = True


class AplicarSolicitud(BaseModel):
    numero_nc: str
    comentario: str | None = None


class AlcanceNotaCredito(BaseModel):
    """
    Qué puede hacer quien está mirando. El frontend no decide permisos: los
    pregunta, y esconde lo que no aplica.
    """
    # Es su turno en la cadena: puede aprobar, rechazar o devolverla.
    puede_responder: bool
    # Registrar el número de la que ya se emitió: cierra el trámite.
    puede_aplicar: bool
    # De quien la pidió: corregir una devuelta, o retirarla.
    puede_reenviar: bool = False
    puede_cancelar: bool = False


class SolicitudOut(BaseModel):
    id: int
    codigo: str | None = None
    punto_venta: str
    factura_afectada: str
    factura_reemplaza: str | None = None
    valor: Decimal | None = None
    motivo_id: int | None = None
    motivo_nombre: str | None = None
    bodega: str | None = None
    observaciones: str
    adjunto: str | None = None

    estado: str
    solicitado_por: int
    solicitante_nombre: str | None = None
    creado_en: datetime

    autorizado_por: int | None = None
    autorizador_nombre: str | None = None
    comentario_respuesta: str | None = None
    fecha_respuesta: datetime | None = None

    numero_nc: str | None = None
    ejecutor_nombre: str | None = None
    fecha_aplicacion: datetime | None = None

    class Config:
        from_attributes = True


class SolicitudDetailOut(SolicitudOut):
    alcance: AlcanceNotaCredito | None = None

    # En qué paso va y qué se espera de quien lo atiende. Lo redacta el
    # SERVIDOR: si la pantalla tradujera «en_contabilidad» por su cuenta,
    # agregar un paso obligaría a acordarse de traducirlo también allí — y
    # ese es justo el olvido que deja una etapa nueva con nombre de columna.
    etapa_nombre: str | None = None
    que_hacer: str | None = None
    etapa_siguiente: str | None = None

    # La cadena completa de manos por las que pasó.
    historial: list[HistorialOut] = []
