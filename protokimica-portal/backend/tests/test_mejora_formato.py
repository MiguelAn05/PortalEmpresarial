"""
Lo que el formato RCN-F-13 le exige al módulo de Mejora.

El Excel oficial del SGC es la fuente de verdad del proceso, y el módulo
tiene que reemplazarlo sin perder información. Aquí se prueba lo que ese
acople trajo: los catálogos, el tratamiento que decide qué campos aplican,
el consecutivo por proceso, los seguimientos y la validación de Calidad.

Las pruebas del ciclo básico —causa raíz, eficacia, permisos por área— viven
en `test_mejora.py`.
"""
from datetime import date

import pytest

from app.models.mejora import Oportunidad
from app.modules.mejora import service
from app.modules.mejora.catalogos import limpiar_no_aplica


def _crear(entorno, **extra):
    cuerpo = {"titulo": "Entregas por debajo de la meta", "origen": "otro",
              "area": "Calidad"}
    cuerpo.update(extra)
    return entorno.post("/mejora", json=cuerpo)


def _catalogos(entorno):
    return entorno.get("/mejora/catalogos").json()


def _id_de(catalogos, tipo, nombre):
    return next(i["id"] for i in catalogos[tipo] if i["nombre"] == nombre)


def _tratamiento(entorno, codigo):
    catalogos = _catalogos(entorno)
    return next(t["id"] for t in catalogos["tratamiento"] if t["codigo"] == codigo)


# ── Catálogos ────────────────────────────────────────────────────────

def test_los_catalogos_se_siembran_solos(entorno):
    """
    Una empresa recién instalada tiene que poder abrir una acción sin que
    nadie corra un script a mano.
    """
    entorno.como("calidad")
    catalogos = _catalogos(entorno)

    assert len(catalogos["proceso"]) == 17, catalogos["proceso"]
    assert len(catalogos["fuente"]) == 9
    assert {t["codigo"] for t in catalogos["tratamiento"]} == {"OMP", "AC", "AM"}


def test_los_catalogos_traen_lo_que_dice_la_hoja_listado(entorno):
    entorno.como("calidad")
    catalogos = _catalogos(entorno)

    procesos = [p["nombre"] for p in catalogos["proceso"]]
    assert "TIC's" in procesos
    assert "SGAmbiental" in procesos
    fuentes = [f["nombre"] for f in catalogos["fuente"]]
    assert "Revisión por la dirección" in fuentes
    assert "Salida no conforme" in fuentes


def test_sembrar_dos_veces_no_duplica(entorno):
    """Se llama en cada creación: tiene que ser idempotente."""
    entorno.como("calidad")
    _catalogos(entorno)
    _crear(entorno)

    db = entorno.Session()
    service.sembrar_catalogos(db, entorno.tenant_id)
    service.sembrar_catalogos(db, entorno.tenant_id)
    db.close()

    assert len(_catalogos(entorno)["proceso"]) == 17


def test_calidad_agrega_un_proceso_sin_esperar_un_despliegue(entorno):
    """El argumento de que sean tabla: el SGC los cambia sin avisarle a TIC's."""
    entorno.como("calidad")

    r = entorno.post("/mejora/catalogos",
                     json={"tipo": "proceso", "nombre": "Comercio Exterior"})

    assert r.status_code == 201, r.text
    assert "Comercio Exterior" in [p["nombre"] for p in _catalogos(entorno)["proceso"]]


def test_un_lider_cualquiera_no_toca_los_catalogos(entorno):
    """Son del SGC: si cada área agregara su proceso, el reporte se parte."""
    entorno.como("tics")
    r = entorno.post("/mejora/catalogos", json={"tipo": "proceso", "nombre": "Lo mío"})

    assert r.status_code == 403
    assert "calidad" in r.json()["detail"].lower()


def test_un_proceso_no_se_borra_se_desactiva(entorno):
    """Las acciones viejas lo siguen apuntando y el reporte tiene que nombrarlo."""
    entorno.como("calidad")
    item_id = _id_de(_catalogos(entorno), "proceso", "SGAmbiental")

    r = entorno.patch(f"/mejora/catalogos/{item_id}", json={"activo": False})

    assert r.status_code == 200
    assert "SGAmbiental" not in [p["nombre"] for p in _catalogos(entorno)["proceso"]]
    con_inactivos = entorno.get("/mejora/catalogos?incluir_inactivos=true").json()
    assert "SGAmbiental" in [p["nombre"] for p in con_inactivos["proceso"]]


