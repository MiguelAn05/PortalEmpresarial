"""
El indicador «Gestión de OMP»: cada OMP viva se revisa cada mes.

Una OMP está al día en un mes si:
1. ninguna acción está vencida (contra su fecha ORIGINAL) ni se cumplió tarde;
2. tuvo algún avance en el mes (seguimiento, cambio de etapa, acción);
3. no pasó su fecha estimada de solución estando abierta.

Las fechas son fijas: agosto de 2026, evaluado con `ahora` en septiembre.
"""
from datetime import date, datetime, timezone

from app.models.mejora import AccionMejora, CambioMejora, Oportunidad, SeguimientoMejora
from app.modules.mejora import gestion

AREA = "Calidad"
AGO_1 = datetime(2026, 8, 1, tzinfo=timezone.utc)
SEPT = datetime(2026, 9, 10, tzinfo=timezone.utc)


def dia(d, mes=8):
    return datetime(2026, mes, d, 12, tzinfo=timezone.utc)


def _omp(db, entorno, codigo, creada=None, area=AREA, estado="ejecucion", **extra):
    omp = Oportunidad(
        tenant_id=entorno.tenant_id, titulo=f"OMP {codigo}", codigo=codigo, area=area,
        estado=estado, origen="auditoria", creado_en=creada or datetime(2026, 6, 1, tzinfo=timezone.utc),
        **extra,
    )
    db.add(omp)
    db.flush()
    return omp


def _seguimiento(db, omp, fecha):
    db.add(SeguimientoMejora(omp_id=omp.id, fecha=fecha, contenido="Avance del mes"))


def _accion(db, omp, **datos):
    db.add(AccionMejora(omp_id=omp.id, descripcion="Tarea", creado_en=datetime(2026, 6, 1, tzinfo=timezone.utc), **datos))


def _estado(db, omp, cuando, nuevo, anterior="ejecucion"):
    db.add(CambioMejora(omp_id=omp.id, campo="Estado", valor_anterior=anterior,
                        valor_nuevo=nuevo, fecha=cuando))


def _evaluar(entorno, mes=8, ahora=SEPT, area=AREA):
    db = entorno.Session()
    resultado = {e.codigo: e for e in gestion.evaluar_mes(db, entorno.tenant_id, area, 2026, mes, ahora=ahora)}
    db.close()
    return resultado


def _preparar(entorno, arma):
    db = entorno.Session()
    arma(db)
    db.commit()
    db.close()


# ── La regla, OMP por OMP ────────────────────────────────────────────

def test_con_seguimiento_y_plan_al_dia_esta_al_dia(entorno, v):
    def arma(db):
        omp = _omp(db, entorno, "A1")
        _seguimiento(db, omp, date(2026, 8, 14))
        _accion(db, omp, fecha_limite=dia(20), fecha_limite_original=dia(20),
                estado="cumplida", fecha_completada=dia(18))
    _preparar(entorno, arma)
    e = _evaluar(entorno)["A1"]
    v.check("al día", e.al_dia, e.motivos)


def test_una_omp_larga_sin_avances_en_el_mes_se_atrasa(entorno, v):
    """El caso que dejaba ciega la primera propuesta: OMP de un año, nada que venza en el mes."""
    def arma(db):
        omp = _omp(db, entorno, "LARGA", fecha_limite=datetime(2027, 6, 1, tzinfo=timezone.utc))
        _accion(db, omp, fecha_limite=datetime(2027, 5, 1, tzinfo=timezone.utc),
                fecha_limite_original=datetime(2027, 5, 1, tzinfo=timezone.utc))
    _preparar(entorno, arma)
    e = _evaluar(entorno)["LARGA"]
    v.check("atrasada", not e.al_dia)
    v.check("por falta de avances", e.motivos == ["sin avances en el mes"], e.motivos)


def test_la_misma_omp_larga_con_seguimiento_esta_al_dia(entorno, v):
    def arma(db):
        omp = _omp(db, entorno, "LARGA", fecha_limite=datetime(2027, 6, 1, tzinfo=timezone.utc))
        _seguimiento(db, omp, date(2026, 8, 30))
    _preparar(entorno, arma)
    v.check("al día", _evaluar(entorno)["LARGA"].al_dia)


def test_aplazar_la_fecha_no_limpia_el_atraso(entorno, v):
    """Se mide contra la fecha original: correr la fecha no mejora el indicador."""
    def arma(db):
        omp = _omp(db, entorno, "APLAZA")
        _seguimiento(db, omp, date(2026, 8, 5))
        _accion(db, omp, fecha_limite=dia(28, mes=10), fecha_limite_original=dia(10))
    _preparar(entorno, arma)
    e = _evaluar(entorno)["APLAZA"]
    v.check("atrasada", e.motivos == ["1 acción vencida"], e.motivos)


