"""
Sincronizar y buscar productos del catálogo.

La sincronización reemplaza el catálogo entero en una sola transacción: o
queda todo el lote nuevo, o no queda nada. Aplicarlo a medias dejaría el
buscador con medio catálogo y nadie se enteraría hasta que un cliente no
encuentre su producto.
"""
import unicodedata

from sqlalchemy import case
from sqlalchemy.orm import Session

from app.models.catalogo import ProductoCatalogo, SincronizacionERP

# Mínimo de caracteres para buscar. Con menos, cualquiera podría recorrer el
# catálogo entero letra por letra desde el formulario público.
MINIMO_BUSQUEDA = 2

# Tope de resultados. Suficiente para encontrar lo que se busca, y poco para
# que el buscador no sirva como forma de descargarse el catálogo.
MAXIMO_RESULTADOS = 15

# Palabras que se tienen en cuenta de lo escrito. Más que esto no afina
# nada y cada una es un filtro más sobre la tabla.
MAXIMO_PALABRAS = 6


def texto_de_busqueda(*partes: str | None) -> str:
    """
    Minúscula, sin tildes y con un solo espacio entre palabras.

    Nadie escribe tildes en un buscador, y el ERP a veces las trae y a veces
    no: «ACIDO» y «Ácido» tienen que ser lo mismo. Gemelo de
    `_texto_de_busqueda` en la migración `b7d41e9a2c63`.
    """
    texto = " ".join(p for p in partes if p)
    sin_tildes = unicodedata.normalize("NFKD", texto)
    sin_tildes = "".join(c for c in sin_tildes if not unicodedata.combining(c))
    return " ".join(sin_tildes.lower().split())[:500]


def registrar(db: Session, tenant_id: int, tipo: str, *,
              resumen: dict | None = None, error: str | None = None) -> None:
    """Deja constancia de lo que mandó el ERP. No hace commit: va con lo demás."""
    db.add(SincronizacionERP(
        tenant_id=tenant_id, tipo=tipo, exitosa=error is None,
        resumen=resumen, error=error,
    ))


def estado(db: Session, tenant_id: int) -> dict:
    """La última sincronización de cada tipo y la última que salió bien."""
    salida = {}
    for tipo in ("productos", "clientes"):
        base = db.query(SincronizacionERP).filter(
            SincronizacionERP.tenant_id == tenant_id, SincronizacionERP.tipo == tipo,
        ).order_by(SincronizacionERP.fecha.desc(), SincronizacionERP.id.desc())
        ultima = base.first()
        exitosa = base.filter(SincronizacionERP.exitosa.is_(True)).first()
        salida[tipo] = {
            "ultima": _fila(ultima),
            "ultima_exitosa": _fila(exitosa),
        }
    return salida


def _fila(s: SincronizacionERP | None) -> dict | None:
    if s is None:
        return None
    return {"fecha": s.fecha, "exitosa": s.exitosa, "resumen": s.resumen, "error": s.error}


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

        # Un código repetido en el lote: se queda el primero. Dos filas
        # nuevas con el mismo código reventarían `uq_producto_codigo`.
        if codigo in vistos:
            continue
        vistos.add(codigo)

        valores = {
            "nombre": nombre,
            "presentacion": (datos.get("presentacion") or "").strip() or None,
            "grupo": (datos.get("grupo") or "").strip() or None,
            "fecha_ultima_venta": datos.get("fecha_ultima_venta"),
            "activo": True,
        }
        valores["texto_busqueda"] = texto_de_busqueda(
            codigo, nombre, valores["presentacion"],
        )

        actual = existentes.get(codigo)
        if actual is None:
            db.add(ProductoCatalogo(tenant_id=tenant_id, codigo=codigo, **valores))
            nuevos += 1
        elif any(getattr(actual, campo) != valor for campo, valor in valores.items()):
            for campo, valor in valores.items():
                setattr(actual, campo, valor)
            actualizados += 1

    descontinuados = 0
    for codigo, producto in existentes.items():
        if codigo not in vistos and producto.activo:
            producto.activo = False
            descontinuados += 1

    db.flush()

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
    Busca por código, nombre o presentación: cada palabra escrita tiene que
    aparecer en alguna parte, en cualquier orden y sin importar tildes ni
    mayúsculas. «hipo 20» encuentra «HIPOCLORITO DE SODIO 13% × 20 L».

    El orden pone primero el código exacto (quien lo copia de la factura no
    debería tener que buscarlo en una lista), luego los códigos que empiezan
    así, y después lo vendido más recientemente.

    Devuelve solo código, nombre y presentación. Aunque el catálogo tuviera
    más columnas, de aquí no sale nada más: este endpoint lo consume el
    formulario público, sin autenticación.
    """
    normalizado = texto_de_busqueda(texto)
    if len(normalizado.replace(" ", "")) < MINIMO_BUSQUEDA:
        return []

    palabras = normalizado.split()[:MAXIMO_PALABRAS]
    codigo = (texto or "").strip().upper()

    consulta = db.query(ProductoCatalogo).filter(
        ProductoCatalogo.tenant_id == tenant_id,
        ProductoCatalogo.activo.is_(True),
    )
    for palabra in palabras:
        # Los comodines de LIKE escritos por alguien se toman como texto.
        palabra = palabra.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        consulta = consulta.filter(
            ProductoCatalogo.texto_busqueda.like(f"%{palabra}%", escape="\\")
        )

    productos = (
        consulta.order_by(
            case(
                (ProductoCatalogo.codigo == codigo, 0),
                (ProductoCatalogo.codigo.startswith(codigo, autoescape=True), 1),
                else_=2,
            ),
            ProductoCatalogo.fecha_ultima_venta.desc().nullslast(),
            ProductoCatalogo.nombre,
        )
        .limit(MAXIMO_RESULTADOS)
        .all()
    )

    return [
        {"codigo": p.codigo, "nombre": p.nombre, "presentacion": p.presentacion}
        for p in productos
    ]