def test_no_se_puede_meter_un_proceso_donde_va_un_tratamiento(entorno):
    entorno.como("calidad")
    proceso_id = _id_de(_catalogos(entorno), "proceso", "SGC")

    r = _crear(entorno, tratamiento_id=proceso_id)

    assert r.status_code == 400
    assert "tratamiento" in r.json()["detail"].lower()


# ── Proceso y área ───────────────────────────────────────────────────

def test_el_proceso_se_propone_desde_el_area(entorno):
    """Para ahorrar un clic. El área sigue decidiendo permisos, el proceso rotula."""
    entorno.como("calidad")
    r = _crear(entorno)

    assert r.json()["proceso_nombre"] == "SGC", r.json()


def test_un_area_sin_equivalente_no_se_adivina(entorno):
    """
    Servicio al Cliente no existe como proceso del SGC. Adivinar mal manda la
    acción al reporte de otro proceso, así que se deja en blanco.
    """
    entorno.como("admin")
    r = _crear(entorno, area="Servicio al Cliente")

    assert r.status_code == 201, r.text
    assert r.json()["proceso_id"] is None


def test_el_proceso_elegido_le_gana_al_propuesto(entorno):
    entorno.como("calidad")
    tics = _id_de(_catalogos(entorno), "proceso", "TIC's")

    r = _crear(entorno, proceso_id=tics)

    assert r.json()["proceso_nombre"] == "TIC's"


def test_la_fuente_se_propone_desde_el_origen(entorno):
    entorno.como("calidad")
    r = _crear(entorno, origen="pqrs")

    assert r.json()["fuente_nombre"] == "PQR", r.json()


# ── Consecutivo por proceso ──────────────────────────────────────────

def test_cada_proceso_lleva_su_propia_numeracion(entorno):
    """
    Hasta hoy cada proceso tenía su archivo y los auditores citan «la 6 de
    TIC's». El código global sigue existiendo aparte.
    """
    entorno.como("calidad")
    catalogos = _catalogos(entorno)
    tics, sgc = _id_de(catalogos, "proceso", "TIC's"), _id_de(catalogos, "proceso", "SGC")

    primera = _crear(entorno, proceso_id=tics).json()
    segunda = _crear(entorno, proceso_id=tics).json()
    otra = _crear(entorno, proceso_id=sgc).json()

    assert [primera["consecutivo"], segunda["consecutivo"]] == [1, 2]
    assert otra["consecutivo"] == 1
    # Y el código del portal sigue siendo único entre todas.
    assert len({primera["codigo"], segunda["codigo"], otra["codigo"]}) == 3


def test_el_consecutivo_por_proceso_sale_del_maximo(entorno):
    """
    El defecto que ya mordió dos veces: contar da un número ya usado en
    cuanto alguien borra una del medio.
    """
    entorno.como("calidad")
    proceso_id = _id_de(_catalogos(entorno), "proceso", "TIC's")

    db = entorno.Session()
    for consecutivo in (1, 3):
        db.add(Oportunidad(tenant_id=entorno.tenant_id, titulo="Vieja",
                           proceso_id=proceso_id, consecutivo=consecutivo))
    db.commit()
    siguiente = service.siguiente_consecutivo(db, entorno.tenant_id, proceso_id)
    db.close()

    assert siguiente == 4


def test_cambiar_de_proceso_le_da_su_numero_alla(entorno):
    entorno.como("calidad")
    catalogos = _catalogos(entorno)
    tics = _id_de(catalogos, "proceso", "TIC's")
    _crear(entorno, proceso_id=tics)

    omp_id = _crear(entorno).json()["id"]      # nace en SGC, consecutivo 1
    r = entorno.patch(f"/mejora/{omp_id}", json={"proceso_id": tics})

    assert r.json()["consecutivo"] == 2, r.json()


# ── El tratamiento decide qué campos aplican ─────────────────────────

def test_una_accion_de_mejora_no_pide_causa_raiz(entorno):
    """
    Una AM no corrige nada: nadie falló. Exigirle causa raíz obligaba a
    escribir «no aplica» para poder avanzar.
    """
    entorno.como("calidad")
    omp_id = _crear(entorno, tratamiento_id=_tratamiento(entorno, "AM")).json()["id"]
    entorno.patch(f"/mejora/{omp_id}",
                  json={"beneficio_mejora": "Ahorra dos horas de digitación al día."})

    r = entorno.patch(f"/mejora/{omp_id}/estado", json={"estado": "ejecucion"})

    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "ejecucion"


