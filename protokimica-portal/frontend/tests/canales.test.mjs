// Los canales son de cada empresa: los da el servidor (`GET /canales`) y se
// administran en Administracion > Canales. Antes eran una lista escrita aqui
// y en `backend/app/core/canales.py`, y esta prueba verificaba que
// coincidieran. Ahora verifica que esa lista no vuelva a aparecer en el
// frontend, y que las funciones que la reciben respondan bien.
import { readdirSync, readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join, relative } from 'node:path'
import {
  EQUIVALENCIAS_HISTORICAS, canalPorCodigo, canalesConPrefijo, nombresDe,
  normalizarCanal, prefijoDe, puntosDeVenta,
} from '../src/core/canales.js'

const PY = readFileSync(new URL('../../backend/app/core/canales.py', import.meta.url), 'utf8')

let fallos = []
const check = (n, cond, extra = '') => {
  console.log((cond ? '  OK   ' : '  FALLA') + `  ${n}` + (!cond && extra ? `  -> ${JSON.stringify(extra)}` : ''))
  if (!cond) fallos.push(n)
}

// Como los manda el servidor.
const CANALES = [
  { nombre: 'Línea telefónica', prefijo: null, tipo: 'general' },
  { nombre: 'Punto de venta Cristo Rey', prefijo: 'PVCR', tipo: 'sede' },
  { nombre: 'Punto de venta Centro', prefijo: 'PVC', tipo: 'sede' },
  { nombre: 'Venta institucional', prefijo: 'VI', tipo: 'institucional' },
]

console.log('\n== Las equivalencias siguen atadas al backend ==')
const bloque = PY.match(/EQUIVALENCIAS_HISTORICAS = \{(.*?)\}/s)
const equivPy = Object.fromEntries([...bloque[1].matchAll(/"([^"]+)":\s*"([^"]+)"/g)].map(m => [m[1], m[2]]))
check('coinciden', JSON.stringify(equivPy) === JSON.stringify(EQUIVALENCIAS_HISTORICAS),
  { python: equivPy, javascript: EQUIVALENCIAS_HISTORICAS })

console.log('\n== Ningun archivo vuelve a tener su propia lista de canales ==')
// Una lista en el navegador no ve una sede nueva, y sigue ofreciendo una que
// la empresa cerro: las PQRS de ahi entrarian sin su prefijo.
const raiz = join(dirname(fileURLToPath(import.meta.url)), '..', 'src')
function archivos(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap(e =>
    e.isDirectory() ? archivos(join(dir, e.name))
      : /\.(js|jsx)$/.test(e.name) ? [join(dir, e.name)] : [])
}
const conLista = archivos(raiz).filter(f => {
  const t = readFileSync(f, 'utf8')
  return /['"]Punto de venta [A-Z]/.test(t) || /export const (CANALES|PREFIJOS_POR_CANAL)\b/.test(t)
}).map(f => relative(raiz, f).replaceAll('\\', '/'))
check('ninguno', conLista.length === 0, conLista)

console.log('\n== Las funciones trabajan sobre la lista que llega ==')
check('los nombres para un desplegable', nombresDe(CANALES).length === CANALES.length)
check('el prefijo de un canal', prefijoDe(CANALES, 'Punto de venta Centro') === 'PVC')
check('null si no tiene', prefijoDe(CANALES, 'Línea telefónica') === null)
check('del QR al canal', canalPorCodigo(CANALES, 'pvcr') === 'Punto de venta Cristo Rey')
check('un codigo que no existe no inventa canal', canalPorCodigo(CANALES, 'XXX') === null)
check('las sedes son las de tipo sede, no las que empiezan por «Punto de venta»',
  puntosDeVenta(CANALES).map(c => c.prefijo).sort().join(',') === 'PVC,PVCR')
check('venta institucional tiene prefijo pero no es sede',
  !puntosDeVenta(CANALES).some(c => c.prefijo === 'VI'))
check('con prefijo, para filtrar el radicado', canalesConPrefijo(CANALES).length === 3)

console.log('\n== Normalizar ==')
check('el nombre viejo se traduce', normalizarCanal('Llamada telefónica') === 'Línea telefónica')
check('vacio da null', normalizarCanal('  ') === null)

console.log()
if (fallos.length) { console.log(`FALLARON ${fallos.length}: ${fallos.join(', ')}`); process.exit(1) }
console.log('TODAS LAS PRUEBAS PASARON')
