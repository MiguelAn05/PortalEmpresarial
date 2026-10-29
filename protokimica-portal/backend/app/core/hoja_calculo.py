"""
Leer los VALORES de un .xlsx, para mostrarlo en pantalla sin descargarlo.

Un .xlsx es un ZIP de XML, y para pintar una cuadrícula basta con eso: los
nombres de las hojas (`xl/workbook.xml`), los textos compartidos
(`xl/sharedStrings.xml`) y cada hoja. Por eso no hay dependencia nueva —el
servidor no reinstala paquetes con fiabilidad— y por eso mismo esto lee
**valores, no formato**: ni colores, ni bordes, ni celdas combinadas. Las
fórmulas llegan con el último resultado que guardó Excel, que es lo que se
revisa.

Las fechas sí se reconocen —un estado financiero tiene fechas en los
encabezados, y «46295» no le dice nada a nadie— mirando el formato de número
de la celda en `xl/styles.xml`.

Topes, porque el archivo lo sube una persona y se abre en el servidor:
`MAX_FILAS` × `MAX_COLUMNAS` celdas por hoja (más allá se avisa
`truncada`), y ninguna parte del ZIP se descomprime si pasa de
`MAX_DESCOMPRIMIDO` — un ZIP de 1 MB puede guardar un XML de 4 GB.
"""
import posixpath
import re
import zipfile
from datetime import date, timedelta
from xml.etree import ElementTree

from fastapi import HTTPException

MAX_FILAS = 1000
MAX_COLUMNAS = 60
MAX_DESCOMPRIMIDO = 80 * 1024 * 1024

# Una celda como la escribe Excel: columna en letras y fila en número (C14).
PATRON_CELDA = re.compile(r"^([A-Z]{1,3})([1-9][0-9]{0,6})$")

# Formatos de número de Excel que son fechas sin estar escritos en el
# archivo (los «integrados»). Los personalizados se reconocen por su código.
_FORMATOS_FECHA_INTEGRADOS = set(range(14, 23)) | {45, 46, 47}
_EPOCA_EXCEL = date(1899, 12, 30)


def _local(etiqueta: str) -> str:
    """El nombre sin el espacio de nombres: hay dos variantes de OOXML en uso."""
    return etiqueta.rsplit("}", 1)[-1]


def _hijos(nodo, nombre: str):
    return [h for h in nodo if _local(h.tag) == nombre]


def letras_a_indice(letras: str) -> int:
    """A → 0, Z → 25, AA → 26."""
    n = 0
    for letra in letras:
        n = n * 26 + (ord(letra) - 64)
    return n - 1


def indice_a_letras(indice: int) -> str:
    letras = ""
    indice += 1
    while indice:
        indice, resto = divmod(indice - 1, 26)
        letras = chr(65 + resto) + letras
    return letras


def _leer_xml(zf: zipfile.ZipFile, nombre: str):
    try:
        info = zf.getinfo(nombre)
    except KeyError:
        return None
    if info.file_size > MAX_DESCOMPRIMIDO:
        raise HTTPException(
            status_code=422,
            detail="Este Excel es demasiado grande para verlo en el portal. Descárgalo para revisarlo.",
        )
    return ElementTree.fromstring(zf.read(nombre))


def _abrir(ruta: str) -> zipfile.ZipFile:
    try:
        return zipfile.ZipFile(ruta)
    except (zipfile.BadZipFile, OSError):
        raise HTTPException(status_code=422, detail="No se pudo leer el Excel. Descárgalo para revisarlo.")


def _hojas_con_ruta(zf: zipfile.ZipFile) -> list[tuple[str, str]]:
    """(nombre, ruta dentro del ZIP) de cada hoja, en el orden del libro."""
    libro = _leer_xml(zf, "xl/workbook.xml")
    rels = _leer_xml(zf, "xl/_rels/workbook.xml.rels")
    if libro is None or rels is None:
        raise HTTPException(status_code=422, detail="El archivo no parece un Excel válido. Descárgalo para revisarlo.")
    destino = {r.get("Id"): r.get("Target") for r in rels if _local(r.tag) == "Relationship"}
    hojas = []
    for contenedor in _hijos(libro, "sheets"):
        for hoja in _hijos(contenedor, "sheet"):
            rid = next((v for k, v in hoja.attrib.items() if _local(k) == "id"), None)
            objetivo = destino.get(rid)
            if not objetivo:
                continue
            ruta = objetivo.lstrip("/") if objetivo.startswith("/") else posixpath.normpath(posixpath.join("xl", objetivo))
            hojas.append((hoja.get("name") or "Hoja", ruta))
    return hojas


