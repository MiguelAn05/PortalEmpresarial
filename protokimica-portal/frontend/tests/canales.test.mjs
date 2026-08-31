// Los canales viven en dos archivos —uno de Python y uno de JavaScript—
// porque el frontend no puede importar Python. Esta prueba es lo unico que
// impide que se desincronicen.
//
// No es teorico: antes de unificarlos, el formulario de felicitaciones decia
// "Llamada telefonica" y el resto del portal "Linea telefonica", asi que la
// misma llamada caia en dos canales distintos y el reporte las contaba
// aparte. Eso es justo lo que esta prueba existe para que no vuelva a pasar.
import { readFileSync } from 'node:fs'
import {
  CANALES, PREFIJOS_POR_CANAL, EQUIVALENCIAS_HISTORICAS,
  normalizarCanal, prefijoDe, canalPorCodigo, puntosDeVenta, canalesConPrefijo,
} from '../src/core/canales.js'

const PY = readFileSync(new URL('../../backend/app/core/canales.py', import.meta.url), 'utf8')

let fallos = []
const check = (n, cond, extra = '') => {
  console.log((cond ? '  OK   ' : '  FALLA') + `  ${n}` + (!cond && extra ? `  -> ${JSON.stringify(extra)}` : ''))
  if (!cond) fallos.push(n)
}

function listaDelPython(nombre) {
  const bloque = PY.match(new RegExp(`^${nombre} = \\[(.*?)\\]`, 'ms'))
  if (!bloque) throw new Error(`No se encontro ${nombre} en canales.py`)
  return [...bloque[1].matchAll(/"([^"]+)"/g)].map(m => m[1])
}

function mapaDelPython(nombre) {
  const bloque = PY.match(new RegExp(`^${nombre} = \\{(.*?)\\}`, 'ms'))
  if (!bloque) throw new Error(`No se encontro ${nombre} en canales.py`)
  return Object.fromEntries([...bloque[1].matchAll(/"([^"]+)":\s*"([^"]+)"/g)].map(m => [m[1], m[2]]))
}

console.log('\n== Backend y frontend dicen lo mismo ==')
const canalesPy = listaDelPython('CANALES')
check('la lista de canales coincide exactamente',
  JSON.stringify(canalesPy) === JSON.stringify(CANALES),
  { python: canalesPy, javascript: CANALES })
check('y en el mismo orden', canalesPy.join('|') === CANALES.join('|'))

const prefijosPy = mapaDelPython('PREFIJOS_POR_CANAL')
check('los prefijos coinciden',
  JSON.stringify(prefijosPy) === JSON.stringify(PREFIJOS_POR_CANAL),
  { python: prefijosPy, javascript: PREFIJOS_POR_CANAL })

const equivPy = mapaDelPython('EQUIVALENCIAS_HISTORICAS')
check('las equivalencias historicas coinciden',
  JSON.stringify(equivPy) === JSON.stringify(EQUIVALENCIAS_HISTORICAS),
  { python: equivPy, javascript: EQUIVALENCIAS_HISTORICAS })

console.log('\n== Coherencia de la lista ==')
check('todo canal con prefijo esta en la lista de canales',
  Object.keys(PREFIJOS_POR_CANAL).every(c => CANALES.includes(c)),
  Object.keys(PREFIJOS_POR_CANAL).filter(c => !CANALES.includes(c)))
check('ningun canal esta repetido', new Set(CANALES).size === CANALES.length)
check('ningun prefijo esta repetido',
  new Set(Object.values(PREFIJOS_POR_CANAL)).size === Object.keys(PREFIJOS_POR_CANAL).length)
// El prefijo se compara contra el codigo del radicado, y un prefijo con
// espacios o minusculas no coincidiria nunca.
check('los prefijos son mayusculas y digitos',
  Object.values(PREFIJOS_POR_CANAL).every(p => /^[A-Z0-9]+$/.test(p)),
  Object.values(PREFIJOS_POR_CANAL))
check('los seis puntos de venta tienen prefijo',
  puntosDeVenta().every(p => prefijoDe(p)), puntosDeVenta().filter(p => !prefijoDe(p)))
check('hay seis puntos de venta', puntosDeVenta().length === 6, puntosDeVenta())

console.log('\n== Del codigo del QR al canal ==')
check('PVG es Guayabal', canalPorCodigo('PVG') === 'Punto de venta Guayabal')
check('VI es venta institucional', canalPorCodigo('VI') === 'Venta institucional')
// El codigo va impreso en un letrero: alguien lo va a teclear a mano.
check('no distingue mayusculas', canalPorCodigo('pvg') === 'Punto de venta Guayabal')
check('ignora espacios de mas', canalPorCodigo('  PVCR ') === 'Punto de venta Cristo Rey')
check('un codigo inventado no devuelve nada', canalPorCodigo('XXX') === null)
check('sin codigo no revienta', canalPorCodigo(null) === null)
check('PV65 no se confunde con PV6', canalPorCodigo('PV6') === null)
// Ida y vuelta: todo canal con prefijo se recupera desde su prefijo.
check('el viaje de ida y vuelta cierra',
  Object.keys(PREFIJOS_POR_CANAL).every(c => canalPorCodigo(prefijoDe(c)) === c))

console.log('\n== Nombres viejos ==')
check('llamada telefonica se traduce a linea telefonica',
  normalizarCanal('Llamada telefónica') === 'Línea telefónica')
check('un canal actual se deja igual',
  normalizarCanal('Punto de venta Belén') === 'Punto de venta Belén')
check('vacio da null', normalizarCanal('   ') === null)
check('null da null', normalizarCanal(null) === null)
check('el nombre viejo ya no se ofrece', !CANALES.includes('Llamada telefónica'))

console.log('\n== Filtro por prefijo ==')
const conPrefijo = canalesConPrefijo()
check('devuelve uno por cada canal con prefijo',
  conPrefijo.length === Object.keys(PREFIJOS_POR_CANAL).length)
check('cada uno trae prefijo y etiqueta',
  conPrefijo.every(x => x.prefijo && x.label))

console.log()
if (fallos.length) { console.log(`FALLARON ${fallos.length}: ${fallos.join(', ')}`); process.exit(1) }
console.log('TODAS LAS PRUEBAS PASARON')
