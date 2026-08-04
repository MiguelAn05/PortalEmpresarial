"""
Indicadores automaticos: que cada calculador corra contra datos reales y
devuelva numerador/denominador coherentes.

Estos no pasan por la API — prueban directamente las funciones de calculo,
que es donde vive la logica delicada de cada indicador.
"""
from datetime import datetime, timezone

from app.models.master_planner import Proyecto, Tarea
from app.models.pqrs import PQRSSolicitud, PQRSEncuesta
from app.models.user import User
from app.modules.indicadores import fuentes


def test_fuentes_automaticas(entorno, v):
    db = entorno.Session()
    tenant_id = entorno.tenant_id
    u = db.get(User, entorno.ids["admin"])
    # Julio 2026 como periodo de prueba
    ANIO, MES = 2026, 7
    def d(dia, hora=12):
        return datetime(ANIO, MES, dia, hora, tzinfo=timezone.utc)

    # 4 PQRS radicadas en julio; 3 se cierran en julio, 2 dentro del plazo
    db.add_all([
        PQRSSolicitud(tenant_id=tenant_id, tipo="reclamo", cliente_nombre="C1", descripcion="x",
                      fecha_creacion=d(1), fecha_limite_sla=d(9), fecha_cierre=d(5)),   # a tiempo, 4 dias
        PQRSSolicitud(tenant_id=tenant_id, tipo="reclamo", cliente_nombre="C2", descripcion="x",
                      fecha_creacion=d(2), fecha_limite_sla=d(10), fecha_cierre=d(8)),  # a tiempo, 6 dias
        PQRSSolicitud(tenant_id=tenant_id, tipo="queja", cliente_nombre="C3", descripcion="x",
                      fecha_creacion=d(3), fecha_limite_sla=d(8), fecha_cierre=d(20)),  # tarde, 17 dias
        PQRSSolicitud(tenant_id=tenant_id, tipo="peticion", cliente_nombre="C4", descripcion="x",
                      fecha_creacion=d(15), fecha_limite_sla=d(30)),                    # abierta
    ])
    db.commit()


    r = fuentes.calcular("pqrs_recibidas", db, tenant_id, ANIO, MES)
    v.check("cuenta las PQRS del mes", r.valor == 4, r)

    r = fuentes.calcular("pqrs_reclamos", db, tenant_id, ANIO, MES)
    v.check("cuenta solo los reclamos", r.valor == 2, r)

    r = fuentes.calcular("pqrs_oportunidad_sla", db, tenant_id, ANIO, MES)
    v.check("oportunidad = 2 de 3 cerradas", r.numerador == 2 and r.denominador == 3, r)
    v.check("y da 66.67%", r.valor == 66.67, r)
    v.check("la abierta no entra en el denominador", r.denominador == 3, r)

    r = fuentes.calcular("pqrs_tiempo_cierre", db, tenant_id, ANIO, MES)
    v.check("tiempo promedio de cierre = 9 dias", r.valor == 9.0, r)
    v.check("y guarda con que se promedio", r.denominador == 3, r)

    # Un mes sin datos no debe dar 0%, debe dar "sin datos"
    r = fuentes.calcular("pqrs_oportunidad_sla", db, tenant_id, ANIO, 3)
    v.check("un mes vacio da None, no 0", r.valor is None, r)
    v.check("y lo explica", "Sin datos" in (r.detalle or ""), r)


    pqrs = db.query(PQRSSolicitud).all()
    db.add_all([
        PQRSEncuesta(pqrs_id=pqrs[0].id, calificacion=5, solucionada="si",
                     recomendaria=True, respondida_en=d(6)),
        PQRSEncuesta(pqrs_id=pqrs[1].id, calificacion=4, solucionada="si",
                     recomendaria=True, respondida_en=d(9)),
        PQRSEncuesta(pqrs_id=pqrs[2].id, calificacion=2, solucionada="no",
                     recomendaria=False, respondida_en=d(21)),
    ])
    db.commit()

    r = fuentes.calcular("pqrs_satisfaccion", db, tenant_id, ANIO, MES)
    v.check("satisfaccion promedio = 3.67", r.valor == 3.67, r)
    v.check("guarda suma y cantidad para acumular", r.numerador == 11 and r.denominador == 3, r)

    r = fuentes.calcular("pqrs_solucionadas", db, tenant_id, ANIO, MES)
    v.check("solucionadas = 2 de 3", r.numerador == 2 and r.denominador == 3, r)

    r = fuentes.calcular("pqrs_recomendaria", db, tenant_id, ANIO, MES)
    v.check("recomendaria = 2 de 3", r.numerador == 2 and r.denominador == 3, r)


    p1 = Proyecto(tenant_id=tenant_id, nombre="Portal", area="TICS", estado="en_ejecucion")
    p2 = Proyecto(tenant_id=tenant_id, nombre="ISO", area="Calidad", estado="en_ejecucion")
    p3 = Proyecto(tenant_id=tenant_id, nombre="Viejo", area="TICS", archivado=True)
    db.add_all([p1, p2, p3]); db.commit()

    db.add_all([
        # completada a tiempo
        Tarea(proyecto_id=p1.id, titulo="T1", avance_pct=100, estado="completada",
              fecha_fin=d(10), fecha_completada=d(8)),
        # completada tarde
        Tarea(proyecto_id=p1.id, titulo="T2", avance_pct=100, estado="completada",
              fecha_fin=d(10), fecha_completada=d(14)),
        # completada sin fecha comprometida: no es medible
        Tarea(proyecto_id=p2.id, titulo="T3", avance_pct=100, estado="completada",
              fecha_completada=d(9)),
        # abierta
        Tarea(proyecto_id=p2.id, titulo="T4", avance_pct=40, estado="en_proceso"),
    ])
    db.commit()

    r = fuentes.calcular("mp_cumplimiento_fechas", db, tenant_id, ANIO, MES)
    v.check("cumplimiento = 1 de 2", r.numerador == 1 and r.denominador == 2, r)
    v.check("la tarea sin fecha no cuenta", r.denominador == 2, r)
    v.check("da 50%", r.valor == 50.0, r)

    r = fuentes.calcular("mp_avance_proyectos", db, tenant_id, ANIO, MES)
    v.check("avance promedio ignora los archivados", r.denominador == 2, r)

    r = fuentes.calcular("mp_ejecucion_presupuestal", db, tenant_id, ANIO, MES)
    v.check("sin presupuesto cargado devuelve None", r.valor is None, r)


    for clave in fuentes.CATALOGO:
        try:
            res = fuentes.calcular(clave, db, tenant_id, ANIO, MES)
            ok = isinstance(res, fuentes.Resultado)
        except Exception as e:
            ok = False
            res = f"{type(e).__name__}: {e}"
        v.check(f"{clave}", ok, res)

    try:
        fuentes.calcular("no_existe", db, tenant_id, ANIO, MES)
        v.check("clave inexistente lanza ValueError", False, "no lanzo nada")
    except ValueError:
        v.check("clave inexistente lanza ValueError", True)


    cat = fuentes.catalogo_publico()
    v.check("el catalogo no expone las funciones", all("fn" not in f for f in cat))
    v.check("todas tienen clave, nombre, unidad y direccion",
          all(f.get("clave") and f.get("nombre") and f.get("unidad") and f.get("direccion") for f in cat))
    v.check("todas declaran su modulo de origen", all(f.get("modulo") for f in cat))
    v.check("las claves del catalogo publico coinciden con las internas",
          {f["clave"] for f in cat} == set(fuentes.CATALOGO))
    db.close()
