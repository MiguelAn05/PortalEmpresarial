"""
Documentos que genera Fichas de seguridad: certificado de análisis (AP-F-06) y
FDS (AP-F-08). Se prueba que la lectura con IA PROPONE y no guarda, que lo
vacío no bloquea pero se señala, que el historial conserva el PDF tal como se
generó, que el consecutivo no repite y que solo escribe quien tiene la
capacidad.

La lectura del documento del proveedor es por reglas (`lectura_reglas.py`): se
prueba con PDF hechos al vuelo, incluido uno generado por el propio portal.
"""
import pytest

from app.core import capacidades
from app.core.config import settings
from app.models.fichas_seguridad import FdsDocumento
from app.modules.fichas_seguridad.permisos import CAPACIDAD_GESTIONAR

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
CERTIFICADO = {
    "producto": "HIPOCLORITO DE CALCIO", "proveedor": "GTM CALDIC", "lote_fabricante": "HKKJ25171",
    "fecha_fabricacion": "15/12/2025", "fecha_vencimiento": "14/12/2027",
    "parametros": [{"nombre": "Cloro disponible", "unidad": "%", "requisito": "≥ 70",
                    "metodo": "Valoración yodométrica", "resultado": "72.3"}],
}


@pytest.fixture
def portal(entorno, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DOCUMENTOS_DIR", str(tmp_path))
    entorno.carpeta = tmp_path
    return entorno




def _generar(portal, datos=None, tipo="certificado_analisis"):
    return portal.post("/fichas-seguridad/documentos/generar", json={"tipo": tipo, "datos": datos or CERTIFICADO})


def _otorgar(portal, area="Calidad"):
    db = portal.Session()
    capacidades.otorgar_a_area(db, portal.tenant_id, CAPACIDAD_GESTIONAR, area, portal.ids["admin"])
    db.close()




def test_generar_guarda_el_pdf_los_datos_y_se_baja_igual(portal, v):
    r = _generar(portal)
    v.check("generar -> 201", r.status_code == 201, r.text[:200])
    doc = r.json()
    v.check("el nombre sigue el formato", doc["nombre_archivo"].endswith("_001.pdf") and "_RMC_" in doc["nombre_archivo"], doc["nombre_archivo"])
    bajado = portal.get(f"/fichas-seguridad/documentos/{doc['id']}/archivo")
    v.check("baja un PDF de verdad", bajado.status_code == 200 and bajado.content[:5] == b"%PDF-")
    v.check("sin caché", bajado.headers["cache-control"] == "no-store")
    v.check("y es el mismo cada vez", portal.get(f"/fichas-seguridad/documentos/{doc['id']}/archivo").content == bajado.content)
    detalle = portal.get(f"/fichas-seguridad/documentos/{doc['id']}").json()
    v.check("guarda los datos firmados", detalle["datos"]["parametros"][0]["resultado"] == "72.3", detalle)


def test_lo_vacio_no_bloquea_pero_sin_producto_si(portal, v):
    v.check("solo con producto -> 201", _generar(portal, {"producto": "Soda cáustica"}).status_code == 201)
    sin = _generar(portal, {"proveedor": "X"})
    v.check("sin producto -> 400 que dice qué hacer", sin.status_code == 400 and "producto" in sin.text, sin.text[:200])
    largo = _generar(portal, {"producto": "A" * 201})
    v.check("texto más largo que el tope -> 400 con el campo", largo.status_code == 400 and "producto" in largo.text, largo.text[:200])
    v.check("tipo desconocido -> 400", _generar(portal, tipo="otro").status_code == 400)


def test_el_consecutivo_del_dia_sube_y_no_repite_aunque_se_borre_uno(portal, v):
    a, b, c = (_generar(portal).json() for _ in range(3))
    v.check("001, 002, 003", [x["nombre_archivo"][-7:-4] for x in (a, b, c)] == ["001", "002", "003"])
    db = portal.Session()
    db.query(FdsDocumento).filter(FdsDocumento.id == b["id"]).delete()
    db.commit()
    db.close()
    d = _generar(portal).json()
    v.check("tras borrar el 002 sigue el 004, no un 003 repetido", d["nombre_archivo"][-7:-4] == "004", d["nombre_archivo"])


def test_el_codigo_sale_del_repositorio_de_fichas(portal, v):
    portal.post("/fichas-seguridad", data={"nombre_producto": "Hipoclorito de calcio", "version": "3",
                                           "fecha_emision": "2024-01-10", "codigo_producto": "mp-0042"},
                files={"archivo": ("f.pdf", PDF, "application/pdf")})
    doc = _generar(portal).json()
    v.check("toma el código de la ficha, sin importar tildes ni mayúsculas", doc["codigo_producto"] == "MP-0042", doc)
    v.check("y se refleja en el nombre del archivo", doc["nombre_archivo"].startswith("MP-0042_RMC_"), doc["nombre_archivo"])
    propio = _generar(portal, {**CERTIFICADO, "codigo_producto": "XX-1"}).json()
    v.check("un código escrito a mano no se pisa", propio["codigo_producto"] == "XX-1")
    desconocido = _generar(portal, {"producto": "Producto sin ficha"}).json()
    v.check("sin coincidencia queda vacío y genera igual", desconocido["codigo_producto"] is None)


def test_la_fds_se_genera_con_sus_16_secciones_y_un_texto_raro_no_rompe_el_pdf(portal, v):
    datos = {"producto": "Ácido <b>acético</b> & cía", "version": "10", "fecha_emision": "2023-09-21",
             "secciones": [{"numero": 1, "titulo": "x", "contenido": "Línea 1\nLínea 2 <script>"}]}
    r = _generar(portal, datos, tipo="fds")
    v.check("FDS -> 201", r.status_code == 201, r.text[:200])
    v.check("baja como PDF", portal.get(f"/fichas-seguridad/documentos/{r.json()['id']}/archivo").content[:5] == b"%PDF-")
    mala = _generar(portal, {"producto": "X", "secciones": [{"numero": 17, "contenido": "x"}]}, tipo="fds")
    v.check("sección fuera de 1 a 16 -> 400", mala.status_code == 400, mala.text[:200])


def test_la_vista_previa_devuelve_el_pdf_sin_guardar(portal, v):
    r = portal.post("/fichas-seguridad/documentos/vista-previa", json={"tipo": "certificado_analisis", "datos": CERTIFICADO})
    v.check("vista previa -> PDF", r.status_code == 200 and r.content[:5] == b"%PDF-", r.text[:100])
    v.check("no queda en el historial", portal.get("/fichas-seguridad/documentos").json()["total"] == 0)


def test_el_historial_se_busca_y_se_filtra_por_tipo(portal, v):
    _generar(portal)
    _generar(portal, {"producto": "Soda cáustica", "proveedor": "Otro"})
    _generar(portal, {"producto": "Ácido acético", "version": "5"}, tipo="fds")
    v.check("hay tres", portal.get("/fichas-seguridad/documentos").json()["total"] == 3)
    v.check("busca sin tildes", portal.get("/fichas-seguridad/documentos", params={"q": "acido acetico"}).json()["total"] == 1)
    v.check("filtra por tipo", portal.get("/fichas-seguridad/documentos", params={"tipo": "fds"}).json()["total"] == 1)
    v.check("tipo desconocido -> 400", portal.get("/fichas-seguridad/documentos", params={"tipo": "x"}).status_code == 400)
    v.check("el más reciente primero", portal.get("/fichas-seguridad/documentos").json()["documentos"][0]["producto"] == "Ácido acético")


def test_solo_escribe_quien_tiene_la_capacidad_pero_todos_consultan(portal, v):
    doc = _generar(portal).json()
    _otorgar(portal, "Calidad")
    pdf = _pdf_fds_de_prueba()
    for quien in ("tics", "lectura", "gerencia"):
        portal.como(quien)
        v.check(f"{quien} no lee el documento", _leer(portal, pdf).status_code == 403)
        v.check(f"{quien} no genera", _generar(portal).status_code == 403)
        v.check(f"{quien} no ve vista previa", portal.post("/fichas-seguridad/documentos/vista-previa",
                json={"tipo": "fds", "datos": {"producto": "x"}}).status_code == 403)
        v.check(f"{quien} sí consulta el historial", portal.get("/fichas-seguridad/documentos").status_code == 200)
        v.check(f"{quien} sí baja el PDF", portal.get(f"/fichas-seguridad/documentos/{doc['id']}/archivo").status_code == 200)
    portal.como("calidad")
    v.check("el área con la capacidad sí genera", _generar(portal).status_code == 201)


def test_cada_empresa_ve_solo_sus_documentos(portal, v):
    import datetime
    from app.models.tenant import Tenant, TenantModulo
    propio = _generar(portal).json()
    db = portal.Session()
    otra = Tenant(nombre="Otra empresa", slug="otra-fds-doc")
    db.add(otra)
    db.flush()
    db.add(TenantModulo(tenant_id=otra.id, modulo="fichas_seguridad", activo=True))
    db.add(FdsDocumento(tenant_id=otra.id, tipo="fds", producto="Ajeno", datos={}, dia=datetime.date.today(),
                        consecutivo=1, nombre_archivo="a.pdf", ruta="x/a.pdf", tamano=1))
    db.commit()
    ajeno_id = db.query(FdsDocumento).filter_by(producto="Ajeno").one().id
    db.close()
    lista = portal.get("/fichas-seguridad/documentos").json()
    v.check("la lista no trae el ajeno", [d["producto"] for d in lista["documentos"]] == [propio["producto"]], lista)
    v.check("abrir el ajeno -> 404", portal.get(f"/fichas-seguridad/documentos/{ajeno_id}").status_code == 404)
    v.check("bajar el ajeno -> 404", portal.get(f"/fichas-seguridad/documentos/{ajeno_id}/archivo").status_code == 404)
    v.check("el propio sí", portal.get(f"/fichas-seguridad/documentos/{propio['id']}").status_code == 200)


# ── Lectura del documento del proveedor ───────────────────────────────

def _pdf_fds_de_prueba(paginas_de_relleno=12):
    """Una FDS larga (varias páginas, para que el encabezado se repita) hecha con el propio generador."""
    from app.modules.fichas_seguridad import pdf_documentos
    relleno = " ".join(["texto"] * 60)
    secciones = [{"numero": i, "contenido": f"a) Primer subtema {i}: {relleno}\nb) Segundo subtema {i}: {relleno}"}
                 for i in range(1, 17)]
    secciones[3]["contenido"] = ("• Ingestión: NO INDUZCA EL VÓMITO. Enjuague la boca\ny dé de beber agua.\n"
                                 "Inhalación: Traslade a la víctima al aire limpio.")
    secciones[1]["contenido"] = "H314 - Provoca quemaduras graves.\nH226 - Líquidos y vapores inflamables."
    return pdf_documentos.generar("fds", {"producto": "ÁCIDO ACÉTICO GLACIAL FOOD GRADE", "version": "10",
                                          "fecha_emision": "21/09/2023", "secciones": secciones}, "x")


def _leer(portal, contenido, tipo="fds"):
    return portal.post("/fichas-seguridad/documentos/extraer", data={"tipo": tipo},
                       files={"archivo": ("f.pdf", contenido, "application/pdf")})


def test_una_fds_con_texto_se_lee_y_no_guarda_nada(portal, v):
    r = _leer(portal, _pdf_fds_de_prueba())
    v.check("-> 200", r.status_code == 200, r.text[:300])
    datos, secciones = r.json()["datos"], r.json()["datos"]["secciones"]
    v.check("producto del título repetido en cada página", datos["producto"] == "ÁCIDO ACÉTICO GLACIAL FOOD GRADE", datos["producto"])
    v.check("versión y fecha del encabezado", datos["version"] == "10" and datos["fecha_emision"] == "21/09/2023", datos)
    v.check("las 16 secciones con contenido", len(secciones) == 16 and all(s["contenido"] for s in secciones),
            [s["numero"] for s in secciones if not s["contenido"]])
    v.check("cada sección con SU contenido", "subtema 7" in secciones[6]["contenido"] and "subtema 8" not in secciones[6]["contenido"])
    todo = " ".join(s["contenido"] for s in secciones)
    v.check("el encabezado y el pie no se cuelan como contenido",
            "Productos Químicos al por Mayor" not in todo and "Página:" not in todo and "Código: AP-F-08" not in todo)
    v.check("los subtemas quedan uno por línea", secciones[0]["contenido"].count("\n") == 1, secciones[0]["contenido"][:120])
    v.check("las frases H, una por línea", secciones[1]["contenido"] == "H314 - Provoca quemaduras graves.\nH226 - Líquidos y vapores inflamables.",
            secciones[1]["contenido"])
    v.check("una línea cortada por el ancho de página se une; un subtema nuevo no",
            secciones[3]["contenido"] == "• Ingestión: NO INDUZCA EL VÓMITO. Enjuague la boca y dé de beber agua.\n"
                                         "Inhalación: Traslade a la víctima al aire limpio.", secciones[3]["contenido"])
    v.check("no inventa lo que no hay: sin faltantes de lectura salvo el proveedor", r.json()["faltantes"] == ["proveedor"], r.json()["faltantes"])
    v.check("avisa que no se tradujo", "sin traducir" in r.json()["avisos"][0], r.json()["avisos"])
    v.check("no guardó nada", portal.get("/fichas-seguridad/documentos").json()["total"] == 0)


def test_lo_leido_se_puede_generar_tal_cual(portal, v):
    datos = _leer(portal, _pdf_fds_de_prueba()).json()["datos"]
    r = _generar(portal, datos, tipo="fds")
    v.check("generar lo leído -> 201", r.status_code == 201, r.text[:200])


def test_un_certificado_trae_la_cabecera_y_avisa_que_la_tabla_no(portal, v):
    from reportlab.pdfgen import canvas
    import io
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    y = 780
    for linea in ("CERTIFICATE OF ANALYSIS", "Product: HIPOCLORITO DE CALCIO 70%", "Lot No: HKKJ25171",
                  "Fecha de fabricación: 15/12/2025", "Fecha de vencimiento: 14/12/2027", "Cloro disponible 72.3 %"):
        c.drawString(60, y, linea)
        y -= 20
    c.save()
    r = _leer(portal, buf.getvalue(), tipo="certificado_analisis")
    v.check("-> 200", r.status_code == 200, r.text[:300])
    datos = r.json()["datos"]
    v.check("producto", datos["producto"] == "HIPOCLORITO DE CALCIO 70%", datos["producto"])
    v.check("lote del fabricante", datos["lote_fabricante"] == "HKKJ25171", datos["lote_fabricante"])
    v.check("fechas", datos["fecha_fabricacion"] == "15/12/2025" and datos["fecha_vencimiento"] == "14/12/2027", datos)
    v.check("la tabla no se inventa y se dice", datos["parametros"] == "" or datos["parametros"] == []
            and "tabla de parámetros" in r.json()["faltantes"] and "tabla de parámetros no se lee" in r.json()["avisos"][0],
            (datos["parametros"], r.json()["faltantes"], r.json()["avisos"]))


def test_un_pdf_sin_texto_una_imagen_o_un_metodo_raro_dicen_que_hacer(portal, v):
    from reportlab.pdfgen import canvas
    import io
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.rect(50, 50, 200, 200)
    c.save()
    escaneo = _leer(portal, buf.getvalue())
    v.check("PDF sin texto -> 400 que habla de escaneo", escaneo.status_code == 400 and "escaneo" in escaneo.text, escaneo.text[:200])
    imagen = _leer(portal, b"\x89PNG\r\n\x1a\n" + b"0" * 50)
    v.check("una imagen sin IA -> 400", imagen.status_code == 400 and "PDF" in imagen.text, imagen.text[:200])
    dañado = _leer(portal, b"%PDF-1.4 esto no es un pdf de verdad")
    v.check("PDF dañado -> 400, no 500", dañado.status_code == 400, dañado.text[:200])


def test_leer_el_documento_tambien_pide_la_capacidad(portal, v):
    _otorgar(portal, "Calidad")
    portal.como("tics")
    v.check("sin la capacidad -> 403", _leer(portal, _pdf_fds_de_prueba()).status_code == 403)


def test_la_propuesta_recorta_lo_que_se_pasa_de_largo_en_vez_de_perder_la_lectura(portal, v):
    from app.modules.fichas_seguridad import documentos
    db = portal.Session()
    r = documentos.propuesta("certificado_analisis", {"producto": "X" * 500, "parametros": ["no soy un objeto", {"nombre": "pH", "resultado": 7}]},
                             db, portal.tenant_id)
    db.close()
    v.check("recorta el texto largo", len(r["datos"]["producto"]) == 200)
    v.check("descarta lo que no es un parámetro y vuelve texto el número",
            len(r["datos"]["parametros"]) == 1 and r["datos"]["parametros"][0]["resultado"] == "7", r["datos"]["parametros"])
