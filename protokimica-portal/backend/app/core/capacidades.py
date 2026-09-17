"""
Catálogo de capacidades y quién las tiene.

Ver `models/capacidad.py` para el porqué. En corto: hoy "quién autoriza
notas crédito" vive en una constante repetida en cinco módulos, y la única
excepción posible es cambiarle el área a una persona. Esto reemplaza esa
constante por una comprobación (`tiene`) contra una tabla que Administración
puede editar sin desplegar.

**El catálogo (`CAPACIDADES`) va en código, no en tabla.** Una capacidad que
alguien pudiera inventar desde la pantalla y que ningún `if` del portal
comprobara sería una promesa vacía — se otorgaría creyendo que protege algo,
y no protegería nada. Lo que SÍ se administra desde el portal es A QUIÉN se
le da cada una, que es exactamente lo que guarda `CapacidadOtorgada`.

**La migración va módulo por módulo, con su propia prueba comparativa antes
de borrar la constante vieja** (`tests/test_capacidades.py` para la garantía
general; cada módulo migrado suma la suya). `notas_credito` fue el primero
—ver `modules/notas_credito/permisos.py`—; los demás (`pqrs.cerrar`,
`mejora.validar_sgc`, `presupuesto.aprobar`, `presupuesto.pagar`) siguen
todavía con su constante de siempre.
"""
from datetime import datetime, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.capacidad import CapacidadOtorgada
from app.models.user import User

# El catálogo entero del portal. Corto a propósito — cada fila es un `if` que
# existe de verdad en algún módulo. Agregar una aquí sin agregar la
# comprobación del otro lado es la trampa que este diseño quiere evitar.
CAPACIDADES = {
    "pqrs.cerrar":             "Cerrar y reclasificar una PQRS",
    "mejora.validar_sgc":      "Validar la eficacia de una oportunidad de mejora (visto bueno del SGC)",
    "presupuesto.aprobar":     "Aprobar el presupuesto de un proyecto",
    "presupuesto.pagar":       "Registrar el pago de un ítem de presupuesto",
    "notas_credito.autorizar": "Autorizar o rechazar una solicitud de nota crédito",
    "notas_credito.registrar": "Registrar el número de la nota crédito ya emitida",
    # Las tres etapas de la cadena institucional. Van separadas de
    # `autorizar` porque son tres manos distintas en tres momentos: la bodega
    # dice si el producto llegó, Comercial si la devolución procede, y
    # Contabilidad si la factura tiene saldo ante la DIAN. Ver
    # `modules/notas_credito/flujo.py`.
    "notas_credito.confirmar_producto": "Confirmar que el producto devuelto llegó a la bodega",
    "notas_credito.aprobar_comercial":  "Aprobar comercialmente una nota crédito de venta institucional",
    "notas_credito.verificar_dian":     "Verificar ante la DIAN el saldo de la factura de una nota crédito",
}


def _validar(capacidad: str) -> None:
    if capacidad not in CAPACIDADES:
        raise ValueError(
            f"'{capacidad}' no está en core.capacidades.CAPACIDADES. "
            "Una capacidad que nadie declaró no protege nada — agrégala ahí "
            "primero, junto al `if` que la va a comprobar."
        )


def tiene(db: Session, usuario: User, capacidad: str) -> bool:
    """
    ¿Esta persona tiene esta capacidad, por su área o a título personal?

    La capacidad se valida SIEMPRE, incluso para `admin` — si el `admin`
    cortara antes de validar, `tiene(db, admin, "algo.que.no.existe")`
    respondería True en vez de avisar que esa capacidad no está declarada.
    Después de validar, `admin` siempre puede: es quien destraba las cosas
    cuando el responsable está de vacaciones, la misma excepción que ya
    existe en cada `permisos.py` del portal.
    """
    _validar(capacidad)
    if usuario.rol == "admin":
        return True

    return db.query(CapacidadOtorgada).filter(
        CapacidadOtorgada.tenant_id == usuario.tenant_id,
        CapacidadOtorgada.capacidad == capacidad,
        CapacidadOtorgada.revocada_en.is_(None),
        or_(
            CapacidadOtorgada.usuario_id == usuario.id,
            CapacidadOtorgada.area == usuario.area,
        ),
    ).first() is not None


