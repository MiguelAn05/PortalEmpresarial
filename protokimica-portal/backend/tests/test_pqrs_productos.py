"""
Una PQRS con varios productos, cada uno con su lote y cantidades.

Un cliente que recibe tres productos malos de la misma compra tiene UN
reclamo: un plazo, un correo, una encuesta. Pero cada producto trae su lote y
sus cantidades, y el informe de qué producto da más problemas tiene que
contar los tres. Antes solo cabía uno y los demás terminaban escondidos en
la descripción.
"""
import json

from app.models.catalogo import ProductoCatalogo

BASE = {"tipo": "reclamo", "descripcion": "Llegaron dañados", "cliente_nombre": "Juan",
        "factura_numero": "FV-100"}

TRES = [
    {"producto_codigo": "PK-001", "producto_nombre": "Hipoclorito 13%", "lote": "L-1",
     "cantidad_factura": "10", "cantidad_reclamo": "2", "presentacion": "Litro",
     "cantidad_presentacion": "20"},
    {"producto_nombre": "el desengrasante verde", "lote": "L-2", "cantidad_factura": "5"},
    {"producto_codigo": "PK-003", "producto_nombre": "Soda cáustica", "lote": "L-3",
     "cantidad_reclamo": "1"},
]


def _radicar(entorno, productos, ruta="/pqrs", **extra):
    return entorno.post(ruta, data={**BASE, **extra, "productos": json.dumps(productos)})


def _catalogo(entorno, codigo="PK-009", nombre="Desengrasante industrial"):
    db = entorno.Session()
    db.add(ProductoCatalogo(tenant_id=entorno.tenant_id, codigo=codigo, nombre=nombre,
                            presentacion="Galón", activo=True))
    db.commit()
    db.close()


def _eventos(entorno, pid, tipo="cambio_producto"):
    return [s for s in entorno.get(f"/pqrs/{pid}").json()["seguimientos"]
            if s["tipo_evento"] == tipo]


# ── Al radicar ───────────────────────────────────────────────────────

def test_radica_varios_productos_con_su_lote(entorno, v):
    r = _radicar(entorno, TRES)
    v.check("radica", r.status_code == 201, r.text[:300])
    productos = r.json()["productos"]
    v.check("los tres", len(productos) == 3, productos)
    v.check("cada uno con su lote", [p["lote"] for p in productos] == ["L-1", "L-2", "L-3"], productos)
    v.check("en el orden en que se escribieron",
            [p["producto_nombre"] for p in productos][0] == "Hipoclorito 13%", productos)
    v.check("la factura es una sola", r.json()["factura_numero"] == "FV-100", r.json())


def test_solo_el_escrito_a_mano_queda_por_confirmar(entorno, v):
    productos = _radicar(entorno, TRES).json()
    marcas = [p["por_confirmar"] for p in productos["productos"]]
    v.check("solo el segundo", marcas == [False, True, False], marcas)
    v.check("y la PQRS lo dice", productos["producto_por_confirmar"] is True, productos)


def test_el_formulario_publico_tambien(entorno, v):
    r = _radicar(entorno, TRES, ruta="/public/pqrs")
    v.check("radica", r.status_code == 201, r.text[:300])
    pid = entorno.get("/pqrs").json()[0]["id"]
    v.check("con los tres", len(entorno.get(f"/pqrs/{pid}").json()["productos"]) == 3)


def test_las_filas_vacias_se_ignoran(entorno, v):
    """El formulario deja una fila en blanco si alguien agrega y no llena."""
    r = _radicar(entorno, [TRES[0], {"producto_nombre": "  ", "lote": ""}])
    v.check("radica", r.status_code == 201, r.text[:300])
    v.check("con uno solo", len(r.json()["productos"]) == 1, r.json()["productos"])


def test_una_fila_con_lote_pero_sin_producto_se_rechaza(entorno, v):
    r = _radicar(entorno, [TRES[0], {"lote": "L-9"}])
    v.check("400", r.status_code == 400, r.text[:300])
    v.check("dice cuál fila", "producto 2" in r.json()["detail"].lower(), r.json())


def test_el_largo_se_revisa_por_producto(entorno, v):
    r = _radicar(entorno, [TRES[0], {**TRES[1], "lote": "L" * 51}])
    v.check("400 y no 500", r.status_code == 400, r.text[:300])
    v.check("dice cuál producto y qué campo",
            "Producto 2" in r.json()["detail"] and "Lote" in r.json()["detail"], r.json())


def test_hay_un_tope_de_productos(entorno, v):
    r = _radicar(entorno, [TRES[0]] * 21)
    v.check("400", r.status_code == 400, r.text[:300])


def test_una_lista_mal_formada_no_revienta(entorno, v):
    r = entorno.post("/pqrs", data={**BASE, "productos": "{no es json"})
    v.check("400 y no 500", r.status_code == 400, r.text[:300])


def test_el_formato_viejo_de_un_producto_sigue_sirviendo(entorno, v):
    """Un formulario cacheado en el celular del cliente no puede quedarse sin radicar."""
    r = entorno.post("/public/pqrs", data={**BASE, "producto_nombre": "Hipoclorito", "lote": "L-5"})
    v.check("radica", r.status_code == 201, r.text[:300])
    pid = entorno.get("/pqrs").json()[0]["id"]
    productos = entorno.get(f"/pqrs/{pid}").json()["productos"]
    v.check("como un producto", len(productos) == 1 and productos[0]["lote"] == "L-5", productos)


