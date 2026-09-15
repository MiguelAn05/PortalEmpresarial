/**
 * El constructor de fórmulas trabaja con PIEZAS, no con texto.
 *
 * Quien arma un indicador no escribe `80 * A / B`: pulsa «80», «×», «A»,
 * «÷», «B». Aquí vive la traducción entre esas piezas y el texto que se
 * guarda. Lo que NO vive aquí es validar ni calcular: eso lo hace el servidor
 * (`POST /indicadores/formula/probar`), para que el resultado que se ve al
 * armar sea el mismo que se guarda y el mismo del informe.
 *
 * La gramática es la de `backend/app/modules/indicadores/formula.py`.
 */

export const MAX_VARIABLES = 10   // ATADO a MAX_VARIABLES de formula.py
export const MAX_ETIQUETA = 120   // ATADO a VariableIn.etiqueta del schema

const LETRAS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'

/** Cómo se ve cada operador en pantalla. En el texto guardado va `* / + -`. */
export const SIMBOLOS = { '+': '+', '-': '−', '*': '×', '/': '÷' }

const EQUIVALENTES = { '×': '*', 'x': '*', '÷': '/', '−': '-', '–': '-' }

/** Las piezas de un texto de fórmula. Lo que no se entiende se descarta. */
export function piezasDeTexto(texto) {
  let limpio = texto ?? ''
  for (const [raro, normal] of Object.entries(EQUIVALENTES)) limpio = limpio.split(raro).join(normal)
  const piezas = []
  const patron = /(\d+(?:[.,]\d+)?)|([A-Z])|([+\-*/])|(\()|(\))/g
  let m
  while ((m = patron.exec(limpio)) !== null) {
    if (m[1]) piezas.push({ tipo: 'num', texto: m[1].replace(',', '.') })
    else if (m[2]) piezas.push({ tipo: 'var', texto: m[2] })
    else if (m[3]) piezas.push({ tipo: 'op', texto: m[3] })
    else if (m[4]) piezas.push({ tipo: 'abre', texto: '(' })
    else piezas.push({ tipo: 'cierra', texto: ')' })
  }
  return piezas
}

/** El texto que se guarda: `80 * A / B`. */
export function textoDePiezas(piezas) {
  return piezas.map(p => p.texto).join(' ').replace(/\( /g, '(').replace(/ \)/g, ')')
}

/**
 * Cómo se muestra una pieza. Los números con coma decimal, como se escriben
 * aquí; las variables con su letra (la etiqueta va aparte, en la vista previa).
 */
export function mostrarPieza(pieza) {
  if (pieza.tipo === 'op') return SIMBOLOS[pieza.texto]
  if (pieza.tipo === 'num') return pieza.texto.replace('.', ',')
  return pieza.texto
}

/**
 * La siguiente letra libre para una variable nueva.
 *
 * Nunca se reutiliza ni se corre una letra al quitar otra: si se quita B, la
 * C sigue siendo C. Correrlas cambiaría en silencio lo que dice una fórmula.
 */
export function siguienteLetra(variables) {
  const usadas = new Set((variables ?? []).map(v => v.letra))
  return [...LETRAS].find(l => !usadas.has(l)) ?? null
}

/**
 * Un número escrito por una persona, listo para ser pieza: acepta coma o
 * punto decimal. `null` si no es un número positivo (el signo negativo se
 * arma con el operador −).
 */
export function numeroDePieza(texto) {
  const limpio = (texto ?? '').trim().replace(',', '.')
  return /^\d+(\.\d+)?$/.test(limpio) ? limpio : null
}

/** Las letras que la fórmula usa y no están declaradas, o al revés. */
export function descuadreVariables(piezas, variables) {
  const usadas = new Set(piezas.filter(p => p.tipo === 'var').map(p => p.texto))
  const declaradas = new Set((variables ?? []).map(v => v.letra))
  return {
    sinDeclarar: [...usadas].filter(l => !declaradas.has(l)).sort(),
    sinUsar: [...declaradas].filter(l => !usadas.has(l)).sort(),
  }
}
