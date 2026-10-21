/**
 * Lo que comparten los informes gerenciales (PQRS y Master Planner) del lado
 * de la pantalla. Vivía en `pqrs/informe.js`; el segundo informe lo habría
 * copiado, y dos copias de «cómo se agrupa en Otros» terminan sumando
 * distinto.
 *
 * Los números NO se calculan aquí: llegan del servidor ya contados.
 */

/** Una fecha como `YYYY-MM-DD` en hora LOCAL (nunca `toISOString`, que da la de UTC). */
export const isoLocal = (d) => {
  const mes = String(d.getMonth() + 1).padStart(2, '0')
  const dia = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${mes}-${dia}`
}

/**
 * Las primeras `max` filas y el resto sumado en «Otros», para que una lista
 * larga no ocupe dos hojas del PDF. El porcentaje de «Otros» es la suma de
 * los que ya mandó el servidor, no una cuenta nueva.
 */
export function conOtros(filas, max = 8) {
  if (!filas || filas.length <= max) return filas || []
  const resto = filas.slice(max - 1)
  const n = resto.reduce((s, f) => s + f.n, 0)
  const pct = Math.round(resto.reduce((s, f) => s + (f.pct || 0), 0) * 10) / 10
  const otros = { clave: '__otros__', etiqueta: `Otros (${resto.length})`, n, pct }
  // El promedio por día hábil de «Otros» es la suma de los suyos, como el %.
  if (resto.some(f => f.por_dia_habil != null)) {
    otros.por_dia_habil = Math.round(resto.reduce((s, f) => s + (f.por_dia_habil || 0), 0) * 100) / 100
  }
  return [...filas.slice(0, max - 1), otros]
}

/**
 * Un promedio como se lee: «1,6», «0,05». Lo calcula el servidor; aquí solo
 * se escribe con coma y sin ceros de más. Sin valor: «—».
 */
export function formatoPromedio(valor) {
  if (valor == null) return '—'
  return Number(valor).toLocaleString('es-CO', { maximumFractionDigits: 2 })
}

/** Marcas del eje de una serie: 0, la mitad y el máximo, en enteros. */
export function marcasEje(maximo) {
  if (!maximo) return [0]
  const tope = Math.max(1, Math.ceil(maximo))
  const medio = Math.round(tope / 2)
  return [...new Set([0, medio, tope])]
}