# ── Después de radicar ───────────────────────────────────────────────

def test_no_cierra_si_falta_confirmar_alguno(entorno, v):
    pid = _radicar(entorno, TRES).json()["id"]
    r = entorno.patch(f"/pqrs/{pid}/estado", data={"estado": "cerrado"})
    v.check("no deja", r.status_code == 400, r.text[:300])
    v.check("nombra el pendiente", "el desengrasante verde" in r.json()["detail"], r.json())


def test_confirmar_uno_no_toca_los_demas(entorno, v):
    _catalogo(entorno)
    datos = _radicar(entorno, TRES).json()
    segundo = datos["productos"][1]
    r = entorno.patch(f"/pqrs/{datos['id']}/productos/{segundo['id']}/confirmar",
                      data={"producto_codigo": "PK-009"})
    v.check("confirma", r.status_code == 200, r.text[:300])
    productos = r.json()["productos"]
    v.check("con el nombre del catálogo", productos[1]["producto_nombre"] == "Desengrasante industrial")
    v.check("conserva su lote", productos[1]["lote"] == "L-2", productos[1])
    v.check("los otros intactos", productos[0]["producto_nombre"] == "Hipoclorito 13%")
    v.check("ya no hay pendientes", r.json()["producto_por_confirmar"] is False)
    r = entorno.patch(f"/pqrs/{datos['id']}/estado", data={"estado": "cerrado"})
    v.check("y ahora sí cierra", r.status_code == 200, r.text[:300])


def test_agregar_un_producto_que_falto(entorno, v):
    pid = _radicar(entorno, [TRES[0]]).json()["id"]
    entorno.como("logistica")
    r = entorno.post(f"/pqrs/{pid}/productos",
                     json={"producto_nombre": "Ácido muriático", "lote": "L-8"})
    v.check("se agrega", r.status_code == 201, r.text[:300])
    v.check("queda al final", r.json()["productos"][-1]["lote"] == "L-8", r.json()["productos"])
    v.check("escrito a mano: por confirmar", r.json()["productos"][-1]["por_confirmar"] is True)
    v.check("y en el historial", len(_eventos(entorno, pid)) == 1)


def test_corregir_el_lote_de_uno(entorno, v):
    datos = _radicar(entorno, TRES).json()
    primero = datos["productos"][0]
    r = entorno.patch(f"/pqrs/{datos['id']}/productos/{primero['id']}", json={"lote": "L-1B"})
    v.check("corrige", r.status_code == 200, r.text[:300])
    v.check("solo ese", [p["lote"] for p in r.json()["productos"]] == ["L-1B", "L-2", "L-3"])
    texto = _eventos(entorno, datos["id"])[0]["comentario"]
    v.check("historial con antes y después", "L-1" in texto and "L-1B" in texto, texto)


def test_corregir_no_cambia_nombre_ni_codigo(entorno, v):
    """Eso va por el catálogo."""
    datos = _radicar(entorno, TRES).json()
    primero = datos["productos"][0]
    r = entorno.patch(f"/pqrs/{datos['id']}/productos/{primero['id']}",
                      json={"producto_nombre": "otra cosa", "lote": "L-X"})
    v.check("el nombre sigue", r.json()["productos"][0]["producto_nombre"] == "Hipoclorito 13%")


def test_quitar_un_producto_deja_sus_datos_en_el_historial(entorno, v):
    datos = _radicar(entorno, TRES).json()
    tercero = datos["productos"][2]
    r = entorno.delete(f"/pqrs/{datos['id']}/productos/{tercero['id']}")
    v.check("se quita", r.status_code == 200 and len(r.json()["productos"]) == 2, r.text[:300])
    texto = _eventos(entorno, datos["id"])[0]["comentario"]
    v.check("con nombre y lote", "Soda cáustica" in texto and "L-3" in texto, texto)


def test_un_producto_de_otra_pqrs_es_404(entorno, v):
    a = _radicar(entorno, [TRES[0]]).json()
    b = _radicar(entorno, [TRES[2]]).json()
    r = entorno.delete(f"/pqrs/{a['id']}/productos/{b['productos'][0]['id']}")
    v.check("404", r.status_code == 404, r.text[:300])


def test_cerrada_no_se_tocan_los_productos(entorno, v):
    datos = _radicar(entorno, [TRES[0]]).json()
    entorno.patch(f"/pqrs/{datos['id']}/estado", data={"estado": "cerrado"})
    pid, prod = datos["id"], datos["productos"][0]["id"]
    v.check("no agrega", entorno.post(f"/pqrs/{pid}/productos",
                                      json={"producto_nombre": "X"}).status_code == 400)
    v.check("no corrige", entorno.patch(f"/pqrs/{pid}/productos/{prod}",
                                        json={"lote": "Z"}).status_code == 400)
    v.check("no quita", entorno.delete(f"/pqrs/{pid}/productos/{prod}").status_code == 400)


def test_lectura_no_toca_productos(entorno, v):
    datos = _radicar(entorno, [TRES[0]]).json()
    entorno.como("lectura")
    r = entorno.post(f"/pqrs/{datos['id']}/productos", json={"producto_nombre": "X"})
    v.check("403", r.status_code == 403, r.text[:300])
