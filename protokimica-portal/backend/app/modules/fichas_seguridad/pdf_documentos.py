"""
Dibuja por código los dos documentos oficiales de Protokimica, copiando sus
plantillas: el certificado de análisis (AP-F-06) y la ficha de datos de
seguridad (AP-F-08).

No parte de un .docx: la plantilla se reproduce aquí con reportlab (Python
puro, sin librerías del sistema). Si el formato oficial cambia, se cambia este
archivo —y `FORMATO_CERTIFICADO`, que lleva la fecha y la versión del formato
AP-F-06 que se está copiando—.

Qué se copió de cada plantilla:

- **Encabezado en TODAS las páginas**: logo y nombre, título, código, fecha,
  versión y «Página x de y» (por eso el lienzo numerado: el total solo se
  sabe al terminar). En el certificado, fecha y versión son las del FORMATO;
  en la FDS son las del DOCUMENTO (su versión y su fecha de emisión).
- **Pie** con los datos de la empresa, y el logo como marca de agua.
- **Certificado**: NIT, título, producto en rojo, las cinco líneas de datos,
  «Especificaciones del producto» con su tabla, las dos firmas en blanco (se
  firman a mano) y la nota. La plantilla NO lleva proveedor: se guarda en el
  historial pero no se imprime.
- **FDS**: nombre del producto en un recuadro bajo el encabezado y las 16
  secciones con su barra gris numerada.

**Todo texto que viene de una persona o de un PDF se escapa** antes de entrar a
un `Paragraph`, que interpreta marcas como `<b>`, y se pasa por `_limpio`: la
fuente embebida (Vera) no trae todos los símbolos y uno que falte saldría como
un cuadro negro en un documento que se imprime.
"""
import io
import os
import re
from xml.sax.saxutils import escape

import reportlab
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as lienzo
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.modules.fichas_seguridad.esquemas_documentos import SECCIONES_FDS

AZUL = colors.HexColor("#1A4FA0")
GRIS_BARRA = colors.HexColor("#BFBFBF")
GRIS_TEXTO = colors.HexColor("#444444")
ROJO = colors.HexColor("#E00000")
LINEA = colors.HexColor("#000000")
LINEA_SUAVE = colors.HexColor("#999999")

CODIGO_FORMATO = {"certificado_analisis": "AP-F-06", "fds": "AP-F-08"}
TITULO_ENCABEZADO = {"certificado_analisis": "CERTIFICADO DE ANÁLISIS", "fds": "FICHA DE DATOS DE SEGURIDAD (FDS)"}

# La fecha y la versión que trae la plantilla AP-F-06 vigente. Cuando Calidad
# emita otra versión del formato, se cambia aquí.
FORMATO_CERTIFICADO = {"fecha": "16/02/2024", "version": "09"}
NIT = "890.922.294-4"

PIE = [
    "Productos Químicos al por Mayor y al Detal – Artículos para Laboratorio y Reactivos",
    "Implementos de Protección Personal – Fragancias y Sabores – Productos para el Aseo y Limpieza",
    "Dirección: Cra. 52 No 6 Sur. |Medellín – Colombia PBX: (+57) (604) 444-8787 WhatsApp: 311-1792216",
    "E-mail: servicioalcliente@protokimica.com   Web: www.protokimica.com",
]

NOTA_CERTIFICADO = (
    "Nota: Los resultados reportados en el presente certificado son tomados de la información suministrada "
    "por nuestro proveedor, por lo tanto, se fundamenta en sus técnicas de análisis. Esta información no "
    "exime al comprador de realizar sus propios análisis"
)

_RECURSOS = os.path.join(os.path.dirname(__file__), "recursos")
LOGO = os.path.join(_RECURSOS, "logo.png")

# Vera viene con reportlab: no hay que instalar fuentes en el servidor.
_FUENTES = os.path.join(os.path.dirname(reportlab.__file__), "fonts")
for _nombre, _archivo in (("PK", "Vera.ttf"), ("PK-B", "VeraBd.ttf"), ("PK-I", "VeraIt.ttf"), ("PK-BI", "VeraBI.ttf")):
    pdfmetrics.registerFont(TTFont(_nombre, os.path.join(_FUENTES, _archivo)))
pdfmetrics.registerFontFamily("PK", normal="PK", bold="PK-B", italic="PK-I", boldItalic="PK-BI")
_GLIFOS = pdfmetrics.getFont("PK").face.charToGlyph

