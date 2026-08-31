"""
Catálogo de productos sincronizado desde el ERP.

Lo que importa probar aquí es la seguridad y la integridad del lote: el
buscador está abierto a internet, y la sincronización reemplaza el catálogo
entero de una sola vez.
"""
from app.core.config import settings
from app.models.catalogo import ProductoCatalogo

CLAVE = "clave-de-prueba-para-sincronizar"


def _sincronizar(portal, productos, clave=CLAVE):
    return portal.post(
        "/catalogo/sincronizar",
        json={"productos": productos},
        headers={"X-Clave-Sincronizacion": clave},
    )


def _con_clave(fn):
    """Corre algo con la clave configurada y la deja como estaba."""
    original = settings.CLAVE_SINCRONIZACION
    settings.CLAVE_SINCRONIZACION = CLAVE
    try:
        return fn()
    finally:
        settings.CLAVE_SINCRONIZACION = original


# ── Quién puede sincronizar ──────────────────────────────────────────────

def test_sin_la_clave_no_se_sincroniza(entorno, v):
    def probar():
        r = _sincronizar(entorno, [{"codigo": "A1", "nombre": "Producto"}], clave="otra")
        v.check("una clave equivocada se rechaza", r.status_code == 403, r.status_code)

        r = entorno.post("/catalogo/sincronizar",
                         json={"productos": [{"codigo": "A1", "nombre": "X"}]})
        v.check("sin clave tampoco entra", r.status_code == 403, r.status_code)
    _con_clave(probar)


def test_si_no_hay_clave_configurada_el_endpoint_esta_cerrado(entorno, v):
    """Sin CLAVE_SINCRONIZACION en el .env, nadie puede escribir el catálogo."""
    original = settings.CLAVE_SINCRONIZACION
    settings.CLAVE_SINCRONIZACION = ""
    try:
        r = _sincronizar(entorno, [{"codigo": "A1", "nombre": "X"}])
        v.check("responde 503", r.status_code == 503, r.status_code)
        v.check("y dice qué falta",
                "CLAVE_SINCRONIZACION" in r.json()["detail"], r.json())
    finally:
        settings.CLAVE_SINCRONIZACION = original


# ── El lote ──────────────────────────────────────────────────────────────

def test_un_lote_vacio_no_borra_el_catalogo(entorno, v):
    """
    Un lote vacío casi siempre significa que la consulta al ERP falló. Si se
    aplicara, el buscador se quedaría sin ningún producto y nadie podría
    radicar una PQRS: es peor que quedarse con el catálogo de ayer.
    """
    def probar():
        _sincronizar(entorno, [{"codigo": "A1", "nombre": "Hipoclorito"}])
        r = _sincronizar(entorno, [])
        v.check("se rechaza", r.status_code == 400, r.status_code)
        v.check("y lo explica", "vacío" in r.json()["detail"], r.json())

        quedan = entorno.get("/catalogo/productos", params={"q": "hipo"}).json()
        v.check("el catálogo anterior sigue en pie", len(quedan) == 1, quedan)
    _con_clave(probar)


def test_sincronizar_agrega_actualiza_y_descontinua(entorno, v):
    def probar():
        r = _sincronizar(entorno, [
            {"codigo": "A1", "nombre": "Hipoclorito 13%", "presentacion": "20L"},
            {"codigo": "A2", "nombre": "Soda cáustica"},
        ])
        v.check("primer lote", r.json()["nuevos"] == 2, r.json())

        # A1 cambia de nombre, A2 desaparece del ERP, A3 es nuevo.
        r = _sincronizar(entorno, [
            {"codigo": "A1", "nombre": "Hipoclorito de sodio 13%", "presentacion": "20L"},
            {"codigo": "A3", "nombre": "Ácido sulfúrico"},
        ])
        datos = r.json()
        v.check("uno nuevo", datos["nuevos"] == 1, datos)
        v.check("uno actualizado", datos["actualizados"] == 1, datos)
        v.check("uno descontinuado", datos["descontinuados"] == 1, datos)
        v.check("quedan dos activos", datos["total_activos"] == 2, datos)

        v.check("el descontinuado ya no se busca",
                entorno.get("/catalogo/productos", params={"q": "soda"}).json() == [])
    _con_clave(probar)


