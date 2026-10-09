"""
Las bodegas de la empresa: una sola lista para todo el portal, con sus
responsables. Ver `models/bodega.py` para el porqué.

Antes era una lista fija aquí (`Guayabal`, `La 65`) que solo usaba Notas
crédito, y PQRS tenía otra. Ahora es tabla por empresa, se edita en
Administración › Bodegas y la usan los dos.

**Quién confirma en una bodega** (`puede_confirmar`): sus responsables, si
tiene; si todavía no tiene ninguno, cualquiera con el permiso de confirmar
producto, para que una bodega recién creada no deje solicitudes sin nadie que
las atienda. `admin` siempre puede.
"""
import unicodedata

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models.bodega import Bodega, BodegaResponsable
from app.models.user import User

# Con lo que arranca una empresa nueva. Lo demás se agrega en Administración.
BODEGAS_INICIALES = ["CD", "La 65", "Guayabal"]

# Las columnas que guardan la bodega por su NOMBRE: renombrar las reescribe,
# igual que `areas.COLUMNAS_CON_AREA`. Las que la guardan por id no hace falta.
COLUMNAS_CON_BODEGA = [
    ("nc_solicitudes", "bodega"),
]

# Lo que es configuración de la bodega y se va con ella: no cuenta como uso.
COLUMNAS_DE_CONFIGURACION = {
    ("bodega_responsables", "bodega_id"),
    ("pqrs_conceptos_bodega", "bodega_id"),
}


def normalizar(nombre: str | None) -> str | None:
    """Sin espacios de más. `None` es válido: no toda solicitud pasa por bodega."""
    limpio = " ".join((nombre or "").split())
    return limpio or None


def clave_alfabetica(nombre: str) -> str:
    sin = unicodedata.normalize("NFD", nombre or "")
    return "".join(c for c in sin if unicodedata.category(c) != "Mn").lower()


def sembrar(db: Session, tenant_id: int) -> None:
    """La lista de arranque, si la empresa no tiene ninguna. No hace commit."""
    if db.query(Bodega.id).filter(Bodega.tenant_id == tenant_id).first():
        return
    for orden, nombre in enumerate(BODEGAS_INICIALES):
        db.add(Bodega(tenant_id=tenant_id, nombre=nombre, orden=orden))
    db.flush()


def del_tenant(db: Session, tenant_id: int, incluir_inactivas: bool = False) -> list[Bodega]:
    sembrar(db, tenant_id)
    consulta = db.query(Bodega).filter(Bodega.tenant_id == tenant_id)
    if not incluir_inactivas:
        consulta = consulta.filter(Bodega.activo.is_(True))
    return consulta.order_by(Bodega.orden, Bodega.nombre).all()


def nombres(db: Session, tenant_id: int) -> list[str]:
    return [b.nombre for b in del_tenant(db, tenant_id)]


def obtener(db: Session, tenant_id: int, bodega_id: int) -> Bodega | None:
    return db.query(Bodega).filter(Bodega.id == bodega_id, Bodega.tenant_id == tenant_id).first()


def por_nombre(db: Session, tenant_id: int, nombre: str | None) -> Bodega | None:
    nombre = normalizar(nombre)
    if not nombre:
        return None
    return db.query(Bodega).filter(Bodega.tenant_id == tenant_id, Bodega.nombre == nombre).first()


def es_valida(db: Session, tenant_id: int, nombre: str | None) -> bool:
    """Una bodega activa de la empresa. `None` pasa: no todo lleva bodega."""
    if normalizar(nombre) is None:
        return True
    bodega = por_nombre(db, tenant_id, nombre)
    return bool(bodega and bodega.activo)


def responsables(db: Session, tenant_id: int, nombre: str | None) -> list[User]:
    """Los responsables ACTIVOS de esa bodega. Vacío si no tiene, o no existe."""
    bodega = por_nombre(db, tenant_id, nombre)
    if not bodega:
        return []
    ids = [r.usuario_id for r in bodega.responsables]
    if not ids:
        return []
    return db.query(User).filter(User.id.in_(ids), User.activo.is_(True)).all()


def de_usuario(db: Session, usuario: User) -> list[str]:
    """Las bodegas por las que responde esta persona."""
    filas = (
        db.query(Bodega.nombre)
        .join(BodegaResponsable, BodegaResponsable.bodega_id == Bodega.id)
        .filter(Bodega.tenant_id == usuario.tenant_id, BodegaResponsable.usuario_id == usuario.id)
    )
    return [n for (n,) in filas]


def puede_confirmar(db: Session, usuario: User, nombre: str | None, tiene_capacidad: bool) -> bool:
    """
    ¿Le toca a esta persona confirmar lo de esta bodega?

    Si la bodega tiene responsables, solo ellos: una devolución de Guayabal no
    la confirma quien maneja La 65. Si no tiene ninguno todavía, quien tenga
    el permiso de confirmar producto, para que nada se quede quieto.
    """
    if usuario.rol == "admin":
        return True
    suyos = responsables(db, usuario.tenant_id, nombre)
    if suyos:
        return any(u.id == usuario.id for u in suyos)
    return tiene_capacidad


def renombrar(db: Session, tenant_id: int, bodega: Bodega, nuevo: str) -> dict[str, int]:
    """
    Cambia el nombre y lo reescribe donde se guarda como texto. Devuelve
    cuántas filas cambió en cada tabla. No hace commit.
    """
    viejo = bodega.nombre
    cambios = {}
    for tabla_nombre, columna in COLUMNAS_CON_BODEGA:
        tabla = Base.metadata.tables[tabla_nombre]
        condicion = tabla.c[columna] == viejo
        if "tenant_id" in tabla.c:
            condicion = condicion & (tabla.c.tenant_id == tenant_id)
        resultado = db.execute(tabla.update().where(condicion).values({columna: nuevo}))
        if resultado.rowcount:
            cambios[tabla_nombre] = resultado.rowcount
    bodega.nombre = nuevo
    return cambios


def usos(db: Session, bodega: Bodega) -> int:
    """
    En cuántos registros aparece: por su nombre (`COLUMNAS_CON_BODEGA`) y por
    su id (toda llave foránea a `bodegas.id`, sacada del esquema, así que una
    tabla nueva queda contada el día que se crea). La configuración de la
    propia bodega no cuenta.
    """
    total = 0
    for tabla_nombre, columna in COLUMNAS_CON_BODEGA:
        tabla = Base.metadata.tables[tabla_nombre]
        condicion = tabla.c[columna] == bodega.nombre
        if "tenant_id" in tabla.c:
            condicion = condicion & (tabla.c.tenant_id == bodega.tenant_id)
        total += db.execute(func.count().select().select_from(tabla).where(condicion)).scalar() or 0
    for tabla in Base.metadata.sorted_tables:
        for columna in tabla.columns:
            if (tabla.name, columna.name) in COLUMNAS_DE_CONFIGURACION:
                continue
            if any(fk.column.table.name == "bodegas" for fk in columna.foreign_keys):
                total += db.execute(
                    func.count().select().select_from(tabla).where(columna == bodega.id)
                ).scalar() or 0
    return total
