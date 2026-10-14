"""
Lo que trae el ERP además del catálogo básico: búsqueda sin tildes y por
palabras sueltas, el orden de los resultados, el registro de cada
sincronización y la verificación del NIT por huellas.

Lo de seguridad del buscador público y de la clave está en `test_catalogo.py`.
"""
from datetime import date

from app.core.config import settings
from app.models.catalogo import HuellaClienteERP, ProductoCatalogo
from app.models.pqrs import PQRSSolicitud
from app.modules.catalogo import clientes
from app.modules.pqrs.router_public import PQRSConsultaOut, PQRSPublicaOut

CLAVE = "clave-de-prueba-para-sincronizar"
CLAVE_HUELLA = "clave-de-prueba-para-huellas"


class _Claves:
    """Configura las dos claves durante la prueba y las deja como estaban."""

    def __init__(self, huella=CLAVE_HUELLA):
        self.huella = huella

    def __enter__(self):
        self.originales = (settings.CLAVE_SINCRONIZACION, settings.CLAVE_HUELLA_NIT)
        settings.CLAVE_SINCRONIZACION = CLAVE
        settings.CLAVE_HUELLA_NIT = self.huella

    def __exit__(self, *_):
        settings.CLAVE_SINCRONIZACION, settings.CLAVE_HUELLA_NIT = self.originales


def _productos(portal, productos):
    return portal.post("/catalogo/sincronizar", json={"productos": productos},
                       headers={"X-Clave-Sincronizacion": CLAVE})


def _huellas(portal, nits, clave=CLAVE_HUELLA, control=None):
    """Lo mismo que hace el script de MORFEO: huella de cada NIT y la de control."""
    return portal.post(
        "/catalogo/sincronizar-clientes",
        json={
            "huellas": [clientes.huella(n, clave) for n in nits],
            "control": control or clientes.huella(clientes.TEXTO_DE_CONTROL, clave),
        },
        headers={"X-Clave-Sincronizacion": CLAVE},
    )


def _buscar(portal, q):
    return [p["codigo"] for p in portal.get("/public/catalogo/productos", params={"q": q}).json()]


def _pqrs(portal, nit):
    db = portal.Session()
    p = PQRSSolicitud(
        tenant_id=portal.tenant_id, tipo="reclamo", cliente_nombre="Cliente",
        descripcion="Algo pasó", estado="recibido", prioridad="media",
        area_responsable="TICS", nit_cedula=nit, origen_publico="publico",
    )
    db.add(p)
    db.commit()
    pid = p.id
    db.close()
    return pid


# ── El buscador ──────────────────────────────────────────────────────────

def test_busca_sin_tildes_y_por_palabras_en_cualquier_orden(entorno, v):
    with _Claves():
        _productos(entorno, [
            {"codigo": "Q1", "nombre": "ÁCIDO SULFÚRICO", "presentacion": "GALÓN"},
            {"codigo": "Q2", "nombre": "HIPOCLORITO DE SODIO 13%", "presentacion": "20 LITROS"},
        ])
        v.check("sin tildes encuentra con tildes", _buscar(entorno, "acido") == ["Q1"])
        v.check("con tildes también", _buscar(entorno, "ácido") == ["Q1"])
        v.check("palabras sueltas en otro orden", _buscar(entorno, "sodio hipo") == ["Q2"])
        v.check("y por la presentación", _buscar(entorno, "hipo 20 litros") == ["Q2"])
        v.check("todas las palabras tienen que estar",
                _buscar(entorno, "hipo galon") == [])


def test_los_comodines_escritos_se_toman_como_texto(entorno, v):
    """Un `%` no puede convertirse en «todo el catálogo» en el buscador público."""
    with _Claves():
        _productos(entorno, [{"codigo": f"P{i}", "nombre": f"Producto {i}"} for i in range(5)])
        v.check("%% no devuelve nada", _buscar(entorno, "%%") == [])
        v.check("__ tampoco", _buscar(entorno, "__") == [])


