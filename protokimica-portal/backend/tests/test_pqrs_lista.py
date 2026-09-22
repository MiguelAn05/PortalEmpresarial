"""
La lista de PQRS: lo que viaja por el cable.

El módulo funciona bien hoy, con unos cientos de solicitudes. El histórico no
se borra —y no debe borrarse—, así que lo que aquí se prueba es lo que decide
si seguirá funcionando con miles: que cada fila pese lo que pinta la tabla y
que la lista sea UNA consulta, no una por solicitud.
"""
import json

from sqlalchemy import event

from app.models.pqrs import PQRSSolicitud
from app.modules.pqrs.schemas import PQRSResumenOut

BASE = {"tipo": "reclamo", "descripcion": "x" * 3000, "cliente_nombre": "Juan",
        "empresa": "Acme S.A.S.", "factura_numero": "FV-100"}

PRODUCTOS = [
    {"producto_codigo": "PK-001", "producto_nombre": "Hipoclorito 13%", "lote": "L-1"},
    {"producto_nombre": "el desengrasante verde", "lote": "L-2"},
]


def _radicar(entorno, **extra):
    return entorno.post("/pqrs", data={**BASE, **extra, "productos": json.dumps(PRODUCTOS)})


class _Consultas:
    """Cuenta las consultas que se ejecutan dentro del bloque."""

    def __init__(self, entorno):
        self.engine = entorno.Session.kw["bind"]
        self.sentencias = []

    def __enter__(self):
        event.listen(self.engine, "after_cursor_execute", self._anotar)
        return self

    def __exit__(self, *_):
        event.remove(self.engine, "after_cursor_execute", self._anotar)

    def _anotar(self, conn, cursor, sentencia, *_):
        self.sentencias.append(" ".join(str(sentencia).split()))

    def contra(self, tabla):
        return [s for s in self.sentencias if f"FROM {tabla}" in s]


def test_la_lista_trae_lo_que_la_tabla_pinta(entorno, v):
    _radicar(entorno)
    fila = entorno.get("/pqrs").json()[0]

    # Las columnas de la tabla, la búsqueda y los filtros de `PQRSList.jsx`.
    for campo in ("id", "codigo_seguimiento", "radicado_calidad", "tipo", "empresa",
                  "nit_cedula", "cliente_nombre", "cliente_email", "area_responsable",
                  "estado", "prioridad", "fecha_creacion", "fecha_limite_sla"):
        v.check(f"la lista trae {campo}", campo in fila, sorted(fila))


def test_la_lista_no_arrastra_la_pqrs_entera(entorno, v):
    """
    Lo que no se pinta no se manda. La descripción llega a cuatro mil
    caracteres y la lista no la muestra; multiplicada por todo el histórico
    es casi todo el peso de la respuesta.
    """
    _radicar(entorno)
    fila = entorno.get("/pqrs").json()[0]

    for campo in ("descripcion", "productos", "adjunto_producto", "adjunto_factura",
                  "adjunto_video", "seguimientos", "solucion"):
        v.check(f"la lista no trae {campo}", campo not in fila, sorted(fila))


def test_la_lista_es_una_consulta_y_no_una_por_solicitud(entorno, v):
    """
    El caso que no se ve venir: los productos son una tabla aparte, así que
    mandarlos en la lista significaba una consulta POR FILA. Con cincuenta
    PQRS en pantalla son cincuenta viajes a la base para pintar una columna
    que no existe.
    """
    for i in range(5):
        _radicar(entorno, cliente_nombre=f"Cliente {i}")

    with _Consultas(entorno) as consultas:
        filas = entorno.get("/pqrs").json()

    v.check("salen las cinco", len(filas) == 5, len(filas))
    v.check("una sola consulta a las solicitudes",
            len(consultas.contra("pqrs_solicitudes")) == 1, consultas.contra("pqrs_solicitudes"))
    v.check("y ninguna a los productos",
            consultas.contra("pqrs_productos") == [], consultas.contra("pqrs_productos"))


def test_el_resumen_se_puede_pedir_columna_por_columna(entorno, v):
    """
    El router arma su `load_only` con los campos de `PQRSResumenOut`. Si
    alguien agrega ahí un campo calculado, la lista revienta para todo el
    mundo; esto lo dice antes, y en un solo sitio.
    """
    columnas = {c.key for c in PQRSSolicitud.__table__.columns}
    for campo in PQRSResumenOut.model_fields:
        v.check(f"{campo} es una columna de la tabla", campo in columnas, sorted(columnas))


def test_los_filtros_del_servidor_siguen_funcionando(entorno, v):
    """Aligerar la respuesta no puede cambiar QUÉ solicitudes salen."""
    _radicar(entorno)
    _radicar(entorno, tipo="peticion", descripcion="Necesito una cotización")

    v.check("por tipo", len(entorno.get("/pqrs?tipo=peticion").json()) == 1)
    v.check("por estado", len(entorno.get("/pqrs?estado=recibido").json()) == 2)
    v.check("por un estado sin PQRS", entorno.get("/pqrs?estado=cerrado").json() == [])
