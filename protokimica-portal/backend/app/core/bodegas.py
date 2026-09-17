"""
Las bodegas donde se recibe el producto de una devolución.

**No son los puntos de venta, aunque dos se llamen igual.** «Guayabal» y «La
65» existen en `canales.py` como mostradores donde un cliente radica, y aquí
como bodegas donde entra la mercancía que vuelve. Son cosas distintas y las
maneja gente distinta: si compartieran lista, un día una devolución
institucional le caería al almacén de Guayabal en vez de a su bodega.

Se usan en las notas crédito de Ventas Institucionales: cuando el motivo
implica producto, antes de que nadie apruebe nada alguien de la bodega tiene
que confirmar que llegó y en qué estado. Quién es ese alguien sale de la
capacidad `notas_credito.confirmar_producto` más el campo `users.bodega`,
igual que el punto de venta se resuelve con el prefijo del canal.

Gemelo en `frontend/src/core/bodegas.js`; una prueba verifica que coincidan.
"""

BODEGAS = [
    "Guayabal",
    "La 65",
]


def normalizar(bodega: str | None) -> str | None:
    """Limpia el texto. `None` es válido: no toda solicitud pasa por bodega."""
    limpio = (bodega or "").strip()
    return limpio or None


def es_valida(bodega: str | None) -> bool:
    """`None` pasa: una solicitud sin producto no tiene bodega que confirmar."""
    return bodega is None or bodega in BODEGAS
