"""
Un texto más largo que su columna no puede tumbar el registro de una PQRS.

Pasó en producción: escribir «5 galones de 20 litros» en la cantidad (una
columna de 20 caracteres) llegaba hasta el `commit`, Postgres respondía
`value too long for type character varying(20)` y la pantalla solo decía
«Error al crear la PQRS». Nadie sabía qué campo corregir, así que no se podía
registrar.

Estas pruebas no dependen de la base: SQLite NO aplica el largo de un
VARCHAR, y por eso el error nunca apareció aquí. Se comprueba la validación
que corre antes de tocar la base.
"""
from app.models.pqrs import PQRSSolicitud

BASE = {
    "tipo": "reclamo",
    "descripcion": "Llegó roto",
    "cliente_nombre": "Juan",
    "empresa": "ACME",
}


def _cuantas(entorno):
    db = entorno.Session()
    n = db.query(PQRSSolicitud).count()
    db.close()
    return n


def test_interna_rechaza_con_el_nombre_del_campo(entorno, v):
    r = entorno.post("/pqrs", data={**BASE, "cantidad_factura": "5 galones de 20 litros"})
    v.check("400 y no 500", r.status_code == 400, r.text[:200])
    detalle = r.json().get("detail", "")
    v.check("dice qué campo", "Cantidad en factura" in detalle, detalle)
    v.check("y cuánto admite", "20" in detalle, detalle)
    v.check("no queda nada guardado", _cuantas(entorno) == 0)


def test_publica_rechaza_igual(entorno, v):
    r = entorno.post("/public/pqrs", data={**BASE, "nit_cedula": "9" * 31})
    v.check("400 y no 500", r.status_code == 400, r.text[:200])
    v.check("dice qué campo", "NIT" in r.json().get("detail", ""), r.json())


def test_el_limite_exacto_si_cabe(entorno, v):
    r = entorno.post("/pqrs", data={**BASE, "cantidad_factura": "1" * 20})
    v.check("20 de 20 se registra", r.status_code == 201, r.text[:200])


def test_la_descripcion_no_tiene_tope(entorno, v):
    """Es Text: ahí va lo que no cabe en los demás campos."""
    r = entorno.post("/pqrs", data={**BASE, "descripcion": "x" * 5000})
    v.check("se registra", r.status_code == 201, r.text[:200])
