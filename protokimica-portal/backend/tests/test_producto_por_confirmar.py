"""
Cuando el cliente no encuentra su producto en el buscador.

El buscador no puede ser una pared: quien tiene un reclamo tiene que poder
radicarlo aunque su producto no aparezca. Pero un nombre escrito a mano no
sirve para un informe —«Hipoclorito», «hipoclorito 13» y «HIPOCLORITO x20L»
son tres productos distintos— así que la solicitud queda MARCADA y Servicio
al Cliente la confirma contra el catálogo antes de cerrarla.

Es el mismo trato que ya recibe el tipo, que el cliente casi nunca acierta.
"""
from app.models.catalogo import ProductoCatalogo
from app.models.pqrs import PQRSSolicitud

CANAL = "Venta institucional"   # tal como lo escribe core/canales.py


def _producto(entorno, codigo="PK-001", nombre="Hipoclorito de Sodio 13% x 20L"):
    db = entorno.Session()
    db.add(ProductoCatalogo(
        tenant_id=entorno.tenant_id, codigo=codigo, nombre=nombre,
        presentacion="Litro", activo=True,
    ))
    db.commit()
    db.close()
    return codigo


def _radicar(entorno, **extra):
    cuerpo = {
        "tipo": "reclamo",
        "descripcion": "El producto llegó con el sello roto.",
        "cliente_nombre": "Cliente",
        "canal_atencion": CANAL,
    }
    cuerpo.update(extra)
    return entorno.post("/pqrs", data=cuerpo)


# ── Al radicar ───────────────────────────────────────────────────────

def test_un_producto_del_catalogo_no_queda_pendiente(entorno, v):
    """Vino con código: está identificado y no hay nada que confirmar."""
    r = _radicar(entorno, producto_codigo="PK-001",
                 producto_nombre="Hipoclorito de Sodio 13% x 20L")

    v.check("radica", r.status_code == 201, r.text[:200])
    v.check("no queda marcada", r.json()["producto_por_confirmar"] is False, r.json())


def test_un_producto_escrito_a_mano_queda_marcado(entorno, v):
    """
    La salida de escape: se radica igual, pero queda señalada. Dejar al
    cliente sin radicar es peor que un dato que alguien tiene que ordenar.
    """
    r = _radicar(entorno, producto_nombre="hipoclorito el de 20 litros")

    v.check("radica igual", r.status_code == 201, r.text[:200])
    v.check("queda marcada", r.json()["producto_por_confirmar"] is True, r.json())
    v.check("y se conserva lo que escribió",
            r.json()["producto_nombre"] == "hipoclorito el de 20 litros", r.json())


def test_sin_producto_no_hay_nada_que_confirmar(entorno, v):
    """Una queja por el servicio no lleva producto: no puede quedar trabada."""
    r = _radicar(entorno, tipo="queja", descripcion="Me atendieron mal por teléfono.")

    v.check("no queda marcada", r.json()["producto_por_confirmar"] is False, r.json())


def test_un_nombre_de_puros_espacios_no_es_un_producto(entorno, v):
    r = _radicar(entorno, producto_nombre="   ")

    v.check("no queda marcada", r.json()["producto_por_confirmar"] is False, r.json())
    v.check("y el nombre entra vacío, no con espacios",
            r.json()["producto_nombre"] is None, r.json())


def test_la_marca_se_deduce_de_los_datos_no_del_formulario(entorno, v):
    """
    Mandar la bandera en el formulario no sirve de nada: se calcula del
    código. Si se aceptara escrita, un nombre a mano podría entrar a los
    informes disfrazado de producto identificado.
    """
    r = _radicar(entorno, producto_nombre="lo que sea",
                 producto_por_confirmar="false")

    v.check("igual queda marcada", r.json()["producto_por_confirmar"] is True, r.json())


