"""
Oportunidades de Mejora: el ciclo, los permisos y la verificación.

Lo que se prueba aquí es lo que distingue el módulo de una lista de tareas
con otro nombre: que no se avance sin causa raíz y que no se cierre sin
comparar el indicador. Si esas dos guardas se caen, el módulo deja de servir
para lo único que tiene que servir — demostrar que la mejora funcionó.
"""
from datetime import datetime, timezone

import pytest

from app.models.indicadores import Indicador, Medicion
from app.models.mejora import Oportunidad
from app.modules.mejora import service


def _indicador(entorno, direccion="arriba", area="Calidad"):
    db = entorno.Session()
    ind = Indicador(
        tenant_id=entorno.tenant_id, nombre="Cumplimiento de entregas",
        unidad="porcentaje", direccion=direccion, area=area, meta=95,
    )
    db.add(ind)
    db.commit()
    ind_id = ind.id
    db.close()
    return ind_id


def _medir(entorno, indicador_id, anio, mes, valor):
    db = entorno.Session()
    db.add(Medicion(indicador_id=indicador_id, anio=anio, mes=mes, valor=valor))
    db.commit()
    db.close()


def _crear(entorno, **extra):
    cuerpo = {
        "titulo": "Entregas por debajo de la meta",
        "origen": "indicador",
        "periodo_anio": 2026, "periodo_mes": 7,
        "valor_inicial": 62,
        "area": "Calidad",
    }
    cuerpo.update(extra)
    return entorno.post("/mejora", json=cuerpo)


# ── Crear ────────────────────────────────────────────────────────────

def test_un_lider_abre_una_omp(entorno):
    """Los líderes manejan la mejora de su área: hoy lo hacen en un Excel."""
    entorno.como("calidad")
    r = _crear(entorno, indicador_id=_indicador(entorno))

    assert r.status_code == 201, r.text
    assert r.json()["codigo"].startswith("OMP-"), r.json()
    assert r.json()["estado"] == "abierta"


def test_queda_registrado_quien_la_abrio(entorno):
    """En el Excel que usan hoy es una columna: quien la levanta responde."""
    entorno.como("calidad")
    r = _crear(entorno)

    assert r.json()["autor_nombre"] == "Cali", r.json()
    assert r.json()["creado_por"] == entorno.ids["calidad"]


def test_el_area_por_defecto_es_la_de_quien_la_abre(entorno):
    entorno.como("calidad")
    r = entorno.post("/mejora", json={"titulo": "Mejorar el empaque de pedidos"})

    assert r.status_code == 201, r.text
    assert r.json()["area"] == "Calidad"


def test_sin_periodo_no_se_puede_verificar_despues(entorno):
    """Sin el periodo no hay contra qué comparar: se avisa al crearla."""
    entorno.como("calidad")
    r = entorno.post("/mejora", json={
        "titulo": "Algo que mejorar en el proceso",
        "indicador_id": _indicador(entorno),
    })

    assert r.status_code == 400
    assert "periodo" in r.json()["detail"].lower()


def test_los_codigos_no_se_repiten(entorno):
    entorno.como("calidad")
    codigos = {_crear(entorno).json()["codigo"] for _ in range(3)}
    assert len(codigos) == 3, codigos


def test_el_consecutivo_sale_del_maximo_no_del_conteo(entorno):
    """El error de las PQRS, que no se repita aquí."""
    db = entorno.Session()
    anio = datetime.now(timezone.utc).year
    for codigo in [f"OMP-{anio}-0001", f"OMP-{anio}-0003"]:
        db.add(Oportunidad(tenant_id=entorno.tenant_id, titulo="Vieja", codigo=codigo))
    db.commit()

    assert service.generar_codigo(db, entorno.tenant_id) == f"OMP-{anio}-0004"
    db.close()


# ── Permisos ─────────────────────────────────────────────────────────

def test_un_agente_no_abre_oportunidades(entorno):
    entorno.como("logistica")
    r = _crear(entorno)
    # El módulo no es para agentes: se corta antes, en el acceso al módulo.
    assert r.status_code == 403, r.text


def test_gerencia_no_entra_al_modulo(entorno):
    """
    La mejora es trabajo de los líderes: a gerencia se le reporta el avance,
    no se le deja el tablero abierto. Se corta en el acceso al módulo, no
    endpoint por endpoint.
    """
    entorno.como("calidad")
    _crear(entorno)

    entorno.como("gerencia")
    assert entorno.get("/mejora").status_code == 403
    assert _crear(entorno).status_code == 403


