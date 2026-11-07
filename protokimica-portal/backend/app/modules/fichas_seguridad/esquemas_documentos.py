"""
Los documentos que genera Fichas de seguridad y la forma de sus datos.

Dos tipos, cada uno con su forma:

- `certificado_analisis` (AP-F-06): producto, proveedor, lotes, fechas y una
  tabla de parámetros (nombre, unidad, requisito, método, resultado).
- `fds` (AP-F-08): la ficha de datos de seguridad, en las 16 secciones del SGA.

**Nada de esto es obligatorio salvo `producto`**: la lectura no siempre entiende todo, y
lo que no leyó se completa a mano en la pantalla. Un campo vacío no bloquea
generar el documento; lo que hace el servidor es DECIR qué quedó sin leer
(`faltantes`), para que la pantalla lo señale.
"""
from pydantic import BaseModel, Field

MAX_TEXTO = 300
MAX_PARAMETROS = 80
MAX_SECCION = 6000

TIPOS = ("certificado_analisis", "fds")

# Las 16 secciones de la FDS, con los títulos de la plantilla AP-F-08 de Protokimica.
SECCIONES_FDS = [
    "Identificación del producto",
    "Identificación de los peligros",
    "Composición – información de los componentes",
    "Primeros auxilios",
    "Medidas de lucha contra incendio",
    "Medidas a tomar en caso de vertido accidental",
    "Manipulación y almacenamiento",
    "Controles de exposición – equipo de protección personal",
    "Propiedades físicas y químicas",
    "Estabilidad y reactividad",
    "Información toxicológica",
    "Información ecotoxicológica",
    "Consideración sobre eliminación",
    "Información relativa al transporte",
    "Información reglamentaria",
    "Otras informaciones",
]


class Parametro(BaseModel):
    nombre: str = Field("", max_length=MAX_TEXTO)
    unidad: str = Field("", max_length=60)
    requisito: str = Field("", max_length=MAX_TEXTO)
    metodo: str = Field("", max_length=MAX_TEXTO)
    resultado: str = Field("", max_length=MAX_TEXTO)


class DatosCertificado(BaseModel):
    producto: str = Field("", max_length=200)
    codigo_producto: str = Field("", max_length=40)
    proveedor: str = Field("", max_length=200)
    lote_fabricante: str = Field("", max_length=100)
    lote_protokimica: str = Field("", max_length=100)
    fecha_fabricacion: str = Field("", max_length=40)
    fecha_vencimiento: str = Field("", max_length=40)
    parametros: list[Parametro] = Field(default_factory=list, max_length=MAX_PARAMETROS)


class SeccionFDS(BaseModel):
    numero: int = Field(ge=1, le=16)
    titulo: str = Field("", max_length=MAX_TEXTO)
    contenido: str = Field("", max_length=MAX_SECCION)


class DatosFDS(BaseModel):
    producto: str = Field("", max_length=200)
    codigo_producto: str = Field("", max_length=40)
    proveedor: str = Field("", max_length=200)
    version: str = Field("", max_length=20)
    fecha_emision: str = Field("", max_length=40)
    secciones: list[SeccionFDS] = Field(default_factory=list, max_length=16)


MODELO_POR_TIPO = {"certificado_analisis": DatosCertificado, "fds": DatosFDS}

# Lo que se avisa como «sin leer» si viene vacío.
OBLIGATORIOS_DE_LECTURA = {
    "certificado_analisis": [
        ("producto", "producto"), ("proveedor", "proveedor"), ("lote_fabricante", "lote del fabricante"),
        ("fecha_fabricacion", "fecha de fabricación"), ("fecha_vencimiento", "fecha de vencimiento"),
    ],
    "fds": [("producto", "producto"), ("proveedor", "proveedor"), ("version", "versión"), ("fecha_emision", "fecha de emisión")],
}


def faltantes(tipo: str, datos: dict) -> list[str]:
    """Lo que la lectura no pudo leer, redactado para la persona que revisa."""
    salida = [etiqueta for campo, etiqueta in OBLIGATORIOS_DE_LECTURA[tipo] if not str(datos.get(campo) or "").strip()]
    if tipo == "certificado_analisis" and not datos.get("parametros"):
        salida.append("tabla de parámetros")
    if tipo == "fds":
        llenas = [s for s in datos.get("secciones") or [] if str(s.get("contenido") or "").strip()]
        if len(llenas) < 16:
            salida.append(f"secciones sin leer ({16 - len(llenas)} de 16)")
    return salida
