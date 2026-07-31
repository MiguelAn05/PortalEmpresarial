// Estados reales de una Tarea en el backend (mp_tareas.estado).
// Antes el mock usaba "Planeación/En ejecución/En riesgo/Pausado/Finalizado"
// como si fueran estados de tablero; ahora el riesgo se documenta como texto
// libre por tarea (campo `riesgos`), no como una columna del Kanban.
export const ESTADOS_TAREA = {
  pendiente:  { label: 'Pendiente',   color: 'bg-blue-100 text-blue-700',    dot: 'bg-blue-400' },
  en_proceso: { label: 'En proceso',  color: 'bg-emerald-100 text-emerald-700', dot: 'bg-emerald-400' },
  bloqueada:  { label: 'Bloqueada',   color: 'bg-red-100 text-red-700',      dot: 'bg-red-400' },
  completada: { label: 'Completada',  color: 'bg-gray-200 text-gray-700',    dot: 'bg-gray-400' },
}

export const ESTADOS_PROYECTO = {
  planeacion:   { label: 'Planeación',   color: 'bg-blue-100 text-blue-700' },
  en_ejecucion: { label: 'En ejecución', color: 'bg-emerald-100 text-emerald-700' },
  pausado:      { label: 'Pausado',      color: 'bg-yellow-100 text-yellow-700' },
  cerrado:      { label: 'Cerrado',      color: 'bg-gray-200 text-gray-700' },
}

export const PRIORIDADES = {
  baja:    { label: 'Baja',    color: 'bg-green-100 text-green-700'  },
  media:   { label: 'Media',   color: 'bg-yellow-100 text-yellow-700' },
  alta:    { label: 'Alta',    color: 'bg-orange-100 text-orange-700' },
  critica: { label: 'Crítica', color: 'bg-red-100 text-red-700'    },
}

export const AREAS = ['TI', 'Comercial', 'Calidad', 'Logística', 'Servicio al cliente', 'Talento Humano']

export function colorAvance(pct) {
  if (pct < 30) return '#EF4444'
  if (pct < 70) return '#F59E0B'
  return '#22C55E'
}

export function formatFecha(f, opts = { day: '2-digit', month: 'short', year: 'numeric' }) {
  if (!f) return '—'
  return new Date(f).toLocaleDateString('es-CO', opts)
}

export function formatMoneda(v) {
  if (v === null || v === undefined) return '—'
  return Number(v).toLocaleString('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 })
}
