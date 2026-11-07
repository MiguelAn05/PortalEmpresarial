"""
Fichas de seguridad: lo que importa probar es que las versiones se conserven,
que solo escriba quien tiene la capacidad (y nadie con rol de consulta), que
el archivo no se pueda bajar sin pasar por el endpoint, y que lo que no es un
PDF de verdad no entre aunque lo disfracen de uno.

Los archivos van a una carpeta temporal por prueba: nada queda en disco.
"""
import os

import pytest

from app.core import capacidades
from app.core.config import settings
from app.models.fichas_seguridad import FdsFicha, FdsVersion
from app.models.tenant import Tenant, TenantModulo
from app.modules.fichas_seguridad.permisos import CAPACIDAD_GESTIONAR

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
PDF_V9 = b"%PDF-1.4\n% version nueve\n%%EOF\n"
EXE_DISFRAZADO = b"MZ\x90\x00\x03\x00\x00\x00 esto no es un pdf"


@pytest.fixture
def portal(entorno, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DOCUMENTOS_DIR", str(tmp_path))
    entorno.carpeta = tmp_path
    return entorno


def _subir(portal, nombre="ÁCIDO ACÉTICO GLACIAL FOOD GRADE", version="10", fecha="2023-09-21",
           codigo="10038", contenido=PDF, archivo="ficha.pdf", **extra):
    datos = {"nombre_producto": nombre, "version": version, "fecha_emision": fecha}
    if codigo is not None:
        datos["codigo_producto"] = codigo
    datos.update(extra)
    return portal.post("/fichas-seguridad", data=datos, files={"archivo": (archivo, contenido, "application/pdf")})


def _version(portal, ficha_id, version, fecha="2024-05-02", contenido=PDF_V9, **extra):
    datos = {"version": version, "fecha_emision": fecha, **extra}
    return portal.post(
        f"/fichas-seguridad/{ficha_id}/versiones", data=datos,
        files={"archivo": ("ficha.pdf", contenido, "application/pdf")},
    )


def _archivos_en_disco(portal) -> list[str]:
    return [f for _, _, fs in os.walk(portal.carpeta) for f in fs]


def _otorgar(portal, area="Calidad"):
    db = portal.Session()
    capacidades.otorgar_a_area(db, portal.tenant_id, CAPACIDAD_GESTIONAR, area, portal.ids["admin"])
    db.close()


# ── Subir una ficha ───────────────────────────────────────────

def test_admin_sube_una_ficha_y_queda_con_su_version_vigente(portal, v):
    r = _subir(portal)
    v.check("subir -> 201", r.status_code == 201, r.text[:200])
    ficha = r.json()
    v.check("la ficha lleva su nombre y código", ficha["nombre_producto"] == "ÁCIDO ACÉTICO GLACIAL FOOD GRADE"
            and ficha["codigo_producto"] == "10038", ficha)
    v.check("la primera versión es la vigente", ficha["vigente"]["version"] == "10"
            and ficha["vigente"]["fecha_emision"] == "2023-09-21", ficha["vigente"])
    v.check("dice quién la subió", ficha["vigente"]["subida_por_nombre"] == "Admin", ficha["vigente"])
    v.check("el PDF quedó guardado fuera de /uploads", len(_archivos_en_disco(portal)) == 1)
    v.check("la ruta guardada no es una URL pública", "/uploads" not in str(ficha))


def test_el_codigo_es_opcional_y_se_guarda_en_mayusculas(portal, v):
    sin = _subir(portal, nombre="Hipoclorito de calcio", codigo=None)
    v.check("sin código se puede", sin.status_code == 201, sin.text[:200])
    v.check("y queda vacío", sin.json()["codigo_producto"] is None, sin.json())
    con = _subir(portal, nombre="Soda cáustica", codigo=" mp-001 ")
    v.check("el código se limpia y va en mayúsculas", con.json()["codigo_producto"] == "MP-001", con.json())
    otra = _subir(portal, nombre="Otra soda", codigo="MP-001")
    v.check("el mismo código en otra ficha -> 409", otra.status_code == 409, otra.text[:200])
    v.check("y dice cuál es la ficha dueña", "Soda cáustica" in otra.text, otra.text[:200])


def test_un_producto_repetido_pide_subir_version_no_crear_otra_ficha(portal, v):
    _subir(portal)
    r = _subir(portal, nombre="acido acetico glacial food grade", codigo=None, version="11")
    v.check("mismo producto aunque cambie tildes y mayúsculas -> 409", r.status_code == 409, r.text[:200])
    v.check("dice qué hacer", "súbele la versión nueva" in r.text, r.text[:200])
    v.check("y no dejó un archivo huérfano", len(_archivos_en_disco(portal)) == 1, _archivos_en_disco(portal))


def test_los_datos_del_formulario_se_validan_con_mensajes_que_dicen_que_hacer(portal, v):
    v.check("nombre vacío -> 400", _subir(portal, nombre="  ").status_code == 400)
    v.check("nombre larguísimo -> 400", _subir(portal, nombre="x" * 201).status_code == 400)
    v.check("versión vacía -> 400", _subir(portal, version=" ").status_code == 400)
    futura = _subir(portal, fecha="2999-01-01")
    v.check("fecha futura -> 400", futura.status_code == 400, futura.text[:200])
    v.check("y dice de dónde sacarla", "encabezado" in futura.text, futura.text[:200])
    v.check("nada de eso dejó archivos", _archivos_en_disco(portal) == [], _archivos_en_disco(portal))


# ── Qué archivos entran ───────────────────────────────────────

def test_solo_entran_pdf_de_verdad(portal, v):
    disfrazado = _subir(portal, contenido=EXE_DISFRAZADO, archivo="ficha.pdf")
    v.check("un ejecutable renombrado a .pdf -> 400", disfrazado.status_code == 400, disfrazado.text[:200])
    vacio = _subir(portal, contenido=b"")
    v.check("un archivo vacío -> 400", vacio.status_code == 400, vacio.text[:200])
    v.check("no quedó nada en disco", _archivos_en_disco(portal) == [], _archivos_en_disco(portal))


def test_un_excel_valido_tampoco_entra_y_no_queda_en_disco(portal, v):
    import io
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("xl/workbook.xml", "<workbook/>")
    r = _subir(portal, contenido=buf.getvalue(), archivo="ficha.xlsx")
    v.check("un .xlsx -> 400", r.status_code == 400, r.text[:200])
    v.check("dice que se sube en PDF", "PDF" in r.text, r.text[:200])
    v.check("y el archivo que alcanzó a escribirse se borró", _archivos_en_disco(portal) == [], _archivos_en_disco(portal))


# ── Versiones ─────────────────────────────────────────────────

def test_una_version_nueva_queda_vigente_y_la_anterior_se_conserva(portal, v):
    ficha_id = _subir(portal).json()["id"]
    r = _version(portal, ficha_id, "11", observaciones="Cambió la sección 8")
    v.check("subir versión -> 201", r.status_code == 201, r.text[:200])
    ficha = r.json()
    por_numero = {x["version"]: x for x in ficha["versiones"]}
    v.check("hay dos versiones", set(por_numero) == {"10", "11"}, list(por_numero))
    v.check("la 11 es la vigente", por_numero["11"]["vigente"] and ficha["vigente"]["version"] == "11", ficha["vigente"])
    v.check("la 10 se conserva, ya no vigente", por_numero["10"]["vigente"] is False, por_numero["10"])
    v.check("las observaciones quedan", por_numero["11"]["observaciones"] == "Cambió la sección 8")
    v.check("los dos PDF siguen en disco", len(_archivos_en_disco(portal)) == 2, _archivos_en_disco(portal))
    v.check("la más reciente sale primero", ficha["versiones"][0]["version"] == "11", ficha["versiones"])


def test_repetir_un_numero_de_version_es_409_y_no_guarda_el_archivo(portal, v):
    ficha_id = _subir(portal).json()["id"]
    r = _version(portal, ficha_id, " 10 ")
    v.check("la versión 10 ya existe -> 409", r.status_code == 409, r.text[:200])
    v.check("dice cuál ya está", "ya tiene la versión 10" in r.text, r.text[:200])
    v.check("no quedó un archivo huérfano", len(_archivos_en_disco(portal)) == 1, _archivos_en_disco(portal))


def test_se_puede_volver_vigente_una_version_anterior(portal, v):
    ficha = _subir(portal).json()
    ficha = _version(portal, ficha["id"], "11").json()
    vieja = next(x for x in ficha["versiones"] if x["version"] == "10")
    r = portal.post(f"/fichas-seguridad/versiones/{vieja['id']}/vigente")
    v.check("-> 200", r.status_code == 200, r.text[:200])
    v.check("la 10 vuelve a ser la vigente", r.json()["vigente"]["version"] == "10", r.json()["vigente"])
    v.check("hay una sola vigente", sum(1 for x in r.json()["versiones"] if x["vigente"]) == 1)
    v.check("no se borró nada", len(r.json()["versiones"]) == 2)


def test_los_datos_de_una_version_se_corrigen_sin_cambiar_el_pdf(portal, v):
    ficha = _subir(portal, version="1O").json()   # una O en vez de un cero, al digitar
    ficha = _version(portal, ficha["id"], "11").json()
    mal = next(x for x in ficha["versiones"] if x["version"] == "1O")
    r = portal.patch(f"/fichas-seguridad/versiones/{mal['id']}",
                     json={"version": " 10 ", "fecha_emision": "2023-09-20", "observaciones": "Primera emisión"})
    v.check("corregir -> 200", r.status_code == 200, r.text[:200])
    corregida = next(x for x in r.json()["versiones"] if x["id"] == mal["id"])
    v.check("número corregido", corregida["version"] == "10", corregida)
    v.check("fecha corregida", corregida["fecha_emision"] == "2023-09-20", corregida)
    v.check("observaciones corregidas", corregida["observaciones"] == "Primera emisión", corregida)
    v.check("el PDF es el mismo", corregida["nombre_original"] == mal["nombre_original"]
            and corregida["tamano"] == mal["tamano"], corregida)
    v.check("la vigente no cambia", r.json()["vigente"]["version"] == "11", r.json()["vigente"])

    choque = portal.patch(f"/fichas-seguridad/versiones/{mal['id']}", json={"version": "11"})
    v.check("repetir el número de otra versión -> 409", choque.status_code == 409, choque.text[:200])
    futura = portal.patch(f"/fichas-seguridad/versiones/{mal['id']}", json={"fecha_emision": "2999-01-01"})
    v.check("fecha futura -> 400", futura.status_code == 400, futura.text[:200])
    vacia = portal.patch(f"/fichas-seguridad/versiones/{mal['id']}", json={"version": "  "})
    v.check("número vacío -> 400", vacia.status_code == 400, vacia.text[:200])
    quitar = portal.patch(f"/fichas-seguridad/versiones/{mal['id']}", json={"observaciones": ""})
    v.check("observaciones vacías las quitan",
            next(x for x in quitar.json()["versiones"] if x["id"] == mal["id"])["observaciones"] is None)

    portal.como("tics")
    v.check("sin la capacidad -> 403",
            portal.patch(f"/fichas-seguridad/versiones/{mal['id']}", json={"version": "12"}).status_code == 403)


# ── Descarga ──────────────────────────────────────────────────

def test_el_pdf_se_baja_por_el_endpoint_sin_cache_y_tambien_el_de_una_version_vieja(portal, v):
    ficha = _subir(portal).json()
    ficha = _version(portal, ficha["id"], "11").json()
    vieja = next(x for x in ficha["versiones"] if x["version"] == "10")
    r = portal.get(f"/fichas-seguridad/versiones/{vieja['id']}/archivo")
    v.check("la vieja se puede bajar -> 200", r.status_code == 200, r.status_code)
    v.check("trae el contenido exacto", r.content == PDF, r.content[:40])
    v.check("es un PDF que se abre en el navegador",
            r.headers["content-type"] == "application/pdf" and "inline" in r.headers["content-disposition"], dict(r.headers))
    v.check("no se cachea", r.headers["cache-control"] == "no-store", r.headers.get("cache-control"))
    v.check("no se deja adivinar el tipo", r.headers["x-content-type-options"] == "nosniff")


def test_lectura_y_gerencia_pueden_consultar_y_bajar(portal, v):
    ficha = _subir(portal).json()
    for quien in ("lectura", "gerencia", "logistica"):
        portal.como(quien)
        v.check(f"{quien} ve la lista", portal.get("/fichas-seguridad").status_code == 200)
        v.check(f"{quien} abre la ficha", portal.get(f"/fichas-seguridad/{ficha['id']}").status_code == 200)
        v.check(f"{quien} baja el PDF",
                portal.get(f"/fichas-seguridad/versiones/{ficha['vigente']['id']}/archivo").status_code == 200)


def test_una_version_inexistente_es_404(portal, v):
    v.check("bajar -> 404", portal.get("/fichas-seguridad/versiones/9999/archivo").status_code == 404)
    v.check("ficha -> 404", portal.get("/fichas-seguridad/9999").status_code == 404)


def test_si_el_archivo_ya_no_esta_en_el_servidor_lo_dice(portal, v):
    ficha = _subir(portal).json()
    for ruta in os.walk(portal.carpeta):
        for f in ruta[2]:
            os.remove(os.path.join(ruta[0], f))
    r = portal.get(f"/fichas-seguridad/versiones/{ficha['vigente']['id']}/archivo")
    v.check("-> 404", r.status_code == 404, r.status_code)
    v.check("y dice qué hacer", "vuelva a cargar" in r.text, r.text[:200])


# ── Quién escribe ─────────────────────────────────────────────

def test_sin_la_capacidad_no_se_escribe_y_el_mensaje_dice_a_quien_pedirlo(portal, v):
    _otorgar(portal, "Calidad")
    portal.como("tics")
    r = _subir(portal)
    v.check("un líder sin la capacidad -> 403", r.status_code == 403, r.text[:200])
    v.check("dice a quién pedírselo", "Calidad" in r.text, r.text[:200])
    v.check("y no guardó nada", _archivos_en_disco(portal) == [])

    portal.como("calidad")
    v.check("el área que la tiene sí sube", _subir(portal).status_code == 201)


def test_la_capacidad_tambien_se_da_a_una_persona(portal, v):
    db = portal.Session()
    capacidades.otorgar_a_usuario(db, portal.tenant_id, CAPACIDAD_GESTIONAR, portal.ids["logistica"], portal.ids["admin"])
    db.close()
    portal.como("logistica")
    v.check("un agente con la capacidad personal sube", _subir(portal).status_code == 201)
    portal.como("tics")
    v.check("el compañero de otra área, no", _subir(portal, nombre="Otro producto", codigo=None).status_code == 403)


def test_lectura_y_gerencia_no_escriben_ni_con_la_capacidad(portal, v):
    ficha = _subir(portal).json()
    _otorgar(portal, "TICS")
    db = portal.Session()
    for quien in ("lectura", "gerencia"):
        capacidades.otorgar_a_usuario(db, portal.tenant_id, CAPACIDAD_GESTIONAR, portal.ids[quien], portal.ids["admin"])
    db.close()
    for quien in ("lectura", "gerencia"):
        portal.como(quien)
        v.check(f"{quien} no sube ficha", _subir(portal, nombre=f"Producto {quien}", codigo=None).status_code == 403)
        v.check(f"{quien} no sube versión", _version(portal, ficha["id"], "99").status_code == 403)
        v.check(f"{quien} no edita",
                portal.patch(f"/fichas-seguridad/{ficha['id']}", json={"activa": False}).status_code == 403)
        v.check(f"{quien} no borra",
                portal.delete(f"/fichas-seguridad/{ficha['id']}?incluir_versiones=true").status_code == 403)
    portal.como("admin")
    v.check("y la ficha sigue intacta", portal.get(f"/fichas-seguridad/{ficha['id']}").json()["total_versiones"] == 1)


# ── Lista y búsqueda ──────────────────────────────────────────

def test_el_buscador_ignora_tildes_mayusculas_y_orden_de_las_palabras(portal, v):
    _subir(portal)
    _subir(portal, nombre="Hipoclorito de calcio", codigo="MP-77", version="3", fecha="2024-01-10")
    _subir(portal, nombre="Soda cáustica en escamas", codigo=None, version="1", fecha="2024-02-01")

    def nombres(q):
        return [f["nombre_producto"] for f in portal.get("/fichas-seguridad", params={"q": q}).json()["fichas"]]

    v.check("sin tildes", nombres("acido acetico") == ["ÁCIDO ACÉTICO GLACIAL FOOD GRADE"], nombres("acido acetico"))
    v.check("otro orden y mayúsculas", nombres("GLACIAL acetico") == ["ÁCIDO ACÉTICO GLACIAL FOOD GRADE"])
    v.check("por código", nombres("mp-77") == ["Hipoclorito de calcio"], nombres("mp-77"))
    esperado = ["Soda cáustica en escamas"]
    v.check("la tilde se ignora en ambos lados: con la tilde bien, mal puesta o sin ella encuentra lo mismo",
            nombres("cáustica") == esperado and nombres("caústica") == esperado and nombres("CAUSTICA") == esperado,
            (nombres("cáustica"), nombres("caústica"), nombres("CAUSTICA")))
    v.check("todas las palabras tienen que estar", nombres("acido soda") == [])
    v.check("un % no es comodín", nombres("%") == [], nombres("%"))
    v.check("sin buscar salen todas, en orden alfabético",
            nombres("") == ["ÁCIDO ACÉTICO GLACIAL FOOD GRADE", "Hipoclorito de calcio", "Soda cáustica en escamas"], nombres(""))
    total = portal.get("/fichas-seguridad", params={"q": "acido"}).json()
    v.check("el total es el de lo filtrado", total["total"] == 1, total["total"])


def test_la_lista_trae_la_version_vigente_y_cuantas_hay(portal, v):
    ficha = _subir(portal).json()
    _version(portal, ficha["id"], "11")
    fila = portal.get("/fichas-seguridad").json()["fichas"][0]
    v.check("la vigente es la 11", fila["vigente"]["version"] == "11", fila["vigente"])
    v.check("dice cuántas versiones hay", fila["total_versiones"] == 2, fila)
    v.check("la lista no arrastra el detalle de cada versión", "versiones" not in fila, list(fila))


# ── Corregir, desactivar y borrar ─────────────────────────────

def test_desactivar_la_saca_de_la_lista_pero_conserva_todo_y_bloquea_subir_versiones(portal, v):
    ficha = _subir(portal).json()
    r = portal.patch(f"/fichas-seguridad/{ficha['id']}", json={"activa": False})
    v.check("desactivar -> 200", r.status_code == 200 and r.json()["activa"] is False, r.text[:200])
    v.check("sale de la lista normal", portal.get("/fichas-seguridad").json()["total"] == 0)
    v.check("aparece en las inactivas", portal.get("/fichas-seguridad", params={"estado": "inactivas"}).json()["total"] == 1)
    v.check("y en todas", portal.get("/fichas-seguridad", params={"estado": "todas"}).json()["total"] == 1)
    v.check("su PDF se sigue pudiendo bajar",
            portal.get(f"/fichas-seguridad/versiones/{ficha['vigente']['id']}/archivo").status_code == 200)
    bloqueada = _version(portal, ficha["id"], "11")
    v.check("subirle una versión -> 409", bloqueada.status_code == 409, bloqueada.text[:200])
    v.check("y dice que la reactive", "Reactívala" in bloqueada.text, bloqueada.text[:200])
    portal.patch(f"/fichas-seguridad/{ficha['id']}", json={"activa": True})
    v.check("reactivada vuelve a la lista", portal.get("/fichas-seguridad").json()["total"] == 1)
    v.check("y acepta versiones", _version(portal, ficha["id"], "11").status_code == 201)


def test_un_estado_de_lista_desconocido_es_400(portal, v):
    r = portal.get("/fichas-seguridad", params={"estado": "rarisimo"})
    v.check("-> 400", r.status_code == 400, r.status_code)
    v.check("y lista los que sí hay", "activas" in r.text, r.text[:200])


def test_corregir_el_nombre_y_el_codigo_recalcula_la_busqueda_y_cuida_los_duplicados(portal, v):
    a = _subir(portal, nombre="Acido citrico", codigo="MP-1").json()
    b = _subir(portal, nombre="Soda", codigo="MP-2").json()
    r = portal.patch(f"/fichas-seguridad/{a['id']}", json={"nombre_producto": "Ácido cítrico anhidro"})
    v.check("corregir el nombre -> 200", r.status_code == 200, r.text[:200])
    v.check("el código no se tocó", r.json()["codigo_producto"] == "MP-1", r.json())
    hallado = portal.get("/fichas-seguridad", params={"q": "anhidro"}).json()["fichas"]
    v.check("el buscador ya lo encuentra por el nombre nuevo", [f["id"] for f in hallado] == [a["id"]], hallado)
    v.check("y ya no por el viejo solo",
            portal.get("/fichas-seguridad", params={"q": "citrico"}).json()["total"] == 1)
    v.check("quitar el código se hace mandándolo vacío",
            portal.patch(f"/fichas-seguridad/{a['id']}", json={"codigo_producto": ""}).json()["codigo_producto"] is None)
    choque = portal.patch(f"/fichas-seguridad/{b['id']}", json={"nombre_producto": "ácido cítrico anhidro"})
    v.check("tomar el nombre de otra ficha -> 409", choque.status_code == 409, choque.text[:200])
    v.check("quedarse con el propio nombre no es choque",
            portal.patch(f"/fichas-seguridad/{b['id']}", json={"nombre_producto": "SODA"}).status_code == 200)


def test_borrar_sin_confirmar_es_409_y_explica_cuanto_se_pierde(portal, v):
    ficha = _subir(portal).json()
    _version(portal, ficha["id"], "11")
    r = portal.delete(f"/fichas-seguridad/{ficha['id']}")
    v.check("sin confirmar -> 409", r.status_code == 409, r.status_code)
    v.check("dice cuántas versiones se perderían", "2 versiones guardadas" in r.text, r.text[:250])
    v.check("ofrece desactivar", "desactívala" in r.text, r.text[:250])
    v.check("no se borró nada", portal.get(f"/fichas-seguridad/{ficha['id']}").status_code == 200
            and len(_archivos_en_disco(portal)) == 2)


def test_borrar_confirmado_quita_la_ficha_sus_versiones_y_sus_archivos(portal, v):
    ficha = _subir(portal).json()
    _version(portal, ficha["id"], "11")
    r = portal.delete(f"/fichas-seguridad/{ficha['id']}?incluir_versiones=true")
    v.check("-> 204", r.status_code == 204, r.status_code)
    v.check("la ficha ya no existe", portal.get(f"/fichas-seguridad/{ficha['id']}").status_code == 404)
    v.check("no quedaron archivos", _archivos_en_disco(portal) == [], _archivos_en_disco(portal))
    db = portal.Session()
    v.check("ni filas de versiones huérfanas", db.query(FdsVersion).count() == 0)
    db.close()


# ── Aislamiento y contrato ────────────────────────────────────

def test_cada_empresa_ve_solo_sus_fichas(portal, v):
    ficha = _subir(portal).json()
    db = portal.Session()
    otra = Tenant(nombre="Otra SAS", slug="otra")
    db.add(otra)
    db.commit()
    db.add(TenantModulo(tenant_id=otra.id, modulo="fichas_seguridad", activo=True))
    db.add(FdsFicha(tenant_id=otra.id, nombre_producto="Ficha ajena", nombre_busqueda="ficha ajena"))
    db.commit()
    db.close()
    lista = portal.get("/fichas-seguridad", params={"estado": "todas"}).json()
    v.check("la lista no trae la de la otra empresa", [f["nombre_producto"] for f in lista["fichas"]] != ["Ficha ajena"]
            and lista["total"] == 1, lista)

    db = portal.Session()
    ajena = db.query(FdsFicha).filter_by(nombre_producto="Ficha ajena").one()
    db.close()
    v.check("abrir la ajena por id -> 404", portal.get(f"/fichas-seguridad/{ajena.id}").status_code == 404)
    v.check("editarla -> 404", portal.patch(f"/fichas-seguridad/{ajena.id}", json={"activa": False}).status_code == 404)
    v.check("y la propia sigue ahí", portal.get(f"/fichas-seguridad/{ficha['id']}").status_code == 200)


def test_sin_contratar_el_modulo_no_se_abre_ni_para_admin(portal, v):
    db = portal.Session()
    db.query(TenantModulo).filter(
        TenantModulo.tenant_id == portal.tenant_id, TenantModulo.modulo == "fichas_seguridad",
    ).update({"activo": False}, synchronize_session=False)
    db.commit()
    db.close()
    portal.como("admin")
    r = portal.get("/fichas-seguridad")
    v.check("la lista -> 403", r.status_code == 403, r.status_code)
    v.check("y dice que no está contratado", "no tiene contratado" in r.text, r.text[:200])
    v.check("subir tampoco", _subir(portal).status_code == 403)
