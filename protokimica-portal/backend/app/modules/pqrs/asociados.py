"""
«Asociado a»: la causa de una PQRS, y el área que la causó.

Calidad clasificaba cada PQRS en su Excel con esta lista, y de ahí salían los
informes y las OMP. En el portal no existía: solo el área causante, opcional
y escondida en la cabecera, así que la mitad de las PQRS se cerraban sin
causa y el informe no servía. Ahora las dos van juntas («la causa») y:

- **La marca quien reparte** (`pqrs.cerrar`, Servicio al Cliente), igual que
  reclasificar el tipo: es quien ve todas y clasifica con el mismo criterio.
- **Es obligatoria para cerrar a mano** (`gestion._validar`). Las que cierra
  el cliente al confirmar, o el cierre automático, no se pueden frenar por
  esto: se clasifican DESPUÉS de cerradas, y la lista tiene el filtro «Sin
  causa» para encontrarlas.
- **Se puede poner desde el principio.** El asociado definitivo se sabe al
  final, pero quien reparte casi siempre tiene una idea desde que la lee, y
  es lo que más adelante decide la ruta del caso. Si cambia, el historial
  guarda el anterior: que empiece como «Mala entrega» y termine como
  «Calidad del producto» también es información.

«En proceso» y «Anulada», que estaban en la lista del Excel, NO son causas y
no se siembran: la primera es dejarlo vacío, la segunda no es un motivo.
"""
from sqlalchemy.orm import Session

from app.core import areas
from app.models.pqrs import PQRSAsociado

# (código, nombre, grupo, área sugerida, tipo de canal, sugiere OMP)
# El área solo se siembra si la empresa la tiene; las dudosas van vacías y
# se completan en Administración › Asociados.
ASOCIADOS_INICIALES = [
    ("CP", "Calidad del Producto", "Producto y empaque", None, None, False),
    ("CE", "Calidad de Empaque, Envase, Etiqueta o información", "Producto y empaque", None, None, False),
    ("CDE", "Contenido diferente a la Etiqueta", "Producto y empaque", None, None, False),
    ("DP", "Diferencia en peso", "Producto y empaque", None, None, False),
    ("FV", "Fecha de vencimiento", "Producto y empaque", None, None, False),
    ("RP", "Referencia o Proveedor Prod Portafolio", "Producto y empaque", None, None, False),
    ("DE", "Demora en entrega", "Entrega", "Logística", None, False),
    ("ME", "Mala Entrega (CEDI)", "Entrega", "Logística", None, False),
    ("ME", "Mala Entrega (Pventa)", "Entrega", "Puntos de Venta", "sede", False),
    ("TR", "Transportadora", "Entrega", "Logística", None, False),
    ("TP-PV", "Toma de pedido en Punto de Venta", "Toma de pedido", "Puntos de Venta", "sede", False),
    ("TP-VI", "Toma de pedido Ventas Institucional", "Toma de pedido", "Ventas Institucionales", "institucional", False),
    ("TP-NV", "Toma de pedido Negocios Virtuales", "Toma de pedido", None, None, False),
    ("N", "Novedad del cliente (Pventa)", "Cliente y entorno", None, "sede", False),
    ("N", "Novedad del cliente (VInst)", "Cliente y entorno", None, "institucional", False),
    ("N", "Novedad del cliente (Negoc Virtuales)", "Cliente y entorno", None, None, False),
    ("NE", "Novedad Externa (condiciones socio políticas demográficas)", "Cliente y entorno", None, None, False),
    ("S", "Servicio", "Servicio", None, None, True),
]

TIPOS_CANAL = ("sede", "institucional")


def sembrar(db: Session, tenant_id: int) -> None:
    """La lista de arranque, si la empresa todavía no tiene ninguno. Idempotente."""
    if db.query(PQRSAsociado.id).filter(PQRSAsociado.tenant_id == tenant_id).first():
        return
    for orden, (codigo, nombre, grupo, area, aplica_a, omp) in enumerate(ASOCIADOS_INICIALES):
        db.add(PQRSAsociado(
            tenant_id=tenant_id, codigo=codigo, nombre=nombre, grupo=grupo,
            area_sugerida=area if area and areas.es_valida(db, tenant_id, area) else None,
            aplica_a=aplica_a, sugiere_omp=omp, orden=orden,
        ))
    db.commit()


def del_tenant(db: Session, tenant_id: int, incluir_inactivos: bool = False) -> list[PQRSAsociado]:
    """En el orden en que se ofrecen: el del catálogo, y por nombre dentro de él."""
    sembrar(db, tenant_id)
    consulta = db.query(PQRSAsociado).filter(PQRSAsociado.tenant_id == tenant_id)
    if not incluir_inactivos:
        consulta = consulta.filter(PQRSAsociado.activo.is_(True))
    return consulta.order_by(PQRSAsociado.orden, PQRSAsociado.nombre).all()


def obtener(db: Session, tenant_id: int, asociado_id: int) -> PQRSAsociado | None:
    return db.query(PQRSAsociado).filter(
        PQRSAsociado.id == asociado_id, PQRSAsociado.tenant_id == tenant_id,
    ).first()


def etiqueta(asociado: PQRSAsociado | None) -> str:
    """Cómo se escribe en el historial: «(ME) Mala Entrega (CEDI)»."""
    return f"({asociado.codigo}) {asociado.nombre}" if asociado else "sin definir"
