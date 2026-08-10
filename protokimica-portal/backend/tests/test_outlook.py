"""
Sincronización de tareas con el calendario de Outlook.

Nada de esto toca la red: se sustituye el cliente de Graph por uno falso que
anota lo que le piden. Lo que se prueba es la decisión (crear, mover, borrar,
no hacer nada) y la traducción de una tarea a un evento — que es donde de
verdad se puede meter la pata.
"""
from datetime import datetime, timedelta

import pytest

from app.core import graph
from app.models.master_planner import Tarea
from app.modules.master_planner import outlook


class GraphFalso:
    """Reemplaza a Microsoft Graph y guarda lo que se le pidió."""

    def __init__(self, falla_actualizar=False):
        self.creados = []
        self.actualizados = []
        self.borrados = []
        self.falla_actualizar = falla_actualizar
        self._siguiente_id = 1

    def crear_evento(self, email, evento):
        evento_id = f"evt-{self._siguiente_id}"
        self._siguiente_id += 1
        self.creados.append((email, evento))
        return evento_id

    def actualizar_evento(self, email, evento_id, evento):
        if self.falla_actualizar:
            return False
        self.actualizados.append((email, evento_id, evento))
        return True

    def borrar_evento(self, email, evento_id):
        self.borrados.append((email, evento_id))
        return True


@pytest.fixture
def graph_falso(monkeypatch):
    falso = GraphFalso()
    monkeypatch.setattr(outlook.graph, "graph_configurado", lambda: True)
    monkeypatch.setattr(outlook.graph, "crear_evento", falso.crear_evento)
    monkeypatch.setattr(outlook.graph, "actualizar_evento", falso.actualizar_evento)
    monkeypatch.setattr(outlook.graph, "borrar_evento", falso.borrar_evento)
    return falso


def _tarea(**kwargs):
    base = dict(
        id=1, titulo="Cotizar reactivos", descripcion=None,
        asignado_a=None, fecha_inicio=None, fecha_fin=None,
        outlook_evento_id=None,
    )
    base.update(kwargs)
    t = Tarea()
    for k, v in base.items():
        setattr(t, k, v)
    return t


# ── Traducción de tarea a evento ─────────────────────────────────────────

def test_sin_fechas_no_hay_evento(v):
    v.check(
        "una tarea sin fechas no puede ir al calendario",
        outlook.construir_evento(_tarea()) is None,
    )


def test_con_inicio_y_fin_va_como_bloque_de_horas(v):
    inicio = datetime(2026, 8, 12, 9, 0)
    evento = outlook.construir_evento(
        _tarea(fecha_inicio=inicio, fecha_fin=inicio + timedelta(hours=2))
    )
    v.check("no es de día completo", evento["isAllDay"] is False, evento["isAllDay"])
    v.check("arranca a las 9", evento["start"]["dateTime"] == "2026-08-12T09:00:00",
            evento["start"])
    v.check("termina a las 11", evento["end"]["dateTime"] == "2026-08-12T11:00:00",
            evento["end"])
    v.check("el título es el de la tarea", evento["subject"] == "Cotizar reactivos")


def test_con_una_sola_fecha_va_como_dia_completo(v):
    evento = outlook.construir_evento(_tarea(fecha_fin=datetime(2026, 8, 12, 17, 30)))
    v.check("es de día completo", evento["isAllDay"] is True, evento["isAllDay"])
    v.check("arranca a medianoche", evento["start"]["dateTime"] == "2026-08-12T00:00:00",
            evento["start"])
    v.check(
        "cierra el día siguiente, como exige Graph",
        evento["end"]["dateTime"] == "2026-08-13T00:00:00",
        evento["end"],
    )


def test_un_fin_anterior_al_inicio_no_genera_evento_invalido(v):
    """Graph rechaza un evento que termina antes de empezar."""
    inicio = datetime(2026, 8, 12, 15, 0)
    evento = outlook.construir_evento(
        _tarea(fecha_inicio=inicio, fecha_fin=inicio - timedelta(hours=3))
    )
    v.check(
        "el fin se corrige para quedar después del inicio",
        evento["end"]["dateTime"] > evento["start"]["dateTime"],
        (evento["start"], evento["end"]),
    )


def test_el_cuerpo_lleva_proyecto_y_enlace(v):
    evento = outlook.construir_evento(
        _tarea(fecha_fin=datetime(2026, 8, 12)), proyecto_nombre="Planta 2"
    )
    cuerpo = evento["body"]["content"]
    v.check("nombra el proyecto", "Planta 2" in cuerpo, cuerpo)
    v.check("lleva enlace a la tarea en el portal", "/master-planner/tareas/1" in cuerpo)


# ── Decisión de qué hacer con el calendario ──────────────────────────────

