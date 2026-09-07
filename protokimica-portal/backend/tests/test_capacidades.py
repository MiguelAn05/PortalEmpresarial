"""
Base del sistema de permisos por capacidad: la tabla, `tiene()`, y la prueba
que hace segura la migración de cada módulo.

**`notas_credito` ya migró** (ver `modules/notas_credito/permisos.py`) y por
eso ya no aparece aquí: su comparación contra la constante vieja vivió en
este archivo hasta el día que se borró esa constante, y quedó su propia
prueba (`tests/test_notas_credito.py`) verificando el comportamiento nuevo.

Los cuatro que faltan siguen preguntando por su constante de siempre
(`AREA_SERVICIO_CLIENTE`, `AREA_SGC`, `AREA_APRUEBA_PAGOS`,
`AREA_REGISTRA_PAGOS`). Lo que se prueba aquí es que, sembrada la tabla,
`tiene()` responde EXACTAMENTE lo mismo que esas cuatro funciones para
cualquier combinación de rol y área — la garantía que permitirá borrar cada
constante, una por una, sin que nadie pierda un permiso en el camino.
"""
import pytest

from app.core.capacidades import (
    CAPACIDADES, SEMILLA_INICIAL, otorgar_a_area, otorgar_a_usuario,
    quienes_tienen, revocar, sembrar_capacidades_iniciales, tiene,
)
from app.models.capacidad import CapacidadOtorgada
from app.models.user import User

# Las mismas cuatro reglas, leídas de los módulos reales — no reescritas a
# mano — para que esta prueba se rompa sola si alguna cambia de área y nadie
# actualizó la semilla.
from app.modules.mejora.permisos import AREA_SGC, es_sgc
from app.modules.master_planner.permisos import (
    AREA_APRUEBA_PAGOS, AREA_REGISTRA_PAGOS,
    puede_aprobar_pagos, puede_registrar_pagos,
)
from app.modules.pqrs.permisos import (
    AREA_SERVICIO_CLIENTE, es_servicio_al_cliente,
)


def _sembrar(portal):
    db = portal.Session()
    sembrar_capacidades_iniciales(db, portal.tenant_id, portal.ids["admin"])
    db.close()


# ── El catálogo existe y cada capacidad tiene su comprobación ────────────

def test_las_capacidades_de_la_semilla_estan_en_el_catalogo(v):
    """
    Una capacidad sembrada que no estuviera en CAPACIDADES sería un
    otorgamiento a algo que ningún `if` del portal comprueba: una promesa
    vacía. `tiene()` la rechazaría con ValueError, así que si esto pasa la
    semilla está mal escrita.
    """
    for capacidad, _area, _origen in SEMILLA_INICIAL:
        v.check(f"'{capacidad}' está declarada", capacidad in CAPACIDADES, capacidad)


def test_pedir_una_capacidad_inexistente_revienta(entorno, v):
    """
    Mejor un error claro al arrancar que un `tiene()` que silenciosamente
    siempre dice que no — eso sería un permiso que nadie sabe que no existe.
    """
    portal = entorno
    db = portal.Session()
    admin = db.get(User, portal.ids["admin"])
    with pytest.raises(ValueError, match="no está en"):
        tiene(db, admin, "algo.que.nadie.declaro")
    db.close()


# ── tiene() reproduce las cinco reglas, para cada rol y área de prueba ───

