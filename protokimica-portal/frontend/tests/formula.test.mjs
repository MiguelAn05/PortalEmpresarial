// Pruebas del constructor de fórmulas: la traducción entre piezas y texto.
// Validar y calcular es del servidor; esto solo tiene que no perder piezas.
import { readFileSync } from 'node:fs'
import {
  piezasDeTexto, textoDePiezas, mostrarPieza, siguienteLetra, numeroDePieza,
  descuadreVariables, MAX_VARIABLES,
} from '../src/modules/indicadores/formula.js'

const PY = readFileSync(new URL('../../backend/app/modules/indicadores/formula.py', import.meta.url), 'utf8')

let fallos = []
const check = (n, cond, extra = '') => {
  console.log((cond ? '  OK   ' : '  FALLA') + `  ${n}` + (!cond && extra ? `  -> ${JSON.stringify(extra)}` : ''))
  if (!cond) fallos.push(n)
}

console.log('\n== Texto ↔ piezas ==')
let piezas = piezasDeTexto('80 * A / B')
check('cinco piezas', piezas.length === 5, piezas)
check('ida y vuelta sin perder nada', textoDePiezas(piezas) === '80 * A / B', textoDePiezas(piezas))

piezas = piezasDeTexto('(A - B) / A * 100')
check('los paréntesis se pegan', textoDePiezas(piezas) === '(A - B) / A * 100', textoDePiezas(piezas))

check('los símbolos de pantalla se entienden',
  textoDePiezas(piezasDeTexto('80 × A ÷ B − 2')) === '80 * A / B - 2')
check('la coma decimal pasa a punto', textoDePiezas(piezasDeTexto('2,5 * A')) === '2.5 * A')
check('un texto vacío no revienta', piezasDeTexto('').length === 0 && piezasDeTexto(null).length === 0)

console.log('\n== Cómo se muestra ==')
check('× en vez de *', mostrarPieza({ tipo: 'op', texto: '*' }) === '×')
check('÷ en vez de /', mostrarPieza({ tipo: 'op', texto: '/' }) === '÷')
check('− tipográfico', mostrarPieza({ tipo: 'op', texto: '-' }) === '−')
check('coma decimal en pantalla', mostrarPieza({ tipo: 'num', texto: '2.5' }) === '2,5')

console.log('\n== Letras de las variables ==')
check('la primera es A', siguienteLetra([]) === 'A')
check('sigue la libre', siguienteLetra([{ letra: 'A' }, { letra: 'B' }]) === 'C')
check('no corre letras al quitar una: con A y C sigue B',
  siguienteLetra([{ letra: 'A' }, { letra: 'C' }]) === 'B')

console.log('\n== Números escritos a mano ==')
check('entero', numeroDePieza('80') === '80')
check('con coma', numeroDePieza(' 2,5 ') === '2.5')
check('texto no', numeroDePieza('ochenta') === null)
check('negativo no (va con el operador)', numeroDePieza('-3') === null)

console.log('\n== Descuadre entre fórmula y variables ==')
const d = descuadreVariables(piezasDeTexto('A / C'), [{ letra: 'A' }, { letra: 'B' }])
check('C se usa sin declarar', JSON.stringify(d.sinDeclarar) === '["C"]', d)
check('B se declara sin usar', JSON.stringify(d.sinUsar) === '["B"]', d)

console.log('\n== Atado al servidor ==')
const maxPy = Number(PY.match(/^MAX_VARIABLES = (\d+)/m)?.[1])
check('el mismo tope de variables', maxPy === MAX_VARIABLES, { python: maxPy, javascript: MAX_VARIABLES })

console.log()
if (fallos.length) { console.log(`FALLARON ${fallos.length}: ${fallos.join(', ')}`); process.exit(1) }
console.log('TODAS LAS PRUEBAS PASARON')