def test_un_lider_no_ve_las_de_otra_area(entorno):
    entorno.como("calidad")
    omp_id = _crear(entorno, area="Calidad").json()["id"]

    entorno.como("tics")
    # 404 y no 403: un 403 confirmaría que existe y con qué número.
    assert entorno.get(f"/mejora/{omp_id}").status_code == 404
    assert all(o["area"] != "Calidad" for o in entorno.get("/mejora").json())


def test_las_de_toda_la_empresa_las_ve_cualquiera(entorno):
    """Sin área no son de nadie; esconderlas haría que nadie las trabaje."""
    entorno.como("admin")
    entorno.post("/mejora", json={"titulo": "Reducir el consumo de papel", "area": None})

    entorno.como("tics")
    assert any(o["area"] is None for o in entorno.get("/mejora").json())


# ── El ciclo ─────────────────────────────────────────────────────────

def test_no_se_ejecuta_sin_causa_raiz(entorno):
    """La guarda que evita que las acciones ataquen el síntoma."""
    entorno.como("calidad")
    omp_id = _crear(entorno).json()["id"]

    r = entorno.patch(f"/mejora/{omp_id}/estado", json={"estado": "ejecucion"})

    assert r.status_code == 400
    assert "causa raíz" in r.json()["detail"].lower()


def test_con_causa_raiz_si_avanza(entorno):
    entorno.como("calidad")
    omp_id = _crear(entorno).json()["id"]
    entorno.patch(f"/mejora/{omp_id}", json={"causa_raiz": "El proveedor entrega tarde."})

    r = entorno.patch(f"/mejora/{omp_id}/estado", json={"estado": "ejecucion"})

    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "ejecucion"


def test_no_se_verifica_sin_acciones(entorno):
    entorno.como("calidad")
    omp_id = _crear(entorno).json()["id"]

    r = entorno.patch(f"/mejora/{omp_id}/estado", json={"estado": "verificacion"})

    assert r.status_code == 400
    assert "acciones" in r.json()["detail"].lower()


def test_no_se_cierra_sin_verificar(entorno):
    """La observación clásica de auditoría: cerrado sin saber si sirvió."""
    entorno.como("calidad")
    omp_id = _crear(entorno).json()["id"]

    r = entorno.patch(f"/mejora/{omp_id}/estado", json={"estado": "cerrada"})

    assert r.status_code == 400
    assert "verificar" in r.json()["detail"].lower()


def test_una_cerrada_no_se_reabre(entorno):
    entorno.como("calidad")
    omp_id = _crear(entorno).json()["id"]
    entorno.post(f"/mejora/{omp_id}/verificacion", json={"eficaz": True})
    entorno.patch(f"/mejora/{omp_id}/estado", json={"estado": "cerrada"})

    r = entorno.patch(f"/mejora/{omp_id}/estado", json={"estado": "ejecucion"})

    assert r.status_code == 400
    assert "nueva" in r.json()["detail"].lower()


# ── Acciones ─────────────────────────────────────────────────────────

def test_el_avance_sale_de_las_acciones(entorno):
    entorno.como("calidad")
    omp_id = _crear(entorno).json()["id"]

    for texto in ["Hablar con el proveedor", "Ajustar el instructivo"]:
        entorno.post(f"/mejora/{omp_id}/acciones", json={"descripcion": texto})

    acciones = entorno.get(f"/mejora/{omp_id}").json()["acciones"]
    entorno.patch(f"/mejora/{omp_id}/acciones/{acciones[0]['id']}",
                  json={"completada": True})

    detalle = entorno.get(f"/mejora/{omp_id}").json()
    assert detalle["avance_pct"] == 50.0, detalle["avance_pct"]
    assert detalle["acciones_completadas"] == 1


def test_completar_una_accion_deja_la_fecha(entorno):
    entorno.como("calidad")
    omp_id = _crear(entorno).json()["id"]
    accion = entorno.post(f"/mejora/{omp_id}/acciones",
                          json={"descripcion": "Revisar el procedimiento"}).json()

    r = entorno.patch(f"/mejora/{omp_id}/acciones/{accion['id']}",
                      json={"completada": True})

    assert r.json()["fecha_completada"] is not None
    # Y al desmarcarla se borra: si no, quedaría una fecha de algo sin hacer.
    r = entorno.patch(f"/mejora/{omp_id}/acciones/{accion['id']}",
                      json={"completada": False})
    assert r.json()["fecha_completada"] is None


