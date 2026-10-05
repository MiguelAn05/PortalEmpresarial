"""
Las áreas de la empresa: cuáles hay, si un nombre es válido y cómo se
renombra una sin dejar datos huérfanos.

Antes era una lista escrita aquí y repetida en el frontend, igual para
cualquier empresa. Ahora cada empresa tiene las suyas en la tabla `areas`
(ver `models/area.py`) y las administra en Administración › Áreas; el
frontend las pide a `GET /areas` en vez de tener su propia copia.

**La escritura exacta importa.** El área se compara como texto —las
capacidades se otorgan a un área por su nombre, la visibilidad filtra por
nombre—, así que «Servicio al Cliente» y «Servicio al cliente» son áreas
distintas. Por eso renombrar pasa por `renombrar()`, que reescribe todas las
columnas que guardan ese nombre, y nunca por un UPDATE suelto a esta tabla.
"""
import unicodedata

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.area import Area

# Con lo que arranca una empresa nueva: las áreas con que nació el portal en
# Protokimica. La migración `d2b7e5a83c19` las copió a la tabla; de ahí en
# adelante cada empresa las cambia desde Administración.
AREAS_INICIALES = [
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

# El área donde trabajan las sedes en una empresa nueva. Después se cambia en
# Administración › Áreas: es la marca `es_de_sedes`, no este nombre, la que
# decide (ver `area_de_sedes`).
AREA_DE_SEDES_INICIAL = "Puntos de Venta"
assert AREA_DE_SEDES_INICIAL in AREAS_INICIALES

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


# ── Las de cada empresa ───────────────────────────────────────

def clave_alfabetica(nombre: str) -> str:
    """
    Para ordenar como lo haría una persona: sin distinguir tildes ni
    mayúsculas. Ordenando el texto tal cual, «Área Técnica» quedaría después
    de «Ventas» y nadie la encontraría donde la busca.
    """
    sin_tildes = unicodedata.normalize("NFKD", nombre)
    return "".join(c for c in sin_tildes if not unicodedata.combining(c)).casefold()


def nombres(db: Session, tenant_id: int, incluir_inactivas: bool = False) -> list[str]:
    """
    Las áreas de la empresa, en orden alfabético.

    Alfabético y no un orden elegido a mano: con más de veinte áreas es el
    orden en que la gente sabe recorrer una lista para encontrar la suya, y
    unas flechas de «subir» y «bajar» en la pantalla de áreas se leían como
    si un área tuviera más nivel que otra.
    """
    query = db.query(Area.nombre).filter(Area.tenant_id == tenant_id)
    if not incluir_inactivas:
        query = query.filter(Area.activa.is_(True))
    return sorted((n for (n,) in query.all()), key=clave_alfabetica)


def es_valida(db: Session, tenant_id: int, area: str | None) -> bool:
    """
    ¿Se puede asignar esta área hoy? None es válido: no todo tiene que tener
    área. Una desactivada no: se conserva en lo que ya la tenía, pero no se
    asigna a nada nuevo.
    """
    return area is None or area in nombres(db, tenant_id)


def area_de_sedes(db: Session, tenant_id: int) -> str | None:
    """
    El área donde trabajan las sedes, o None si la empresa no tiene sedes.

    Quien está en ella lleva su punto de venta y ve solo las PQRS de su
    mostrador (ver `pqrs/permisos.py`). Antes era la constante
    `AREA_PUNTOS_DE_VENTA`; ahora es una marca que se pone en Administración ›
    Áreas, y por eso esa área ya se puede renombrar.
    """
    fila = db.query(Area.nombre).filter(
        Area.tenant_id == tenant_id, Area.es_de_sedes.is_(True),
    ).first()
    return fila[0] if fila else None


def sembrar(db: Session, tenant_id: int) -> list[str]:
    """
    Le da a una empresa las áreas de arranque que le falten. Idempotente; no
    reactiva una que alguien desactivó. Devuelve las agregadas. No hace
    commit: lo decide quien llama.
    """
    existentes = set(nombres(db, tenant_id, incluir_inactivas=True))
    hay_area_de_sedes = area_de_sedes(db, tenant_id) is not None
    agregadas = []
    for nombre in AREAS_INICIALES:
        if nombre not in existentes:
            db.add(Area(
                tenant_id=tenant_id, nombre=nombre,
                es_de_sedes=(nombre == AREA_DE_SEDES_INICIAL and not hay_area_de_sedes),
            ))
            agregadas.append(nombre)
    db.flush()
    return agregadas


# ── Renombrar sin dejar nada huérfano ─────────────────────────
#
# Toda columna que guarda el nombre de un área, con cómo se llega a la
# empresa de cada fila: directo por `tenant_id`, o por la tabla padre cuando
# la fila no lo tiene. `tests/test_areas.py` recorre el esquema y falla si
# aparece una columna `area*` que no esté aquí: una tabla nueva que guarde un
# área quedaría con el nombre viejo después de renombrar, en silencio.
#
# (tabla, columna, None)                  -> la tabla tiene tenant_id
# (tabla, columna, (fk, tabla_padre))     -> la empresa sale del padre
COLUMNAS_CON_AREA = [
    ("users", "area", None),
    ("usuario_areas_supervisadas", "area", ("usuario_id", "users")),
    ("capacidades_otorgadas", "area", None),
    ("tipos_autorizacion", "area_autorizadora", None),
    ("pqrs_solicitudes", "area_responsable", None),
    ("pqrs_solicitudes", "area_causante", None),
    ("pqrs_pasos_area", "area", None),
    ("mp_proyectos", "area", None),
    ("mp_proyecto_areas", "area", ("proyecto_id", "mp_proyectos")),
    ("mp_tareas", "area", ("proyecto_id", "mp_proyectos")),
    ("mp_actividades", "area", None),
    ("ind_indicadores", "area", None),
    ("omp_oportunidades", "area", None),
]


def renombrar(db: Session, tenant_id: int, area: Area, nuevo: str) -> dict[str, int]:
    """
    Cambia el nombre de un área y de todo lo que lo lleva escrito. Devuelve
    cuántas filas cambió en cada tabla, para decírselo a quien lo hizo.

    No hace commit: si algo falla a mitad de camino, quien llama deshace todo
    y no queda la mitad de los datos con un nombre y la mitad con el otro.
    """
    from app.core.database import Base  # el esquema completo, ya cargado

    viejo = area.nombre
    cambios: dict[str, int] = {}
    for tabla_nombre, columna, ruta in COLUMNAS_CON_AREA:
        tabla = Base.metadata.tables[tabla_nombre]
        col = tabla.c[columna]
        if ruta is None:
            de_la_empresa = tabla.c.tenant_id == tenant_id
        else:
            fk, padre_nombre = ruta
            padre = Base.metadata.tables[padre_nombre]
            de_la_empresa = tabla.c[fk].in_(
                select(padre.c.id).where(padre.c.tenant_id == tenant_id)
            )
        resultado = db.execute(
            update(tabla).where(col == viejo, de_la_empresa).values({columna: nuevo})
        )
        if resultado.rowcount:
            clave = f"{tabla_nombre}.{columna}"
            cambios[clave] = cambios.get(clave, 0) + resultado.rowcount
    area.nombre = nuevo
    db.flush()
    return cambios