def test_lo_descontinuado_no_se_borra(entorno, v):
    """Si mañana vuelve al catálogo del ERP, no se pierde nada."""
    def probar():
        _sincronizar(entorno, [{"codigo": "A1", "nombre": "Soda cáustica"}])
        _sincronizar(entorno, [{"codigo": "A9", "nombre": "Otro"}])

        db = entorno.Session()
        soda = db.query(ProductoCatalogo).filter(ProductoCatalogo.codigo == "A1").first()
        v.check("la fila sigue ahí", soda is not None)
        v.check("pero inactiva", soda.activo is False, soda.activo if soda else None)
        db.close()

        # Vuelve al ERP: se reactiva, no se duplica.
        r = _sincronizar(entorno, [{"codigo": "A1", "nombre": "Soda cáustica"}])
        v.check("se reactiva sin duplicar", r.json()["actualizados"] == 1, r.json())
    _con_clave(probar)


def test_las_filas_sin_codigo_o_sin_nombre_se_ignoran(entorno, v):
    """Un producto sin código no se puede ofrecer: mejor saltarlo que meter basura."""
    def probar():
        r = _sincronizar(entorno, [
            {"codigo": "A1", "nombre": "Bueno"},
            {"codigo": "", "nombre": "Sin código"},
            {"codigo": "A3", "nombre": "   "},
        ])
        v.check("solo entra el bueno", r.json()["total_activos"] == 1, r.json())
    _con_clave(probar)


# ── El buscador público ──────────────────────────────────────────────────

def test_el_buscador_publico_no_pide_sesion(entorno, v):
    def probar():
        _sincronizar(entorno, [{"codigo": "PK-001", "nombre": "Hipoclorito de sodio"}])
        r = entorno.get("/public/catalogo/productos", params={"q": "hipo"})
        v.check("responde sin autenticación", r.status_code == 200, r.status_code)
        v.check("y encuentra el producto", len(r.json()) == 1, r.json())
    _con_clave(probar)


def test_solo_devuelve_codigo_nombre_y_presentacion(entorno, v):
    """
    Lo consume el formulario público. Aunque el catálogo creciera, de aquí no
    puede salir nada más que esto.
    """
    def probar():
        _sincronizar(entorno, [
            {"codigo": "PK-001", "nombre": "Hipoclorito", "presentacion": "20L"},
        ])
        producto = entorno.get("/public/catalogo/productos", params={"q": "hipo"}).json()[0]
        v.check("exactamente tres campos",
                sorted(producto.keys()) == ["codigo", "nombre", "presentacion"],
                sorted(producto.keys()))
    _con_clave(probar)


def test_no_se_puede_recorrer_el_catalogo_letra_por_letra(entorno, v):
    """Con una sola letra no se busca: sería una forma de descargarse todo."""
    def probar():
        _sincronizar(entorno, [{"codigo": "PK-001", "nombre": "Hipoclorito"}])
        v.check("una letra no devuelve nada",
                entorno.get("/public/catalogo/productos", params={"q": "h"}).json() == [])
        v.check("vacío tampoco",
                entorno.get("/public/catalogo/productos", params={"q": ""}).json() == [])
        v.check("con dos ya sí",
                len(entorno.get("/public/catalogo/productos", params={"q": "hi"}).json()) == 1)
    _con_clave(probar)


def test_se_busca_por_codigo_y_sin_importar_mayusculas(entorno, v):
    def probar():
        _sincronizar(entorno, [{"codigo": "MP10957094", "nombre": "PAC Sólido"}])
        v.check("por código", len(entorno.get(
            "/public/catalogo/productos", params={"q": "MP109"}).json()) == 1)
        v.check("en minúscula también", len(entorno.get(
            "/public/catalogo/productos", params={"q": "mp109"}).json()) == 1)
        v.check("por nombre en mayúscula", len(entorno.get(
            "/public/catalogo/productos", params={"q": "PAC"}).json()) == 1)
    _con_clave(probar)


def test_el_buscador_limita_cuantos_devuelve(entorno, v):
    """Otro freno a la enumeración: no se devuelve el catálogo completo."""
    def probar():
        _sincronizar(entorno, [
            {"codigo": f"PK-{i:03d}", "nombre": f"Producto de prueba {i}"}
            for i in range(40)
        ])
        r = entorno.get("/public/catalogo/productos", params={"q": "prueba"}).json()
        v.check("devuelve como mucho 15", len(r) <= 15, len(r))
    _con_clave(probar)
