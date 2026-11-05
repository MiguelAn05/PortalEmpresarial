/**
 * La lógica de la pantalla de Marcaciones que se puede probar sin navegador.
 *
 * Filtrar lo que ya llegó, formatear y armar las fechas del informe: nada de
 * reglas de asistencia (eso lo calcula el servidor).
 */
import { ESTADOS_MARCA, PRESENCIAS, VISTAS } from './constants.js'
import { isoLocal } from '../../core/informe.js'

const sinTildes = (t) => String(t ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()

/** ¿Entra en la vista elegida? Es la MISMA regla para la tarjeta y para la lista. */
export function coincideConVista(persona, vista) {
  if (!vista || vista === 'todos') return true
  if (vista === 'novedades') return persona.novedades.length > 0
  return persona.presencia === vista
}

/** Vista, área, líder y buscador. El líder se resuelve por las áreas que mandó el servidor. */
export function filtrarPersonas(personas, { vista = 'todos', area = '', lider = '', buscar = '' } = {}, porLider = []) {
  const areasDelLider = lider ? porLider.find(l => l.lider === lider)?.areas : null
  const texto = sinTildes(buscar).trim()
  return personas.filter(p => {
    if (!coincideConVista(p, vista)) return false
    if (area && (p.area || 'Sin área') !== area) return false
    if (areasDelLider && !areasDelLider.includes(p.area || 'Sin área')) return false
    if (texto && !sinTildes(`${p.nombre} ${p.emp_code}`).includes(texto)) return false
    return true
  })
}

export function contarPorVista(personas) {
  return Object.fromEntries(VISTAS.map(v => [v.clave, personas.filter(p => coincideConVista(p, v.clave)).length]))
}

export const horaOGuion = (h) => h || '—'

/** «12:40 · Regresa de descanso». */
export function textoUltimaMarca(ultima) {
  if (!ultima) return '—'
  return `${ultima.hora} · ${ESTADOS_MARCA[ultima.estado] ?? ultima.estado}`
}

export const etiquetaPresencia = (clave) => PRESENCIAS[clave]?.label ?? clave

/**
 * El aviso de datos atrasados, o null. Un tablero «en vivo» que dejó de
 * estarlo y no lo dice es peor que no tenerlo. Solo se avisa al mirar HOY.
 */
export function avisoDeAtraso(estado, esHoy) {
  if (!esHoy || !estado) return null
  if (estado.nunca) return 'Todavía no ha llegado ninguna marcación del reloj. Cuando el script del servidor de ZKBio empiece a enviar, aparecerán aquí.'
  if (!estado.atrasado) return null
  const m = estado.minutos_sin_datos
  const hace = m >= 120 ? `${Math.floor(m / 60)} horas` : `${m} minutos`
  const error = estado.ultimo_error ? ` Último error del envío: ${estado.ultimo_error}` : ''
  return `Los datos pueden estar atrasados: el reloj no envía desde hace ${hace}.${error}`
}

/** Mover una fecha `YYYY-MM-DD` `dias` días, sin pasar por UTC. */
export function moverDia(fecha, dias) {
  const [a, m, d] = fecha.split('-').map(Number)
  return isoLocal(new Date(a, m - 1, d + dias))
}

/** Los periodos rápidos del informe, con la fecha de quien mira. */
export function periodosRapidos(ahora = new Date()) {
  const hoy = new Date(ahora.getFullYear(), ahora.getMonth(), ahora.getDate())
  const dia = hoy.getDay() === 0 ? 7 : hoy.getDay()
  const lunes = new Date(hoy.getFullYear(), hoy.getMonth(), hoy.getDate() - (dia - 1))
  return [
    { clave: 'hoy', etiqueta: 'Hoy', desde: isoLocal(hoy), hasta: isoLocal(hoy) },
    { clave: 'semana', etiqueta: 'Esta semana', desde: isoLocal(lunes), hasta: isoLocal(hoy) },
    { clave: 'mes', etiqueta: 'Este mes', desde: isoLocal(new Date(hoy.getFullYear(), hoy.getMonth(), 1)), hasta: isoLocal(hoy) },
    { clave: 'mes_pasado', etiqueta: 'Mes pasado',
      desde: isoLocal(new Date(hoy.getFullYear(), hoy.getMonth() - 1, 1)),
      hasta: isoLocal(new Date(hoy.getFullYear(), hoy.getMonth(), 0)) },
  ]
}

/** Las novedades del informe como filas para `Barras` (n y %). */
export function filasDeNovedades(totales, etiquetas) {
  const total = totales.total_novedades || 0
  return Object.entries(totales.novedades || {})
    .filter(([, n]) => n > 0)
    .map(([clave, n]) => ({ clave, etiqueta: etiquetas[clave] ?? clave, n, pct: total ? Math.round((n / total) * 1000) / 10 : 0 }))
    .sort((a, b) => b.n - a.n)
}
