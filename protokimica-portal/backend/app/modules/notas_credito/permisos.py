"""
Quién hace qué con una solicitud de nota crédito.

**Primer módulo migrado a permisos por capacidad** (ver `core/capacidades.py`).
Antes esto era `usuario.rol == "admin" or usuario.area == "Contabilidad"`, y
la única forma de que otra área también tramitara notas crédito era
cambiarle el área a alguien — con lo que se le entregaba también todo lo
demás que Contabilidad decide en otros módulos. Ahora un administrador
otorga la capacidad desde Administración › Capacidades, a un área o a una
persona puntual, sin desplegar nada.

Contabilidad sigue teniendo las dos capacidades por defecto — eso lo dejó
sembrado la migración `d81f6a4c92e3`, no este archivo — así que para el caso
de todos los días nada cambió.

Autorizar (aprobar/rechazar) y registrar el número ya emitido son DOS
capacidades separadas (`notas_credito.autorizar` y `notas_credito.registrar`)
aunque hoy las tenga la misma gente: un administrador podría, por ejemplo,
darle a alguien solo el registro sin dejarlo aprobar montos. Antes una sola
función cubría las dos acciones, así que no había manera de separarlas.

Servicio al Cliente NO participa. Esto es un trámite entre el punto de venta
y quien tenga la capacidad; meterlos sería darles una bandeja más que
revisar sin que tengan nada que decidir en ella.
"""
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.core.capacidades import CAPACIDADES, quienes_tienen, tiene
from app.models.nota_credito import ESTADO_EN_BODEGA, SolicitudNotaCredito
from app.models.user import User
from app.modules.notas_credito import flujo

CAP_AUTORIZAR = "notas_credito.autorizar"
CAP_REGISTRAR = "notas_credito.registrar"
CAP_CONFIRMAR_PRODUCTO = "notas_credito.confirmar_producto"
CAP_APROBAR_COMERCIAL = "notas_credito.aprobar_comercial"
CAP_VERIFICAR_DIAN = "notas_credito.verificar_dian"

CAPACIDADES_DEL_MODULO = (
    CAP_AUTORIZAR, CAP_REGISTRAR, CAP_CONFIRMAR_PRODUCTO,
    CAP_APROBAR_COMERCIAL, CAP_VERIFICAR_DIAN,
)

assert all(c in CAPACIDADES for c in CAPACIDADES_DEL_MODULO), (
    "Alguna capacidad de notas crédito ya no está en core/capacidades.py. "
    "Actualiza este módulo o habrá una etapa de la cadena que nadie pueda "
    "atender, y la solicitud se quedará ahí sin que nadie sepa por qué."
)


def puede_autorizar(db: Session, usuario: User) -> bool:
    """Aprobar o rechazar una solicitud."""
    return tiene(db, usuario, CAP_AUTORIZAR)


def puede_registrar(db: Session, usuario: User) -> bool:
    """Registrar el número de la nota crédito que ya se emitió."""
    return tiene(db, usuario, CAP_REGISTRAR)


def puede_radicar(usuario: User) -> bool:
    """
    Quién puede pedir una nota crédito.

    Hoy es cualquier usuario interno que escriba en el portal. La idea es que
    sean los puntos de venta y los vendedores institucionales, pero el usuario
    todavía no guarda a qué punto de venta pertenece —`User` tiene `area`, no
    canal—, así que no hay contra qué comprobarlo. Mientras tanto el punto de
    venta se elige de la lista cerrada al radicar y queda en el registro.
    """
    return usuario.rol not in ("lectura", "gerencia")


def puede_atender(db: Session, usuario: User, solicitud) -> bool:
    """
    ¿Es SU turno? La pregunta que gobierna toda la cadena.

    No basta con tener la capacidad: hay que tenerla **en la etapa en la que
    está la solicitud**. Comercial no aprueba algo que todavía no confirmó la
    bodega, y de esa manera el orden de los pasos no depende de que la gente
    se acuerde de respetarlo — lo impone el servidor.

    En la bodega se afina todavía más: solo la persona de ESA bodega. Una
    devolución que entró en Guayabal no la confirma quien maneja La 65, por
    la misma razón que una PQRS de Guayabal no la atiende Belén.
    """
    capacidad = flujo.capacidad_de(solicitud.estado)
    if capacidad is None:
        return False   # estado final, o en manos del solicitante
    if not tiene(db, usuario, capacidad):
        return False
    if solicitud.estado == ESTADO_EN_BODEGA:
        return flujo.atiende_la_bodega(usuario, solicitud.bodega)
    return True


