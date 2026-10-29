"""
Aprobación de documentos dentro de una tarea de Master Planner.

El caso real: la analista sube los estados financieros, el Contador los
revisa y la Revisora Fiscal los firma. Lo que se prueba:

- quién firma ve la tarea aunque no tenga nada más en el proyecto;
- el tipo del archivo se decide por su contenido, no por la extensión;
- firma solo quien tiene el turno, y devolver exige decir qué corregir;
- una versión nueva arranca la cadena desde el primer paso;
- la última firma completa la tarea, y a mano no se puede;
- el archivo solo lo baja quien ve la tarea, y sin caché;
- «Repetir tarea» copia los revisores y deja atrás el documento;
- un Excel se lee en pantalla y sus observaciones van en una celda;
- las tarjetas traen el estado del documento, y hay dos indicadores.

Se prueba con lo que manda la pantalla: multipart con `archivo` y JSON.
"""
import io
import zipfile

import pytest

from app.core.config import settings
from app.models.user import User

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


_NS = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" ' \
      'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'


def _xlsx() -> bytes:
    """
    Un libro como el que guarda Excel, armado a mano: dos hojas, textos
    compartidos, una fórmula con su resultado y una fecha con formato.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("xl/workbook.xml",
                   f'<workbook {_NS}><sheets>'
                   '<sheet name="Balance" sheetId="1" r:id="rId1"/>'
                   '<sheet name="Bancos" sheetId="2" r:id="rId2"/>'
                   '</sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels",
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Target="worksheets/sheet1.xml"/>'
                   '<Relationship Id="rId2" Target="/xl/worksheets/sheet2.xml"/>'
                   '</Relationships>')
        z.writestr("xl/sharedStrings.xml",
                   f'<sst {_NS}><si><t>Activos</t></si><si><r><t>Total </t></r><r><t>pasivos</t></r></si></sst>')
        z.writestr("xl/styles.xml",
                   f'<styleSheet {_NS}><numFmts><numFmt numFmtId="164" formatCode="dd/mm/yyyy"/></numFmts>'
                   '<cellXfs><xf numFmtId="0"/><xf numFmtId="164"/><xf numFmtId="4"/></cellXfs></styleSheet>')
        z.writestr("xl/worksheets/sheet1.xml",
                   f'<worksheet {_NS}><sheetData>'
                   '<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" s="1"><v>46296</v></c></row>'
                   '<row r="3"><c r="A3" t="s"><v>1</v></c><c r="C3" s="2"><f>SUM(C1:C2)</f><v>1250000.5</v></c></row>'
                   '</sheetData></worksheet>')
        z.writestr("xl/worksheets/sheet2.xml", f'<worksheet {_NS}><sheetData/></worksheet>')
    return buf.getvalue()


@pytest.fixture
def portal(entorno, tmp_path, monkeypatch):
    # Los documentos de prueba no van a la carpeta real.
    monkeypatch.setattr(settings, "DOCUMENTOS_DIR", str(tmp_path))
    db = entorno.Session()
    revisora = User(
        tenant_id=entorno.tenant_id, nombre="Revisora", email="revisora@p.com",
        password_hash="x", rol="agente", area="Contabilidad", activo=True,
    )
    db.add(revisora)
    db.commit()
    entorno.ids["revisora"] = revisora.id
    db.close()
    return entorno


def _plantilla(portal):
    r = portal.get("/master-planner/plantillas-revision")
    assert r.status_code == 200, r.text
    plantilla = next(p for p in r.json() if p["nombre"] == "Revisión contable")
    return plantilla


def _proyecto(portal):
    portal.como("admin")
    return portal.post("/master-planner/proyectos", json={
        "nombre": "Contabilidad 2026", "lider_id": portal.ids["admin"],
    }).json()["id"]


def _tarea_con_flujo(portal, P, plantilla, revisores=None):
    portal.como("admin")
    r = portal.post(f"/master-planner/proyectos/{P}/tareas", json={
        "titulo": "Estados financieros de septiembre",
        "asignado_a": portal.ids["logistica"],
        "fecha_fin": "2026-10-10T17:00:00",
        "revision": {
            "plantilla_id": plantilla["id"],
            "revisores": revisores or [portal.ids["calidad"], portal.ids["revisora"]],
        },
    })
    return r


def _subir(portal, T, contenido=PDF, nombre="estados.pdf"):
    return portal.post(f"/master-planner/tareas/{T}/documentos",
                       files={"archivo": (nombre, contenido, "application/octet-stream")})


def _revision(portal, T):
    return portal.get(f"/master-planner/tareas/{T}/revision").json()


def test_la_plantilla_se_siembra_sola_con_sus_dos_pasos(portal, v):
    plantilla = _plantilla(portal)
    v.check("trae Contador y Revisora Fiscal, en ese orden",
            [p["nombre"] for p in plantilla["pasos"]] == ["Contador", "Revisora Fiscal"], plantilla)
    portal.get("/master-planner/plantillas-revision")
    v.check("pedirla dos veces no la duplica",
            len([p for p in portal.get("/master-planner/plantillas-revision").json()
                 if p["nombre"] == "Revisión contable"]) == 1)


def test_quien_firma_ve_la_tarea_y_nada_mas(portal, v):
    plantilla = _plantilla(portal)
    P = _proyecto(portal)
    T = _tarea_con_flujo(portal, P, plantilla).json()["id"]
    otra = portal.post(f"/master-planner/proyectos/{P}/tareas", json={"titulo": "Otra"}).json()["id"]
    otro_proyecto = portal.post("/master-planner/proyectos", json={
        "nombre": "Ajeno", "lider_id": portal.ids["admin"],
    }).json()["id"]

    portal.como("revisora")
    v.check("la Revisora abre la tarea que firma", portal.get(f"/master-planner/tareas/{T}").status_code == 200)
    v.check("y ve su proyecto en la lista",
            P in [p["id"] for p in portal.get("/master-planner/proyectos").json()])
    v.check("pero no un proyecto donde no firma nada",
            otro_proyecto not in [p["id"] for p in portal.get("/master-planner/proyectos").json()])
    v.check("la tarea dice que pide aprobación",
            portal.get(f"/master-planner/tareas/{T}").json()["requiere_revision"] is True)
    v.check("la que no la pide, no",
            portal.get(f"/master-planner/tareas/{otra}").json()["requiere_revision"] is False)


def test_el_recorrido_completo(portal, v):
    plantilla = _plantilla(portal)
    P = _proyecto(portal)
    r = _tarea_con_flujo(portal, P, plantilla)
    v.check("la tarea nace con su flujo", r.status_code == 201, r.text)
    T = r.json()["id"]
    v.check("sin documento todavía", _revision(portal, T)["estado"] == "sin_documento")

    # A mano no se completa: lo hace la última firma.
    portal.como("logistica")
    r = portal.patch(f"/master-planner/tareas/{T}", json={"estado": "completada"})
    v.check("completarla a mano responde 400", r.status_code == 400, r.text)
    v.check("y el mensaje dice quién la completa", "Revisora Fiscal" in r.text, r.text)
    portal.post(f"/master-planner/tareas/{T}/actualizaciones", data={"avance_pct_nuevo": "100"})
    v.check("un avance del 100 % tampoco la completa",
            portal.get(f"/master-planner/tareas/{T}").json()["estado"] != "completada")

    # Subir: el tipo lo decide el contenido.
    r = _subir(portal, T, b"MZ esto es un ejecutable", "estados.pdf")
    v.check("un .pdf que no es PDF se rechaza", r.status_code == 400, r.text)
    portal.como("calidad")
    v.check("quien revisa no sube el documento", _subir(portal, T).status_code == 403)
    portal.como("logistica")
    r = _subir(portal, T)
    v.check("la analista sube el PDF", r.status_code == 201, r.text)
    v.check("queda en borrador", r.json()["estado"] == "borrador")
    _subir(portal, T, nombre="estados-bien.pdf")
    rev = _revision(portal, T)
    v.check("volver a subir un borrador lo reemplaza, no crea otra versión",
            len(rev["versiones"]) == 1 and rev["versiones"][0]["nombre_original"] == "estados-bien.pdf", rev)

    r = portal.post(f"/master-planner/tareas/{T}/documentos/enviar", json={})
    v.check("se envía", r.status_code == 200, r.text)
    v1 = r.json()["versiones"][0]
    v.check("el turno es del Contador", v1["turno_de"]["nombre"] == "Contador", v1)
    v.check("subir otra mientras la revisan responde 409", _subir(portal, T).status_code == 409)

    # Firma solo quien tiene el turno.
    portal.como("revisora")
    r = portal.post(f"/master-planner/documentos/{v1['id']}/responder", json={"decision": "aprobar"})
    v.check("la Revisora no se salta al Contador", r.status_code == 403, r.text)
    portal.como("calidad")
    r = portal.post(f"/master-planner/documentos/{v1['id']}/responder", json={"decision": "devolver"})
    v.check("devolver sin decir qué corregir responde 400", r.status_code == 400, r.text)
    r = portal.post(f"/master-planner/documentos/{v1['id']}/observaciones", json={
        "texto": "El total de activos no cuadra con el balance", "pagina": 1, "pos_x": 0.5, "pos_y": 0.25,
    })
    v.check("el Contador marca una observación en la página", r.status_code == 201, r.text)
    r = portal.post(f"/master-planner/documentos/{v1['id']}/responder", json={"decision": "devolver"})
    v.check("con la observación ya se puede devolver", r.status_code == 200, r.text)
    v.check("la versión queda devuelta", r.json()["estado"] == "devuelta")
    v.check("y cuenta una devolución", r.json()["veces_devuelto"] == 1)

    portal.como("logistica")
    pend = portal.get("/master-planner/revisiones/pendientes").json()
    v.check("a la analista le aparece por corregir",
            [f["tarea_id"] for f in pend["por_corregir"]] == [T], pend)

    # La versión 2 arranca desde el primer paso.
    _subir(portal, T, nombre="estados-v2.pdf")
    rev = portal.post(f"/master-planner/tareas/{T}/documentos/enviar", json={"comentario": "Corregido"}).json()
    v2 = rev["versiones"][0]
    v.check("es la versión 2", v2["numero"] == 2, v2)
    v.check("y vuelve al Contador, no a la Revisora", v2["turno_de"]["nombre"] == "Contador", v2)
    v.check("la versión 1 conserva su observación",
            rev["versiones"][1]["total_observaciones"] == 1, rev["versiones"][1])

    portal.como("calidad")
    portal.post(f"/master-planner/documentos/{v2['id']}/responder", json={"decision": "aprobar"})
    portal.como("revisora")
    pend = portal.get("/master-planner/revisiones/pendientes").json()
    v.check("a la Revisora le llega por revisar",
            [f["tarea_id"] for f in pend["por_revisar"]] == [T], pend)
    r = portal.post(f"/master-planner/documentos/{v2['id']}/responder",
                    json={"decision": "aprobar", "comentario": "Firmado"})
    v.check("la Revisora firma", r.status_code == 200, r.text)
    v.check("el documento queda aprobado", r.json()["estado"] == "aprobada")

    tarea = portal.get(f"/master-planner/tareas/{T}").json()
    v.check("la tarea quedó cumplida sola", tarea["estado"] == "completada", tarea["estado"])
    v.check("con su fecha de finalización", tarea["fecha_completada"] is not None)
    v.check("y al 100 %", tarea["avance_pct"] == 100)
    v.check("la tarjeta lo dice aprobado", tarea["estado_documento"] == "aprobada", tarea.get("estado_documento"))

    # El archivo: solo quien ve la tarea, y sin caché.
    r = portal.get(f"/master-planner/documentos/{v2['id']}/archivo")
    v.check("la Revisora lo descarga", r.status_code == 200 and r.content == PDF, r.status_code)
    v.check("sin quedarse en la caché", r.headers.get("cache-control") == "no-store", dict(r.headers))
    portal.como("lectura")
    v.check("alguien que no ve la tarea recibe 404",
            portal.get(f"/master-planner/documentos/{v2['id']}/archivo").status_code == 404)

    portal.como("admin")
    v.check("una tarea con un documento revisado no se borra",
            portal.delete(f"/master-planner/tareas/{T}").status_code == 409)


def test_la_configuracion_se_defiende(portal, v):
    plantilla = _plantilla(portal)
    P = _proyecto(portal)
    r = _tarea_con_flujo(portal, P, plantilla, [portal.ids["logistica"], portal.ids["revisora"]])
    v.check("quien hace el documento no lo firma", r.status_code == 400, r.text)
    r = _tarea_con_flujo(portal, P, plantilla, [portal.ids["lectura"], portal.ids["revisora"]])
    v.check("un usuario de consulta no firma", r.status_code == 400, r.text)
    r = _tarea_con_flujo(portal, P, plantilla, [portal.ids["calidad"]])
    v.check("una persona por paso", r.status_code == 400, r.text)
    r = _tarea_con_flujo(portal, P, plantilla, [portal.ids["calidad"], portal.ids["calidad"]])
    v.check("y personas distintas", r.status_code == 400, r.text)
    v.check("ninguna de esas tareas quedó creada a medias",
            portal.get(f"/master-planner/proyectos/{P}/tareas").json() == [])

    T = _tarea_con_flujo(portal, P, plantilla).json()["id"]
    r = portal.patch(f"/master-planner/tareas/{T}", json={"asignado_a": portal.ids["revisora"]})
    v.check("no se le asigna la tarea a quien la firma", r.status_code == 400, r.text)


def test_un_excel_se_revisa_en_pantalla_celda_por_celda(portal, v):
    plantilla = _plantilla(portal)
    P = _proyecto(portal)
    T = _tarea_con_flujo(portal, P, plantilla).json()["id"]
    portal.como("logistica")
    r = _subir(portal, T, _xlsx(), "conciliacion.xlsx")
    v.check("un .xlsx de verdad entra", r.status_code == 201, r.text)
    v.check("como Excel", r.json()["versiones"][0]["tipo"] == "xlsx")
    vid = portal.post(f"/master-planner/tareas/{T}/documentos/enviar", json={}).json()["versiones"][0]["id"]

    # Lo lee el servidor: valores, no formato.
    portal.como("calidad")
    r = portal.get(f"/master-planner/documentos/{vid}/hojas")
    v.check("dice sus hojas en el orden del libro", r.json() == {"hojas": ["Balance", "Bancos"]}, r.text)
    hoja = portal.get(f"/master-planner/documentos/{vid}/hojas/0").json()
    v.check("las columnas van de A hasta la última con algo", hoja["columnas"] == ["A", "B", "C"], hoja)
    v.check("un texto compartido se lee", hoja["filas"][0][0] == "Activos", hoja["filas"])
    v.check("y uno partido en tramos, entero", hoja["filas"][2][0] == "Total pasivos", hoja["filas"])
    v.check("la fecha llega como fecha, no como número", hoja["filas"][0][1] == "2026-10-01", hoja["filas"])
    v.check("la fórmula llega con su resultado", hoja["filas"][2][2] == 1250000.5, hoja["filas"])
    v.check("la fila vacía del medio se respeta", hoja["filas"][1] == [None, None, None], hoja["filas"])
    v.check("una hoja vacía no revienta",
            portal.get(f"/master-planner/documentos/{vid}/hojas/1").json()["filas"] == [])
    v.check("una hoja que no existe responde 404",
            portal.get(f"/master-planner/documentos/{vid}/hojas/7").status_code == 404)

    # Las observaciones van en una celda de una hoja.
    r = portal.post(f"/master-planner/documentos/{vid}/observaciones",
                    json={"texto": "Falta la hoja de bancos", "pagina": 1, "pos_x": 0.1, "pos_y": 0.1})
    v.check("en un Excel no se marca página", r.status_code == 400, r.text)
    r = portal.post(f"/master-planner/documentos/{vid}/observaciones",
                    json={"texto": "No cuadra", "hoja": "Balance", "celda": "c3"})
    v.check("se marca una celda", r.status_code == 201, r.text)
    v.check("escrita como la escribe Excel", (r.json()["hoja"], r.json()["celda"]) == ("Balance", "C3"), r.json())
    r = portal.post(f"/master-planner/documentos/{vid}/observaciones",
                    json={"texto": "x", "hoja": "Caja", "celda": "A1"})
    v.check("una hoja que el libro no tiene se rechaza", r.status_code == 400 and "Caja" in r.text, r.text)
    r = portal.post(f"/master-planner/documentos/{vid}/observaciones",
                    json={"texto": "x", "hoja": "Balance", "celda": "3C"})
    v.check("una celda mal escrita se rechaza", r.status_code == 400, r.text)
    r = portal.post(f"/master-planner/documentos/{vid}/observaciones", json={"texto": "Falta la hoja de bancos"})
    v.check("y sigue habiendo observación general", r.status_code == 201, r.text)

    portal.como("lectura")
    v.check("quien no ve la tarea no lee la hoja",
            portal.get(f"/master-planner/documentos/{vid}/hojas/0").status_code == 404)


def test_un_pdf_no_lleva_celda(portal, v):
    plantilla = _plantilla(portal)
    P = _proyecto(portal)
    T = _tarea_con_flujo(portal, P, plantilla).json()["id"]
    portal.como("logistica")
    _subir(portal, T)
    vid = portal.post(f"/master-planner/tareas/{T}/documentos/enviar", json={}).json()["versiones"][0]["id"]
    portal.como("calidad")
    r = portal.post(f"/master-planner/documentos/{vid}/observaciones",
                    json={"texto": "x", "hoja": "Balance", "celda": "C3"})
    v.check("una celda en un PDF se rechaza", r.status_code == 400, r.text)
    r = portal.post(f"/master-planner/documentos/{vid}/observaciones", json={"texto": "x", "pagina": 1})
    v.check("y una página sin su punto también", r.status_code == 400, r.text)
    v.check("las hojas solo son de un Excel",
            portal.get(f"/master-planner/documentos/{vid}/hojas").status_code == 400)


def test_la_tarjeta_sabe_en_que_va_el_documento(portal, v):
    plantilla = _plantilla(portal)
    P = _proyecto(portal)
    T = _tarea_con_flujo(portal, P, plantilla).json()["id"]
    sin_flujo = portal.post(f"/master-planner/proyectos/{P}/tareas", json={"titulo": "Otra"}).json()["id"]

    def estado(tid):
        tareas = portal.get(f"/master-planner/proyectos/{P}/tareas").json()
        return next(t for t in tareas if t["id"] == tid)["estado_documento"]

    v.check("sin subir nada no hay estado", estado(T) is None)
    v.check("una tarea sin flujo tampoco", estado(sin_flujo) is None)
    portal.como("logistica")
    _subir(portal, T)
    portal.como("admin")
    v.check("subido, en borrador", estado(T) == "borrador")
    portal.como("logistica")
    portal.post(f"/master-planner/tareas/{T}/documentos/enviar", json={})
    portal.como("admin")
    v.check("enviado, en revisión: en la lista, sin pedir el detalle", estado(T) == "en_revision")


def test_los_indicadores_de_documentos(portal, v):
    from datetime import datetime, timezone
    from app.modules.master_planner import fuentes_indicador as fi

    plantilla = _plantilla(portal)
    P = _proyecto(portal)

    def aprobar(T, devolver_antes):
        portal.como("logistica")
        _subir(portal, T)
        vid = portal.post(f"/master-planner/tareas/{T}/documentos/enviar", json={}).json()["versiones"][0]["id"]
        if devolver_antes:
            portal.como("calidad")
            portal.post(f"/master-planner/documentos/{vid}/responder",
                        json={"decision": "devolver", "comentario": "No cuadra"})
            portal.como("logistica")
            _subir(portal, T, nombre="v2.pdf")
            vid = portal.post(f"/master-planner/tareas/{T}/documentos/enviar", json={}).json()["versiones"][0]["id"]
        for quien in ("calidad", "revisora"):
            portal.como(quien)
            r = portal.post(f"/master-planner/documentos/{vid}/responder", json={"decision": "aprobar"})
            assert r.status_code == 200, r.text

    hoy = datetime.now(timezone.utc)
    db = portal.Session()
    v.check("sin aprobaciones es «sin dato», no un cero",
            fi.mp_documentos_sin_devolucion(db, portal.tenant_id, hoy.year, hoy.month).valor is None)

    aprobar(_tarea_con_flujo(portal, P, plantilla).json()["id"], devolver_antes=True)
    aprobar(_tarea_con_flujo(portal, P, plantilla).json()["id"], devolver_antes=False)
    db.expire_all()
    r = fi.mp_documentos_sin_devolucion(db, portal.tenant_id, hoy.year, hoy.month)
    v.check("uno de dos pasó a la primera", (r.numerador, r.denominador, r.valor) == (1, 2, 50.0), r)
    r = fi.mp_dias_en_revision(db, portal.tenant_id, hoy.year, hoy.month)
    v.check("los días se miden de los dos", r.denominador == 2 and r.valor is not None, r)
    r = fi.mp_documentos_sin_devolucion(db, portal.tenant_id, hoy.year, hoy.month, area="Ninguna")
    v.check("con un área ajena no cuenta los de otro", r.valor is None, r)
    db.close()


def test_repetir_copia_los_revisores_y_no_el_documento(portal, v):
    plantilla = _plantilla(portal)
    P = _proyecto(portal)
    T = _tarea_con_flujo(portal, P, plantilla).json()["id"]
    portal.como("logistica")
    _subir(portal, T)

    portal.como("admin")
    r = portal.post(f"/master-planner/tareas/{T}/repetir", json={"fecha_fin": "2026-11-10T17:00:00"})
    v.check("se repite", r.status_code == 201, r.text)
    nueva = r.json()
    v.check("con la misma responsable", nueva["asignado_a"] == portal.ids["logistica"])
    v.check("con la fecha nueva", nueva["fecha_fin"].startswith("2026-11-10"), nueva["fecha_fin"])
    v.check("arranca pendiente", nueva["estado"] == "pendiente")
    rev = _revision(portal, nueva["id"])
    v.check("con los mismos revisores",
            [p["revisor_id"] for p in rev["pasos"]] == [portal.ids["calidad"], portal.ids["revisora"]], rev)
    v.check("y sin el documento del mes anterior", rev["versiones"] == [] and rev["estado"] == "sin_documento", rev)