_SUBINDICES = str.maketrans("₀₁₂₃₄₅₆₇₈₉⁰⁴⁵⁶⁷⁸⁹", "01234567890456789")
_SUSTITUTOS = {"▪": "•", "→": "->", "≠": "!=", " ": " ", "​": ""}


def _limpio(texto) -> str:
    """El texto con lo que la fuente no tiene reemplazado por algo legible (o «?», que se ve y se corrige)."""
    salida = []
    for c in str(texto or "").translate(_SUBINDICES):
        c = _SUSTITUTOS.get(c, c)
        salida.append(c if c in "\n\t" or all(ord(x) in _GLIFOS for x in c) else "?")
    return "".join(salida)


def _e(valor) -> str:
    """Texto seguro para un Paragraph, SIN recortar espacios: sirve para trozos de una misma línea."""
    return escape(_limpio(valor)).replace("\n", "<br/>")


def _t(valor) -> str:
    """Texto seguro para un Paragraph; los saltos de línea se conservan."""
    return _e(str(valor or "").strip())


def _estilo(nombre, **extra):
    base = dict(fontName="PK", fontSize=8, leading=10.5)
    base.update(extra)
    return ParagraphStyle(nombre, **base)


NORMAL = _estilo("n")
CELDA = _estilo("c", fontSize=7.5, leading=9.5)
ETIQUETA = _estilo("e", fontName="PK-B", fontSize=9.5, leading=13)
TITULO_DOC = _estilo("t", fontName="PK-B", fontSize=14, leading=18, alignment=TA_CENTER)
PRODUCTO_ROJO = _estilo("r", fontSize=13, leading=17, alignment=TA_CENTER, textColor=ROJO)
BARRA = _estilo("b", fontName="PK-B", fontSize=8.5, leading=11)
NOTA = _estilo("no", fontSize=8.5, leading=11, alignment=TA_CENTER)

ANCHO, ALTO = A4
MARGEN_X = 15 * mm
ANCHO_UTIL = ANCHO - 2 * MARGEN_X
Y_ENCABEZADO = ALTO - 12 * mm          # borde superior del encabezado
ALTO_ENCABEZADO = 18 * mm
ALTO_PRODUCTO = 7 * mm


# ── Dibujo de cada página: encabezado, pie y marca de agua ────────────────

def _celda_texto(c, x, y, ancho, alto, texto, fuente="PK", tam=8, alinear="izq"):
    c.setFont(fuente, tam)
    c.setFillColor(colors.black)
    y_texto = y + alto / 2 - tam * 0.35
    if alinear == "centro":
        c.drawCentredString(x + ancho / 2, y_texto, texto)
    else:
        c.drawString(x + 2 * mm, y_texto, texto)


def _etiqueta_valor(c, x, y, ancho, alto, etiqueta, valor):
    c.setFont("PK-B", 7.5)
    c.drawString(x + 2 * mm, y + alto / 2 - 2.6, etiqueta)
    desplazamiento = c.stringWidth(etiqueta + " ", "PK-B", 7.5)
    c.setFont("PK", 7.5)
    c.drawString(x + 2 * mm + desplazamiento, y + alto / 2 - 2.6, valor)


