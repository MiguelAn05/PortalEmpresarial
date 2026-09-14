"""
Corregir los datos de una PQRS radicada: cliente, factura y adjuntos.

El cliente escribe con prisa desde el celular. Un correo con una letra de más
es un cliente que nunca recibe la solución ni la encuesta, así que tiene que
poder arreglarse — pero dejando rastro: cada corrección queda en el historial
con el valor anterior y el nuevo.
"""
from app.models.pqrs import PQRSSolicitud


def _pqrs(entorno, estado="en_proceso", **extra):
    datos = dict(
        tenant_id=entorno.tenant_id, tipo="reclamo", cliente_nombre="Juan Pérez",
        cliente_email="juan@correo.com", empresa="Industrias del Valle",
        descripcion="Llegó roto", estado=estado, prioridad="alta",
        origen_publico="publico",
    )
    datos.update(extra)
    db = entorno.Session()
    p = PQRSSolicitud(**datos)
    db.add(p)
    db.commit()
    pid = p.id
    db.close()
    return pid


def _historial(entorno, pid, tipo_evento):
    segs = entorno.get(f"/pqrs/{pid}").json()["seguimientos"]
    return [s for s in segs if s["tipo_evento"] == tipo_evento]


# ── Datos ────────────────────────────────────────────────────────────

def test_corrige_solo_lo_que_llega(entorno, v):
    pid = _pqrs(entorno)
    entorno.como("logistica")

    r = entorno.patch(f"/pqrs/{pid}/datos",
                      json={"cliente_email": "  juan.perez@correo.com ", "ciudad": "Bello"})
    v.check("guarda", r.status_code == 200, r.text[:200])
    v.check("correo corregido y sin espacios",
            r.json()["cliente_email"] == "juan.perez@correo.com", r.json())
    v.check("ciudad nueva", r.json()["ciudad"] == "Bello", r.json())
    v.check("lo que no llegó no se toca",
            r.json()["empresa"] == "Industrias del Valle", r.json())


def test_queda_en_el_historial_con_antes_y_despues(entorno, v):
    pid = _pqrs(entorno)
    entorno.patch(f"/pqrs/{pid}/datos", json={"cliente_email": "otro@correo.com"})

    eventos = _historial(entorno, pid, "edicion_datos")
    v.check("un evento", len(eventos) == 1, eventos)
    texto = eventos[0]["comentario"] if eventos else ""
    v.check("con el valor anterior", "juan@correo.com" in texto, texto)
    v.check("y el nuevo", "otro@correo.com" in texto, texto)


def test_vaciar_un_campo_es_borrarlo(entorno, v):
    pid = _pqrs(entorno)
    r = entorno.patch(f"/pqrs/{pid}/datos", json={"empresa": "   "})
    v.check("queda vacío, no con espacios", r.json()["empresa"] is None, r.json())


def test_el_contacto_no_puede_quedar_vacio(entorno, v):
    pid = _pqrs(entorno)
    r = entorno.patch(f"/pqrs/{pid}/datos", json={"cliente_nombre": ""})
    v.check("se rechaza", r.status_code == 400, r.text[:200])


def test_un_correo_invalido_se_rechaza_con_explicacion(entorno, v):
    pid = _pqrs(entorno)
    r = entorno.patch(f"/pqrs/{pid}/datos", json={"cliente_email": "juan@@correo"})
    v.check("400", r.status_code == 400, r.text[:200])
    v.check("dice por qué importa", "encuesta" in r.json()["detail"], r.json())


def test_sin_cambios_no_ensucia_el_historial(entorno, v):
    pid = _pqrs(entorno)
    r = entorno.patch(f"/pqrs/{pid}/datos", json={"empresa": "Industrias del Valle"})
    v.check("se rechaza", r.status_code == 400, r.text[:200])
    v.check("sin evento", _historial(entorno, pid, "edicion_datos") == [])


def test_ni_tipo_ni_canal_ni_descripcion_se_cuelan(entorno, v):
    """Esos tienen su propio camino (ver pqrs/edicion.py)."""
    pid = _pqrs(entorno, canal_atencion="Punto de venta Centro")
    entorno.patch(f"/pqrs/{pid}/datos", json={
        "ciudad": "Envigado", "tipo": "felicitacion",
        "canal_atencion": "WhatsApp", "descripcion": "otra cosa",
    })
    p = entorno.get(f"/pqrs/{pid}").json()
    v.check("tipo intacto", p["tipo"] == "reclamo", p["tipo"])
    v.check("canal intacto", p["canal_atencion"] == "Punto de venta Centro", p["canal_atencion"])
    v.check("descripción intacta", p["descripcion"] == "Llegó roto", p["descripcion"])