def test_una_omp_cerrada_no_admite_acciones_nuevas(entorno):
    entorno.como("calidad")
    omp_id = _crear(entorno).json()["id"]
    entorno.post(f"/mejora/{omp_id}/verificacion", json={"eficaz": True})
    entorno.patch(f"/mejora/{omp_id}/estado", json={"estado": "cerrada"})

    r = entorno.post(f"/mejora/{omp_id}/acciones", json={"descripcion": "Otra cosa más"})
    assert r.status_code == 400


# ── Verificación de eficacia ─────────────────────────────────────────

@pytest.mark.parametrize("direccion,inicial,nuevo,esperado", [
    ("arriba", 62, 88, True),    # subir la satisfacción es bueno
    ("arriba", 62, 55, False),
    ("abajo", 12, 4, True),      # bajar los reprocesos es bueno
    ("abajo", 12, 20, False),
    ("arriba", 62, 62, False),   # quedarse igual no es haber mejorado
])
def test_mejorar_depende_de_hacia_donde_mejora(entorno, direccion, inicial, nuevo, esperado):
    db = entorno.Session()
    ind = db.get(Indicador, _indicador(entorno, direccion=direccion))
    assert service.evaluar_mejora(ind, inicial, nuevo) is esperado
    db.close()


def test_sin_la_medicion_del_mes_siguiente_todavia_no_se_puede(entorno):
    """No es un error: es que hay que esperar el cierre del mes."""
    entorno.como("calidad")
    ind_id = _indicador(entorno)
    omp_id = _crear(entorno, indicador_id=ind_id).json()["id"]

    r = entorno.get(f"/mejora/{omp_id}/verificacion").json()

    assert r["hay_medicion"] is False
    assert r["periodo_esperado"] == {"anio": 2026, "mes": 8}


def test_cuando_llega_la_medicion_el_portal_propone_el_resultado(entorno):
    entorno.como("calidad")
    ind_id = _indicador(entorno, direccion="arriba")
    omp_id = _crear(entorno, indicador_id=ind_id).json()["id"]
    _medir(entorno, ind_id, 2026, 8, 91)      # el mes siguiente al que falló

    r = entorno.get(f"/mejora/{omp_id}/verificacion").json()

    assert r["hay_medicion"] is True
    assert float(r["valor_inicial"]) == 62
    assert float(r["valor_nuevo"]) == 91
    assert r["mejoro"] is True


def test_diciembre_verifica_contra_enero_del_ano_siguiente(entorno):
    assert service.periodo_siguiente(2026, 12) == (2027, 1)
    assert service.periodo_siguiente(2026, 7) == (2026, 8)


def test_si_no_fue_eficaz_vuelve_a_analisis(entorno):
    """No se cierra: el problema sigue ahí."""
    entorno.como("calidad")
    omp_id = _crear(entorno).json()["id"]

    r = entorno.post(f"/mejora/{omp_id}/verificacion",
                     json={"eficaz": False, "nota": "El indicador siguió cayendo."})

    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "analisis"
    assert r.json()["eficaz"] is False


# ── Indicadores en rojo sin atender ──────────────────────────────────

def test_un_rojo_con_omp_abierta_ya_no_cuenta_como_desatendido(entorno):
    entorno.como("calidad")
    ind_id = _indicador(entorno)
    otro_id = _indicador(entorno)
    _crear(entorno, indicador_id=ind_id)

    db = entorno.Session()
    sin_atender = service.indicadores_en_rojo_sin_omp(
        db, entorno.tenant_id, [ind_id, otro_id])
    db.close()

    assert sin_atender == [otro_id]


def test_una_omp_cerrada_deja_el_indicador_desatendido_otra_vez(entorno):
    """Si el problema vuelve, tiene que volver a aparecer como desatendido."""
    entorno.como("calidad")
    ind_id = _indicador(entorno)
    omp_id = _crear(entorno, indicador_id=ind_id).json()["id"]
    entorno.post(f"/mejora/{omp_id}/verificacion", json={"eficaz": True})
    entorno.patch(f"/mejora/{omp_id}/estado", json={"estado": "cerrada"})

    db = entorno.Session()
    sin_atender = service.indicadores_en_rojo_sin_omp(db, entorno.tenant_id, [ind_id])
    db.close()

    assert sin_atender == [ind_id]


# ── Borrar vs descartar ──────────────────────────────────────────────

def test_lo_que_no_funciono_se_descarta_no_se_borra(entorno):
    entorno.como("calidad")
    omp_id = _crear(entorno).json()["id"]

    # Un líder no borra: el historial de mejora es lo que se audita.
    assert entorno.delete(f"/mejora/{omp_id}").status_code == 403
    r = entorno.patch(f"/mejora/{omp_id}/estado", json={"estado": "descartada"})
    assert r.status_code == 200
    assert r.json()["estado"] == "descartada"
