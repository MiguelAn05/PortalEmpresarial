/**
 * Las bodegas donde se recibe el producto de una devolución.
 *
 * **No son los puntos de venta, aunque dos se llamen igual.** «Guayabal» y
 * «La 65» existen en `canales.js` como mostradores donde un cliente radica, y
 * aquí como bodegas donde entra la mercancía que vuelve. Son cosas distintas
 * y las maneja gente distinta.
 *
 * Gemelo de `backend/app/core/bodegas.py`; `tests/bodegas.test.mjs` verifica
 * que las dos listas digan lo mismo — si se separan, la pantalla ofrecería
 * una bodega que el servidor rechaza, y la persona no podría radicar.
 */

export const BODEGAS = [
  'Guayabal',
  'La 65',
]

/** `null` es válido: no toda solicitud pasa por bodega. */
export function esBodegaValida(bodega) {
  const limpio = (bodega ?? '').trim()
  return limpio === '' || BODEGAS.includes(limpio)
}

/**
 * En qué áreas tiene sentido OFRECER el campo de bodega en Admin.
 *
 * Es una ayuda de pantalla y **nada más**: quien confirma una devolución lo
 * decide la capacidad `notas_credito.confirmar_producto`, que se otorga en
 * Administración › Capacidades, y el servidor no mira el área para esto. Esta
 * lista existe solo para no poner un selector de bodega en las cuarenta filas
 * de usuarios cuando le sirve a dos personas.
 *
 * Si alguien ya tiene bodega asignada, el selector se muestra igual aunque su
 * área no esté aquí — si no, no habría forma de quitársela.
 */
export const AREAS_CON_BODEGA = ['Logística', 'Producción']