def usuarios_con(db: Session, tenant_id: int, capacidad: str) -> list[User]:
    """
    Los usuarios ACTIVOS que tienen esta capacidad hoy, por área o a título
    personal.

    Devuelve usuarios y no solo correos porque a veces hay que filtrarlos por
    algo más: el aviso de «nota crédito por emitir» va al punto de venta de
    la solicitud, no a todo el que pueda registrarla.
    """
    _validar(capacidad)
    otorgamientos = quienes_tienen(db, tenant_id, capacidad)
    areas = {o.area for o in otorgamientos if o.area}
    usuarios_directos = {o.usuario_id for o in otorgamientos if o.usuario_id}
    if not areas and not usuarios_directos:
        return []

    usuarios = db.query(User).filter(
        User.tenant_id == tenant_id, User.activo.is_(True),
    ).all()
    return [u for u in usuarios if u.area in areas or u.id in usuarios_directos]


def correos_de(db: Session, tenant_id: int, capacidad: str) -> list[str]:
    """
    Los correos de todos los que tienen esta capacidad hoy — por área o a
    título personal — listos para un aviso.

    Sustituye a mandarle el correo a una sola área quemada en el código: si
    un administrador le otorga esta capacidad también a Aseguramiento, el
    aviso tiene que llegarle a Aseguramiento sin que nadie tenga que tocar el
    módulo que arma el correo.

    Vive aquí y no en `pqrs/notificaciones.py` a propósito: ese módulo es de
    PQRS, no de capacidades, y `core/` no puede depender de un módulo — sería
    la dependencia al revés.
    """
    return sorted({u.email for u in usuarios_con(db, tenant_id, capacidad) if u.email})


def quienes_tienen(db: Session, tenant_id: int, capacidad: str) -> list[CapacidadOtorgada]:
    """
    Los otorgamientos VIGENTES de una capacidad: la pregunta que hace un
    auditor («¿quién puede autorizar notas crédito, hoy?») respondida de un
    vistazo, en vez de revisar usuario por usuario.
    """
    _validar(capacidad)
    return db.query(CapacidadOtorgada).filter(
        CapacidadOtorgada.tenant_id == tenant_id,
        CapacidadOtorgada.capacidad == capacidad,
        CapacidadOtorgada.revocada_en.is_(None),
    ).all()


def _reactivar_o_ninguno(db: Session, existente: CapacidadOtorgada | None,
                         otorgada_por: int) -> CapacidadOtorgada | None:
    """
    Si ya hay una fila (vigente o revocada antes) para este otorgamiento, la
    devuelve lista para usar: vigente tal cual, o revocada se reactiva.

    Reactivar y no crear una fila nueva evita terminar con dos filas para el
    mismo (capacidad, área) — una revocada y otra vigente — que dejarían la
    pregunta «¿cuándo se otorgó esto?» con dos respuestas.
    """
    if existente is None:
        return None
    if existente.revocada_en is not None:
        existente.revocada_en = None
        existente.otorgada_por = otorgada_por
        existente.otorgada_en = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existente)
    return existente


def otorgar_a_area(db: Session, tenant_id: int, capacidad: str, area: str,
                   otorgada_por: int) -> CapacidadOtorgada:
    """
    El caso normal: toda un área tiene la capacidad, y se hereda sola cuando
    entra gente nueva a esa área.
    """
    _validar(capacidad)
    existente = db.query(CapacidadOtorgada).filter(
        CapacidadOtorgada.tenant_id == tenant_id,
        CapacidadOtorgada.capacidad == capacidad,
        CapacidadOtorgada.area == area,
    ).first()
    reactivado = _reactivar_o_ninguno(db, existente, otorgada_por)
    if reactivado is not None:
        return reactivado

    otorgamiento = CapacidadOtorgada(
        tenant_id=tenant_id, capacidad=capacidad, area=area,
        otorgada_por=otorgada_por,
    )
    db.add(otorgamiento)
    db.commit()
    db.refresh(otorgamiento)
    return otorgamiento


def otorgar_a_usuario(db: Session, tenant_id: int, capacidad: str, usuario_id: int,
                      otorgada_por: int) -> CapacidadOtorgada:
    """
    La excepción: una persona concreta tiene la capacidad aunque su área no
    la tenga. Queda con quién y cuándo — es lo que hace explicable la
    excepción cuando alguien pregunte por qué puede hacer esto.
    """
    _validar(capacidad)
    existente = db.query(CapacidadOtorgada).filter(
        CapacidadOtorgada.tenant_id == tenant_id,
        CapacidadOtorgada.capacidad == capacidad,
        CapacidadOtorgada.usuario_id == usuario_id,
    ).first()
    reactivado = _reactivar_o_ninguno(db, existente, otorgada_por)
    if reactivado is not None:
        return reactivado

    otorgamiento = CapacidadOtorgada(
        tenant_id=tenant_id, capacidad=capacidad, usuario_id=usuario_id,
        otorgada_por=otorgada_por,
    )
    db.add(otorgamiento)
    db.commit()
    db.refresh(otorgamiento)
    return otorgamiento