def test_el_formulario_publico_marca_igual(entorno, v):
    """La ruta por la que entra de verdad un cliente."""
    r = entorno.post("/public/pqrs", data={
        "tipo": "reclamo",
        "descripcion": "Llegó menos cantidad de la que pedí.",
        "cliente_nombre": "Cliente",
        "cliente_email": "cliente@empresa.com",
        "canal_atencion": CANAL,
        "producto_nombre": "el blanqueador ese",
    })

    v.check("radica", r.status_code == 201, r.text[:200])

    db = entorno.Session()
    solicitud = db.query(PQRSSolicitud).order_by(PQRSSolicitud.id.desc()).first()
    v.check("queda marcada", solicitud.producto_por_confirmar is True)
    v.check("sin código", solicitud.producto_codigo is None, solicitud.producto_codigo)
    db.close()


# ── Confirmarlo antes de cerrar ──────────────────────────────────────

def test_no_se_cierra_con_el_producto_sin_confirmar(entorno, v):
    """
    La guarda: después de cerrar ya no se puede corregir, y el informe por
    producto —el que dice cuál da más problemas— quedaría mal.
    """
    entorno.como("admin")
    pqrs_id = _radicar(entorno, producto_nombre="hipoclorito el de 20 litros").json()["id"]

    r = entorno.patch(f"/pqrs/{pqrs_id}/estado", data={"estado": "cerrado"})

    v.check("no deja cerrar", r.status_code == 400, r.status_code)
    v.check("y dice qué hacer", "confirmar el producto" in r.json()["detail"].lower(),
            r.json()["detail"])
    v.check("mostrando lo que escribió el cliente",
            "hipoclorito el de 20 litros" in r.json()["detail"], r.json()["detail"])


def test_confirmarlo_toma_el_nombre_del_catalogo(entorno, v):
    """
    El nombre NO se recibe escrito: sale del catálogo a partir del código.
    Aceptarlo escrito sería volver al problema que esto viene a resolver.
    """
    entorno.como("admin")
    codigo = _producto(entorno)
    pqrs_id = _radicar(entorno, producto_nombre="hipoclorito el de 20 litros").json()["id"]

    r = entorno.patch(f"/pqrs/{pqrs_id}/producto", data={"producto_codigo": codigo})

    v.check("confirma", r.status_code == 200, r.text[:200])
    v.check("queda el nombre del catálogo",
            r.json()["producto_nombre"] == "Hipoclorito de Sodio 13% x 20L", r.json())
    v.check("con su código", r.json()["producto_codigo"] == codigo, r.json())
    v.check("y ya no está marcada",
            r.json()["producto_por_confirmar"] is False, r.json())


def test_una_vez_confirmado_ya_cierra(entorno, v):
    entorno.como("admin")
    codigo = _producto(entorno)
    pqrs_id = _radicar(entorno, producto_nombre="el blanqueador ese").json()["id"]
    entorno.patch(f"/pqrs/{pqrs_id}/producto", data={"producto_codigo": codigo})

    r = entorno.patch(f"/pqrs/{pqrs_id}/estado", data={"estado": "cerrado"})

    v.check("cierra", r.status_code == 200, r.text[:200])


def test_queda_en_la_trazabilidad_que_escribio_el_cliente(entorno, v):
    """
    Si mucha gente pide el mismo producto con un nombre que no está en el
    catálogo, eso dice algo del catálogo, no de los clientes.
    """
    entorno.como("admin")
    codigo = _producto(entorno)
    pqrs_id = _radicar(entorno, producto_nombre="hipoclorito el de 20 litros").json()["id"]
    entorno.patch(f"/pqrs/{pqrs_id}/producto", data={"producto_codigo": codigo})

    detalle = entorno.get(f"/pqrs/{pqrs_id}").json()
    eventos = [s for s in detalle["seguimientos"]
               if s["tipo_evento"] == "confirmacion_producto"]

    v.check("hay un registro", len(eventos) == 1, detalle["seguimientos"])
    v.check("dice lo que escribió el cliente",
            "hipoclorito el de 20 litros" in eventos[0]["comentario"],
            eventos[0]["comentario"])
    v.check("y a qué se cambió", codigo in eventos[0]["comentario"],
            eventos[0]["comentario"])


