"""
Lee un PDF CON TEXTO: corta el texto por sus encabezados y busca los datos
por su etiqueta. Es rápido, gratis y el documento no sale del servidor.

**Qué sirve y qué no, dicho claro:**

- **Una FDS** casi siempre trae las 16 secciones numeradas («1. IDENTIFICACIÓN
  DEL PRODUCTO», «2. …», o «SECCIÓN 3: …»), así que se corta por ahí. Funciona
  bien con las que siguen el SGA, en español o en inglés. **No traduce**: una
  FDS en inglés queda en inglés.
- **Un certificado de análisis** cambia de forma con cada proveedor. Aquí solo
  se buscan sus datos de cabecera por etiqueta (producto, lotes, fechas); **la
  tabla de parámetros NO se lee** y se completa a mano.
- **Un escaneo o una foto no tiene texto** que leer: se dice con claridad y se
  manda a llenar el documento a mano.

Lo que sale es una PROPUESTA que la persona revisa.
Lo que no se entiende se deja VACÍO y se avisa: nunca se adivina.
"""
import io
import math
import re
import unicodedata
from collections import Counter

from fastapi import HTTPException
from pypdf import PdfReader

from app.modules.fichas_seguridad.esquemas_documentos import MAX_SECCION, SECCIONES_FDS

MAX_PAGINAS = 60

# ── Texto ─────────────────────────────────────────────────────


def _sin_tildes(texto: str) -> str:
    sin = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in sin if not unicodedata.combining(c)).casefold()


def _paginas(contenido: bytes) -> list[list[str]]:
    """Las líneas de cada página, sin espacios sobrantes ni líneas vacías."""
    try:
        lector = PdfReader(io.BytesIO(contenido))
        if lector.is_encrypted:
            raise HTTPException(
                status_code=400,
                detail="El PDF está protegido con contraseña. Quítale la protección y vuelve a subirlo.",
            )
        if len(lector.pages) > MAX_PAGINAS:
            raise HTTPException(
                status_code=400,
                detail=f"El PDF tiene más de {MAX_PAGINAS} páginas, demasiadas para una ficha. Revisa que sea el documento correcto.",
            )
        paginas = [(p.extract_text() or "") for p in lector.pages]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail="No se pudo abrir el PDF: parece dañado. Intenta con otro archivo o llena el documento a mano.",
        ) from e
    salida = [[re.sub(r"[ \t]+", " ", l).strip() for l in p.splitlines() if l.strip()] for p in paginas]
    if sum(len(p) for p in salida) < 5:
        raise HTTPException(
            status_code=400,
            detail="Este PDF no trae texto que se pueda leer (parece un escaneo o una foto). "
                   "Llena el documento a mano.",
        )
    return salida


_NUMERO_DE_PAGINA = re.compile(r"(?:p[áa]gina|page)\s*:?\s*\d+\s*(?:de|of|/)\s*\d+", re.I)


def _clave_repetida(linea: str) -> str:
    """La línea para comparar entre páginas; solo «Página 3 de 10» ignora el número, el resto se compara exacto."""
    limpia = re.sub(r"\s+", " ", linea.lower())
    return re.sub(r"\d+", "#", limpia) if re.search(r"p[áa]g(?:ina)?|page", limpia) else limpia


def _sin_encabezados_repetidos(paginas: list[list[str]]) -> list[str]:
    """Quita lo que se repite en las páginas (encabezado, pie, «Página x de y») y junta el resto."""
    # La numeración de páginas se descarta siempre: según cómo el PDF corte el
    # renglón, «Versión: 10 Página: 6 de 10» no siempre se repite igual.
    paginas = [[l for l in p if not (len(l) < 70 and _NUMERO_DE_PAGINA.search(l))] for p in paginas]
    n = len(paginas)
    if n < 2:
        return [l for p in paginas for l in p]
    cuenta = Counter(k for p in paginas for k in {_clave_repetida(l) for l in p})
    umbral = max(2, math.ceil(0.6 * n))
    return [l for p in paginas for l in p if cuenta[_clave_repetida(l)] < umbral]


# ── FDS: cortar por secciones ─────────────────────────────────