def es_el_solicitante(usuario: User, solicitud) -> bool:
    return solicitud.solicitado_por == usuario.id


def _capacidades_de(db: Session, usuario: User) -> set[str]:
    return {c for c in CAPACIDADES_DEL_MODULO if tiene(db, usuario, c)}


def ve_todas(db: Session, usuario: User) -> bool:
    """
    Quién ve el módulo completo: los roles que ven todo el portal y quienes
    tramitan CUALQUIER nota crédito —autorizar y registrar—, que necesitan la
    lista entera para trabajar.
    """
    return (
        usuario.rol in ("admin", "gerencia")
        or tiene(db, usuario, CAP_AUTORIZAR)
        or tiene(db, usuario, CAP_REGISTRAR)
    )


def puede_ver(db: Session, usuario: User, solicitud) -> bool:
    """
    Quién ve una solicitud.

    La ve quien la pidió, quien tramita todas (ver `ve_todas`), y quien
    participa en la cadena institucional — pero solo de las institucionales:
    una nota crédito del almacén de Belén no es asunto de Coordinación
    Comercial, y llenarle la bandeja de casos que no le tocan es cómo se
    consigue que deje de mirarla.

    Quien confirma producto ve además solo las de SU bodega.

    Por defecto se cierra en vez de abrirse: una solicitud lleva números de
    factura y valores de un cliente, y ampliar después es más fácil que
    explicar por qué medio portal los estuvo viendo.
    """
    if ve_todas(db, usuario) or es_el_solicitante(usuario, solicitud):
        return True

    suyas = _capacidades_de(db, usuario)
    if not suyas or not flujo.es_institucional(solicitud.punto_venta):
        return False
    if suyas & {CAP_APROBAR_COMERCIAL, CAP_VERIFICAR_DIAN}:
        return True
    if CAP_CONFIRMAR_PRODUCTO in suyas:
        return flujo.atiende_la_bodega(usuario, solicitud.bodega)
    return False


def filtrar_visibles(query, db: Session, usuario: User):
    """
    La misma regla de `puede_ver`, pero dentro de la consulta.

    Van juntas a propósito: filtrar en la lista y comprobar al abrir son dos
    caras de lo mismo, y cuando viven en archivos distintos un día dicen
    cosas distintas — la lista muestra algo que al abrirlo responde 404.
    """
    if ve_todas(db, usuario):
        return query

    condiciones = [SolicitudNotaCredito.solicitado_por == usuario.id]
    suyas = _capacidades_de(db, usuario)
    institucional = SolicitudNotaCredito.punto_venta == flujo.CANAL_INSTITUCIONAL

    if suyas & {CAP_APROBAR_COMERCIAL, CAP_VERIFICAR_DIAN}:
        condiciones.append(institucional)
    elif CAP_CONFIRMAR_PRODUCTO in suyas:
        # Sin bodega marcada responde por las dos, igual que el coordinador
        # sin punto de venta ve los seis puntos.
        if usuario.bodega:
            condiciones.append(and_(
                institucional, SolicitudNotaCredito.bodega == usuario.bodega,
            ))
        else:
            condiciones.append(institucional)

    return query.filter(or_(*condiciones))


def mensaje_falta_capacidad(db: Session, tenant_id: int, capacidad: str, accion: str) -> str:
    """
    El mensaje del 403, armado con quién puede AHORA MISMO — no con un
    nombre de área quemado en el texto, que dejaría de ser cierto apenas un
    administrador reconfigure esto desde Administración › Capacidades.
    """
    areas = sorted({
        o.area for o in quienes_tienen(db, tenant_id, capacidad) if o.area
    })
    if areas:
        quien = f"el área de {' o '.join(areas)}" if len(areas) <= 2 else "alguna de estas áreas: " + ", ".join(areas)
    else:
        quien = "quien tenga el permiso otorgado"
    return (
        f"{accion} lo hace {quien}. Un administrador puede otorgar este "
        "permiso desde Administración › Capacidades."
    )
