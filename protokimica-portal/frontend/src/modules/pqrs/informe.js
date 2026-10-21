/**
 * El informe gerencial de PQRS: lo que la pantalla necesita decidir sola.
 *
 * Los números NO se calculan aquí: llegan del servidor ya contados, con su
 * porcentaje redondeado una vez (`backend/app/modules/pqrs/informe.py`).
 * Aquí solo están los periodos que se ofrecen y cómo se dicen las cifras.
 * Lo que comparte con el informe de Master Planner vive en `core/informe.js`
 * y se reexporta desde aquí.
 */
import { isoLocal as iso } from '../../core/informe.js'

export { conOtros, formatoPromedio, marcasEje } from '../../core/informe.js'

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