def test_una_accion_de_mejora_si_pide_su_beneficio(entorno):
    entorno.como("calidad")
    omp_id = _crear(entorno, tratamiento_id=_tratamiento(entorno, "AM")).json()["id"]

    r = entorno.patch(f"/mejora/{omp_id}/estado", json={"estado": "ejecucion"})

    assert r.status_code == 400
    assert "beneficio" in r.json()["detail"].lower()


def test_una_accion_correctiva_pide_causa_y_correccion(entorno):
    """Primero qué se hizo para tapar el hueco, y aparte qué evita que vuelva."""
    entorno.como("calidad")
    omp_id = _crear(entorno, tratamiento_id=_tratamiento(entorno, "AC")).json()["id"]

    entorno.patch(f"/mejora/{omp_id}", json={"causa_raiz": "El instructivo estaba mal."})
    r = entorno.patch(f"/mejora/{omp_id}/estado", json={"estado": "ejecucion"})
    assert r.status_code == 400
    assert "corrección" in r.json()["detail"].lower()

    entorno.patch(f"/mejora/{omp_id}", json={"correccion": "Se rehízo el lote."})
    assert entorno.patch(f"/mejora/{omp_id}/estado",
                         json={"estado": "ejecucion"}).status_code == 200


def test_sin_tratamiento_elegido_se_sigue_pidiendo_causa(entorno):
    """El comportamiento que el módulo ya tenía: no se afloja por omisión."""
    entorno.como("calidad")
    omp_id = _crear(entorno).json()["id"]

    r = entorno.patch(f"/mejora/{omp_id}/estado", json={"estado": "ejecucion"})

    assert r.status_code == 400
    assert "causa raíz" in r.json()["detail"].lower()


def test_el_servidor_dice_que_campos_aplican(entorno):
    """
    El frontend no lo deduce del nombre del catálogo: renombrarlo desde
    Admin le escondería un campo obligatorio a media empresa.
    """
    entorno.como("calidad")
    omp = _crear(entorno, tratamiento_id=_tratamiento(entorno, "AC")).json()

    assert omp["pide_causa"] is True
    assert omp["pide_correccion"] is True
    assert omp["pide_beneficio"] is False


# ── Análisis de causas en 6M ─────────────────────────────────────────

def test_las_6m_se_guardan_por_separado(entorno):
    entorno.como("calidad")
    omp_id = _crear(entorno).json()["id"]

    r = entorno.patch(f"/mejora/{omp_id}", json={
        "causa_efecto": "Las entregas llegan tarde.",
        "causa_metodo": "No hay ruta definida.",
        "causa_material": "El empaque se demora.",
    })

    assert r.status_code == 200, r.text
    assert r.json()["causa_metodo"] == "No hay ruta definida."
    assert r.json()["causa_maquinaria"] is None


def test_el_bloque_6m_se_reconstruye_como_lo_imprime_el_formato(entorno):
    """Al exportar, el .xlsx tiene que leerse igual que siempre."""
    entorno.como("calidad")
    omp_id = _crear(entorno).json()["id"]
    entorno.patch(f"/mejora/{omp_id}", json={
        "causa_efecto": "Reprocesos", "causa_metodo": "Sin instructivo",
    })

    db = entorno.Session()
    bloque = service.bloque_6m(db.get(Oportunidad, omp_id))
    db.close()

    lineas = bloque.split("\n")
    assert lineas[0] == "Efecto: Reprocesos"
    assert lineas[1] == "Método: Sin instructivo"
    # Las que no se escribieron salen como N/A, que es como lo escribe el
    # formato: una M ausente y una que no aplica se leen distinto.
    assert lineas[3] == "Maquinaria: N/A"
    assert len(lineas) == 7


def test_sin_ninguna_6m_no_hay_bloque_que_imprimir(entorno):
    entorno.como("calidad")
    omp_id = _crear(entorno).json()["id"]

    db = entorno.Session()
    assert service.bloque_6m(db.get(Oportunidad, omp_id)) is None
    db.close()


@pytest.mark.parametrize("crudo,esperado", [
    ("N/A", None), ("n/a", None), ("NA", None), ("No aplica", None),
    ("  ", None), ("-", None), (None, None),
    ("Se cambió el proveedor", "Se cambió el proveedor"),
])
def test_los_no_aplica_del_excel_entran_como_vacio(crudo, esperado):
    """Guardar el literal «N/A» obliga a filtrarlo en cada consulta después."""
    assert limpiar_no_aplica(crudo) == esperado


