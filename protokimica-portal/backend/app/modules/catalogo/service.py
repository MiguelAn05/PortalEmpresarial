"""
Sincronizar y buscar productos del catálogo.

La sincronización reemplaza el catálogo entero en una sola transacción: o
queda todo el lote nuevo, o no queda nada. Aplicarlo a medias dejaría el
buscador con medio catálogo y nadie se enteraría hasta que un cliente no
encuentre su producto.
"""
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.catalogo import ProductoCatalogo

# Mínimo de caracteres para buscar. Con menos, cualquiera podría recorrer el
# catálogo entero letra por letra desde el formulario público.
MINIMO_BUSQUEDA = 2

# Tope de resultados. Suficiente para encontrar lo que se busca, y poco para
# que el buscador no sirva como forma de descargarse el catálogo.
MAXIMO_RESULTADOS = 15


def sincronizar(db: Session, tenant_id: int, productos: list[dict]) -> dict:
    """
    Deja el catálogo igual al lote recibido.

    Lo que ya existe se actualiza, lo nuevo se agrega, y lo que dejó de venir
    se marca inactivo en vez de borrarse: si mañana vuelve al catálogo del
    ERP, no se pierde nada, y las PQRS viejas que lo mencionan siguen
    teniendo sentido.
    """
    existentes = {
        p.codigo: p
        for p in db.query(ProductoCatalogo).filter(
            ProductoCatalogo.tenant_id == tenant_id
        ).all()
    }

    vistos = set()
    nuevos = actualizados = 0

    for datos in productos:
        codigo = (datos.get("codigo") or "").strip()
        nombre = (datos.get("nombre") or "").strip()
        # Sin código o sin nombre no se puede ofrecer en un buscador: se
        # ignora la fila en vez de meter basura al catálogo.
        if not codigo or not nombre:
            continue

        vistos.add(codigo)
        presentacion = (datos.get("presentacion") or "").strip() or None

        actual = existentes.get(codigo)
        if actual is None:
            db.add(ProductoCatalogo(
                tenant_id=tenant_id, codigo=codigo, nombre=nombre,
                presentacion=presentacion, activo=True,
            ))
            nuevos += 1
        else:
            cambio = (
                actual.nombre != nombre
                or actual.presentacion != presentacion
                or not actual.activo
            )
            if cambio:
                actual.nombre = nombre
                actual.presentacion = presentacion
                actual.activo = True
                actualizados += 1

    descontinuados = 0
    for codigo, producto in existentes.items():
        if codigo not in vistos and producto.activo:
            producto.activo = False
            descontinuados += 1

    db.commit()

    return {
        "recibidos": len(productos),
        "nuevos": nuevos,
        "actualizados": actualizados,
        "descontinuados": descontinuados,
        "total_activos": db.query(ProductoCatalogo).filter(
            ProductoCatalogo.tenant_id == tenant_id,
            ProductoCatalogo.activo.is_(True),
        ).count(),
    }


def buscar(db: Session, tenant_id: int, texto: str) -> list[dict]:
    """
    Busca por código o por nombre, sin distinguir mayúsculas.

    Devuelve solo código, nombre y presentación. Aunque el catálogo tuviera
    más columnas, de aquí no sale nada más: este endpoint lo consume el
    formulario público, sin autenticación.
    """
    texto = (texto or "").strip()
    if len(texto) < MINIMO_BUSQUEDA:
        return []

    patron = f"%{texto.lower()}%"
    productos = (
        db.query(ProductoCatalogo)
        .filter(
            ProductoCatalogo.tenant_id == tenant_id,
            ProductoCatalogo.activo.is_(True),
            or_(
                func.lower(ProductoCatalogo.nombre).like(patron),
                func.lower(ProductoCatalogo.codigo).like(patron),
            ),
        )
        .order_by(ProductoCatalogo.nombre)
        .limit(MAXIMO_RESULTADOS)
        .all()
    )

    return [
        {"codigo": p.codigo, "nombre": p.nombre, "presentacion": p.presentacion}
        for p in productos
    ]
