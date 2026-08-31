/**
 * Los canales de atención por los que entra una PQRS. Fuente única del
 * frontend.
 *
 * Gemelo de `backend/app/core/canales.py`; `tests/canales.test.mjs` verifica
 * que digan lo mismo. Antes esta lista estaba copiada en cuatro sitios y ya
 * había empezado a separarse: el formulario de felicitaciones ofrecía
 * «Llamada telefónica» donde el resto del portal dice «Línea telefónica», así
 * que la misma llamada caía en dos canales y el reporte las contaba aparte.
 *
 * **La escritura exacta importa.** El canal se compara como texto en el
 * servidor para decidir el prefijo del código de seguimiento. Cambiar una
 * tilde deja a ese punto de venta sin su consecutivo propio, en silencio.
 */

export const CANALES = [
  'Venta institucional',
  'WhatsApp',
  'Punto de venta Centro',
  'Punto de venta Belén',
  'Punto de venta Guayabal',
  'Punto de venta La 65',
  'Punto de venta Cristo Rey',
  'Punto de venta Itagüí',
  'Línea telefónica',
]

/**
 * Los canales con consecutivo propio, y con qué prefijo.
 *
 * El prefijo es además el código del QR: `/q/PVG` abre el formulario ya
 * marcado como Guayabal. No se cambia a la ligera — un letrero impreso y
 * pegado en una sede no se actualiza solo.
 */
export const PREFIJOS_POR_CANAL = {
  'Punto de venta Centro': 'PVC',
  'Punto de venta Belén': 'PVB',
  'Punto de venta Guayabal': 'PVG',
  'Punto de venta La 65': 'PV65',
  'Punto de venta Cristo Rey': 'PVCR',
  'Punto de venta Itagüí': 'PVI',
  'Venta institucional': 'VI',
}

export const EQUIVALENCIAS_HISTORICAS = {
  'Llamada telefónica': 'Línea telefónica',
}

/** Traduce un nombre viejo al actual. Devuelve null si viene vacío. */
export function normalizarCanal(canal) {
  if (!canal || !canal.trim()) return null
  const limpio = canal.trim()
  return EQUIVALENCIAS_HISTORICAS[limpio] ?? limpio
}

/** El prefijo del código de seguimiento, o null si el canal no tiene uno. */
export function prefijoDe(canal) {
  return PREFIJOS_POR_CANAL[(canal ?? '').trim()] ?? null
}

/**
 * El canal al que apunta un código de QR (`PVG` → «Punto de venta Guayabal»).
 *
 * Sin distinguir mayúsculas: el código va impreso en un letrero y alguien lo
 * va a teclear a mano tarde o temprano.
 */
export function canalPorCodigo(codigo) {
  if (!codigo) return null
  const buscado = codigo.trim().toUpperCase()
  return Object.keys(PREFIJOS_POR_CANAL)
    .find(canal => PREFIJOS_POR_CANAL[canal] === buscado) ?? null
}

/**
 * Los canales que son un punto de venta físico: los que llevan un QR pegado
 * en el mostrador. «Venta institucional» tiene prefijo pero no es una sede
 * donde alguien pueda escanear algo.
 */
export function puntosDeVenta() {
  return CANALES.filter(c => c.startsWith('Punto de venta'))
}

/** Para pintar el filtro por punto de venta a partir del prefijo. */
export function canalesConPrefijo() {
  return Object.entries(PREFIJOS_POR_CANAL).map(([label, prefijo]) => ({ prefijo, label }))
}