def test_el_codigo_exacto_va_primero_y_luego_lo_vendido_hace_poco(entorno, v):
    with _Claves():
        _productos(entorno, [
            {"codigo": "AE20667093X", "nombre": "Desengrasante industrial",
             "fecha_ultima_venta": "2026-10-01"},
            {"codigo": "AE20667093", "nombre": "Desengrasante industrial",
             "fecha_ultima_venta": "2020-01-01"},
            {"codigo": "ZZ1", "nombre": "Desengrasante viejo", "fecha_ultima_venta": "2019-05-01"},
            {"codigo": "ZZ2", "nombre": "Desengrasante nuevo", "fecha_ultima_venta": "2026-09-01"},
            {"codigo": "ZZ3", "nombre": "Desengrasante sin ventas"},
        ])
        r = _buscar(entorno, "ae20667093")
        v.check("el código exacto, aunque no se venda hace años", r[0] == "AE20667093", r)

        r = _buscar(entorno, "desengrasante")
        v.check("lo vendido hace poco primero, lo que nunca se vendió al final",
                r.index("ZZ2") < r.index("ZZ1") < r.index("ZZ3"), r)


def test_se_guardan_el_grupo_y_la_ultima_venta(entorno, v):
    with _Claves():
        _productos(entorno, [{"codigo": "Q1", "nombre": "Soda", "grupo": "QUIMICOS GRAV. 19%",
                              "fecha_ultima_venta": "2026-09-30"}])
        db = entorno.Session()
        p = db.query(ProductoCatalogo).filter_by(codigo="Q1").one()
        v.check("grupo", p.grupo == "QUIMICOS GRAV. 19%", p.grupo)
        v.check("última venta", p.fecha_ultima_venta == date(2026, 9, 30), p.fecha_ultima_venta)
        db.close()

        r = _productos(entorno, [{"codigo": "Q1", "nombre": "Soda", "grupo": "OTRO"}])
        v.check("cambiar el grupo cuenta como actualizado", r.json()["actualizados"] == 1, r.json())


def test_un_codigo_repetido_en_el_lote_no_revienta(entorno, v):
    with _Claves():
        r = _productos(entorno, [{"codigo": "Q1", "nombre": "Uno"}, {"codigo": "Q1", "nombre": "Dos"}])
        v.check("responde bien", r.status_code == 200, r.text)
        v.check("queda uno solo", r.json()["total_activos"] == 1, r.json())


def test_un_valor_mas_largo_que_su_columna_rechaza_con_422(entorno, v):
    """Mejor un 422 que dice cuál que un 500 de Postgres en el commit."""
    with _Claves():
        r = _productos(entorno, [{"codigo": "Q1", "nombre": "Soda", "grupo": "x" * 61}])
        v.check("422", r.status_code == 422, r.status_code)


# ── El registro de sincronizaciones ──────────────────────────────────────

def test_cada_envio_queda_registrado_y_solo_admin_lo_consulta(entorno, v):
    with _Claves():
        _productos(entorno, [{"codigo": "Q1", "nombre": "Soda"}])
        _productos(entorno, [])  # rechazado: lote vacío

        estado = entorno.get("/catalogo/estado").json()
        productos = estado["productos"]
        v.check("la última fue la rechazada", productos["ultima"]["exitosa"] is False, productos)
        v.check("y dice por qué", "vacío" in productos["ultima"]["error"], productos)
        v.check("la última buena se sigue viendo",
                productos["ultima_exitosa"]["resumen"]["nuevos"] == 1, productos)
        v.check("de clientes no hay nada todavía", estado["clientes"]["ultima"] is None, estado)

        entorno.como("tics")
        v.check("un líder no la ve", entorno.get("/catalogo/estado").status_code == 403)


# ── Clientes: el NIT ─────────────────────────────────────────────────────

def test_digito_de_verificacion_de_la_dian(v):
    # 800.197.268-4 es el NIT de la DIAN; 860.034.313-7, el de Davivienda.
    v.check("DIAN", clientes.digito_verificacion("800197268") == 4)
    v.check("Davivienda", clientes.digito_verificacion("860034313") == 7)


def test_el_nit_se_reconoce_como_lo_escriba_la_gente(v):
    v.check("con puntos y guion", clientes.candidatos("800.197.268-4") == ["800197268"])
    v.check("con espacio", clientes.candidatos("800197268 4") == ["800197268"])
    v.check("pegado: se prueban las dos formas",
            clientes.candidatos("8001972684") == ["8001972684", "800197268"])
    v.check("una cédula cuya última cifra no es DV va tal cual",
            clientes.candidatos("8001972685") == ["8001972685"])
    v.check("ceros a la izquierda fuera", clientes.candidatos("00123456") == ["123456"])
    v.check("vacío", clientes.candidatos("  ") == [])
    v.check("sin cifras", clientes.candidatos("no tengo") == [])


