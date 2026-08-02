// ── Semáforo ──────────────────────────────────────────────────
// El ámbar de la marca no alcanza el contraste mínimo sobre fondo claro, así
// que el estado NUNCA se comunica solo con color: cada semáforo lleva punto
// + etiqueta de texto. Es la misma razón por la que hay `label` aquí.
export const SEMAFOROS = {
  verde:     { label: 'Cumple',      punto: '#2E9E6B', chip: 'bg-green-50 text-green-700 border-green-200', texto: 'text-green-700' },
  amarillo:  { label: 'En alerta',   punto: '#F5A800', chip: 'bg-amber-50 text-amber-800 border-amber-200', texto: 'text-amber-800' },
  rojo:      { label: 'No cumple',   punto: '#D93B3B', chip: 'bg-red-50 text-red-700 border-red-200',       texto: 'text-red-700' },
  sin_datos: { label: 'Sin dato',    punto: '#C3CFE2', chip: 'bg-gray-50 text-gray-500 border-gray-200',    texto: 'text-gray-500' },
}

// Color único de la serie en las gráficas. Una sola serie no necesita paleta
// categórica ni leyenda: el título ya dice qué es.
export const COLOR_SERIE = '#1A4FA0'
export const COLOR_META = '#9BACC8'

export const UNIDADES = {
  porcentaje: { label: 'Porcentaje (%)', sufijo: '%' },
  moneda:     { label: 'Dinero (COP)',   sufijo: '' },
  dias:       { label: 'Días',           sufijo: ' días' },
  cantidad:   { label: 'Cantidad',       sufijo: '' },
  razon:      { label: 'Razón / puntaje', sufijo: '' },
}

export const TIPOS_CAPTURA = {
  automatico: {
    label: 'Automático — lo calcula el sistema',
    ayuda: 'Se toma de PQRS o Master Planner. Nadie tiene que digitarlo.',
  },
  razon: {
    label: 'Numerador y denominador',
    ayuda: 'Se registran los dos números y el % lo calcula el sistema. Es la única forma de que el acumulado trimestral y anual salga correcto.',
  },
  valor: {
    label: 'Un solo valor',
    ayuda: 'Se digita el resultado directamente. Úsalo cuando no sea una proporción.',
  },
}

export const DIRECCIONES = {
  arriba: { label: 'Mejor cuando sube', ayuda: 'Satisfacción, cumplimiento, ventas...' },
  abajo:  { label: 'Mejor cuando baja', ayuda: 'Días de respuesta, reclamos, accidentes...' },
}

export const MESES = [
  'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
  'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
]

export const MESES_CORTOS = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']

/** Formatea un valor según la unidad del indicador. */
export function formatValor(valor, unidad) {
  if (valor === null || valor === undefined) return '—'
  if (unidad === 'moneda') {
    return Number(valor).toLocaleString('es-CO', {
      style: 'currency', currency: 'COP', maximumFractionDigits: 0,
    })
  }
  // Sin decimales cuando el número es entero: "90%" se lee mejor que "90.0%".
  const numero = Number(valor)
  const texto = Number.isInteger(numero) ? String(numero) : numero.toFixed(2).replace(/0$/, '')
  return `${texto}${UNIDADES[unidad]?.sufijo ?? ''}`
}

/** Variación con su signo, para comparar contra otro periodo. */
export function formatVariacion(v, unidad) {
  if (v === null || v === undefined) return null
  if (v === 0) return 'igual'
  const signo = v > 0 ? '+' : '−'
  return `${signo}${formatValor(Math.abs(v), unidad === 'moneda' ? 'moneda' : unidad)}`
}

/**
 * Si una variación es buena o mala depende de hacia dónde mejora el
 * indicador: subir los accidentes es malo, subir la satisfacción es bueno.
 */
export function tonoVariacion(v, direccion) {
  if (v === null || v === undefined || v === 0) return 'text-[#9BACC8]'
  const mejora = direccion === 'arriba' ? v > 0 : v < 0
  return mejora ? 'text-green-700' : 'text-red-700'
}

export function periodoAnterior(anio, mes) {
  return mes === 1 ? { anio: anio - 1, mes: 12 } : { anio, mes: mes - 1 }
}

export function periodoSiguiente(anio, mes) {
  return mes === 12 ? { anio: anio + 1, mes: 1 } : { anio, mes: mes + 1 }
}

/** El mes cerrado más reciente: el actual siempre está incompleto. */
export function periodoPorDefecto() {
  const hoy = new Date()
  return periodoAnterior(hoy.getFullYear(), hoy.getMonth() + 1)
}