# ── Responsables (varios, y a veces un comité) ───────────────────────

def test_una_accion_admite_varios_responsables(entorno):
    """En el Excel van separados por saltos de línea dentro de la celda."""
    entorno.como("calidad")
    r = _crear(entorno, responsables=[
        {"tipo": "resolucion", "usuario_id": entorno.ids["tics"]},
        {"tipo": "resolucion", "usuario_id": entorno.ids["calidad"]},
        {"tipo": "seguimiento", "nombre_texto": "Comité de TIC's"},
    ])

    assert r.status_code == 201, r.text
    nombres = {x["nombre"] for x in r.json()["responsables"]}
    assert nombres == {"Tico", "Cali", "Comité de TIC's"}


def test_el_responsable_del_seguimiento_puede_ser_un_comite(entorno):
    """Un comité no tiene usuario ni correo, pero es quien responde."""
    entorno.como("calidad")
    omp_id = _crear(entorno).json()["id"]

    r = entorno.post(f"/mejora/{omp_id}/responsables",
                     json={"tipo": "seguimiento", "nombre_texto": "Comité de Calidad"})

    assert r.status_code == 201, r.text
    assert any(x["nombre"] == "Comité de Calidad" for x in r.json())


def test_un_responsable_sin_nombre_ni_usuario_no_pasa(entorno):
    entorno.como("calidad")
    r = _crear(entorno, responsables=[{"tipo": "resolucion"}])

    assert r.status_code == 400
    assert "nombre" in r.json()["detail"].lower()


# ── Seguimientos ─────────────────────────────────────────────────────

def test_el_seguimiento_es_una_fila_por_entrada(entorno):
    """
    En el Excel son tres columnas con hasta veinticinco entradas apretadas
    dentro de una celda. Aquí es lo que siempre fue: un histórico.
    """
    entorno.como("calidad")
    omp_id = _crear(entorno).json()["id"]

    entorno.post(f"/mejora/{omp_id}/seguimientos",
                 json={"contenido": "Se pidió cotización.", "fecha": "2026-03-02"})
    entorno.post(f"/mejora/{omp_id}/seguimientos",
                 json={"contenido": "Llegó el equipo.", "fecha": "2026-05-14"})

    detalle = entorno.get(f"/mejora/{omp_id}").json()
    assert detalle["total_seguimientos"] == 2
    # Ascendente: es una línea de tiempo, se lee de arriba abajo.
    assert [s["fecha"] for s in detalle["seguimientos"]] == ["2026-03-02", "2026-05-14"]
    assert detalle["seguimientos"][0]["autor_nombre"] == "Cali"


def test_el_seguimiento_lo_escribe_quien_hace_el_trabajo(entorno):
    """
    No solo el líder: obligar a contárselo para que él lo escriba es cómo
    estos registros se llenan de resúmenes de segunda mano.
    """
    entorno.como("admin")
    omp_id = entorno.post("/mejora", json={"titulo": "Reducir el consumo de papel",
                                           "area": None}).json()["id"]

    entorno.como("tics")
    r = entorno.post(f"/mejora/{omp_id}/seguimientos",
                     json={"contenido": "Se configuró la impresora a doble cara."})

    assert r.status_code == 201, r.text


def test_sin_fecha_el_seguimiento_es_de_hoy(entorno):
    entorno.como("calidad")
    omp_id = _crear(entorno).json()["id"]

    r = entorno.post(f"/mejora/{omp_id}/seguimientos", json={"contenido": "Va en curso."})

    assert r.json()["fecha"] == date.today().isoformat()


def test_un_seguimiento_ajeno_no_se_borra(entorno):
    """Es el registro de lo que alguien dijo en una fecha: eso es lo que se audita."""
    entorno.como("admin")
    omp_id = entorno.post("/mejora", json={"titulo": "Reducir el consumo de papel",
                                           "area": None}).json()["id"]
    seguimiento = entorno.post(f"/mejora/{omp_id}/seguimientos",
                               json={"contenido": "Lo revisé el martes."}).json()

    entorno.como("tics")
    r = entorno.delete(f"/mejora/{omp_id}/seguimientos/{seguimiento['id']}")

    assert r.status_code == 403
    assert "escribió" in r.json()["detail"].lower()


# ── Validación del SGC antes de cerrar ───────────────────────────────

