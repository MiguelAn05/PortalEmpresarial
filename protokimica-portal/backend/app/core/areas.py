"""
Las áreas de la empresa. Fuente única del backend.

Antes vivían repetidas en seis archivos del frontend y con listas distintas
entre módulos: PQRS conocía "Facturación" y Master Planner no, así que un
indicador de Facturación no cruzaba con nada.

El gemelo de este archivo es `frontend/src/core/areas.js`, y una prueba
verifica que los dos digan exactamente lo mismo.

**La escritura exacta importa.** El área se compara como texto en varios
sitios (por ejemplo, quién puede cerrar una PQRS), así que "Servicio al
Cliente" y "Servicio al cliente" son áreas distintas para el sistema. Si hay
que cambiar cómo se escribe una, va con migración de datos.

Cuando el portal se venda a más de una empresa esto pasa a ser una tabla por
tenant. Que hoy sea una sola lista es lo que hace ese cambio barato: se
reemplaza este módulo por una consulta y nada más se entera.
"""

AREAS = [
    "TICS",
    "Calidad",
    "SST",
    # «Controlados» se retiró en la migración `e7b2a940cf1f`: era la misma
    # área que «Control Interno», y dos nombres para lo mismo parten el
    # reporte en dos mitades que no son ninguna de las dos. Lo que estaba en
    # ella se movió, no se perdió.
    "Facturación",
    "Ventas Institucionales",
    "Mercadeo",
    "Servicio al Cliente",
    "Infraestructura",
    "Logística",
    "Gestión Humana",
    "Contabilidad",
    "Producción",
    "Control Interno",
    "Aseguramiento",
    "Abastecimiento",
    "Comercial",
    "Administración",
    "Tesorería",
    "Puntos de Venta",
    "Ambiental",
    "Dirección Técnica",
    "Investigación y Desarrollo (IDI)",
    "Salvak",
]

# El área de las seis sedes. Tiene reglas propias en dos módulos —en PQRS cada
# punto ve solo las suyas, y en usuarios es la única que lleva `punto_venta`—,
# así que su nombre vive aquí y no dentro de uno de ellos.
AREA_PUNTOS_DE_VENTA = "Puntos de Venta"
assert AREA_PUNTOS_DE_VENTA in AREAS, (
    f"'{AREA_PUNTOS_DE_VENTA}' ya no esta en AREAS. Actualiza esta constante o "
    "los puntos de venta volverian a ver todas las PQRS."
)

# Nombres viejos que quedaron en datos ya guardados y a qué área corresponden
# hoy. Las migraciones `d4a8c1f70b32` y `b9e2f4a17c05` los reescribieron en la
# base; esto se queda como documentación de la equivalencia y por si aparece
# un dato rezagado.
EQUIVALENCIAS_HISTORICAS = {
    "TI": "TICS",
    "Sistemas": "TICS",
    "Talento Humano": "Gestión Humana",
    "Gestión humana": "Gestión Humana",
    "Servicio al cliente": "Servicio al Cliente",
    "Ventas institucionales": "Ventas Institucionales",
}


def normalizar(area: str | None) -> str | None:
    """Traduce un nombre viejo al actual. Devuelve None si viene vacío."""
    if not area or not area.strip():
        return None
    limpia = area.strip()
    return EQUIVALENCIAS_HISTORICAS.get(limpia, limpia)


def es_valida(area: str | None) -> bool:
    """None es válido: no todo tiene que tener área asignada."""
    return area is None or area in AREAS
