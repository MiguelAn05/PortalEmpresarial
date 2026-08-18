/**
 * Constantes y lógica pura del módulo de Encuestas.
 *
 * Lo que se pueda probar sin pintar nada vive aquí, en un archivo sin JSX:
 * Node importa .js pero no .jsx, así que la lógica que quiera cubrirse con
 * pruebas tiene que estar fuera de los componentes.
 */

export const ESCALA_MAX = 5

export const TIPOS_PREGUNTA = {
  escala: {
    label: 'Calificación de 1 a 5',
    ayuda: 'La típica de estrellas. Es la que alimenta promedios e indicadores.',
  },
  opcion: {
    label: 'Una opción de varias',
    ayuda: 'Por ejemplo: Sí / Parcialmente / No. Se escriben separadas por |',
  },
  si_no: {
    label: 'Sí o no',
    ayuda: 'Se resume como porcentaje de "sí".',
  },
  texto: {
    label: 'Comentario abierto',
    ayuda: 'No entra en promedios, pero suele ser lo más útil de leer.',
  },
}

/**
 * Cómo se lee una calificación promedio.
 *
 * Los cortes son los de NPS adaptados a escala de 5: por debajo de 3 hay un
 * problema, y por encima de 4 la cosa va bien. El estado NUNCA se comunica
 * solo con color, así que cada nivel trae su etiqueta.
 */
export function nivelCalificacion(promedio) {
  if (promedio === null || promedio === undefined) return 'sin_datos'
  if (promedio >= 4) return 'bueno'
  if (promedio >= 3) return 'regular'
  return 'malo'
}

export const NIVELES = {
  bueno:     { label: 'Bien',     punto: 'var(--color-positivo-vivo)', chip: 'bg-positivo-bg text-positivo border-positivo/25', texto: 'text-positivo' },
  regular:   { label: 'Regular',  punto: 'var(--color-ambar)', chip: 'bg-alerta-bg text-alerta border-ambar/30', texto: 'text-alerta' },
  malo:      { label: 'Mal',      punto: 'var(--color-negativo-vivo)', chip: 'bg-negativo-bg text-negativo border-negativo/25',       texto: 'text-negativo' },
  sin_datos: { label: 'Sin nota', punto: 'var(--color-borde-fuerte)', chip: 'bg-superficie-2 text-texto-2 border-borde',    texto: 'text-texto-2' },
}

/** "4.35" -> "4.4"; sin nota -> guion. */
export function formatNota(valor) {
  if (valor === null || valor === undefined) return '—'
  return Number(valor).toFixed(1)
}

/**
 * Convierte el slug que escribe la persona en uno válido para una URL.
 *
 * Termina impreso en un código QR, así que no puede llevar tildes, espacios
 * ni mayúsculas: un enlace que falla por un acento es un QR inservible
 * pegado en una pared.
 */
export function normalizarSlug(texto) {
  return (texto || '')
    // NFD separa cada letra de su acento; \p{Diacritic} borra los acentos
    // sueltos que quedan. Se escribe así y no con el rango de códigos para
    // que no dependa de con qué codificación se guarde este archivo.
    .normalize('NFD').replace(/\p{Diacritic}/gu, '')
    .toLowerCase()
    .replace(/[^a-z0-9-]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 60)
}

/**
 * La dirección que se imprime en el QR.
 *
 * Corta a propósito (/e/loquesea): un QR con menos caracteres se lee más
 * rápido y con peor luz, que es justo la condición de un punto de venta.
 */
export function urlPublica(slug) {
  const base = typeof window !== 'undefined' ? window.location.origin : ''
  return `${base}/e/${slug}`
}
