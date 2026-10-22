// Las presentaciones del formulario y las que el servidor sabe traducir del ERP.
//
// El servidor traduce «FCOS X 500 CC» a «Mililitro · 500» y el formulario la
// muestra fija. Si el servidor produjera una unidad que el desplegable no
// tiene («Galón» antes de agregarla), al corregir un producto la pantalla no
// sabría mostrarla. Y el formulario público llevaba su propia copia de la
// lista: el día que se agregó una unidad, quedó solo en una de las dos.
import { readFileSync } from 'node:fs'
import { PRESENTACIONES } from '../src/modules/pqrs/constants.js'

let fallos = []
const check = (n, cond, extra = '') => {
  console.log((cond ? '  OK   ' : '  FALLA') + `  ${n}` + (!cond && extra ? `  -> ${JSON.stringify(extra)}` : ''))
  if (!cond) fallos.push(n)
}

const PY = readFileSync(
  new URL('../../backend/app/modules/catalogo/presentaciones.py', import.meta.url), 'utf8')
const FORMULARIO = readFileSync(
  new URL('../src/modules/publico/FormularioPQRS.jsx', import.meta.url), 'utf8')

console.log('\n== Las unidades son las mismas en los dos lados ==')
const tupla = PY.match(/^UNIDADES = \(([^)]*)\)/m)
check('el servidor declara UNIDADES', Boolean(tupla))
const delServidor = tupla ? [...tupla[1].matchAll(/"([^"]+)"/g)].map(m => m[1]) : []
check('PRESENTACIONES es igual a UNIDADES, en el mismo orden',
  JSON.stringify(delServidor) === JSON.stringify(PRESENTACIONES),
  { servidor: delServidor, pantalla: PRESENTACIONES })
check('incluye Galón', PRESENTACIONES.includes('Galón'))

console.log('\n== El formulario público no lleva su propia lista ==')
check('no declara PRESENTACIONES',
  !/const PRESENTACIONES\s*=/.test(FORMULARIO))
check('la importa de pqrs/constants.js',
  /PRESENTACIONES[\s\S]*?from '\.\.\/pqrs\/constants\.js'/.test(FORMULARIO))

console.log()
if (fallos.length) { console.log(`FALLARON ${fallos.length}: ${fallos.join(', ')}`); process.exit(1) }
console.log('TODAS LAS PRUEBAS PASARON')