def test_solo_servicio_al_cliente_confirma_el_producto(entorno, v):
    """
    Por ÁREA, igual que cerrar y reclasificar: quien tiene el catálogo
    enfrente es Servicio al Cliente.
    """
    entorno.como("admin")
    codigo = _producto(entorno)
    pqrs_id = _radicar(entorno, producto_nombre="el blanqueador ese").json()["id"]

    entorno.como("logistica")
    r = entorno.patch(f"/pqrs/{pqrs_id}/producto", data={"producto_codigo": codigo})

    v.check("no puede", r.status_code == 403, r.status_code)


def test_un_codigo_que_no_esta_en_el_catalogo_se_rechaza(entorno, v):
    entorno.como("admin")
    pqrs_id = _radicar(entorno, producto_nombre="el blanqueador ese").json()["id"]

    r = entorno.patch(f"/pqrs/{pqrs_id}/producto", data={"producto_codigo": "NO-EXISTE"})

    v.check("responde 404", r.status_code == 404, r.status_code)
    v.check("y sugiere revisar la sincronización",
            "sincronización" in r.json()["detail"].lower(), r.json()["detail"])


def test_un_producto_descontinuado_no_sirve_para_confirmar(entorno, v):
    """
    Si dejó de venir del ERP, no es a lo que hay que amarrar una PQRS nueva:
    el informe quedaría apuntando a algo que ya no se vende.
    """
    entorno.como("admin")
    codigo = _producto(entorno)
    db = entorno.Session()
    db.query(ProductoCatalogo).filter(ProductoCatalogo.codigo == codigo).update(
        {"activo": False})
    db.commit()
    db.close()

    pqrs_id = _radicar(entorno, producto_nombre="el blanqueador ese").json()["id"]
    r = entorno.patch(f"/pqrs/{pqrs_id}/producto", data={"producto_codigo": codigo})

    v.check("no deja confirmarlo", r.status_code == 404, r.status_code)


def test_una_pqrs_cerrada_ya_no_cambia_de_producto(entorno, v):
    """Su producto ya entró a los indicadores del mes."""
    entorno.como("admin")
    codigo = _producto(entorno)
    pqrs_id = _radicar(entorno, producto_codigo=codigo,
                       producto_nombre="Hipoclorito de Sodio 13% x 20L").json()["id"]
    entorno.patch(f"/pqrs/{pqrs_id}/estado", data={"estado": "cerrado"})

    r = entorno.patch(f"/pqrs/{pqrs_id}/producto", data={"producto_codigo": codigo})

    v.check("no deja", r.status_code == 400, r.status_code)
    v.check("y explica cuándo se hace", "antes de cerrarla" in r.json()["detail"],
            r.json()["detail"])


# ── El buscador tiene que caber ──────────────────────────────────────

def test_un_nombre_largo_del_catalogo_cabe_en_la_pqrs(entorno, v):
    """
    `producto_nombre` mide lo mismo que `cat_productos.nombre` (300). Antes
    medía 200 y un producto de nombre largo se truncaba al radicar.
    """
    largo = "Lauril Éter Sulfato de Sodio 70% grado cosmético " * 5   # 240
    entorno.como("admin")
    codigo = _producto(entorno, codigo="PK-LARGO", nombre=largo[:300])
    pqrs_id = _radicar(entorno, producto_nombre="el que tiene el nombre largo").json()["id"]

    r = entorno.patch(f"/pqrs/{pqrs_id}/producto", data={"producto_codigo": codigo})

    v.check("confirma sin truncar", r.status_code == 200, r.text[:200])
    v.check("con el nombre completo",
            r.json()["producto_nombre"] == largo[:300], len(r.json()["producto_nombre"] or ""))