@pytest.mark.parametrize("clave,area_usuario,capacidad,funcion_vieja", [
    ("calidad",   "Calidad",   "mejora.validar_sgc",  es_sgc),
    ("calidad",   "Calidad",   "pqrs.cerrar",         es_servicio_al_cliente),
    ("logistica", "Logística", "presupuesto.aprobar", puede_aprobar_pagos),
    ("logistica", "Logística", "presupuesto.pagar",   puede_registrar_pagos),
])
def test_tiene_coincide_con_area_ajena(entorno, v, clave, area_usuario, capacidad, funcion_vieja):
    """Alguien de un área que NO tiene la capacidad: los dos deben decir que no."""
    portal = entorno
    _sembrar(portal)
    db = portal.Session()
    usuario = db.get(User, portal.ids[clave])
    usuario.area = area_usuario
    db.commit()

    esperado = funcion_vieja(usuario)
    obtenido = tiene(db, usuario, capacidad)
    db.close()

    nombre = getattr(funcion_vieja, "__name__", "regla")
    v.check(
        f"{clave} ({area_usuario}) vs {capacidad}: {nombre}={esperado} tiene()={obtenido}",
        esperado == obtenido, (esperado, obtenido),
    )


@pytest.mark.parametrize("capacidad,area_regla,funcion_vieja", [
    ("mejora.validar_sgc",  AREA_SGC,               es_sgc),
    ("pqrs.cerrar",         AREA_SERVICIO_CLIENTE,  es_servicio_al_cliente),
    ("presupuesto.aprobar", AREA_APRUEBA_PAGOS,     puede_aprobar_pagos),
    ("presupuesto.pagar",   AREA_REGISTRA_PAGOS,    puede_registrar_pagos),
])
def test_tiene_coincide_con_el_area_dueña(entorno, v, capacidad, area_regla, funcion_vieja):
    """Alguien del área que SÍ tiene la capacidad: los dos deben decir que sí."""
    portal = entorno
    _sembrar(portal)
    db = portal.Session()
    usuario = db.get(User, portal.ids["logistica"])   # rol agente, cambia de área
    usuario.area = area_regla
    db.commit()

    esperado = funcion_vieja(usuario)
    obtenido = tiene(db, usuario, capacidad)
    db.close()

    nombre = getattr(funcion_vieja, "__name__", "regla")
    v.check(
        f"{area_regla} vs {capacidad}: {nombre}={esperado} tiene()={obtenido}",
        esperado is True and obtenido is True, (esperado, obtenido),
    )


@pytest.mark.parametrize("capacidad", list(CAPACIDADES))
def test_admin_siempre_tiene_todo(entorno, v, capacidad):
    """La misma excepción que ya existe en cada permisos.py del portal."""
    portal = entorno
    _sembrar(portal)
    db = portal.Session()
    admin = db.get(User, portal.ids["admin"])
    v.check(f"admin tiene {capacidad}", tiene(db, admin, capacidad) is True)
    db.close()


def test_gerencia_no_hereda_capacidades_de_nadie(entorno, v):
    """
    Gerencia ve todo el portal sin límite de área, pero no modifica nada. Una
    capacidad otorgada a un área no debe colársele por ningún lado.
    """
    portal = entorno
    _sembrar(portal)
    db = portal.Session()
    gerencia = db.get(User, portal.ids["gerencia"])
    v.check("gerencia no autoriza notas crédito",
            tiene(db, gerencia, "notas_credito.autorizar") is False)
    db.close()


# ── La excepción: otorgar a una persona sin tocar su área ────────────────

def test_otorgar_a_una_persona_no_le_cambia_el_area(entorno, v):
    """
    Es justo el caso que las constantes no resolvían: alguien de Logística
    necesita autorizar notas crédito sin ser de Contabilidad, y sin que eso
    le dé también todo lo demás que Contabilidad puede hacer en otros
    módulos.
    """
    portal = entorno
    db = portal.Session()
    logistica = db.get(User, portal.ids["logistica"])   # área Logística, se queda así
    v.check("antes de otorgar, no puede",
            tiene(db, logistica, "notas_credito.autorizar") is False)

    otorgar_a_usuario(db, portal.tenant_id, "notas_credito.autorizar",
                      logistica.id, portal.ids["admin"])

    v.check("después de otorgar, sí puede",
            tiene(db, logistica, "notas_credito.autorizar") is True)
    v.check("pero su área sigue siendo la misma",
            logistica.area == "Logística", logistica.area)
    v.check("y OTRA capacidad de Contabilidad sigue sin tenerla",
            tiene(db, logistica, "presupuesto.pagar") is False)
    db.close()


