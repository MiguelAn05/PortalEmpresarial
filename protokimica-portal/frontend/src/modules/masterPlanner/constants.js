// Estados reales de una Tarea en el backend (mp_tareas.estado).
// Antes el mock usaba "Planeación/En ejecución/En riesgo/Pausado/Finalizado"
// como si fueran estados de tablero; ahora el riesgo se documenta como texto
// libre por tarea (campo `riesgos`), no como una columna del Kanban.
export const ESTADOS_TAREA = {
  pendiente:  { label: 'Pendiente',   color: 'bg-blue-100 text-blue-700',    dot: 'bg-blue-400',    barra: '#60A5FA' },
  en_proceso: { label: 'En proceso',  color: 'bg-emerald-100 text-emerald-700', dot: 'bg-emerald-400', barra: '#34D399' },
  bloqueada:  { label: 'Bloqueada',   color: 'bg-red-100 text-red-700',      dot: 'bg-red-400',     barra: '#F87171' },
  completada: { label: 'Completada',  color: 'bg-gray-200 text-gray-700',    dot: 'bg-gray-400',    barra: '#9CA3AF' },
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

// Las áreas viven en un solo sitio: src/core/areas.js
export { AREAS } from '../../core/areas.js'

export const MESES = [
  'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
  'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
]

// La semana arranca en lunes, como el calendario que se usa en la empresa.
export const DIAS_SEMANA = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']

export function colorAvance(pct) {
  if (pct < 30) return '#EF4444'
  if (pct < 70) return '#F59E0B'
  return '#22C55E'
}

// ── Vencimientos ──────────────────────────────────────────────
// Una tarea "vencida" es la que ya pasó su fecha de fin sin completarse.
// "Por vencer" son los 3 días siguientes: suficiente para reaccionar sin
// que todo el tablero se vuelva amarillo.
export const DIAS_AVISO_VENCIMIENTO = 3

export const ALERTAS = {
  vencida:    { label: 'Vencida',    chip: 'bg-red-100 text-red-700 border-red-200',       borde: 'border-l-4 border-l-red-400',   texto: 'text-red-600' },
  por_vencer: { label: 'Por vencer', chip: 'bg-amber-100 text-amber-700 border-amber-200', borde: 'border-l-4 border-l-amber-400', texto: 'text-amber-600' },
}

export function alertaVencimiento(tarea) {
  if (!tarea?.fecha_fin || tarea.estado === 'completada') return null
  const fin = new Date(tarea.fecha_fin)
  const ahora = new Date()
  if (fin < ahora) return 'vencida'
  const dias = (fin - ahora) / 86400000
  return dias <= DIAS_AVISO_VENCIMIENTO ? 'por_vencer' : null
}

export function diasRestantes(fechaFin) {
  if (!fechaFin) return null
  return Math.ceil((new Date(fechaFin) - new Date()) / 86400000)
}

// ── Roles y permisos ──────────────────────────────────────────
// El backend es la autoridad: estas funciones solo sirven para no mostrar
// botones que de todas formas darían 403.
export const ROLES = {
  admin:    { label: 'Administrador' },
  gerencia: { label: 'Gerencia / Dirección' },
  lider:    { label: 'Líder de área' },
  agente:   { label: 'Agente' },
  lectura:  { label: 'Solo lectura' },
}

/** Puede crear, editar o borrar proyectos, tareas y presupuesto. */
export function puedeEditar(usuario) {
  return !['lectura', 'gerencia'].includes(usuario?.rol)
}

/** Puede escribir actualizaciones de avance y comentarios. */
export function puedeComentar(usuario) {
  return usuario?.rol !== 'lectura'
}

/** Gerencia comenta, pero no mueve el % de avance: eso es planeación. */
export function puedeReportarAvance(usuario) {
  return puedeEditar(usuario)
}

// ── Aprobación y pago del presupuesto ─────────────────────────
export const AREA_APRUEBA_PAGOS = 'Administración'
export const AREA_REGISTRA_PAGOS = 'Tesorería'

export function puedeAprobarPagos(usuario) {
  return usuario?.rol === 'admin' || usuario?.area === AREA_APRUEBA_PAGOS
}

export function puedeRegistrarPagos(usuario) {
  return usuario?.rol === 'admin' || usuario?.area === AREA_REGISTRA_PAGOS
}

/** Estado de un ítem en el recorrido planeado → aprobado → pagado. */
export const ESTADOS_PAGO = {
  por_aprobar: { label: 'Por aprobar', chip: 'bg-gray-100 text-gray-600 border-gray-200', punto: '#9BACC8' },
  aprobado:    { label: 'Aprobado',    chip: 'bg-blue-50 text-blue-700 border-blue-200',  punto: '#1A4FA0' },
  parcial:     { label: 'Pago parcial', chip: 'bg-amber-50 text-amber-800 border-amber-200', punto: '#F5A800' },
  pagado:      { label: 'Pagado',      chip: 'bg-green-50 text-green-700 border-green-200', punto: '#2E9E6B' },
}

// ── Semáforo de proyectos ─────────────────────────────────────
// Lo calcula el backend comparando avance real contra plazo consumido.
export const SALUD = {
  verde:     { label: 'En tiempo',  color: 'bg-green-100 text-green-700',  punto: 'bg-green-500',  texto: 'text-green-600' },
  amarillo:  { label: 'Atrasado',   color: 'bg-amber-100 text-amber-700',  punto: 'bg-amber-500',  texto: 'text-amber-600' },
  rojo:      { label: 'En riesgo',  color: 'bg-red-100 text-red-700',      punto: 'bg-red-500',    texto: 'text-red-600' },
  cerrado:   { label: 'Cerrado',    color: 'bg-gray-200 text-gray-600',    punto: 'bg-gray-400',   texto: 'text-gray-500' },
  sin_datos: { label: 'Sin fechas', color: 'bg-gray-100 text-gray-500',    punto: 'bg-gray-300',   texto: 'text-gray-400' },
}

/**
 * Traduce a lenguaje llano la comparación entre avance y plazo consumido.
 *
 * La idea: si un proyecto va por el 50% y solo ha transcurrido el 6% de su
 * tiempo, va adelantado. Al revés, va atrasado. Mostrar los dos porcentajes
 * crudos obliga a hacer esa resta mentalmente, así que aquí ya se hace y se
 * dice el resultado con palabras.
 */
export function lecturaAvancePlazo(avance, plazo) {
  if (plazo === null || plazo === undefined) {
    return { texto: `${avance}% de avance`, detalle: 'Sin fechas para comparar', tono: 'neutro' }
  }

  const diferencia = Math.round(avance - plazo)
  const comparacion = `Debería ir por el ${Math.round(plazo)}% y va en el ${Math.round(avance)}%`

  if (plazo >= 100 && avance < 100) {
    return {
      texto: 'Plazo vencido',
      detalle: `La fecha de entrega ya pasó y va en el ${Math.round(avance)}%`,
      tono: 'malo',
    }
  }
  if (diferencia >= 10) {
    return { texto: `Adelantado ${diferencia} puntos`, detalle: comparacion, tono: 'bueno' }
  }
  if (diferencia >= -10) {
    return { texto: 'Al día', detalle: comparacion, tono: 'bueno' }
  }
  return {
    texto: `Atrasado ${Math.abs(diferencia)} puntos`,
    detalle: comparacion,
    tono: diferencia >= -25 ? 'regular' : 'malo',
  }
}

export const TONOS = {
  bueno:   'text-green-600',
  regular: 'text-amber-600',
  malo:    'text-red-600',
  neutro:  'text-[#9BACC8]',
}

// ── Historial de cambios ──────────────────────────────────────
// Cómo se lee cada `campo` que devuelve el backend. `tipo` decide el formato
// del valor: 'fecha' lo pinta como fecha, 'texto_largo' solo dice que cambió.
export const CAMPOS_HISTORIAL = {
  // Proyecto
  nombre:             { label: 'Nombre del proyecto', tipo: 'texto' },
  estado:             { label: 'Estado',              tipo: 'estado' },
  prioridad:          { label: 'Prioridad',           tipo: 'prioridad' },
  area:               { label: 'Área',                tipo: 'texto' },
  lider_id:           { label: 'Líder',               tipo: 'texto' },
  archivado:          { label: 'Archivado',           tipo: 'si_no' },
  fecha_inicio:       { label: 'Fecha de inicio',     tipo: 'fecha' },
  fecha_fin_estimada: { label: 'Fecha de entrega',    tipo: 'fecha' },
  fecha_fin_real:     { label: 'Fecha de cierre real', tipo: 'fecha' },
  objetivo:           { label: 'Objetivo',            tipo: 'texto_largo' },
  alcance:            { label: 'Alcance',             tipo: 'texto_largo' },
  // Tarea
  titulo:             { label: 'Título',              tipo: 'texto' },
  asignado_a:         { label: 'Responsable',         tipo: 'texto' },
  avance_pct:         { label: 'Avance',              tipo: 'porcentaje' },
  fecha_fin:          { label: 'Fecha de fin',        tipo: 'fecha' },
  descripcion:        { label: 'Descripción',         tipo: 'texto_largo' },
  riesgos:            { label: 'Riesgos',             tipo: 'texto_largo' },
  // Eventos de presupuesto
  presupuesto_agregado:  { label: 'Ítem de presupuesto agregado',  tipo: 'evento' },
  presupuesto_eliminado: { label: 'Ítem de presupuesto eliminado', tipo: 'evento' },
  presupuesto_ejecutado: { label: 'Ejecución de presupuesto',      tipo: 'evento' },
}

export function etiquetaCampo(campo) {
  return CAMPOS_HISTORIAL[campo]?.label || campo
}

/** Convierte el valor crudo del historial en algo legible según el tipo del campo. */
export function valorHistorial(campo, valor) {
  if (valor === null || valor === undefined || valor === '') return 'sin definir'
  const tipo = CAMPOS_HISTORIAL[campo]?.tipo
  if (tipo === 'fecha') return formatFechaHora(valor)
  if (tipo === 'estado') return ESTADOS_TAREA[valor]?.label || ESTADOS_PROYECTO[valor]?.label || valor
  if (tipo === 'prioridad') return PRIORIDADES[valor]?.label || valor
  if (tipo === 'porcentaje') return `${valor}%`
  if (tipo === 'si_no') return valor === 'si' ? 'Sí' : 'No'
  return valor
}

/**
 * Para un cambio de fecha, cuántos días se corrió. Positivo = se aplazó.
 * Es el dato que a gerencia le interesa de verdad de un cambio de fecha.
 */
export function diasDesplazados(entrada) {
  if (CAMPOS_HISTORIAL[entrada.campo]?.tipo !== 'fecha') return null
  if (!entrada.valor_anterior || !entrada.valor_nuevo) return null
  const antes = new Date(entrada.valor_anterior)
  const despues = new Date(entrada.valor_nuevo)
  if (isNaN(antes) || isNaN(despues)) return null
  return Math.round((despues - antes) / 86400000)
}

// ── Filtrado de tareas ────────────────────────────────────────
// Mismo criterio para el tablero, la tabla, el cronograma y el calendario,
// para que "12 de 30 tareas" signifique lo mismo en todas las vistas.
export const FILTROS_TAREAS_VACIOS = {
  busqueda: "", proyecto_id: "", asignado_a: "", area: "", estado: "", prioridad: "", vencimiento: "",
}

export function filtrarTareas(tareas, filtros) {
  const busqueda = (filtros.busqueda || "").trim().toLowerCase()
  return tareas.filter(t => {
    if (filtros.proyecto_id && String(t.proyecto_id) !== String(filtros.proyecto_id)) return false
    if (filtros.area && t.area !== filtros.area) return false
    if (filtros.estado && t.estado !== filtros.estado) return false
    if (filtros.prioridad && t.prioridad !== filtros.prioridad) return false

    if (filtros.asignado_a) {
      if (filtros.asignado_a === 'sin_asignar') {
        if (t.asignado_a) return false
      } else if (String(t.asignado_a) !== String(filtros.asignado_a)) return false
    }

    if (filtros.vencimiento) {
      const alerta = alertaVencimiento(t)
      if (filtros.vencimiento === 'sin_fecha' && t.fecha_fin) return false
      if (filtros.vencimiento === 'vencida' && alerta !== 'vencida') return false
      if (filtros.vencimiento === 'por_vencer' && alerta !== 'por_vencer') return false
      if (filtros.vencimiento === 'en_riesgo' && !alerta) return false
    }

    if (busqueda) {
      const texto = `${t.titulo} ${t.descripcion || ''} ${t.proyecto_nombre || ''} ${t.asignado_nombre || ''}`.toLowerCase()
      if (!texto.includes(busqueda)) return false
    }
    return true
  })
}

// ── Formato ───────────────────────────────────────────────────
export function formatFecha(f, opts = { day: '2-digit', month: 'short', year: 'numeric' }) {
  if (!f) return '—'
  return new Date(f).toLocaleDateString('es-CO', opts)
}

export function formatHora(f) {
  if (!f) return ''
  return new Date(f).toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit', hour12: false })
}

/** Muestra la hora solo si la tarea realmente tiene una (no 00:00). */
export function formatFechaHora(f) {
  if (!f) return '—'
  const d = new Date(f)
  const fecha = formatFecha(f)
  return tieneHora(f) ? `${fecha}, ${formatHora(d)}` : fecha
}

export function tieneHora(f) {
  if (!f) return false
  const d = new Date(f)
  return d.getHours() !== 0 || d.getMinutes() !== 0
}

export function formatMoneda(v) {
  if (v === null || v === undefined) return '—'
  return Number(v).toLocaleString('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 })
}

// ── Conversión para <input type="datetime-local"> ──────────────
// El input trabaja en hora local sin zona ("2026-07-31T14:30") y el backend
// guarda timestamps con zona. Estas dos funciones son el puente: sin ellas
// la hora se corre según la diferencia horaria del servidor.
export function isoADatetimeLocal(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`
}

export function datetimeLocalAIso(valor) {
  if (!valor) return null
  const d = new Date(valor)
  return isNaN(d) ? null : d.toISOString()
}

// Las fechas de un proyecto se manejan a nivel de día (no de hora).
export function isoADateInput(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

// ── Utilidades de calendario ──────────────────────────────────
/** Medianoche local del día de `f`, para comparar días sin que estorbe la hora. */
export function inicioDia(f) {
  const d = new Date(f)
  d.setHours(0, 0, 0, 0)
  return d
}

export function mismoDia(a, b) {
  return inicioDia(a).getTime() === inicioDia(b).getTime()
}

export function sumarDias(f, n) {
  const d = new Date(f)
  d.setDate(d.getDate() + n)
  return d
}

/** Lunes de la semana a la que pertenece `f`. */
export function lunesDeLaSemana(f) {
  const d = inicioDia(f)
  const diaSemana = (d.getDay() + 6) % 7 // 0 = lunes
  return sumarDias(d, -diaSemana)
}

/**
 * Rejilla de 6 semanas (42 días) que contiene el mes de `fecha`, empezando
 * en lunes — es la forma clásica de dibujar un mes sin que salte el alto
 * de la tabla entre un mes y otro.
 */
export function rejillaMes(fecha) {
  const primero = new Date(fecha.getFullYear(), fecha.getMonth(), 1)
  const inicio = lunesDeLaSemana(primero)
  return Array.from({ length: 42 }, (_, i) => sumarDias(inicio, i))
}

/**
 * Rango [inicio, fin] que ocupa una tarea en el calendario. Si solo tiene
 * una de las dos fechas, ocupa ese único día.
 */
export function rangoTarea(tarea) {
  const ini = tarea.fecha_inicio ? inicioDia(tarea.fecha_inicio) : null
  const fin = tarea.fecha_fin ? inicioDia(tarea.fecha_fin) : null
  if (!ini && !fin) return null
  const desde = ini || fin
  const hasta = fin || ini
  return hasta < desde ? { desde: hasta, hasta: desde } : { desde, hasta }
}

export function tareaOcupaDia(tarea, dia) {
  const rango = rangoTarea(tarea)
  if (!rango) return false
  const d = inicioDia(dia)
  return d >= rango.desde && d <= rango.hasta
}