_ENCABEZADO_ES = re.compile(r"^(\d{1,2})\s*[.\-–)]\s+(\S.{3,150})$")
_ENCABEZADO_SECCION = re.compile(r"^(?:SECCI[OÓ]N|SECTION)\s+(\d{1,2})\s*[:.\-–]?\s*(.{0,150})$", re.I)
_NUEVO_ITEM = re.compile(
    r"^(?:[a-z]\)|[•▪\-–]\s|\d+\.\d+\s|[HP]\d{3}\b|\d+\)\s)"          # a) • 3.1  H314  P301  1)
    r"|^[A-ZÁÉÍÓÚÑ][^:.\n]{1,70}:(?:\s|$)"                            # «Ingestión: …»
    r"|^[A-Z]{2,}[A-Z0-9\-/]*\b[^\n]{0,100}?:\s"                       # «ETA-CE50 (…): > 100 mg/l»
)


def _es_encabezado(linea: str, ultimo: int) -> tuple[int, str] | None:
    """(número, título) si la línea abre la sección que sigue; None si no."""
    m = _ENCABEZADO_SECCION.match(linea)
    if m:
        n, titulo = int(m.group(1)), m.group(2).strip()
    else:
        m = _ENCABEZADO_ES.match(linea)
        if not m:
            return None
        n, titulo = int(m.group(1)), m.group(2).strip()
        letras = [c for c in titulo if c.isalpha()]
        mayusculas = sum(c.isupper() for c in letras) / len(letras) if letras else 0
        canonico = _sin_tildes(SECCIONES_FDS[n - 1])[:10] if 1 <= n <= 16 else ""
        if mayusculas < 0.8 and not (canonico and _sin_tildes(titulo).startswith(canonico)):
            return None
    if not (ultimo < n <= 16):
        return None
    return n, titulo


def _cortar_secciones(lineas: list[str]) -> tuple[list[str], dict[int, list[str]]]:
    """(lo que hay antes de la sección 1, líneas de cada sección)."""
    previo, secciones, actual, ultimo = [], {}, None, 0
    for linea in lineas:
        encabezado = _es_encabezado(linea, ultimo)
        if encabezado:
            actual, ultimo = encabezado[0], encabezado[0]
            secciones[actual] = []
            # «SECCIÓN 1: Identificación» puede traer el texto en la misma línea; el título no es contenido.
            continue
        # La misma sección continúa en la página siguiente y repite su título: no es contenido.
        if actual and (m := _ENCABEZADO_ES.match(linea)) and int(m.group(1)) == actual:
            continue
        (secciones[actual] if actual else previo).append(linea)
    return previo, secciones


def _como_texto(lineas: list[str]) -> str:
    """Une las líneas cortadas por el ancho de la página y deja un subtema por línea."""
    items: list[str] = []
    previa = ""
    for linea in lineas:
        # Línea nueva si trae su marca («a)», «•», «H314»), o si la anterior ya cerró
        # una frase y esta empieza con mayúscula o número: en el PDF cada renglón de
        # una lista (valores, tablas) es suyo, mientras que una frase cortada por el
        # ancho de la página sigue en minúscula.
        cierra_frase = previa.endswith((".", ";", ":")) and (linea[:1].isupper() or linea[:1].isdigit())
        if items and not (_NUEVO_ITEM.match(linea) or cierra_frase):
            items[-1] += " " + linea
        else:
            items.append(linea)
        previa = linea
    return "\n".join(items)


# ── Datos de cabecera ─────────────────────────────────────────

_NO_ES_PRODUCTO = re.compile(
    r"FICHA|FDS|HOJA DE|SEGURIDAD|C[OÓ]DIGO|P[ÁA]GINA|VERSI[OÓ]N|FECHA|PELIGRO|ATENCI[OÓ]N|PRODUCTOS QU[IÍ]MICOS|"
    r"EMERGENCIA|SAFETY DATA|SECTION|SECCI[OÓ]N|ADVERTENCIA|WARNING|DANGER|^\d",
)


_PARECE_CODIGO = re.compile(r"^[A-Z]{1,4}(?:[-/][A-Z0-9]{1,4})+$")   # «AP-F-08»


def _producto(paginas: list[list[str]]) -> str:
    """
    El nombre del producto es la línea en MAYÚSCULAS que se repite arriba de
    cada página; con una sola página, la primera que lo parezca.
    """
    candidatas = Counter()
    orden: dict[str, int] = {}
    for p in paginas:
        for linea in p:
            if (4 <= len(linea) <= 120 and linea == linea.upper() and any(c.isalpha() for c in linea)
                    and not _NO_ES_PRODUCTO.search(linea) and not _PARECE_CODIGO.match(linea) and ":" not in linea and not re.search(r"https?://|@", linea)):
                candidatas[linea] += 1
                orden.setdefault(linea, len(orden))
    if not candidatas:
        return ""
    return min(candidatas, key=lambda l: (-candidatas[l], orden[l]))


