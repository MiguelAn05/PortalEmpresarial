/**
 * El informe gerencial de PQRS: lo que la pantalla necesita decidir sola.
 *
 * Los números NO se calculan aquí: llegan del servidor ya contados, con su
 * porcentaje redondeado una vez (`backend/app/modules/pqrs/informe.py`).
 * Aquí solo están los periodos que se ofrecen y cómo se dicen las cifras.
 */

const iso = (d) => {
  const mes = String(d.getMonth() + 1).padStart(2, '0')
  const dia = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${mes}-${dia}`
}

/**
 * Los periodos de un clic, en fechas locales (nunca `toISOString`, que da la
 * fecha de UTC y a las 7 p. m. ya es mañana). «Este mes» llega hasta hoy;
 * los cerrados, hasta su último día.
 */
export function periodosRapidos(hoy = new Date()) {
  const a = hoy.getFullYear()
  const m = hoy.getMonth()
  return [
    { clave: 'mes', etiqueta: 'Este mes', desde: iso(new Date(a, m, 1)), hasta: iso(hoy) },
    { clave: 'anterior', etiqueta: 'Mes anterior', desde: iso(new Date(a, m - 1, 1)), hasta: iso(new Date(a, m, 0)) },
    { clave: 'trimestre', etiqueta: 'Últimos 3 meses', desde: iso(new Date(a, m - 2, 1)), hasta: iso(hoy) },
    { clave: 'anio', etiqueta: 'Este año', desde: iso(new Date(a, 0, 1)), hasta: iso(hoy) },
  ]
}

/** «12 más que septiembre (+40%)», o lo que corresponda. Null si no hay con qué. */
export function textoVariacion(resumen, etiquetaAnterior) {
  if (!resumen) return null
  const { total, total_anterior: antes, variacion_pct: pct } = resumen
  const contra = (etiquetaAnterior || 'el periodo anterior').toLowerCase()
  if (!antes && !total) return null
  if (!antes) return { texto: `Sin PQRS en ${contra}`, tono: 'neutro' }
  const diferencia = total - antes
  if (diferencia === 0) return { texto: `Igual que en ${contra}`, tono: 'neutro' }
  const signo = diferencia > 0 ? '+' : '−'
  return {
    texto: `${signo}${Math.abs(pct)}% frente a ${contra} (${antes})`,
    // Más PQRS es peor noticia: no se pinta de verde que suban.
    tono: diferencia > 0 ? 'negativo' : 'positivo',
  }
}

/** El estado de «respondidas a tiempo», con su etiqueta. Nunca solo color. */
export function estadoATiempo(pct) {
  if (pct == null) return { tono: 'neutro', etiqueta: 'Sin respuestas aún' }
  if (pct >= 90) return { tono: 'positivo', etiqueta: 'En término' }
  if (pct >= 75) return { tono: 'alerta', etiqueta: 'Por mejorar' }
  return { tono: 'negativo', etiqueta: 'Fuera de término' }
}

/**
 * Las primeras `max` filas y el resto sumado en «Otros», para que una lista
 * larga de causas no ocupe dos hojas del PDF. El porcentaje de «Otros» es la
 * suma de los que ya mandó el servidor, no una cuenta nueva.
 */
export function conOtros(filas, max = 8) {
  if (!filas || filas.length <= max) return filas || []
  const resto = filas.slice(max - 1)
  const n = resto.reduce((s, f) => s + f.n, 0)
  const pct = Math.round(resto.reduce((s, f) => s + (f.pct || 0), 0) * 10) / 10
  return [...filas.slice(0, max - 1), { clave: '__otros__', etiqueta: `Otros (${resto.length})`, n, pct }]
}

/** Marcas del eje de la tendencia: 0, la mitad y el máximo, en enteros. */
export function marcasEje(maximo) {
  if (!maximo) return [0]
  const tope = Math.max(1, Math.ceil(maximo))
  const medio = Math.round(tope / 2)
  return [...new Set([0, medio, tope])]
}