def _dibujar_pagina(c, tipo: str, encabezado: dict, pagina: int, total: int):
    # Marca de agua: el logo grande y casi transparente.
    c.saveState()
    c.setFillAlpha(0.07)
    lado = 120 * mm
    c.drawImage(LOGO, (ANCHO - lado) / 2, (ALTO - lado) / 2, lado, lado, mask="auto", preserveAspectRatio=True)
    c.restoreState()

    # Encabezado de tres celdas.
    x0, y1 = MARGEN_X, Y_ENCABEZADO - ALTO_ENCABEZADO
    ancho_logo, ancho_cod = 45 * mm, 52 * mm
    ancho_centro = ANCHO_UTIL - ancho_logo - ancho_cod
    c.saveState()
    c.setStrokeColor(LINEA)
    c.setLineWidth(0.8)
    c.rect(x0, y1, ANCHO_UTIL, ALTO_ENCABEZADO)
    c.line(x0 + ancho_logo, y1, x0 + ancho_logo, y1 + ALTO_ENCABEZADO)
    c.line(x0 + ancho_logo + ancho_centro, y1, x0 + ancho_logo + ancho_centro, y1 + ALTO_ENCABEZADO)
    c.setLineWidth(0.5)
    c.line(x0 + ancho_logo, y1 + ALTO_ENCABEZADO * 0.42, x0 + ancho_logo + ancho_centro, y1 + ALTO_ENCABEZADO * 0.42)
    tercio = ALTO_ENCABEZADO / 3
    xr = x0 + ancho_logo + ancho_centro
    c.line(xr, y1 + tercio, xr + ancho_cod, y1 + tercio)
    c.line(xr, y1 + 2 * tercio, xr + ancho_cod, y1 + 2 * tercio)

    # Logo y nombre.
    c.drawImage(LOGO, x0 + 2.5 * mm, y1 + 2.5 * mm, 13 * mm, 13 * mm, mask="auto", preserveAspectRatio=True)
    c.setFillColor(AZUL)
    c.setFont("PK-B", 10)
    c.drawString(x0 + 17 * mm, y1 + ALTO_ENCABEZADO / 2 - 3.5, "protokimica")

    # Título y versión.
    _celda_texto(c, x0 + ancho_logo, y1 + ALTO_ENCABEZADO * 0.42, ancho_centro, ALTO_ENCABEZADO * 0.58,
                 _limpio(TITULO_ENCABEZADO[tipo]), "PK-B", 9.5, "centro")
    c.setFillColor(colors.black)
    _etiqueta_valor(c, x0 + ancho_logo, y1, ancho_centro, ALTO_ENCABEZADO * 0.42, "Versión:", _limpio(encabezado["version"]))

    # Código, fecha y página.
    _etiqueta_valor(c, xr, y1 + 2 * tercio, ancho_cod, tercio, "Código:", CODIGO_FORMATO[tipo])
    _etiqueta_valor(c, xr, y1 + tercio, ancho_cod, tercio, "Fecha:", _limpio(encabezado["fecha"]))
    _etiqueta_valor(c, xr, y1, ancho_cod, tercio, "Página:", f"{pagina} de {total}")

    # FDS: el producto en su recuadro, en cada página.
    if tipo == "fds":
        y_p = y1 - 3 * mm - ALTO_PRODUCTO
        c.rect(x0, y_p, ANCHO_UTIL, ALTO_PRODUCTO)
        nombre = _limpio(encabezado["producto"]).upper()
        c.setFont("PK-B", 8.5)
        while c.stringWidth(nombre, "PK-B", 8.5) > ANCHO_UTIL - 6 * mm and len(nombre) > 4:
            nombre = nombre[:-2]
        _celda_texto(c, x0, y_p, ANCHO_UTIL, ALTO_PRODUCTO, nombre, "PK-B", 8.5, "centro")
    c.restoreState()

    # Pie.
    c.saveState()
    c.setFillColor(AZUL)
    y = 19 * mm
    for i, linea in enumerate(PIE):
        c.setFont("PK", 6.5 if i < 3 else 6.8)
        c.drawCentredString(ANCHO / 2, y - i * 3.2 * mm, _limpio(linea))
    c.restoreState()


def _lienzo_numerado(tipo: str, encabezado: dict):
    """Un lienzo que dibuja cada página al final, cuando ya se sabe cuántas son."""
    class Numerado(lienzo.Canvas):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self._estados = []

        def showPage(self):
            self._estados.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self._estados)
            for estado in self._estados:
                self.__dict__.update(estado)
                _dibujar_pagina(self, tipo, encabezado, self._pageNumber, total)
                super().showPage()
            super().save()
    return Numerado


# ── Contenido ─────────────────────────────────────────────────────────────

