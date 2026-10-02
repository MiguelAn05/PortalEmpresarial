"""
Base del sistema de permisos por capacidad: la tabla, `tiene()`, y que los
módulos le pregunten a ella y no al nombre de un área.

**Ya no queda ninguna constante de área decidiendo un permiso.** Mientras
existieron, este archivo comparaba `tiene()` contra cada una
(`AREA_SERVICIO_CLIENTE`, `AREA_SGC`, `AREA_APRUEBA_PAGOS`,
`AREA_REGISTRA_PAGOS`) para cada rol y área: esa comparación pasó, y fue la
garantía para borrarlas. Lo que se prueba ahora es el comportamiento nuevo:
con la semilla de arranque cada permiso lo tiene la misma área de siempre, y
otorgárselo a otra área —lo que antes exigía cambiar código— funciona sin
tocar nada más.
"""
import pytest

from app.core.capacidades import (
    CAPACIDADES, SEMILLA_INICIAL, otorgar_a_area, otorgar_a_usuario,
    quienes_tienen, revocar, sembrar_capacidades_iniciales, tiene,
)
from app.models.capacidad import CapacidadOtorgada
from app.models.user import User

# Las reglas reales de cada módulo: la prueba pregunta lo mismo que ellos.
from app.modules.mejora.permisos import es_sgc
from app.modules.master_planner.permisos import (
    puede_aprobar_pagos, puede_registrar_pagos, ve_todo,
)
from app.modules.pqrs.permisos import puede_gestionar_pqrs

# (capacidad, área que la tiene en la semilla, regla del módulo que la usa)
REGLAS = [
    ("pqrs.cerrar",         "Servicio al Cliente", puede_gestionar_pqrs),
    ("mejora.validar_sgc",  "Calidad",             es_sgc),
    ("presupuesto.aprobar", "Administración",      puede_aprobar_pagos),
    ("presupuesto.pagar",   "Tesorería",           puede_registrar_pagos),
]


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


# ── Cada regla del módulo responde según la tabla ────────────────────────

def _usuario_en_area(portal, area):
    """Un agente movido al área pedida, con su propia sesión."""
    db = portal.Session()
    usuario = db.get(User, portal.ids["logistica"])
    usuario.area = area
    db.commit()
    return db, usuario


@pytest.mark.parametrize("capacidad,area,regla", REGLAS)
def test_el_area_de_la_semilla_tiene_el_permiso(entorno, v, capacidad, area, regla):
    db, usuario = _usuario_en_area(entorno, area)
    v.check(f"{area} -> {capacidad}", regla(usuario) is True and tiene(db, usuario, capacidad))
    db.close()


@pytest.mark.parametrize("capacidad,area,regla", REGLAS)
def test_otra_area_no_lo_tiene(entorno, v, capacidad, area, regla):
    db, usuario = _usuario_en_area(entorno, "Logística")
    v.check(f"Logística no tiene {capacidad}", regla(usuario) is False)
    db.close()


@pytest.mark.parametrize("capacidad,area,regla", REGLAS)
def test_otorgarlo_a_otra_area_funciona_sin_tocar_codigo(entorno, v, capacidad, area, regla):
    """
    Lo que justifica todo esto: en otra empresa quien cierra una PQRS no se
    llama «Servicio al Cliente». Antes había que cambiar una constante y
    desplegar; ahora se otorga desde Administración.
    """
    db = entorno.Session()
    otorgar_a_area(db, entorno.tenant_id, capacidad, "Mercadeo", entorno.ids["admin"])
    db.close()
    db, usuario = _usuario_en_area(entorno, "Mercadeo")
    v.check(f"Mercadeo ahora tiene {capacidad}", regla(usuario) is True)
    db.close()


@pytest.mark.parametrize("capacidad,area,regla", REGLAS)
def test_revocarle_el_permiso_al_area_de_siempre_lo_quita(entorno, v, capacidad, area, regla):
    db = entorno.Session()
    for o in quienes_tienen(db, entorno.tenant_id, capacidad):
        revocar(db, entorno.tenant_id, o.id)
    db.close()
    db, usuario = _usuario_en_area(entorno, area)
    v.check(f"{area} ya no tiene {capacidad}", regla(usuario) is False)
    db.close()


def test_quien_aprueba_o_paga_ve_todos_los_proyectos(entorno, v):
    """La visibilidad del Master Planner también sale de las capacidades."""
    for area in ("Administración", "Tesorería"):
        db, usuario = _usuario_en_area(entorno, area)
        v.check(f"{area} ve todo", ve_todo(usuario) is True)
        db.close()
    db, usuario = _usuario_en_area(entorno, "Logística")
    v.check("Logística no", ve_todo(usuario) is False)
    db.close()


def test_el_mensaje_dice_a_quien_pedirselo(entorno, v):
    """Un 403 que no dice a quién acudir obliga a preguntar por chat."""
    entorno.como("logistica")
    r = entorno.post("/pqrs/1/cerrar", json={})
    if r.status_code == 403:
        v.check("nombra el área que lo hace", "Servicio al Cliente" in r.text, r.text[:200])


def test_me_trae_las_capacidades(entorno, v):
    entorno.como("calidad")
    r = entorno.get("/auth/me")
    v.check("Calidad trae la validación del SGC",
            "mejora.validar_sgc" in r.json()["capacidades"], r.json())
    v.check("y no cerrar PQRS", "pqrs.cerrar" not in r.json()["capacidades"])
    entorno.como("admin")
    v.check("admin las trae todas",
            set(entorno.get("/auth/me").json()["capacidades"]) == set(CAPACIDADES))


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