def test_sin_responsable_no_se_toca_el_calendario(entorno, graph_falso, v):
    db = entorno.Session()
    tarea = _tarea(fecha_fin=datetime(2026, 8, 12))
    outlook.sincronizar_tarea(db, tarea)
    v.check("no se creó nada", graph_falso.creados == [], graph_falso.creados)
    db.close()


def test_se_crea_el_evento_y_se_guarda_su_id(entorno, graph_falso, v):
    db = entorno.Session()
    tarea = _tarea(
        asignado_a=entorno.ids["tics"], fecha_fin=datetime(2026, 8, 12),
    )
    outlook.sincronizar_tarea(db, tarea)

    v.check("se creó un evento", len(graph_falso.creados) == 1, graph_falso.creados)
    v.check(
        "se guardó el id para poder moverlo después",
        tarea.outlook_evento_id == "evt-1",
        tarea.outlook_evento_id,
    )
    db.close()


def test_la_segunda_vez_mueve_el_evento_en_vez_de_duplicarlo(entorno, graph_falso, v):
    db = entorno.Session()
    tarea = _tarea(
        asignado_a=entorno.ids["tics"], fecha_fin=datetime(2026, 8, 12),
        outlook_evento_id="evt-ya-existe",
    )
    outlook.sincronizar_tarea(db, tarea)

    v.check("no creó uno nuevo", graph_falso.creados == [], graph_falso.creados)
    v.check("actualizó el que ya estaba", len(graph_falso.actualizados) == 1,
            graph_falso.actualizados)
    db.close()


def test_si_le_quitan_las_fechas_se_borra_el_evento(entorno, graph_falso, v):
    db = entorno.Session()
    tarea = _tarea(
        asignado_a=entorno.ids["tics"], outlook_evento_id="evt-viejo",
    )
    outlook.sincronizar_tarea(db, tarea)

    v.check("se borró del calendario", len(graph_falso.borrados) == 1,
            graph_falso.borrados)
    v.check("la tarea deja de apuntar a un evento",
            tarea.outlook_evento_id is None, tarea.outlook_evento_id)
    db.close()


def test_si_borraron_el_evento_a_mano_se_vuelve_a_crear(entorno, monkeypatch, v):
    """Alguien borra el evento en Outlook; el portal no debe quedarse mudo."""
    falso = GraphFalso(falla_actualizar=True)
    monkeypatch.setattr(outlook.graph, "graph_configurado", lambda: True)
    monkeypatch.setattr(outlook.graph, "crear_evento", falso.crear_evento)
    monkeypatch.setattr(outlook.graph, "actualizar_evento", falso.actualizar_evento)
    monkeypatch.setattr(outlook.graph, "borrar_evento", falso.borrar_evento)

    db = entorno.Session()
    tarea = _tarea(
        asignado_a=entorno.ids["tics"], fecha_fin=datetime(2026, 8, 12),
        outlook_evento_id="evt-que-ya-no-existe",
    )
    outlook.sincronizar_tarea(db, tarea)

    v.check("se creó uno nuevo", len(falso.creados) == 1, falso.creados)
    v.check("con su id nuevo guardado", tarea.outlook_evento_id == "evt-1",
            tarea.outlook_evento_id)
    db.close()


def test_si_graph_esta_apagado_no_pasa_nada(entorno, monkeypatch, v):
    """Sin credenciales configuradas, el portal funciona igual que siempre."""
    llamadas = []
    monkeypatch.setattr(outlook.graph, "graph_configurado", lambda: False)
    monkeypatch.setattr(outlook.graph, "crear_evento",
                        lambda *a, **k: llamadas.append(a))

    db = entorno.Session()
    tarea = _tarea(asignado_a=entorno.ids["tics"], fecha_fin=datetime(2026, 8, 12))
    outlook.sincronizar_tarea(db, tarea)

    v.check("no se llamó a Graph", llamadas == [], llamadas)
    db.close()


def test_un_fallo_de_graph_no_tumba_la_operacion(entorno, monkeypatch, v):
    """
    Lo más importante de todo: si Microsoft falla, la tarea ya se guardó y
    nadie puede quedarse sin registrar su trabajo por eso.
    """
    def explota(*a, **k):
        raise RuntimeError("Graph caído")

    monkeypatch.setattr(outlook.graph, "graph_configurado", lambda: True)
    monkeypatch.setattr(outlook.graph, "crear_evento", explota)

    db = entorno.Session()
    tarea = _tarea(asignado_a=entorno.ids["tics"], fecha_fin=datetime(2026, 8, 12))
    try:
        outlook.sincronizar_tarea(db, tarea)
        exploto = False
    except Exception:
        exploto = True

    v.check("sincronizar no propaga la excepción", exploto is False)
    db.close()


def test_graph_apagado_por_defecto(v):
    """Sin las tres variables en el .env, la integración no se activa sola."""
    v.check(
        "con credenciales vacías, graph_configurado() es False",
        graph.graph_configurado() is False,
    )