def _buscar(patron: str, texto: str, flags=re.I) -> str:
    m = re.search(patron, texto, flags)
    return re.sub(r"\s+", " ", m.group(1)).strip(" .;,/") if m else ""


_FECHA = r"(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}|\d{4}[/\-.]\d{1,2}[/\-.]\d{1,2})"


def _fds(paginas: list[list[str]]) -> tuple[dict, list[str]]:
    avisos = ["El texto se copia tal como viene en el PDF, sin traducir. Revísalo antes de generar."]
    primera = "\n".join(paginas[0])
    lineas = _sin_encabezados_repetidos(paginas)
    _, cortadas = _cortar_secciones(lineas)

    secciones = []
    for n in range(1, 17):
        texto = _como_texto(cortadas.get(n, []))
        if len(texto) > MAX_SECCION:
            avisos.append(f"La sección {n} es más larga de lo que cabe ({MAX_SECCION} caracteres) y se recortó: revísala.")
            texto = texto[:MAX_SECCION]
        secciones.append({"numero": n, "titulo": SECCIONES_FDS[n - 1], "contenido": texto})

    seccion1 = "\n".join(cortadas.get(1, []))
    datos = {
        "producto": _producto(paginas)
                   or _buscar(r"(?:Identificaci[oó]n del producto|Identificador del producto|Nombre del producto|Product (?:name|identifier))\s*:\s*(.+)", seccion1),
        "proveedor": _buscar(r"(?:Datos sobre el proveedor|Proveedor|Fabricante|Empresa|Supplier|Manufacturer|Company)\s*:\s*([^/\n]+)", seccion1),
        "version": _buscar(r"Versi[oó]n\s*:?\s*(\d[\d.]*)", primera) or _buscar(r"Version\s*:?\s*(\d[\d.]*)", primera),
        "fecha_emision": _buscar(rf"(?:Fecha(?: de (?:emisi[oó]n|revisi[oó]n|elaboraci[oó]n))?|Revision date|Issue date|Date)\s*:?\s*{_FECHA}", primera),
        "secciones": secciones,
    }
    return datos, avisos


# ── Certificado: solo la cabecera ─────────────────────────────

def _certificado(paginas: list[list[str]]) -> tuple[dict, list[str]]:
    texto = "\n".join(l for p in paginas for l in p)
    datos = {
        "producto": _buscar(r"(?:Nombre del producto|Producto|Product(?: name)?|Descripci[oó]n)\s*[:：]\s*(.+)", texto),
        "proveedor": "",
        "lote_fabricante": _buscar(r"(?:Lote(?: del fabricante)?|Lot(?: No\.?| number)?|Batch(?: No\.?| number)?)\s*[:：#]?\s*([A-Z0-9][A-Z0-9\-/]{3,})", texto, 0),
        "lote_protokimica": "",
        "fecha_fabricacion": _buscar(rf"(?:Fecha de fabricaci[oó]n|Manufactur\w* date|Production date|MFG(?: date)?)\s*[:：]?\s*{_FECHA}", texto),
        "fecha_vencimiento": _buscar(rf"(?:Fecha de (?:vencimiento|expiraci[oó]n)|Expir\w* date|EXP(?: date)?|Best before)\s*[:：]?\s*{_FECHA}", texto),
        "parametros": [],
    }
    avisos = [
        "Solo se leyeron los datos de cabecera. La tabla de parámetros no se lee: agrégala a mano.",
    ]
    return datos, avisos


def leer(tipo: str, contenido: bytes) -> tuple[dict, list[str]]:
    """(datos leídos, avisos) de un PDF con texto. Lanza 400 diciendo qué hacer si no se puede."""
    if contenido[:5] != b"%PDF-":
        raise HTTPException(
            status_code=400,
            detail="Solo se pueden leer PDF que tengan texto. Si es una imagen o una foto, llena el documento a mano.",
        )
    paginas = _paginas(contenido)
    return _fds(paginas) if tipo == "fds" else _certificado(paginas)
