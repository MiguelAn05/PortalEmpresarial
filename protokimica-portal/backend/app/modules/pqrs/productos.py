"""
Los productos de una PQRS: uno o varios, cada uno con su lote y cantidades.

Un reclamo no siempre es por un solo producto. Cuando un cliente recibe tres
productos malos de la misma compra, el reclamo es uno —un plazo, un correo,
una encuesta— pero cada producto tiene su lote y sus cantidades, y el
informe de qué producto da más problemas tiene que contar los tres.

Reglas que se mantienen de cuando era uno solo:

- **`por_confirmar` se DEDUCE** («hay nombre y no hay código»), nunca se
  recibe. Una bandera puede llegar diciendo lo contrario de los campos.
- **Confirmar toma el nombre del catálogo**, a partir del código.
- **No se cierra** mientras quede un producto por confirmar.
- **Nada cambia con la PQRS cerrada**: ya entró a los indicadores.

Todo cambio queda en el historial con los datos de antes: quitar un producto
no puede borrar sin rastro lo que el cliente radicó.
"""
import json

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.catalogo import ProductoCatalogo
from app.models.pqrs import PQRSProducto, PQRSSeguimiento, PQRSSolicitud
from app.models.user import User
from app.modules.pqrs.service import NOMBRES_CAMPOS, validar_largos

# Un reclamo con más productos que esto es un pedido entero, y probablemente
# merece hablarse por teléfono. El tope existe sobre todo para que nadie
# pueda mandar diez mil filas por el formulario público. ATADO a
# `MAX_PRODUCTOS` en `frontend/src/modules/pqrs/constants.js`.
MAX_PRODUCTOS = 20

CAMPOS_PRODUCTO = [
    "producto_codigo", "producto_nombre", "presentacion", "cantidad_presentacion",
    "lote", "cantidad_factura", "cantidad_reclamo",
]
# Lo que se corrige de un producto ya radicado. El código y el nombre no:
# eso va por el catálogo (`confirmar`).
CAMPOS_CORREGIBLES = [
    "presentacion", "cantidad_presentacion", "lote", "cantidad_factura", "cantidad_reclamo",
]


def _limpio(valor):
    if valor is None:
        return None
    if not isinstance(valor, str):
        valor = str(valor)
    return valor.strip() or None


def _normalizar(datos: dict, posicion: int) -> dict | None:
    """Una fila recibida, limpia. `None` si venía completamente vacía."""
    fila = {c: _limpio(datos.get(c)) for c in CAMPOS_PRODUCTO}
    if not any(fila.values()):
        return None
    validar_largos(fila, modelo=PQRSProducto, prefijo=f"Producto {posicion}: ")
    if not fila["producto_nombre"] and not fila["producto_codigo"]:
        raise HTTPException(
            status_code=400,
            detail=(
                f"El producto {posicion} tiene datos pero no dice cuál es. "
                "Búscalo o escribe su nombre, o quita esa fila."
            ),
        )
    return fila


def leer_productos(productos_json: str | None, legado: dict) -> list[dict]:
    """
    Los productos que llegaron al radicar, validados y sin filas vacías.

    `productos_json` es la lista que manda el formulario. `legado` son los
    campos sueltos de cuando había un solo producto: un formulario viejo que
    quedó abierto o cacheado en el celular del cliente los sigue mandando, y
    no puede quedarse sin radicar por eso.
    """
    if productos_json and productos_json.strip():
        try:
            recibidos = json.loads(productos_json)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="No se entendió la lista de productos. Recarga la página e inténtalo de nuevo.",
            )
        if not isinstance(recibidos, list) or not all(isinstance(p, dict) for p in recibidos):
            raise HTTPException(
                status_code=400,
                detail="No se entendió la lista de productos. Recarga la página e inténtalo de nuevo.",
            )
    else:
        recibidos = [legado]

    if len(recibidos) > MAX_PRODUCTOS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Una PQRS admite hasta {MAX_PRODUCTOS} productos. Si son más, "
                "radica otra solicitud con los restantes."
            ),
        )

    filas = []
    for posicion, datos in enumerate(recibidos, start=1):
        fila = _normalizar(datos, posicion)
        if fila:
            filas.append(fila)
    return filas


def _nuevo(fila: dict, orden: int) -> PQRSProducto:
    return PQRSProducto(
        orden=orden,
        por_confirmar=bool(fila["producto_nombre"]) and not fila["producto_codigo"],
        **fila,
    )


def agregar_a_solicitud(solicitud: PQRSSolicitud, filas: list[dict]) -> None:
    """Al radicar: se cuelgan de la solicitud y se guardan con ella."""
    for orden, fila in enumerate(filas):
        solicitud.productos.append(_nuevo(fila, orden))


def describir(producto: PQRSProducto) -> str:
    """Cómo se nombra un producto en el historial y en los mensajes."""
    nombre = producto.producto_nombre or producto.producto_codigo or "sin nombre"
    return f"«{nombre}»" + (f" (lote {producto.lote})" if producto.lote else "")


def _detalle(producto: PQRSProducto) -> str:
    """Todos sus datos, para que quitarlo no los borre sin rastro."""
    partes = [
        f"{NOMBRES_CAMPOS[c]}: {getattr(producto, c)}"
        for c in CAMPOS_PRODUCTO if getattr(producto, c)
    ]
    return "; ".join(partes)


def _no_cerrada(solicitud: PQRSSolicitud, accion: str) -> None:
    if solicitud.estado == "cerrado":
        raise HTTPException(
            status_code=400,
            detail=(
                f"No se puede {accion} en una PQRS cerrada: ya entró a los "
                "indicadores. Los productos se corrigen antes de cerrarla."
            ),
        )