def test_cerrada_no_se_corrige(entorno, v):
    pid = _pqrs(entorno, estado="cerrado")
    r = entorno.patch(f"/pqrs/{pid}/datos", json={"ciudad": "Bello"})
    v.check("se rechaza", r.status_code == 400, r.text[:200])
    v.check("y el alcance no lo ofrece",
            entorno.get(f"/pqrs/{pid}").json()["alcance"]["puede_editar_datos"] is False)


def test_lectura_y_gerencia_no_corrigen(entorno, v):
    pid = _pqrs(entorno)
    for quien in ("lectura", "gerencia"):
        entorno.como(quien)
        r = entorno.patch(f"/pqrs/{pid}/datos", json={"ciudad": "Bello"})
        v.check(f"{quien}: 403", r.status_code == 403, r.text[:200])
        v.check(f"{quien}: el alcance no lo ofrece",
                entorno.get(f"/pqrs/{pid}").json()["alcance"]["puede_editar_datos"] is False)


def test_un_texto_mas_largo_que_la_columna_se_rechaza(entorno, v):
    pid = _pqrs(entorno)
    r = entorno.patch(f"/pqrs/{pid}/datos", json={"nit_cedula": "9" * 31})
    v.check("422", r.status_code == 422, r.text[:200])


# ── Adjuntos ─────────────────────────────────────────────────────────

PDF = ("factura.pdf", b"%PDF-1.4 prueba", "application/pdf")


def test_reemplazar_la_factura(entorno, v):
    pid = _pqrs(entorno, adjunto_factura="/uploads/facturas/vieja.pdf")
    r = entorno.client.put(f"/pqrs/{pid}/adjuntos/factura", files={"archivo": PDF})
    v.check("guarda", r.status_code == 200, r.text[:200])
    nueva = r.json()["adjunto_factura"]
    v.check("apunta a un archivo nuevo",
            nueva and nueva != "/uploads/facturas/vieja.pdf", nueva)

    eventos = _historial(entorno, pid, "cambio_adjunto")
    v.check("queda en el historial", len(eventos) == 1, eventos)
    v.check("con la ruta del anterior, para recuperarlo",
            "vieja.pdf" in (eventos[0]["comentario"] if eventos else ""), eventos)


def test_quitar_un_adjunto_equivocado(entorno, v):
    pid = _pqrs(entorno, adjunto_producto="/uploads/productos/otro.jpg")
    r = entorno.delete(f"/pqrs/{pid}/adjuntos/producto")
    v.check("se quita", r.status_code == 200, r.text[:200])
    v.check("queda sin foto", r.json()["adjunto_producto"] is None, r.json())
    v.check("y deja rastro", len(_historial(entorno, pid, "cambio_adjunto")) == 1)


def test_adjuntar_donde_no_habia_nada(entorno, v):
    pid = _pqrs(entorno)
    r = entorno.client.put(f"/pqrs/{pid}/adjuntos/factura", files={"archivo": PDF})
    v.check("se adjunta", r.status_code == 200 and r.json()["adjunto_factura"], r.text[:200])


def test_quitar_lo_que_no_existe_se_rechaza(entorno, v):
    pid = _pqrs(entorno)
    r = entorno.delete(f"/pqrs/{pid}/adjuntos/video")
    v.check("400", r.status_code == 400, r.text[:200])


def test_un_adjunto_desconocido_es_404(entorno, v):
    pid = _pqrs(entorno)
    r = entorno.delete(f"/pqrs/{pid}/adjuntos/cedula")
    v.check("404", r.status_code == 404, r.text[:200])


def test_el_video_valida_como_video(entorno, v):
    pid = _pqrs(entorno)
    r = entorno.client.put(f"/pqrs/{pid}/adjuntos/video", files={"archivo": PDF})
    v.check("un PDF no pasa como video", r.status_code == 400, r.text[:200])


def test_adjuntos_de_una_cerrada_no_se_tocan(entorno, v):
    pid = _pqrs(entorno, estado="cerrado", adjunto_factura="/uploads/facturas/f.pdf")
    v.check("no se quita", entorno.delete(f"/pqrs/{pid}/adjuntos/factura").status_code == 400)
    r = entorno.client.put(f"/pqrs/{pid}/adjuntos/factura", files={"archivo": PDF})
    v.check("ni se reemplaza", r.status_code == 400, r.text[:200])
