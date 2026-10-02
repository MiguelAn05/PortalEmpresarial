"""
Los canales de atención de la empresa: por dónde entra una PQRS, cuáles son
sedes y con qué prefijo numeran sus casos.

Antes eran una lista en este archivo y su gemelo `canales.js`, con los seis
puntos de venta de Protokimica escritos a mano. Ahora cada empresa tiene los
suyos en la tabla `canales` (ver `models/canal.py` para los tipos y por qué
el prefijo no se cambia) y los administra en Administración › Canales.

Antes de eso ya se habían separado una vez: el formulario normal ofrecía
«Línea telefónica» y el de felicitaciones «Llamada telefónica», así que la
misma llamada caía en dos canales y el reporte las contaba aparte. Una lista
por empresa, servida desde aquí, es lo que evita que vuelva a pasar.
"""
import re

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.areas import clave_alfabetica
from app.models.canal import MAX_PREFIJO, TIPOS_CANAL, Canal

# Con lo que arranca una empresa nueva: los canales con que nació el portal en
# Protokimica. La migración `f3a9d6b28e51` los copió a la tabla.
# (nombre, prefijo, tipo)
CANALES_INICIALES = [
    ("Venta institucional", "VI", "institucional"),
    ("WhatsApp", None, "general"),
    ("Punto de venta Centro", "PVC", "sede"),
    ("Punto de venta Belén", "PVB", "sede"),
    ("Punto de venta Guayabal", "PVG", "sede"),
    ("Punto de venta La 65", "PV65", "sede"),
    ("Punto de venta Cristo Rey", "PVCR", "sede"),
    ("Punto de venta Itagüí", "PVI", "sede"),
    ("Línea telefónica", None, "general"),
]

# Nombres que quedaron en datos ya guardados y a qué canal corresponden hoy.
# «Llamada telefónica» solo existía en el formulario de felicitaciones: era la
# misma llamada que el resto del portal llama «Línea telefónica», contada
# aparte en los reportes por culpa de una palabra.
EQUIVALENCIAS_HISTORICAS = {
    "Llamada telefónica": "Línea telefónica",
}


def normalizar(canal: str | None) -> str | None:
    """Traduce un nombre viejo al actual. Devuelve None si viene vacío."""
    if not canal or not canal.strip():
        return None
    limpio = canal.strip()
    return EQUIVALENCIAS_HISTORICAS.get(limpio, limpio)


# ── Los de cada empresa ───────────────────────────────────────

def del_tenant(db: Session, tenant_id: int, incluir_inactivos: bool = False) -> list[Canal]:
    """Los canales de la empresa, en orden alfabético."""
    query = db.query(Canal).filter(Canal.tenant_id == tenant_id)
    if not incluir_inactivos:
        query = query.filter(Canal.activo.is_(True))
    return sorted(query.all(), key=lambda c: clave_alfabetica(c.nombre))


def nombres(db: Session, tenant_id: int) -> list[str]:
    """Los activos: lo que se ofrece en los formularios."""
    return [c.nombre for c in del_tenant(db, tenant_id)]


def es_valido(db: Session, tenant_id: int, canal: str | None) -> bool:
    """None es válido: una PQRS interna puede no tener canal."""
    return canal is None or canal in nombres(db, tenant_id)


def _por_nombre(db: Session, tenant_id: int, canal: str | None) -> Canal | None:
    if not canal:
        return None
    return db.query(Canal).filter(
        Canal.tenant_id == tenant_id, Canal.nombre == canal.strip(),
    ).first()


def prefijo_de(db: Session, tenant_id: int, canal: str | None) -> str | None:
    """
    El prefijo del código de seguimiento, o None si el canal no tiene uno.
    Vale también para un canal desactivado: sus PQRS viejas siguen
    llevando su prefijo y hay que poder reconocerlas.
    """
    encontrado = _por_nombre(db, tenant_id, canal)
    return encontrado.prefijo if encontrado else None


def prefijos(db: Session, tenant_id: int) -> list[str]:
    """Todos los prefijos de la empresa, activos o no."""
    return [c.prefijo for c in del_tenant(db, tenant_id, incluir_inactivos=True) if c.prefijo]


