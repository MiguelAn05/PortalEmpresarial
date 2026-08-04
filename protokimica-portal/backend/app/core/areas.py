"""
Las áreas de la empresa. Fuente única del backend.

Antes vivían repetidas en seis archivos del frontend y con listas distintas
entre módulos: PQRS conocía "Facturación" y Master Planner no, así que un
indicador de Facturación no cruzaba con nada.

El gemelo de este archivo es `frontend/src/core/areas.js`, y una prueba
verifica que los dos digan exactamente lo mismo.

Cuando el portal se venda a más de una empresa esto pasa a ser una tabla por
tenant. Que hoy sea una sola lista es lo que hace ese cambio barato: se
reemplaza este módulo por una consulta y nada más se entera.
"""

AREAS = [
    "TICS",
    "Calidad",
    "SST",
    "Controlados",
    "Facturación",
    "Ventas institucionales",
    "Mercadeo",
    "Servicio al cliente",
    "Infraestructura",
    "Logística",
    "Gestión humana",
    "Contabilidad",
]

# Nombres viejos que quedaron en datos ya guardados y a qué área corresponden
# hoy. La migración `d4a8c1f70b32` los reescribió en la base; esto se queda
# como documentación de la equivalencia y por si aparece un dato rezagado.
EQUIVALENCIAS_HISTORICAS = {
    "TI": "TICS",
    "Sistemas": "TICS",
    "Talento Humano": "Gestión humana",
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
