"""
De la presentación del ERP («FCOS X 500 CC», «PAQ X 5 KIL») a la que pide
el formulario: una unidad de `UNIDADES` y una cantidad («Mililitro», «500»).

El ERP la escribe como texto libre en `UNIDADESDEMEDIDA`, y con un producto
escogido del catálogo no tiene sentido volver a preguntársela al cliente: el
código ya la dice. Así que se traduce al sincronizar y el formulario la
llena sola.

Reglas:

  - **Lo que no se entiende queda vacío, nunca adivinado.** Entonces el
    formulario se la pregunta al cliente, como antes. Una presentación mal
    traducida entraría a los informes como si fuera cierta.
  - **No se traduce por el código de tres cifras** (`…094`), aunque casi
    siempre coincide: hay `…094` que dicen UNIDAD y `…093` que dicen
    FCOS X 500 CC. El texto es lo que el ERP afirma.
  - **El garrafón (GFON) no dice cuánto trae**: su contenido varía («x 20L»,
    «GX18Kg», «Gx19K») y está en el NOMBRE del producto. Es el único caso que
    se lee del nombre; en los demás, un número del nombre puede ser una
    concentración («ACIDO 37%») y no la presentación.
"""
import re
import unicodedata

# Las del desplegable del formulario. ATADO a `PRESENTACIONES` de
# `frontend/src/modules/pqrs/constants.js` (una prueba lo verifica).
UNIDADES = ("Unidad", "Kilo", "Gramo", "Litro", "Mililitro", "Galón")

# Las que no traen número y no se pueden leer con el patrón. Las claves van
# como las deja `_normalizar`: mayúscula, sin tildes, un espacio.
CONOCIDAS = {
    "KILO GRANEL": ("Kilo", "1"),
    "PAQ X KILO": ("Kilo", "1"),
    "UNIDAD": ("Unidad", "1"),
    "LITRO": ("Litro", "1"),
    # La libra colombiana es de 500 gramos.
    "LIBRA": ("Gramo", "500"),
    "1/2 LIBRA": ("Gramo", "250"),
    "GALON": ("Galón", "1"),
    # Medio galón: los productos con esta presentación dicen «1.9 L» en el nombre.
    "MG- M/ GALON": ("Galón", "0,5"),
}

# Las que no dicen el contenido: se busca en el nombre del producto.
SIN_CONTENIDO = {"GFON"}

# Número seguido de unidad. El orden importa: las largas antes que las
# cortas, o «KILOS» se leería como «K» y «MLT» como «ML».
_UNIDAD_DE = [
    (r"KILOS?|KIL|KGS?|K", "Kilo"),
    (r"GRAMOS?|GRS?|GRM|GR|G", "Gramo"),
    (r"MLT|ML|CC", "Mililitro"),
    (r"LITROS?|LTS?|LT|L", "Litro"),
    (r"UNIDADES|UNID|UND|UN", "Unidad"),
]
_PATRON = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(" + "|".join(p for p, _ in _UNIDAD_DE) + r")(?![A-Z])"
)


def _normalizar(texto: str | None) -> str:
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return " ".join(texto.upper().split())


def _cantidad(numero: str) -> str:
    """«2.5» y «2,5» → «2,5»; «500.0» → «500». Coma decimal, como en Colombia."""
    valor = float(numero.replace(",", "."))
    if valor.is_integer():
        return str(int(valor))
    return f"{valor:g}".replace(".", ",")


def _leer(texto: str) -> tuple[str, str] | None:
    coincidencia = _PATRON.search(texto)
    if not coincidencia:
        return None
    numero, unidad = coincidencia.groups()
    for patron, nombre in _UNIDAD_DE:
        if re.fullmatch(patron, unidad):
            return nombre, _cantidad(numero)
    return None


def interpretar(presentacion: str | None, nombre: str | None = None) -> tuple[str | None, str | None]:
    """
    `(unidad, cantidad)` del formulario, o `(None, None)` si no se entiende.

    >>> interpretar("FCOS X 500 CC")
    ('Mililitro', '500')
    >>> interpretar("GFON", "DESINFECTANTE IND DE SUPERFICIES x 20L**")
    ('Litro', '20')
    """
    clave = _normalizar(presentacion)
    if not clave:
        return None, None
    if clave in CONOCIDAS:
        return CONOCIDAS[clave]
    if clave in SIN_CONTENIDO:
        return _leer(_normalizar(nombre)) or (None, None)
    return _leer(clave) or (None, None)