def _certificado(datos: dict) -> list:
    historia = [
        Paragraph(f"NIT: {NIT}", _estilo("nit", fontSize=8.5)),
        Spacer(1, 8 * mm),
        Paragraph("CERTIFICADO DE ANÁLISIS", TITULO_DOC),
        Spacer(1, 4 * mm),
        Paragraph(_t(datos.get("producto")).upper(), PRODUCTO_ROJO),
        Spacer(1, 2 * mm),
    ]
    for etiqueta, clave in (
        ("Código PK:", "codigo_producto"), ("Número Lote de Protokimica SAS:", "lote_protokimica"),
        ("Número lote del Fabricante:", "lote_fabricante"), ("Fecha de Fabricación (DD/MM/AA):", "fecha_fabricacion"),
        ("Fecha de vencimiento (DD/MM/AA):", "fecha_vencimiento"),
    ):
        historia.append(Paragraph(f"<b>{etiqueta}</b> {_t(datos.get(clave))}", _estilo("l", fontSize=9.5, leading=13.5)))
    historia += [Spacer(1, 6 * mm), Paragraph("ESPECIFICACIONES DEL PRODUCTO", _estilo("es", fontName="PK-B", fontSize=11, alignment=TA_CENTER)), Spacer(1, 3 * mm)]

    filas = [[Paragraph(f"<b>{h}</b>", CELDA) for h in ("Parámetro", "Unidad", "Requisito", "Método", "Resultado")]]
    for p in datos.get("parametros") or []:
        filas.append([Paragraph(_t(p.get(k)) or "—", CELDA) for k in ("nombre", "unidad", "requisito", "metodo", "resultado")])
    if len(filas) == 1:
        filas.append([Paragraph("Sin parámetros registrados", CELDA), "", "", "", ""])
    tabla = Table(filas, colWidths=[50 * mm, 18 * mm, 38 * mm, 42 * mm, 32 * mm], repeatRows=1)
    tabla.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, LINEA), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EDEDED")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    historia += [
        tabla, Spacer(1, 16 * mm),
        KeepTogether([
            Paragraph("<b>Revisado por analista de Aseguramiento:</b>", _estilo("f", fontSize=9.5, leading=14)),
            Paragraph("<b>Aprobado Por Supervisor de Aseguramiento:</b>", _estilo("f2", fontSize=9.5, leading=14)),
            Spacer(1, 14 * mm),
            Paragraph(_t(NOTA_CERTIFICADO), NOTA),
        ]),
    ]
    return historia


# «a) Etiqueta: texto» → la etiqueta en negrita, como en la plantilla.
_SUBITEM = re.compile(r"^((?:[a-z]\)|•|▪|-)\s*)([^:\n]{2,120}:)(.*)$", re.S)


def _linea_fds(linea: str) -> str:
    m = _SUBITEM.match(linea.strip())
    if not m:
        return _t(linea)
    return f"{_e(m.group(1))}<b>{_e(m.group(2))}</b>{_e(m.group(3))}"


def _contenido_fds(texto) -> list:
    lineas = [l for l in str(texto or "").split("\n") if l.strip()]
    if not lineas:
        return [Paragraph("No disponible.", NORMAL)]
    return [Paragraph(_linea_fds(l), NORMAL) for l in lineas]


def _fds(datos: dict) -> list:
    historia = []
    por_numero = {int(s.get("numero", 0)): s for s in datos.get("secciones") or []}
    for numero, titulo in enumerate(SECCIONES_FDS, 1):
        barra = Table([[Paragraph(f"{numero}. {_t(titulo).upper()}", BARRA)]], colWidths=[ANCHO_UTIL])
        barra.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), GRIS_BARRA), ("BOX", (0, 0), (-1, -1), 0.5, LINEA),
            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        cuerpo = _contenido_fds(por_numero.get(numero, {}).get("contenido"))
        # La barra no se queda sola al final de una página: va con el primer párrafo.
        historia += [Spacer(1, 3 * mm), KeepTogether([barra, Spacer(1, 1.5 * mm), cuerpo[0]]), *cuerpo[1:]]
    return historia


def generar(tipo: str, datos: dict, codigo_documento: str = "") -> bytes:
    """El PDF del documento, en memoria. `codigo_documento` es el nombre con el que se guarda."""
    if tipo == "certificado_analisis":
        encabezado = {**FORMATO_CERTIFICADO, "producto": datos.get("producto", "")}
        arriba = 12 * mm + ALTO_ENCABEZADO + 6 * mm
    else:
        encabezado = {"version": datos.get("version") or "—", "fecha": datos.get("fecha_emision") or "—",
                      "producto": datos.get("producto", "")}
        arriba = 12 * mm + ALTO_ENCABEZADO + 3 * mm + ALTO_PRODUCTO + 3 * mm
    salida = io.BytesIO()
    documento = SimpleDocTemplate(
        salida, pagesize=A4, leftMargin=MARGEN_X, rightMargin=MARGEN_X, topMargin=arriba, bottomMargin=30 * mm,
        title=f"{TITULO_ENCABEZADO[tipo].title()} — {_limpio(datos.get('producto', ''))}", author="Protokimica",
        subject=codigo_documento,
    )
    historia = _certificado(datos) if tipo == "certificado_analisis" else _fds(datos)
    documento.build(historia, canvasmaker=_lienzo_numerado(tipo, encabezado))
    return salida.getvalue()