def test_no_se_cierra_sin_que_calidad_lo_valide(entorno):
    """
    Los cierres reales del formato dicen «se validó con el SGC». Es un paso
    de aprobación, no un campo de texto.
    """
    entorno.como("calidad")
    omp_id = _crear(entorno).json()["id"]
    entorno.post(f"/mejora/{omp_id}/verificacion", json={"eficaz": True})

    r = entorno.patch(f"/mejora/{omp_id}/estado", json={"estado": "cerrada"})

    assert r.status_code == 400
    assert "calidad" in r.json()["detail"].lower()


def test_con_el_visto_bueno_de_calidad_si_cierra(entorno):
    entorno.como("calidad")
    omp_id = _crear(entorno).json()["id"]
    entorno.post(f"/mejora/{omp_id}/verificacion", json={"eficaz": True})

    validada = entorno.post(f"/mejora/{omp_id}/validacion-sgc",
                            json={"nota": "Evidencia revisada."}).json()
    assert validada["validado_sgc_nombre"] == "Cali"
    assert validada["validado_sgc_en"] is not None

    r = entorno.patch(f"/mejora/{omp_id}/estado", json={"estado": "cerrada"})
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "cerrada"


def test_otra_area_no_valida_el_cierre(entorno):
    entorno.como("admin")
    omp_id = entorno.post("/mejora", json={"titulo": "Reducir el consumo de papel",
                                           "area": None}).json()["id"]
    entorno.post(f"/mejora/{omp_id}/verificacion", json={"eficaz": True})

    entorno.como("tics")
    r = entorno.post(f"/mejora/{omp_id}/validacion-sgc", json={})

    assert r.status_code == 403
    assert "calidad" in r.json()["detail"].lower()


def test_calidad_no_valida_sobre_una_promesa(entorno):
    """Se valida un resultado: sin verificación de eficacia no hay qué revisar."""
    entorno.como("calidad")
    omp_id = _crear(entorno).json()["id"]

    r = entorno.post(f"/mejora/{omp_id}/validacion-sgc", json={})

    assert r.status_code == 400
    assert "eficacia" in r.json()["detail"].lower()


def test_una_verificacion_negativa_anula_el_visto_bueno(entorno):
    """
    Si no funcionó, la firma anterior no puede quedar: la siguiente vuelta se
    cerraría con la validación de una evidencia que ya se sabe insuficiente.
    """
    entorno.como("calidad")
    omp_id = _crear(entorno).json()["id"]
    entorno.post(f"/mejora/{omp_id}/verificacion", json={"eficaz": True})
    entorno.post(f"/mejora/{omp_id}/validacion-sgc", json={})

    r = entorno.post(f"/mejora/{omp_id}/verificacion",
                     json={"eficaz": False, "nota": "El indicador siguió cayendo."})

    assert r.json()["estado"] == "analisis"
    assert r.json()["validado_sgc_en"] is None


# ── Plan de acción con tres estados ──────────────────────────────────

def test_una_tarea_en_curso_no_cuenta_como_cumplida(entorno):
    """
    Sin «en curso» la gente marca cumplido antes de tiempo para que el
    avance se mueva.
    """
    entorno.como("calidad")
    omp_id = _crear(entorno).json()["id"]
    accion = entorno.post(f"/mejora/{omp_id}/acciones",
                          json={"descripcion": "Cotizar el equipo"}).json()

    r = entorno.patch(f"/mejora/{omp_id}/acciones/{accion['id']}",
                      json={"estado": "en_curso"})

    assert r.json()["completada"] is False
    assert entorno.get(f"/mejora/{omp_id}").json()["avance_pct"] == 0.0


def test_las_tareas_del_plan_van_numeradas(entorno):
    """El Excel las numera a mano y el orden importa: unas dependen de otras."""
    entorno.como("calidad")
    omp_id = _crear(entorno).json()["id"]
    for texto in ["Cotizar", "Comprar", "Capacitar"]:
        entorno.post(f"/mejora/{omp_id}/acciones", json={"descripcion": texto})

    acciones = entorno.get(f"/mejora/{omp_id}").json()["acciones"]

    assert [a["orden"] for a in acciones] == [1, 2, 3]
    assert [a["descripcion"] for a in acciones] == ["Cotizar", "Comprar", "Capacitar"]