def test_cumplida_tarde_en_el_mes_cuenta_en_contra(entorno, v):
    def arma(db):
        omp = _omp(db, entorno, "TARDE")
        _accion(db, omp, fecha_limite=dia(5), fecha_limite_original=dia(5),
                estado="cumplida", fecha_completada=dia(20))
    _preparar(entorno, arma)
    e = _evaluar(entorno)["TARDE"]
    v.check("cumplida tarde", e.motivos == ["1 acción cumplida tarde"], e.motivos)


def test_cumplir_una_accion_es_un_avance(entorno, v):
    def arma(db):
        omp = _omp(db, entorno, "PLAN")
        _accion(db, omp, fecha_limite=dia(25), fecha_limite_original=dia(25),
                estado="cumplida", fecha_completada=dia(22))
    _preparar(entorno, arma)
    v.check("al día sin seguimiento escrito", _evaluar(entorno)["PLAN"].al_dia)


def test_pasarse_de_la_fecha_estimada_la_atrasa(entorno, v):
    def arma(db):
        omp = _omp(db, entorno, "PLAZO", fecha_limite=dia(15))
        _seguimiento(db, omp, date(2026, 8, 20))
    _preparar(entorno, arma)
    e = _evaluar(entorno)["PLAZO"]
    v.check("atrasada por plazo", e.motivos == ["pasó su fecha estimada de solución"], e.motivos)


def test_recien_registrada_no_se_le_exigen_avances(entorno, v):
    def arma(db):
        _omp(db, entorno, "NUEVA", creada=dia(25), estado="abierta")
    _preparar(entorno, arma)
    v.check("al día", _evaluar(entorno)["NUEVA"].al_dia)


def test_cerrada_antes_del_mes_no_cuenta(entorno, v):
    def arma(db):
        omp = _omp(db, entorno, "VIEJA", estado="cerrada",
                   fecha_cierre=datetime(2026, 7, 10, tzinfo=timezone.utc))
        _estado(db, omp, datetime(2026, 7, 10, tzinfo=timezone.utc), "cerrada")
    _preparar(entorno, arma)
    v.check("no está entre las del mes", "VIEJA" not in _evaluar(entorno))


def test_cerrada_en_el_mes_cuenta_y_el_cierre_es_un_avance(entorno, v):
    def arma(db):
        omp = _omp(db, entorno, "CIERRA", estado="cerrada", fecha_cierre=dia(12))
        _estado(db, omp, dia(12), "cerrada", anterior="verificacion")
    _preparar(entorno, arma)
    evaluaciones = _evaluar(entorno)
    v.check("cuenta en el mes", "CIERRA" in evaluaciones)
    v.check("y está al día", evaluaciones["CIERRA"].al_dia, evaluaciones.get("CIERRA"))


def test_descartada_todo_el_mes_no_cuenta_y_retomada_si(entorno, v):
    """Los meses descartada no se cobran como meses sin avances."""
    def arma(db):
        omp = _omp(db, entorno, "RETOMA", estado="analisis")
        _estado(db, omp, datetime(2026, 7, 1, tzinfo=timezone.utc), "descartada")
        _estado(db, omp, dia(10, mes=9), "analisis", anterior="descartada")
    _preparar(entorno, arma)
    v.check("agosto (descartada) no cuenta", "RETOMA" not in _evaluar(entorno, mes=8))
    v.check("septiembre (retomada) sí", "RETOMA" in _evaluar(entorno, mes=9, ahora=dia(30, mes=9)))


def test_a_mitad_de_mes_no_se_exigen_avances_todavia(entorno, v):
    def arma(db):
        _omp(db, entorno, "MITAD")
    _preparar(entorno, arma)
    e = _evaluar(entorno, mes=8, ahora=dia(10))["MITAD"]
    v.check("al día a mitad de mes", e.al_dia, e.motivos)


def test_solo_cuenta_las_del_area(entorno, v):
    def arma(db):
        _omp(db, entorno, "OTRA", area="Logística")
    _preparar(entorno, arma)
    v.check("Calidad no ve la de Logística", "OTRA" not in _evaluar(entorno))


def test_el_detalle_nombra_las_atrasadas_y_por_que(entorno, v):
    def arma(db):
        ok = _omp(db, entorno, "OK1")
        _seguimiento(db, ok, date(2026, 8, 3))
        _omp(db, entorno, "MAL1")
    _preparar(entorno, arma)
    db = entorno.Session()
    al_dia, total, detalle = gestion.resumir(
        gestion.evaluar_mes(db, entorno.tenant_id, AREA, 2026, 8, ahora=SEPT))
    db.close()
    v.check("1 de 2", (al_dia, total) == (1, 2), (al_dia, total))
    v.check("nombra la atrasada con su motivo", "MAL1 (sin avances en el mes)" in detalle, detalle)


