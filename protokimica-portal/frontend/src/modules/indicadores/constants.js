// ── Semáforo ──────────────────────────────────────────────────
// El ámbar de la marca no alcanza el contraste mínimo sobre fondo claro, así
// que el estado NUNCA se comunica solo con color: cada semáforo lleva punto
// + etiqueta de texto. Es la misma razón por la que hay `label` aquí.
export const SEMAFOROS = {
  verde:     { label: 'Cumple',      punto: 'var(--color-positivo-vivo)', chip: 'bg-positivo-bg text-positivo border-positivo/25', texto: 'text-positivo' },
  amarillo:  { label: 'En alerta',   punto: 'var(--color-ambar)', chip: 'bg-alerta-bg text-alerta border-ambar/30', texto: 'text-alerta' },
  rojo:      { label: 'No cumple',   punto: 'var(--color-negativo-vivo)', chip: 'bg-negativo-bg text-negativo border-negativo/25',       texto: 'text-negativo' },
  sin_datos: { label: 'Sin dato',    punto: 'var(--color-borde-fuerte)', chip: 'bg-superficie-2 text-texto-2 border-borde',    texto: 'text-texto-2' },
}

// Color único de la serie en las gráficas. Una sola serie no necesita paleta
// categórica ni leyenda: el título ya dice qué es.
export const COLOR_SERIE = 'var(--color-acento)'
export const COLOR_META = 'var(--color-texto-3)'

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
    ayuda: 'Se calcula de un modulo. No tienes que digitarlo.',
  },
  formula: {
    label: 'Fórmula personalizada',
    ayuda: 'Para cuentas como 80 × A ÷ B o (A − B) ÷ A × 100. Cada mes se digitan las variables y el portal calcula.',
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

/**
 * Con qué pestaña abre el módulo cada quien.
 *
 * Gerencia viene a leer cómo va la empresa; Calidad y los líderes vienen a
 * registrar. Mandar a todos a la misma pantalla obliga a la mitad a navegar
 * cada vez que entran.
 *
 * Vive aquí y no en el componente para poder probarse: es una regla de
 * negocio, no una decisión de presentación.
 */
export function pestanaInicial(usuario) {
  return usuario?.rol === 'gerencia' ? 'como-vamos' : 'tablero'
}

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
  if (v === null || v === undefined || v === 0) return 'text-texto-3'
  const mejora = direccion === 'arriba' ? v > 0 : v < 0
  return mejora ? 'text-positivo' : 'text-negativo'
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

// ── Las tres pestañas ─────────────────────────────────────────
/**
 * El módulo hace tres cosas distintas y cada una necesita su pantalla:
 * leer cómo va la empresa, registrar y consultar, y mirar el año completo.
 *
 * La matriz anual vivía dentro de «Cómo vamos» y ahí no cabe: 73 filas por
 * 12 meses empujan todo lo demás fuera de la pantalla, así que quien entraba
 * a ver el estado del mes tenía que pasar por encima de ochocientas celdas.
 */
export const PESTANAS = [
  { clave: 'como-vamos', texto: 'Cómo vamos' },
  { clave: 'tablero',    texto: 'Tablero' },
  { clave: 'el-ano',     texto: 'El año' },
]

// ── Buscador ──────────────────────────────────────────────────
/**
 * Busca por nombre, área o responsable, sin tildes ni mayúsculas.
 *
 * Por responsable porque es la pregunta del cierre de mes —«qué le falta a
 * Hoover»— y sin eso hay que abrir los indicadores de a uno. Sin tildes
 * porque nadie escribe «Logística» con su tilde en un buscador, y un
 * buscador que no encuentra lo que existe se deja de usar.
 */
export function normalizarBusqueda(texto) {
  return (texto ?? '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .trim()
}

export function coincideBusqueda(fila, busqueda) {
  const q = normalizarBusqueda(busqueda)
  if (!q) return true
  return [fila?.nombre, fila?.area, fila?.responsable_nombre]
    .filter(Boolean)
    .some(campo => normalizarBusqueda(campo).includes(q))
}

// ── Agrupación de la matriz anual ─────────────────────────────
/**
 * La fuente automática de «Gestión de OMP», que se crea UNO POR ÁREA.
 *
 * Son veinte filas idénticas en estructura que nadie lee de a una, y puestas
 * en medio de la matriz separan indicadores que sí se comparan entre sí. Se
 * pliegan en un solo renglón que se puede abrir.
 *
 * Se reconoce por la FUENTE y no por el nombre: renombrar un indicador desde
 * Administración no puede romper la agrupación, que es exactamente lo que
 * pasa cuando la regla cuelga de un texto.
 */
export const FUENTE_GESTION_OMP = 'mejora_gestion_omp'

export const GRUPO_SUELTAS = 'sueltas'
export const GRUPO_GESTION_OMP = 'gestion_omp'
export const GRUPO_SIN_REGISTROS = 'sin_registros'

/**
 * Reparte las filas de la matriz en los tres bloques que se pintan.
 *
 * El orden importa y es el de la lectura: primero lo que se mira de verdad,
 * después los automáticos por área, y al final lo que no tiene un solo dato
 * del año — que no es ruido, es la pregunta «¿este indicador sigue vivo?».
 *
 * Una fila sin registros va a su grupo AUNQUE sea de Gestión de OMP: lo que
 * manda es que no haya nada que leer en ella.
 */
export function agruparMatriz(matriz = []) {
  const grupos = { [GRUPO_SUELTAS]: [], [GRUPO_GESTION_OMP]: [], [GRUPO_SIN_REGISTROS]: [] }
  for (const fila of matriz) {
    if (fila.sin_registros) grupos[GRUPO_SIN_REGISTROS].push(fila)
    else if (fila.fuente_automatica === FUENTE_GESTION_OMP) grupos[GRUPO_GESTION_OMP].push(fila)
    else grupos[GRUPO_SUELTAS].push(fila)
  }
  return grupos
}

// ── El delta del cumplimiento ─────────────────────────────────
/**
 * Cómo se lee el movimiento del cumplimiento contra el mes pasado.
 *
 * El NÚMERO lo calcula el servidor (`delta_cumplimiento`); aquí solo se
 * decide cómo se dice y de qué color va. Subir el cumplimiento siempre es
 * bueno —a diferencia de un indicador suelto, donde depende de su
 * dirección—, así que la regla no necesita mirar nada más.
 */
export function leerDelta(delta, mesAnterior) {
  if (delta === null || delta === undefined) return null
  if (delta === 0) {
    return { texto: `igual que ${(mesAnterior || '').toLowerCase()}`, tono: 'text-texto-3', flecha: null }
  }
  const subio = delta > 0
  return {
    texto: `${Math.abs(delta).toFixed(1).replace(/\.0$/, '')} pts vs. ${(mesAnterior || '').toLowerCase()}`,
    tono: subio ? 'text-positivo' : 'text-negativo',
    flecha: subio ? 'sube' : 'baja',
  }
}