def test_otorgar_dos_veces_no_duplica(entorno, v):
    portal = entorno
    db = portal.Session()
    otorgar_a_area(db, portal.tenant_id, "notas_credito.autorizar", "Aseguramiento", portal.ids["admin"])
    otorgar_a_area(db, portal.tenant_id, "notas_credito.autorizar", "Aseguramiento", portal.ids["admin"])
    filas = quienes_tienen(db, portal.tenant_id, "notas_credito.autorizar")
    db.close()
    v.check("una sola fila para el mismo otorgamiento",
            len([f for f in filas if f.area == "Aseguramiento"]) == 1, filas)


def test_quienes_tienen_muestra_areas_y_personas_juntas(entorno, v):
    """La pregunta de auditoría: «¿quién puede?», de un vistazo."""
    portal = entorno
    db = portal.Session()
    otorgar_a_area(db, portal.tenant_id, "notas_credito.autorizar", "Contabilidad", portal.ids["admin"])
    otorgar_a_usuario(db, portal.tenant_id, "notas_credito.autorizar",
                      portal.ids["logistica"], portal.ids["admin"])
    filas = quienes_tienen(db, portal.tenant_id, "notas_credito.autorizar")
    db.close()

    v.check("aparecen los dos otorgamientos", len(filas) == 2, filas)
    v.check("uno por área", any(f.area == "Contabilidad" for f in filas), filas)
    v.check("uno por persona", any(f.usuario_id == portal.ids["logistica"] for f in filas), filas)


def test_revocar_quita_la_capacidad(entorno, v):
    portal = entorno
    db = portal.Session()
    otorgamiento = otorgar_a_usuario(db, portal.tenant_id, "notas_credito.autorizar",
                                     portal.ids["logistica"], portal.ids["admin"])
    logistica = db.get(User, portal.ids["logistica"])
    v.check("antes de revocar, puede", tiene(db, logistica, "notas_credito.autorizar") is True)

    revocar(db, portal.tenant_id, otorgamiento.id)
    v.check("después de revocar, no puede",
            tiene(db, logistica, "notas_credito.autorizar") is False)
    db.close()


# ── La semilla es idempotente ─────────────────────────────────────────────

def test_sembrar_dos_veces_no_duplica(entorno, v):
    """
    Igual que `mejora.sembrar_catalogos`: una siembra que reescribiera le
    borraría a Administración lo que ya hubiera otorgado o revocado a mano.
    """
    portal = entorno
    db = portal.Session()
    sembrar_capacidades_iniciales(db, portal.tenant_id, portal.ids["admin"])
    primera = db.query(CapacidadOtorgada).count()
    sembrar_capacidades_iniciales(db, portal.tenant_id, portal.ids["admin"])
    segunda = db.query(CapacidadOtorgada).count()
    db.close()
    v.check("no crece al sembrar otra vez", primera == segunda, (primera, segunda))


def test_sembrar_no_pisa_una_revocacion_manual(entorno, v):
    """
    El caso que de verdad importa: Contabilidad tenía la capacidad, un
    administrador se la quitó a propósito, y sembrar otra vez —al arrancar,
    o al pedir el catálogo— NO puede devolvérsela sola.
    """
    portal = entorno
    db = portal.Session()
    sembrar_capacidades_iniciales(db, portal.tenant_id, portal.ids["admin"])
    otorgamiento = next(
        f for f in quienes_tienen(db, portal.tenant_id, "notas_credito.autorizar")
        if f.area == "Contabilidad"
    )
    revocar(db, portal.tenant_id, otorgamiento.id)

    sembrar_capacidades_iniciales(db, portal.tenant_id, portal.ids["admin"])
    filas = quienes_tienen(db, portal.tenant_id, "notas_credito.autorizar")
    db.close()

    v.check("Contabilidad sigue sin la capacidad",
            not any(f.area == "Contabilidad" for f in filas), filas)