def _producto_de(db: Session, solicitud: PQRSSolicitud, producto_id: int) -> PQRSProducto:
    producto = (
        db.query(PQRSProducto)
        .filter(PQRSProducto.id == producto_id, PQRSProducto.pqrs_id == solicitud.id)
        .first()
    )
    if not producto:
        raise HTTPException(
            status_code=404,
            detail="Ese producto no está en esta PQRS. Recarga la página: puede que ya lo hayan quitado.",
        )
    return producto


def _anotar(db: Session, solicitud: PQRSSolicitud, usuario: User, tipo: str, texto: str) -> None:
    db.add(PQRSSeguimiento(
        pqrs_id=solicitud.id, usuario_id=usuario.id, tipo_evento=tipo, comentario=texto,
    ))


def agregar(db: Session, solicitud: PQRSSolicitud, usuario: User, datos: dict) -> PQRSSolicitud:
    """Un producto que faltó al radicar."""
    _no_cerrada(solicitud, "agregar productos")
    if len(solicitud.productos) >= MAX_PRODUCTOS:
        raise HTTPException(
            status_code=400,
            detail=f"Esta PQRS ya tiene {MAX_PRODUCTOS} productos, que es el máximo.",
        )
    fila = _normalizar(datos, len(solicitud.productos) + 1)
    if not fila:
        raise HTTPException(status_code=400, detail="Escribe al menos cuál es el producto.")

    orden = max((p.orden for p in solicitud.productos), default=-1) + 1
    producto = _nuevo(fila, orden)
    solicitud.productos.append(producto)
    _anotar(db, solicitud, usuario, "cambio_producto",
            f"Se agregó el producto {describir(producto)}. {_detalle(producto)}.")
    db.commit()
    db.refresh(solicitud)
    return solicitud


def corregir(db: Session, solicitud: PQRSSolicitud, usuario: User,
             producto_id: int, cambios: dict) -> PQRSSolicitud:
    """Lote, presentación y cantidades. Solo lo que llega y de verdad cambió."""
    _no_cerrada(solicitud, "corregir productos")
    producto = _producto_de(db, solicitud, producto_id)

    nuevos = {c: _limpio(v) for c, v in cambios.items() if c in CAMPOS_CORREGIBLES}
    validar_largos(nuevos, modelo=PQRSProducto, prefijo=f"{describir(producto)}: ")
    diferencias = [
        (c, getattr(producto, c), v) for c, v in nuevos.items() if getattr(producto, c) != v
    ]
    if not diferencias:
        raise HTTPException(
            status_code=400,
            detail="No cambiaste ningún dato del producto. Modifica al menos un campo antes de guardar.",
        )

    nombre = describir(producto)
    for campo, _antes, valor in diferencias:
        setattr(producto, campo, valor)
    detalle = "; ".join(
        f"{NOMBRES_CAMPOS[c]}: «{a or '(vacío)'}» → «{n or '(vacío)'}»"
        for c, a, n in sorted(diferencias, key=lambda d: CAMPOS_CORREGIBLES.index(d[0]))
    )
    _anotar(db, solicitud, usuario, "cambio_producto", f"Producto {nombre} corregido. {detalle}.")
    db.commit()
    db.refresh(solicitud)
    return solicitud


def quitar(db: Session, solicitud: PQRSSolicitud, usuario: User, producto_id: int) -> PQRSSolicitud:
    """Un producto que no correspondía. Sus datos quedan escritos en el historial."""
    _no_cerrada(solicitud, "quitar productos")
    producto = _producto_de(db, solicitud, producto_id)
    texto = f"Se quitó el producto {describir(producto)}. Tenía: {_detalle(producto)}."
    solicitud.productos.remove(producto)
    _anotar(db, solicitud, usuario, "cambio_producto", texto)
    db.commit()
    db.refresh(solicitud)
    return solicitud


def confirmar(db: Session, tenant_id: int, solicitud: PQRSSolicitud, usuario: User,
              producto_id: int, codigo: str) -> PQRSSolicitud:
    """
    Cambia un producto escrito a mano por el del catálogo.

    El nombre NO se recibe: se toma del catálogo a partir del código. Si se
    aceptara escrito, volveríamos al mismo problema que esto viene a resolver.
    """
    if solicitud.estado == "cerrado":
        raise HTTPException(
            status_code=400,
            detail=(
                "No se puede cambiar el producto de una PQRS cerrada. Se "
                "confirma antes de cerrarla."
            ),
        )
    producto = _producto_de(db, solicitud, producto_id)

    catalogo = (
        db.query(ProductoCatalogo)
        .filter(
            ProductoCatalogo.tenant_id == tenant_id,
            ProductoCatalogo.codigo == (codigo or "").strip(),
            ProductoCatalogo.activo.is_(True),
        )
        .first()
    )
    if not catalogo:
        raise HTTPException(
            status_code=404,
            detail=(
                "Ese producto no está en el catálogo. Búscalo de nuevo; si de "
                "verdad no existe, revisa con TIC's que la sincronización con "
                "el ERP esté corriendo."
            ),
        )

    escrito_por_el_cliente = producto.producto_nombre
    producto.producto_codigo = catalogo.codigo
    producto.producto_nombre = catalogo.nombre
    producto.por_confirmar = False

    # Queda qué escribió el cliente: si mucha gente pide el mismo producto
    # con un nombre que no está en el catálogo, eso es una señal sobre el
    # catálogo, no sobre los clientes.
    _anotar(db, solicitud, usuario, "confirmacion_producto", (
        f"Producto confirmado: «{escrito_por_el_cliente}» (escrito por el "
        f"cliente) -> {catalogo.codigo} {catalogo.nombre}."
    ))
    db.commit()
    db.refresh(solicitud)
    return solicitud
