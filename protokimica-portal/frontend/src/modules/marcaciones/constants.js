/**
 * Lo que la pantalla de Marcaciones sabe decir con palabras.
 *
 * Las reglas —quién llegó tarde, quién es ausente— NO están aquí: las calcula
 * el servidor (`backend/app/modules/marcaciones/evaluacion.py`) y llegan hechas.
 * Esto solo da nombre, tono y orden a lo que llega. Las claves son las del
 * backend (`constants.py`) y no cambian nunca: van en enlaces y en el CSV.
 */

/** Dónde está la persona ahora. `tono` es el punto que acompaña al texto. */
export const PRESENCIAS = {
  adentro: { label: 'En la empresa', tono: 'positivo' },
  en_descanso: { label: 'En descanso', tono: 'alerta' },
  salio: { label: 'Ya salió', tono: 'neutro' },
  pendiente: { label: 'Aún no marca', tono: 'neutro' },
  ausente: { label: 'Ausente', tono: 'negativo' },
  justificado: { label: 'Justificado', tono: 'neutro' },
  sin_turno: { label: 'Sin turno hoy', tono: 'neutro' },
}

export const NOVEDADES = {
  llegada_tarde: 'Llegada tarde',
  salida_anticipada: 'Salida anticipada',
  ausencia: 'Ausencia',
  exceso_almuerzo: 'Exceso de almuerzo',
  exceso_break: 'Exceso de break',
  turno_por_confirmar: 'Turno por confirmar',
}

/** Qué significa cada botón del reloj. */
export const ESTADOS_MARCA = {
  0: 'Entrada',
  1: 'Salida',
  2: 'Sale a descanso',
  3: 'Regresa de descanso',
  4: 'Extra: entrada',
  5: 'Extra: salida',
}

/** Las vistas que se eligen con las tarjetas y con el desplegable. */
export const VISTAS = [
  { clave: 'todos', label: 'Todos' },
  { clave: 'adentro', label: 'En la empresa' },
  { clave: 'en_descanso', label: 'En descanso' },
  { clave: 'salio', label: 'Ya salieron' },
  { clave: 'pendiente', label: 'Aún no marcan' },
  { clave: 'ausente', label: 'Ausentes' },
  { clave: 'novedades', label: 'Con novedades' },
]

/** Cada cuánto se vuelve a pedir el día de hoy. */
export const SEGUNDOS_ACTUALIZACION = 30

export const FILTROS_MARCACIONES = { fecha: '', area: '', lider: '', vista: 'todos', buscar: '', persona: '' }
