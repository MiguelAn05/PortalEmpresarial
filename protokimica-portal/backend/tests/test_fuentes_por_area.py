"""
Los indicadores automáticos del Master Planner se miden por área.

El defecto era visible desde el tablero: «Avance promedio de proyectos»
puesto en TICS, en Calidad y en Mercadeo mostraba EXACTAMENTE el mismo
número, porque promediaba los proyectos de toda la empresa. Un indicador que
da igual sin importar de quién sea no mide a nadie, y nadie puede responder
por él.

Sin área se sigue midiendo toda la empresa: eso es lo que quiere un indicador
de gerencia, y es lo que ya tienen los indicadores que existen hoy.

La diferencia entre las dos formas de acotar es lo que más importa aquí:
  - lo que se PROMEDIA cuenta los proyectos en los que el área participa;
  - lo que se SUMA o se cuenta se atribuye solo al área responsable, o la
    empresa terminaría sumando el mismo proyecto varias veces.
"""
from datetime import datetime, timezone

from app.models.master_planner import Proyecto, ProyectoArea
from app.modules.indicadores import fuentes

ANIO, MES = 2026, 7


def _proyecto(db, tenant_id, nombre, area, avance_por_tarea=None, **extra):
    p = Proyecto(tenant_id=tenant_id, nombre=nombre, area=area, **extra)
    db.add(p)
    db.commit()
    return p


def _escenario(entorno):
    """
    Tres proyectos: uno de TICS, uno de Calidad, y uno de Calidad donde TICS
    participa — el caso que distingue las dos formas de acotar.
    """
    db = entorno.Session()
    tid = entorno.tenant_id

    de_tics = _proyecto(db, tid, "Portal interno", "TICS")
    de_calidad = _proyecto(db, tid, "Auditoría anual", "Calidad")
    compartido = _proyecto(db, tid, "Trazabilidad", "Calidad")
    db.add(ProyectoArea(proyecto_id=compartido.id, area="TICS"))
    db.commit()

    return db, tid, {"tics": de_tics, "calidad": de_calidad, "compartido": compartido}


def test_el_avance_se_mide_con_los_proyectos_del_area(entorno, v):
    db, tid, p = _escenario(entorno)

    de_tics = fuentes.calcular("mp_avance_proyectos", db, tid, ANIO, MES, area="TICS")
    de_calidad = fuentes.calcular("mp_avance_proyectos", db, tid, ANIO, MES, area="Calidad")

    # TICS lidera uno y participa en otro; Calidad lidera dos.
    v.check("TICS mide dos proyectos", de_tics.denominador == 2, de_tics)
    v.check("Calidad mide dos", de_calidad.denominador == 2, de_calidad)
    v.check("y el detalle dice de quién son", "TICS" in (de_tics.detalle or ""), de_tics)
    db.close()


def test_sin_area_se_sigue_midiendo_toda_la_empresa(entorno, v):
    """Es lo que quiere un indicador de gerencia, y lo que ya existe hoy."""
    db, tid, _ = _escenario(entorno)

    r = fuentes.calcular("mp_avance_proyectos", db, tid, ANIO, MES)
    v.check("entran los tres", r.denominador == 3, r)
    db.close()


def test_un_area_sin_proyectos_queda_sin_dato_y_no_en_cero(entorno, v):
    """Un cero diría «no avanzaron», y lo cierto es que no hay qué medir."""
    db, tid, _ = _escenario(entorno)

    r = fuentes.calcular("mp_avance_proyectos", db, tid, ANIO, MES, area="Logística")
    v.check("sin dato", r.valor is None, r)
    v.check("y lo explica nombrando el área", "Logística" in (r.detalle or ""), r)
    db.close()


def test_el_presupuesto_se_le_atribuye_solo_al_area_responsable(entorno, v):
    """
    Aquí NO entran las áreas participantes: si el proyecto compartido contara
    para las dos, sumar las áreas daría más plata de la que existe.
    """
    db, tid, p = _escenario(entorno)
    from app.models.master_planner import ItemPresupuesto
    db.add(ItemPresupuesto(proyecto_id=p["compartido"].id, concepto="Equipos",
                           valor_unitario=1000, cantidad=1, valor_aprobado=1000))
    db.commit()

    de_tics = fuentes.calcular("mp_ejecucion_presupuestal", db, tid, ANIO, MES, area="TICS")
    de_calidad = fuentes.calcular("mp_ejecucion_presupuestal", db, tid, ANIO, MES, area="Calidad")

    v.check("TICS no carga con el presupuesto del proyecto de Calidad",
            de_tics.denominador in (0, None), de_tics)
    v.check("Calidad sí, que es la responsable", de_calidad.denominador == 1000, de_calidad)
    db.close()


def test_los_proyectos_cerrados_se_cuentan_una_sola_vez(entorno, v):
    db, tid, p = _escenario(entorno)
    p["compartido"].fecha_fin_real = datetime(ANIO, MES, 10, tzinfo=timezone.utc)
    db.commit()

    de_tics = fuentes.calcular("mp_proyectos_cerrados", db, tid, ANIO, MES, area="TICS")
    de_calidad = fuentes.calcular("mp_proyectos_cerrados", db, tid, ANIO, MES, area="Calidad")

    v.check("no se le cuenta a la participante", de_tics.valor == 0, de_tics)
    v.check("se le cuenta a la responsable", de_calidad.valor == 1, de_calidad)
    db.close()


def test_el_catalogo_declara_cuales_aceptan_area(entorno, v):
    """
    La pantalla lo lee de aquí para decir qué va a medir el indicador. Si una
    fuente acota por área y no lo declara, el formulario promete un número de
    toda la empresa y entrega otro.
    """
    catalogo = {f["clave"]: f for f in fuentes.catalogo_publico()}
    for clave in ("mp_avance_proyectos", "mp_cumplimiento_fechas",
                  "mp_ejecucion_presupuestal", "mp_proyectos_cerrados"):
        v.check(f"{clave} acepta área", catalogo[clave].get("acepta_area") is True, catalogo[clave])

    v.check("y no se vuelven obligatorias por área",
            not any(catalogo[c].get("por_area") for c in catalogo if c.startswith("mp_")))
    v.check("la de gestión de OMP sí sigue exigiéndola",
            catalogo[fuentes.CLAVE_GESTION_OMP]["por_area"] is True)
