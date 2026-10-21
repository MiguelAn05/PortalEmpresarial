/**
 * El informe gerencial de Master Planner: lo poco que decide la pantalla.
 *
 * Los números llegan contados del servidor (`master_planner/informe.py`),
 * porcentajes y diferencias contra el periodo anterior incluidos: restarlos
 * aquí es la cuenta que un día deja de coincidir con el reporte. Aquí solo
 * están los periodos que se ofrecen y cómo se dicen las cifras.
 */
import { isoLocal } from '../../core/informe.js'

/**
 * Los periodos de un clic, en fechas locales. Mes y trimestre son los de
 * calendario —«el tercer trimestre» es julio a septiembre, no «los últimos
 * noventa días»—, que es como se presentan en un comité. Los que están en
 * curso llegan hasta hoy; los cerrados, hasta su último día.
 */
export function periodosInforme(hoy = new Date()) {
  const a = hoy.getFullYear()
  const m = hoy.getMonth()
  const t = Math.floor(m / 3) * 3          // primer mes del trimestre en curso
  return [
    { clave: 'mes', etiqueta: 'Este mes', desde: isoLocal(new Date(a, m, 1)), hasta: isoLocal(hoy) },
    { clave: 'mes_anterior', etiqueta: 'Mes anterior', desde: isoLocal(new Date(a, m - 1, 1)), hasta: isoLocal(new Date(a, m, 0)) },
    { clave: 'trimestre', etiqueta: 'Este trimestre', desde: isoLocal(new Date(a, t, 1)), hasta: isoLocal(hoy) },
    { clave: 'trimestre_anterior', etiqueta: 'Trimestre anterior', desde: isoLocal(new Date(a, t - 3, 1)), hasta: isoLocal(new Date(a, t, 0)) },
    { clave: 'anio', etiqueta: 'Este año', desde: isoLocal(new Date(a, 0, 1)), hasta: isoLocal(hoy) },
  ]
}

/**
 * Qué tan bien se cumplió, con su etiqueta: nunca solo el color. Los mismos
 * cortes del informe de PQRS, para que «por mejorar» signifique lo mismo en
 * los dos informes que se presentan juntos.
 */
export function estadoCumplimiento(pct) {
  if (pct == null) return { tono: 'neutro', etiqueta: 'Nada que juzgar todavía' }
  if (pct >= 90) return { tono: 'positivo', etiqueta: 'Al día' }
  if (pct >= 75) return { tono: 'alerta', etiqueta: 'Por mejorar' }
  return { tono: 'negativo', etiqueta: 'Bajo' }
}

const coma = (n) => Number(n).toLocaleString('es-CO', { maximumFractionDigits: 1 })

/**
 * «+5,2 puntos frente a septiembre». La diferencia ya viene hecha del
 * servidor (`variacion_puntos`); aquí solo se dice, y se pinta de verde
 * cuando subir es bueno.
 */
export function textoPuntos(variacion, etiquetaAnterior, { subirEsBueno = true } = {}) {
  if (variacion == null) return null
  const contra = (etiquetaAnterior || 'el periodo anterior').toLowerCase()
  if (variacion === 0) return { texto: `Igual que en ${contra}`, tono: 'neutro' }
  const sube = variacion > 0
  return {
    texto: `${sube ? '+' : '−'}${coma(Math.abs(variacion))} puntos frente a ${contra}`,
    tono: sube === subirEsBueno ? 'positivo' : 'negativo',
  }
}

/** «Antes 4»: el conteo del periodo anterior, o nada si no hay con qué comparar. */
export function textoAntes(anterior, etiquetaAnterior) {
  if (anterior == null) return null
  return `${anterior} en ${(etiquetaAnterior || 'el periodo anterior').toLowerCase()}`
}

/** El semáforo de un proyecto: el tono de cada salud que manda el servidor. */
export const TONO_SALUD = { rojo: 'negativo', amarillo: 'alerta', verde: 'positivo', sin_datos: 'neutro' }

/** Cómo terminaron los compromisos del periodo, como tramos de una barra. */
export function tramosCompromisos(c) {
  if (!c) return []
  return [
    { clave: 'a_tiempo', etiqueta: 'Entregadas a tiempo', n: c.a_tiempo, tono: 'positivo' },
    { clave: 'tarde', etiqueta: 'Entregadas tarde', n: c.tarde, tono: 'alerta' },
    { clave: 'vencidas', etiqueta: 'Vencidas sin entregar', n: c.vencidas, tono: 'negativo' },
    { clave: 'pendientes', etiqueta: 'Vencen más adelante', n: c.pendientes, tono: 'neutro' },
  ]
}

/** «Cumplió 8 de 10» o «—»: el porcentaje nunca va sin su base. */
export function textoBase(c) {
  if (!c || !c.juzgadas) return 'Sin compromisos para juzgar'
  return `${c.a_tiempo} de ${c.juzgadas} a tiempo`
}

/** ¿Hay algo que mostrar? Un periodo sin proyectos ni compromisos se dice, no se dibuja vacío. */
export function informeVacio(inf) {
  if (!inf) return true
  return !inf.resumen.proyectos_activos && !inf.cumplimiento.total && !inf.entregas.total
    && !inf.cierres.length && !inf.actividades.esperados
}