def test_el_detalle_dice_si_el_nit_es_cliente(entorno, v):
    with _Claves():
        cliente = _pqrs(entorno, "800.197.268-4")
        otro = _pqrs(entorno, "123456789")
        sin_nit = _pqrs(entorno, None)

        v.check("antes de sincronizar no se afirma nada",
                entorno.get(f"/pqrs/{cliente}").json()["cliente_en_erp"] is None)

        r = _huellas(entorno, ["800197268", "860034313"])
        v.check("sincroniza", r.status_code == 200, r.text)

        v.check("el cliente aparece",
                entorno.get(f"/pqrs/{cliente}").json()["cliente_en_erp"] is True)
        v.check("el que no está, no",
                entorno.get(f"/pqrs/{otro}").json()["cliente_en_erp"] is False)
        v.check("sin NIT no se sabe",
                entorno.get(f"/pqrs/{sin_nit}").json()["cliente_en_erp"] is None)

    with _Claves(huella=""):
        v.check("sin clave configurada tampoco se afirma nada",
                entorno.get(f"/pqrs/{otro}").json()["cliente_en_erp"] is None)


def test_al_cliente_nunca_se_le_dice_si_es_cliente(v):
    """Si no, el formulario serviría para averiguar quién le compra a la empresa."""
    for schema in (PQRSPublicaOut, PQRSConsultaOut):
        v.check(f"{schema.__name__} no lleva la marca",
                "cliente_en_erp" not in schema.model_fields)


def test_no_se_guarda_ningun_nit(entorno, v):
    with _Claves():
        _huellas(entorno, ["800197268"])
        db = entorno.Session()
        guardado = [h.huella for h in db.query(HuellaClienteERP).all()]
        db.close()
        v.check("solo la huella", guardado == [clientes.huella("800197268", CLAVE_HUELLA)], guardado)
        v.check("y el número no aparece", all("800197268" not in h for h in guardado))


def test_las_huellas_se_reemplazan(entorno, v):
    with _Claves():
        _huellas(entorno, ["1001", "1002"])
        r = _huellas(entorno, ["1002", "1003"]).json()
        v.check("una nueva", r["nuevos"] == 1, r)
        v.check("una retirada", r["retirados"] == 1, r)
        v.check("quedan dos", r["total"] == 2, r)


def test_una_clave_distinta_en_morfeo_se_rechaza(entorno, v):
    """Con claves distintas ningún NIT coincidiría, y nadie se daría cuenta."""
    with _Claves():
        r = _huellas(entorno, ["800197268"], clave="otra-clave")
        v.check("409", r.status_code == 409, r.status_code)
        v.check("y dice qué hacer", "CLAVE_HUELLA_NIT" in r.json()["detail"], r.json())
        v.check("queda registrado como fallido",
                entorno.get("/catalogo/estado").json()["clientes"]["ultima"]["exitosa"] is False)


def test_lista_vacia_o_mal_formada_no_se_aplica(entorno, v):
    with _Claves():
        _huellas(entorno, ["800197268"])
        r = entorno.post("/catalogo/sincronizar-clientes", json={
            "huellas": [], "control": clientes.huella(clientes.TEXTO_DE_CONTROL, CLAVE_HUELLA),
        }, headers={"X-Clave-Sincronizacion": CLAVE})
        v.check("vacía: 400", r.status_code == 400, r.status_code)

        r = entorno.post("/catalogo/sincronizar-clientes", json={
            "huellas": ["800197268"],  # el NIT en claro, no la huella
            "control": clientes.huella(clientes.TEXTO_DE_CONTROL, CLAVE_HUELLA),
        }, headers={"X-Clave-Sincronizacion": CLAVE})
        v.check("un NIT en claro: 400", r.status_code == 400, r.status_code)

        db = entorno.Session()
        v.check("la lista anterior sigue en pie",
                db.query(HuellaClienteERP).count() == 1)
        db.close()


def test_sin_clave_de_huellas_se_cierra(entorno, v):
    with _Claves(huella=""):
        r = _huellas(entorno, ["800197268"], clave="x")
        v.check("503", r.status_code == 503, r.status_code)
        v.check("y dice qué falta", "CLAVE_HUELLA_NIT" in r.json()["detail"], r.json())


def test_sin_la_clave_de_sincronizacion_no_entra(entorno, v):
    with _Claves():
        r = entorno.post("/catalogo/sincronizar-clientes", json={"huellas": [], "control": ""},
                         headers={"X-Clave-Sincronizacion": "otra"})
        v.check("403", r.status_code == 403, r.status_code)