def test_un_estado_de_tarea_inventado_no_pasa(entorno):
    entorno.como("calidad")
    omp_id = _crear(entorno).json()["id"]
    accion = entorno.post(f"/mejora/{omp_id}/acciones",
                          json={"descripcion": "Cotizar el equipo"}).json()

    r = entorno.patch(f"/mejora/{omp_id}/acciones/{accion['id']}",
                      json={"estado": "casi"})

    assert r.status_code == 400


# ── Hallazgos similares ──────────────────────────────────────────────

def test_relacionar_dos_acciones_del_mismo_hallazgo(entorno):
    """
    El «Sí» del formato no dice cuáles, así que no sirve para revisar qué ya
    se intentó. Aquí apunta a las acciones concretas, en las dos direcciones.
    """
    entorno.como("calidad")
    una = _crear(entorno).json()["id"]
    otra = _crear(entorno, titulo="Las entregas siguen llegando tarde").json()["id"]

    r = entorno.post(f"/mejora/{una}/relacionadas/{otra}")

    assert r.status_code == 204, r.text
    assert [o["id"] for o in entorno.get(f"/mejora/{una}/relacionadas").json()] == [otra]
    assert [o["id"] for o in entorno.get(f"/mejora/{otra}/relacionadas").json()] == [una]
    assert entorno.get(f"/mejora/{una}").json()["hallazgos_similares"] is True


def test_relacionar_dos_veces_no_duplica(entorno):
    entorno.como("calidad")
    una = _crear(entorno).json()["id"]
    otra = _crear(entorno, titulo="Las entregas siguen llegando tarde").json()["id"]

    entorno.post(f"/mejora/{una}/relacionadas/{otra}")
    r = entorno.post(f"/mejora/{una}/relacionadas/{otra}")

    assert r.status_code == 204, r.text
    assert len(entorno.get(f"/mejora/{una}/relacionadas").json()) == 1


def test_una_accion_no_se_relaciona_consigo_misma(entorno):
    entorno.como("calidad")
    una = _crear(entorno).json()["id"]

    assert entorno.post(f"/mejora/{una}/relacionadas/{una}").status_code == 400


# ── Trazabilidad ─────────────────────────────────────────────────────

def test_queda_registro_de_quien_movio_que(entorno):
    """Para responder «¿por qué esto se aplazó tres veces?» sin depender de nadie."""
    entorno.como("calidad")
    omp_id = _crear(entorno).json()["id"]
    entorno.patch(f"/mejora/{omp_id}", json={"causa_raiz": "El proveedor entrega tarde."})
    entorno.patch(f"/mejora/{omp_id}/estado", json={"estado": "ejecucion"})

    historial = entorno.get(f"/mejora/{omp_id}/historial").json()

    campos = [c["campo"] for c in historial]
    assert "Estado" in campos
    assert "Causa raíz" in campos
    cambio_estado = next(c for c in historial if c["campo"] == "Estado")
    assert cambio_estado["valor_anterior"] == "abierta"
    assert cambio_estado["valor_nuevo"] == "ejecucion"
    assert cambio_estado["usuario_nombre"] == "Cali"


def test_el_historial_no_guarda_lo_que_no_importa(entorno):
    """Una bitácora con cada corrección de ortografía entierra la pregunta real."""
    entorno.como("calidad")
    omp_id = _crear(entorno).json()["id"]

    entorno.patch(f"/mejora/{omp_id}", json={"descripcion": "Un texto cualquiera."})

    assert entorno.get(f"/mejora/{omp_id}/historial").json() == []


def test_guardar_lo_mismo_no_ensucia_el_historial(entorno):
    entorno.como("calidad")
    omp_id = _crear(entorno).json()["id"]
    entorno.patch(f"/mejora/{omp_id}", json={"prioridad": "alta"})
    entorno.patch(f"/mejora/{omp_id}", json={"prioridad": "alta"})

    assert len(entorno.get(f"/mejora/{omp_id}/historial").json()) == 1


# ── La fecha del formato ─────────────────────────────────────────────

def test_la_fecha_de_registro_se_puede_escribir(entorno):
    """
    Al importar el histórico la acción se registró en 2022 aunque la fila se
    cree hoy, y el reporte tiene que decir 2022.
    """
    entorno.como("calidad")
    r = _crear(entorno, fecha_registro="2022-09-23")

    assert r.json()["fecha_registro"] == "2022-09-23"


def test_sin_fecha_de_registro_es_la_de_hoy(entorno):
    entorno.como("calidad")
    assert _crear(entorno).json()["fecha_registro"] == date.today().isoformat()