def nombres_de_hojas(ruta: str) -> list[str]:
    with _abrir(ruta) as zf:
        return [nombre for nombre, _ in _hojas_con_ruta(zf)]


def _textos_compartidos(zf: zipfile.ZipFile) -> list[str]:
    raiz = _leer_xml(zf, "xl/sharedStrings.xml")
    if raiz is None:
        return []
    # Un texto con formato mezclado viene partido en tramos (<r><t>): se unen.
    return ["".join(t.text or "" for t in si.iter() if _local(t.tag) == "t") for si in _hijos(raiz, "si")]


def _estilos_de_fecha(zf: zipfile.ZipFile) -> set[int]:
    """Qué índices de estilo (`s` de la celda) tienen formato de fecha."""
    raiz = _leer_xml(zf, "xl/styles.xml")
    if raiz is None:
        return set()
    personalizados = {}
    for contenedor in _hijos(raiz, "numFmts"):
        for fmt in _hijos(contenedor, "numFmt"):
            # Sin lo que va entre comillas o corchetes (texto y colores),
            # un formato con d, m o y es de fecha: «dd/mm/yyyy», «mmm-yy».
            codigo = re.sub(r'"[^"]*"|\[[^\]]*\]', "", fmt.get("formatCode") or "").lower()
            personalizados[int(fmt.get("numFmtId", -1))] = bool(re.search(r"[dmy]", codigo)) and "0" not in codigo
    fechas = set()
    for contenedor in _hijos(raiz, "cellXfs"):
        for i, xf in enumerate(_hijos(contenedor, "xf")):
            fmt = int(xf.get("numFmtId", 0))
            if fmt in _FORMATOS_FECHA_INTEGRADOS or personalizados.get(fmt):
                fechas.add(i)
    return fechas


def _valor(celda, textos: list[str], fechas: set[int]):
    tipo = celda.get("t", "n")
    v = next((h.text for h in celda if _local(h.tag) == "v"), None)
    if tipo == "inlineStr":
        return "".join(t.text or "" for t in celda.iter() if _local(t.tag) == "t")
    if v is None:
        return None
    if tipo == "s":
        try:
            return textos[int(v)]
        except (ValueError, IndexError):
            return None
    if tipo == "b":
        return "VERDADERO" if v == "1" else "FALSO"
    if tipo in ("str", "e"):
        return v
    try:
        numero = float(v)
    except ValueError:
        return v
    if int(celda.get("s", 0)) in fechas and 0 < numero < 2958466:
        return (_EPOCA_EXCEL + timedelta(days=int(numero))).isoformat()
    return int(numero) if numero.is_integer() else numero


def leer_hoja(ruta: str, indice: int) -> dict:
    """
    La hoja `indice` (desde 0) como cuadrícula densa de valores, desde A1
    hasta la última celda con algo, sin pasar de los topes.
    """
    with _abrir(ruta) as zf:
        hojas = _hojas_con_ruta(zf)
        if not 0 <= indice < len(hojas):
            raise HTTPException(status_code=404, detail="Esa hoja no existe en este Excel.")
        nombre, ruta_hoja = hojas[indice]
        textos = _textos_compartidos(zf)
        fechas = _estilos_de_fecha(zf)
        raiz = _leer_xml(zf, ruta_hoja)

    celdas: dict[tuple[int, int], object] = {}
    truncada = False
    ultima_fila = ultima_col = -1
    datos = next((h for h in raiz if _local(h.tag) == "sheetData"), None) if raiz is not None else None
    for fila in (_hijos(datos, "row") if datos is not None else []):
        for celda in _hijos(fila, "c"):
            m = PATRON_CELDA.match(celda.get("r") or "")
            if not m:
                continue
            col, fil = letras_a_indice(m.group(1)), int(m.group(2)) - 1
            if fil >= MAX_FILAS or col >= MAX_COLUMNAS:
                truncada = True
                continue
            valor = _valor(celda, textos, fechas)
            if valor is None or valor == "":
                continue
            celdas[(fil, col)] = valor
            ultima_fila, ultima_col = max(ultima_fila, fil), max(ultima_col, col)

    filas = [[celdas.get((f, c)) for c in range(ultima_col + 1)] for f in range(ultima_fila + 1)]
    return {
        "indice": indice,
        "nombre": nombre,
        "columnas": [indice_a_letras(c) for c in range(ultima_col + 1)],
        "filas": filas,
        "truncada": truncada,
        "max_filas": MAX_FILAS,
        "max_columnas": MAX_COLUMNAS,
    }
