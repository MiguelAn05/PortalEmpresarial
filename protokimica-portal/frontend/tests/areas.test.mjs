// Las areas viven en dos archivos —uno de Python y uno de JavaScript— porque
// el frontend no puede importar Python. Esta prueba es lo unico que impide
// que se desincronicen: corre en la maquina, donde los dos archivos existen.
import { readFileSync } from 'node:fs'
import { AREAS, EQUIVALENCIAS_HISTORICAS, normalizarArea, areasParaSelect } from '../src/core/areas.js'

const PY = readFileSync(new URL('../../backend/app/core/areas.py', import.meta.url), 'utf8')

let fallos = []
const check = (n, cond, extra = '') => {
  console.log((cond ? '  OK   ' : '  FALLA') + `  ${n}` + (!cond && extra ? `  -> ${JSON.stringify(extra)}` : ''))
  if (!cond) fallos.push(n)
}

/** Lee una lista `NOMBRE = [ "a", "b" ]` del archivo de Python. */
function listaDelPython(nombre) {
  const bloque = PY.match(new RegExp(`${nombre} = \\[(.*?)\\]`, 's'))
  if (!bloque) throw new Error(`No se encontro ${nombre} en areas.py`)
  return [...bloque[1].matchAll(/"([^"]+)"/g)].map(m => m[1])
}

function mapaDelPython(nombre) {
  const bloque = PY.match(new RegExp(`${nombre} = \\{(.*?)\\}`, 's'))
  if (!bloque) throw new Error(`No se encontro ${nombre} en areas.py`)
  return Object.fromEntries([...bloque[1].matchAll(/"([^"]+)":\s*"([^"]+)"/g)].map(m => [m[1], m[2]]))
}

console.log('\n== Backend y frontend dicen lo mismo ==')
const areasPy = listaDelPython('AREAS')
check('la lista de areas coincide exactamente',
  JSON.stringify(areasPy) === JSON.stringify(AREAS),
  { python: areasPy, javascript: AREAS })
check('y en el mismo orden', areasPy.join('|') === AREAS.join('|'))

const equivPy = mapaDelPython('EQUIVALENCIAS_HISTORICAS')
check('las equivalencias historicas coinciden',
  JSON.stringify(equivPy) === JSON.stringify(EQUIVALENCIAS_HISTORICAS),
  { python: equivPy, javascript: EQUIVALENCIAS_HISTORICAS })

console.log('\n== Contenido de la lista ==')
check('la lista no esta vacia', AREAS.length > 0, AREAS.length)
check('no hay repetidas', new Set(AREAS).size === AREAS.length)
check('ningun nombre viejo quedo en la lista',
  Object.keys(EQUIVALENCIAS_HISTORICAS).every(v => !AREAS.includes(v)),
  Object.keys(EQUIVALENCIAS_HISTORICAS).filter(v => AREAS.includes(v)))
check('toda equivalencia apunta a un area real',
  Object.values(EQUIVALENCIAS_HISTORICAS).every(a => AREAS.includes(a)))

console.log('\n== Normalizar ==')
check('TI se traduce a TICS', normalizarArea('TI') === 'TICS')
check('Sistemas tambien', normalizarArea('Sistemas') === 'TICS')
check('Talento Humano pasa a Gestion Humana', normalizarArea('Talento Humano') === 'Gestión Humana')
check('un area actual se deja igual', normalizarArea('Calidad') === 'Calidad')
check('la cadena vacia da null', normalizarArea('') === null)
check('los espacios dan null', normalizarArea('   ') === null)
check('null da null', normalizarArea(null) === null)
check('recorta espacios', normalizarArea('  Calidad  ') === 'Calidad')

console.log('\n== Desplegables ==')
// Sin esto, editar un registro con un area vieja se la borraria al guardar.
check('un area vieja se agrega al desplegable para no perderla',
  areasParaSelect('Area Inventada').includes('Area Inventada'))
check('y va al final, sin desordenar la lista',
  areasParaSelect('Area Inventada').slice(0, AREAS.length).join('|') === AREAS.join('|'))
check('un area actual no se duplica',
  areasParaSelect('Calidad').length === AREAS.length)
check('sin valor devuelve la lista tal cual',
  areasParaSelect(null).length === AREAS.length)

console.log()
if (fallos.length) { console.log(`FALLARON ${fallos.length}: ${fallos.join(', ')}`); process.exit(1) }
console.log('TODAS LAS PRUEBAS PASARON')