# ── Conectado a Indicadores ──────────────────────────────────────────

def test_crear_en_todas_las_areas_no_duplica(entorno, v):
    entorno.como("admin")
    faltan = entorno.get("/indicadores/gestion-omp").json()["faltantes"]
    r = entorno.post("/indicadores/gestion-omp/crear-en-areas")
    v.check("crea en todas las que faltan", r.json()["creados"] == faltan, r.json())
    r = entorno.post("/indicadores/gestion-omp/crear-en-areas")
    v.check("la segunda vez no crea nada", r.json()["creados"] == [], r.json())
    v.check("ya no falta ninguna", entorno.get("/indicadores/gestion-omp").json()["faltantes"] == [])


def test_un_lider_no_crea_en_todas_las_areas(entorno, v):
    entorno.como("calidad")
    r = entorno.post("/indicadores/gestion-omp/crear-en-areas")
    v.check("403", r.status_code == 403, r.text[:200])


def test_sin_area_no_se_puede_crear_a_mano(entorno, v):
    entorno.como("admin")
    r = entorno.post("/indicadores", json={
        "nombre": "Gestión de OMP", "tipo_captura": "automatico",
        "fuente_automatica": "mejora_gestion_omp", "unidad": "porcentaje",
    })
    v.check("400", r.status_code == 400, r.text[:200])
    v.check("dice qué hacer", "área" in r.json()["detail"], r.json())


def test_recalcular_guarda_los_dos_numeros_y_el_detalle(entorno, v):
    def arma(db):
        ok = _omp(db, entorno, "OK1")
        _seguimiento(db, ok, date(2026, 8, 3))
        _omp(db, entorno, "MAL1")
    _preparar(entorno, arma)

    entorno.como("admin")
    entorno.post("/indicadores/gestion-omp/crear-en-areas")
    iid = next(i["id"] for i in entorno.get("/indicadores").json()
               if i["area"] == AREA and i["fuente_automatica"] == "mejora_gestion_omp")
    r = entorno.post(f"/indicadores/{iid}/calcular", params={"anio": 2026, "mes": 8})
    v.check("200", r.status_code == 200, r.text[:200])
    m = r.json()
    v.check("50 %", m["valor"] == 50, m)
    v.check("guarda 1 de 2 para acumular", (m["numerador"], m["denominador"]) == (1, 2), m)
    v.check("el análisis nombra la atrasada", "MAL1" in (m["analisis"] or ""), m)


def test_en_rojo_no_pide_una_omp_sobre_si_mismo(entorno, v):
    from app.models.indicadores import Indicador
    from app.modules.mejora.service import indicadores_en_rojo_sin_omp
    db = entorno.Session()
    ind = Indicador(tenant_id=entorno.tenant_id, nombre="Gestión de OMP", area=AREA,
                    tipo_captura="automatico", fuente_automatica="mejora_gestion_omp")
    otro = Indicador(tenant_id=entorno.tenant_id, nombre="Reprocesos", area=AREA, tipo_captura="valor")
    db.add_all([ind, otro])
    db.commit()
    sin_omp = indicadores_en_rojo_sin_omp(db, entorno.tenant_id, [ind.id, otro.id])
    v.check("excluye Gestión de OMP", ind.id not in sin_omp, sin_omp)
    v.check("los demás siguen apareciendo", otro.id in sin_omp, sin_omp)
    db.close()


def test_la_accion_guarda_su_fecha_original(entorno, v):
    entorno.como("admin")
    db = entorno.Session()
    omp = _omp(db, entorno, "API1")
    db.commit()
    oid = omp.id
    db.close()

    r = entorno.post(f"/mejora/{oid}/acciones", json={
        "descripcion": "Capacitar al equipo", "fecha_limite": "2026-08-10T00:00:00Z"})
    v.check("201", r.status_code == 201, r.text[:300])
    aid = r.json()["id"]
    v.check("nace con la original", (r.json()["fecha_limite_original"] or "").startswith("2026-08-10"), r.json())

    r = entorno.patch(f"/mejora/{oid}/acciones/{aid}", json={"fecha_limite": "2026-09-30T00:00:00Z"})
    v.check("aplazar no mueve la original",
            (r.json()["fecha_limite_original"] or "").startswith("2026-08-10"), r.json())
    v.check("y queda marcada como aplazada", r.json()["aplazada"] is True, r.json())
