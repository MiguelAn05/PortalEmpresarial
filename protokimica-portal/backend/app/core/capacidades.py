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

**Fase 1 de la migración: esto no cambia el comportamiento de nada.** Ningún
módulo existente llama todavía a `tiene()` — siguen con su constante de
siempre. `sembrar_capacidades_iniciales()` dejó la tabla con exactamente las
mismas cinco reglas que ya rigen, para que el día que un módulo migre, la
prueba comparativa (`tests/test_capacidades.py`) demuestre que nadie perdió
un permiso en el camino.
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


# ── Semilla: las cinco reglas que hoy viven en una constante por módulo ──
#
# (capacidad, área que hoy la tiene quemada, módulo de origen)
# El módulo de origen es solo documentación — nadie lo lee en tiempo de
# ejecución — para que quien migre un módulo sepa qué constante puede borrar
# después de que la prueba comparativa confirme que `tiene()` responde igual.
SEMILLA_INICIAL = [
    ("pqrs.cerrar",             "Servicio al Cliente", "pqrs/permisos.py::AREA_SERVICIO_CLIENTE"),
    ("mejora.validar_sgc",      "Calidad",              "mejora/permisos.py::AREA_SGC"),
    ("presupuesto.aprobar",     "Administración",       "master_planner/permisos.py::AREA_APRUEBA_PAGOS"),
    ("presupuesto.pagar",       "Tesorería",             "master_planner/permisos.py::AREA_REGISTRA_PAGOS"),
    ("notas_credito.autorizar", "Contabilidad",          "notas_credito/permisos.py::AREA_AUTORIZADORA"),
    ("notas_credito.registrar", "Contabilidad",          "notas_credito/permisos.py::AREA_AUTORIZADORA"),
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