def canal_por_codigo(db: Session, tenant_id: int, codigo: str | None,
                     solo_activos: bool = True) -> Canal | None:
    """
    El canal al que apunta un código de QR (`PVG` → «Punto de venta Guayabal»).

    Se compara sin distinguir mayúsculas porque el código va impreso en un
    letrero y alguien lo va a teclear a mano tarde o temprano.
    """
    if not codigo:
        return None
    query = db.query(Canal).filter(
        Canal.tenant_id == tenant_id, Canal.prefijo == codigo.strip().upper(),
    )
    if solo_activos:
        query = query.filter(Canal.activo.is_(True))
    return query.first()


def puntos_de_venta(db: Session, tenant_id: int, incluir_inactivos: bool = False) -> list[str]:
    """
    Los canales que son una sede física: los que se le asignan a un usuario
    como su punto de venta. «Venta institucional» tiene prefijo pero no es una
    sede —nadie trabaja «en» ella detrás de un mostrador—, y por eso va con
    su propio tipo.
    """
    return [c.nombre for c in del_tenant(db, tenant_id, incluir_inactivos) if c.tipo == "sede"]


def es_institucional(db: Session, tenant_id: int, canal: str | None) -> bool:
    """¿Este canal sigue la cadena institucional de las notas crédito?"""
    encontrado = _por_nombre(db, tenant_id, normalizar(canal))
    return bool(encontrado and encontrado.tipo == "institucional")


def sembrar(db: Session, tenant_id: int) -> list[str]:
    """
    Le da a una empresa los canales de arranque que le falten. Idempotente;
    no reactiva uno desactivado. No hace commit.
    """
    existentes = {c.nombre for c in del_tenant(db, tenant_id, incluir_inactivos=True)}
    agregados = []
    for nombre, prefijo, tipo in CANALES_INICIALES:
        if nombre not in existentes:
            db.add(Canal(tenant_id=tenant_id, nombre=nombre, prefijo=prefijo, tipo=tipo))
            agregados.append(nombre)
    db.flush()
    return agregados


# ── Reglas para crear y cambiar ───────────────────────────────

_PREFIJO_VALIDO = re.compile(r"^[A-Z0-9]{2,%d}$" % MAX_PREFIJO)


def validar_prefijo(prefijo: str | None) -> str | None:
    """
    El prefijo limpio, en mayúsculas, o ValueError con lo que hay que
    corregir. Solo letras y números: va dentro de una URL (`/q/PVG`) y al
    comienzo de un consecutivo (`PVG0010`).
    """
    if prefijo is None or not prefijo.strip():
        return None
    limpio = prefijo.strip().upper()
    if not _PREFIJO_VALIDO.match(limpio):
        raise ValueError(
            f"El prefijo «{prefijo}» no sirve: usa de 2 a {MAX_PREFIJO} letras o "
            "números, sin espacios ni guiones (por ejemplo PVG)."
        )
    return limpio


def validar_tipo(tipo: str) -> str:
    if tipo not in TIPOS_CANAL:
        raise ValueError(f"El tipo tiene que ser uno de: {', '.join(TIPOS_CANAL)}.")
    return tipo


# Toda columna que guarda el NOMBRE de un canal. `users.punto_venta` guarda el
# PREFIJO, que no cambia, y por eso no está aquí. `tests/test_canales.py`
# falla si aparece una columna `canal*` que no esté en la lista.
COLUMNAS_CON_CANAL = [
    ("pqrs_solicitudes", "canal_atencion"),
    ("nc_solicitudes", "punto_venta"),
]


def renombrar(db: Session, tenant_id: int, canal: Canal, nuevo: str) -> dict[str, int]:
    """
    Cambia el nombre de un canal y de las PQRS y notas crédito que lo llevan.
    No hace commit: si algo falla, quien llama deshace todo.
    """
    from app.core.database import Base  # el esquema completo, ya cargado

    viejo = canal.nombre
    cambios: dict[str, int] = {}
    for tabla_nombre, columna in COLUMNAS_CON_CANAL:
        tabla = Base.metadata.tables[tabla_nombre]
        resultado = db.execute(
            update(tabla)
            .where(tabla.c[columna] == viejo, tabla.c.tenant_id == tenant_id)
            .values({columna: nuevo})
        )
        if resultado.rowcount:
            cambios[f"{tabla_nombre}.{columna}"] = resultado.rowcount
    canal.nombre = nuevo
    db.flush()
    return cambios
