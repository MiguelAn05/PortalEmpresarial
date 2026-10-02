// Las areas son de cada empresa: las da el servidor (`GET /areas`) y se
// administran en Administracion > Areas. Antes eran una lista escrita aqui y
// en `backend/app/core/areas.py`, y esta prueba verificaba que coincidieran.
// Ahora verifica que esa lista no vuelva a aparecer en el frontend, y que lo
// que si quedo (las equivalencias de nombres viejos) siga atado al backend.
import { readdirSync, readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join, relative } from 'node:path'
import { EQUIVALENCIAS_HISTORICAS, normalizarArea, areasParaSelect } from '../src/core/areas.js'

const PY = readFileSync(new URL('../../backend/app/core/areas.py', import.meta.url), 'utf8')

let fallos = []
const check = (n, cond, extra = '') => {
  console.log((cond ? '  OK   ' : '  FALLA') + `  ${n}` + (!cond && extra ? `  -> ${JSON.stringify(extra)}` : ''))
  if (!cond) fallos.push(n)
}

function mapaDelPython(nombre) {
  const bloque = PY.match(new RegExp(`${nombre} = \\{(.*?)\\}`, 's'))
  if (!bloque) throw new Error(`No se encontro ${nombre} en areas.py`)
  return Object.fromEntries([...bloque[1].matchAll(/"([^"]+)":\s*"([^"]+)"/g)].map(m => [m[1], m[2]]))
}

console.log('\n== Las equivalencias siguen atadas al backend ==')
const equivPy = mapaDelPython('EQUIVALENCIAS_HISTORICAS')
check('las equivalencias historicas coinciden',
  JSON.stringify(equivPy) === JSON.stringify(EQUIVALENCIAS_HISTORICAS),
  { python: equivPy, javascript: EQUIVALENCIAS_HISTORICAS })

console.log('\n== Ningun archivo vuelve a tener su propia lista de areas ==')
// Una lista escrita en el navegador es una lista que no ve lo que la empresa
// configuro: el area nueva no aparece y la desactivada sigue ofreciendose.
const aqui = dirname(fileURLToPath(import.meta.url))
const raiz = join(aqui, '..', 'src')
function archivos(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap(e =>
    e.isDirectory() ? archivos(join(dir, e.name))
      : /\.(js|jsx)$/.test(e.name) ? [join(dir, e.name)] : [])
}
const conLista = archivos(raiz).filter(f => {
  const texto = readFileSync(f, 'utf8')
  // Tres areas reales seguidas en un arreglo es una lista de areas.
  return /\[\s*['"]TICS['"],\s*['"]Calidad['"],\s*['"]SST['"]/.test(texto)
    || /export const AREAS\b/.test(texto)
}).map(f => relative(raiz, f).replaceAll('\\', '/'))
check('ninguno', conLista.length === 0, conLista)

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
const DE_LA_EMPRESA = ['TICS', 'Calidad', 'Comercial']
// Sin esto, editar un registro con un area vieja o desactivada se la borraria
// al guardar.
check('un area que ya no esta se agrega para no perderla',
  areasParaSelect(DE_LA_EMPRESA, 'Area Inventada').includes('Area Inventada'))
check('y va al final, sin desordenar la lista',
  areasParaSelect(DE_LA_EMPRESA, 'Area Inventada').slice(0, 3).join('|') === DE_LA_EMPRESA.join('|'))
check('un area actual no se duplica',
  areasParaSelect(DE_LA_EMPRESA, 'Calidad').length === DE_LA_EMPRESA.length)
check('sin valor devuelve la lista tal cual',
  areasParaSelect(DE_LA_EMPRESA, null).length === DE_LA_EMPRESA.length)

console.log()
if (fallos.length) { console.log(`FALLARON ${fallos.length}: ${fallos.join(', ')}`); process.exit(1) }
console.log('TODAS LAS PRUEBAS PASARON')