def revocar(db: Session, tenant_id: int, otorgamiento_id: int) -> None:
    """
    Marca la fila como revocada — NO la borra.

    Un borrado no se distingue de "esto nunca se otorgó", y la siembra que
    deja la tabla al día con las reglas base (`sembrar_capacidades_iniciales`)
    le devolvería a Contabilidad, en el próximo arranque, una capacidad que un
    administrador le quitó a propósito.
    """
    otorgamiento = db.query(CapacidadOtorgada).filter(
        CapacidadOtorgada.id == otorgamiento_id,
        CapacidadOtorgada.tenant_id == tenant_id,
        CapacidadOtorgada.revocada_en.is_(None),
    ).first()
    if otorgamiento:
        otorgamiento.revocada_en = datetime.now(timezone.utc)
        db.commit()


# ── Semilla: el estado base que un tenant nuevo debe traer ──────────────
#
# (capacidad, área que la tiene por defecto, de dónde salió esa regla)
# El origen es solo documentación — nadie lo lee en tiempo de ejecución.
# `notas_credito.*` ya YA MIGRÓ (ver `modules/notas_credito/permisos.py`):
# esta fila sigue aquí porque su trabajo no era "ayudar a migrar" sino ser el
# estado de arranque de un tenant nuevo, y ese sigue siendo el mismo — para
# los cuatro que faltan, además marca qué constante se podrá borrar el día
# que su propia prueba comparativa confirme que `tiene()` responde igual.
SEMILLA_INICIAL = [
    ("pqrs.cerrar",             "Servicio al Cliente", "pqrs/permisos.py::AREA_SERVICIO_CLIENTE (por migrar)"),
    ("mejora.validar_sgc",      "Calidad",              "mejora/permisos.py::AREA_SGC (por migrar)"),
    ("presupuesto.aprobar",     "Administración",       "master_planner/permisos.py::AREA_APRUEBA_PAGOS (por migrar)"),
    ("presupuesto.pagar",       "Tesorería",             "master_planner/permisos.py::AREA_REGISTRA_PAGOS (por migrar)"),
    ("notas_credito.autorizar", "Contabilidad",          "ya migrado — ver notas_credito/permisos.py"),
    ("notas_credito.registrar", "Contabilidad",          "ya migrado — ver notas_credito/permisos.py"),
    # La cadena institucional. Las bodegas arrancan con el ÁREA entera y no
    # con las dos personas encargadas a propósito: una etapa que nadie puede
    # atender deja la solicitud atascada sin que nadie sepa por qué, y eso es
    # peor que un correo de más. Para acotarlo a los dos coordinadores se
    # revoca el área y se otorga por nombre desde Administración ›
    # Capacidades, sin tocar código.
    ("notas_credito.confirmar_producto", "Logística",    "bodega La 65 — ver notas_credito/flujo.py"),
    ("notas_credito.confirmar_producto", "Producción",   "bodega Guayabal (operaciones) — ver notas_credito/flujo.py"),
    ("notas_credito.aprobar_comercial",  "Comercial",    "coordinación comercial — ver notas_credito/flujo.py"),
    ("notas_credito.verificar_dian",     "Contabilidad", "verificación ante la DIAN — ver notas_credito/flujo.py"),
]


def sembrar_capacidades_iniciales(db: Session, tenant_id: int, otorgada_por: int) -> None:
    """
    Deja la tabla con exactamente las reglas que ya rigen hoy por las
    constantes de cada módulo.

    Idempotente y solo agrega lo que falta — igual que
    `mejora.sembrar_catalogos`. La comprobación de "ya existe" mira TODAS las
    filas, vigentes o revocadas: si un administrador revocó a propósito una
    de estas capacidades base, sembrar otra vez no puede devolvérsela sola.
    """
    existentes = {
        (o.capacidad, o.area)
        for o in db.query(CapacidadOtorgada.capacidad, CapacidadOtorgada.area)
        .filter(CapacidadOtorgada.tenant_id == tenant_id, CapacidadOtorgada.area.isnot(None))
        .all()
    }
    for capacidad, area, _origen in SEMILLA_INICIAL:
        if (capacidad, area) not in existentes:
            otorgar_a_area(db, tenant_id, capacidad, area, otorgada_por)
