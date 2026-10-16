// Los filtros viven en la URL y la pestaña los recuerda: abrir el detalle de
// una PQRS y volver no puede obligar a filtrar otra vez. Se prueba la regla
// (`core/filtrosEnUrl.js`); el hook solo la conecta con React Router.
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'

let fallas = 0
function check(nombre, condicion, detalle) {
  if (condicion) console.log(`  OK  ${nombre}`)
  else { fallas++; console.log(`  FALLA ${nombre}`, detalle ?? '') }
}

function almacenFalso(rompe = false) {
  const datos = new Map()
  const a = {
    getItem: (k) => { if (rompe) throw new Error('bloqueado'); return datos.has(k) ? datos.get(k) : null },
    setItem: (k, v) => { if (rompe) throw new Error('bloqueado'); datos.set(k, String(v)) },
    removeItem: (k) => { if (rompe) throw new Error('bloqueado'); datos.delete(k) },
  }
  // `Object.keys(sessionStorage)` en el navegador da las claves guardadas.
  return new Proxy(a, { ownKeys: () => [...datos.keys()], getOwnPropertyDescriptor: () => ({ enumerable: true, configurable: true }) })
}
let sesion = almacenFalso()
globalThis.window = { get sessionStorage() { return sesion } }

const {
  escribirFiltros, filtrosGuardados, guardarFiltros, leerFiltros, olvidarFiltros, soloFiltros, tieneFiltros,
} = await import('../src/core/filtrosEnUrl.js')
const { FILTROS_LISTA } = await import('../src/modules/pqrs/constants.js')

const DEFECTO = { vista: 'abiertas', area: '', busqueda: '' }
const url = (texto) => new URLSearchParams(texto)

console.log('\n== Leer y escribir ==')
check('sin nada en la URL, los valores por defecto',
  JSON.stringify(leerFiltros(url(''), DEFECTO)) === JSON.stringify(DEFECTO))
check('lo de la URL manda', leerFiltros(url('vista=cerradas&area=Calidad'), DEFECTO).vista === 'cerradas')
check('lo que no trae queda por defecto', leerFiltros(url('area=Calidad'), DEFECTO).vista === 'abiertas')
check('el valor por defecto no se escribe: la URL de quien no filtra sigue limpia',
  escribirFiltros(url(''), { vista: 'abiertas', area: '' }, DEFECTO).toString() === '')
check('lo distinto sí', escribirFiltros(url(''), { vista: 'cerradas' }, DEFECTO).toString() === 'vista=cerradas')
check('volver al defecto lo quita', escribirFiltros(url('vista=cerradas&area=X'), { vista: 'abiertas' }, DEFECTO).toString() === 'area=X')
check('no toca los parámetros ajenos (?tarea=42)',
  escribirFiltros(url('tarea=42'), { area: 'Calidad' }, DEFECTO).get('tarea') === '42')
check('ignora claves que no son filtros', !escribirFiltros(url(''), { otra: 'x' }, DEFECTO).has('otra'))
check('null y vacío son «sin filtro»', escribirFiltros(url('area=X'), { area: null }, DEFECTO).toString() === '')
check('tieneFiltros mira solo los suyos', !tieneFiltros(url('tarea=42'), DEFECTO) && tieneFiltros(url('area=X'), DEFECTO))

console.log('\n== El prefijo separa dos listas de una misma ruta ==')
const p = escribirFiltros(url(''), { area: 'TICS' }, DEFECTO, 'p_')
check('se escribe con prefijo', p.get('p_area') === 'TICS' && !p.has('area'))
check('la otra lista no lo ve', leerFiltros(p, DEFECTO, 't_').area === '')
check('soloFiltros toma solo los propios', soloFiltros(url('p_area=X&t_area=Y&tarea=3'), DEFECTO, 'p_').toString() === 'p_area=X')

console.log('\n== Lo que recuerda la pestaña ==')
guardarFiltros('/pqrs', '', url('vista=cerradas'))
check('se guarda por ruta', filtrosGuardados('/pqrs').get('vista') === 'cerradas')
check('otra ruta no lo hereda', filtrosGuardados('/mejora').toString() === '')
guardarFiltros('/pqrs', '', url(''))
check('limpiar borra lo guardado (si no, /pqrs limpio lo restauraría)', filtrosGuardados('/pqrs').toString() === '')
guardarFiltros('/pqrs', '', url('area=X'))
guardarFiltros('/mejora', '', url('estado=abierta'))
olvidarFiltros()
check('cerrar sesión los olvida todos',
  filtrosGuardados('/pqrs').toString() === '' && filtrosGuardados('/mejora').toString() === '')
sesion = almacenFalso(true)
let revento = false
try { guardarFiltros('/pqrs', '', url('vista=todas')); filtrosGuardados('/pqrs'); olvidarFiltros() } catch { revento = true }
check('en modo privado (el almacén lanza) no revienta', !revento)

console.log('\n== PQRS ==')
check('la lista arranca en Abiertas', FILTROS_LISTA.vista === 'abiertas')
check('todo filtro de la lista tiene valor por defecto de texto',
  Object.values(FILTROS_LISTA).every(v => typeof v === 'string'))

console.log('\n== Ninguna lista vuelve a guardar sus filtros solo en useState ==')
// La lista exacta de pantallas que tienen que usar el hook: si una vuelve a
// `useState`, sus filtros se pierden otra vez al abrir un detalle.
const DEBEN_USARLO = [
  'modules/pqrs/PQRSList.jsx', 'modules/indicadores/Indicadores.jsx', 'modules/mejora/Mejora.jsx',
  'modules/notas_credito/NotasCredito.jsx', 'modules/encuestas/Encuestas.jsx',
  'modules/masterPlanner/MasterPlanner.jsx', 'modules/masterPlanner/views/ProyectosView.jsx',
  'modules/masterPlanner/views/TareasView.jsx', 'modules/masterPlanner/views/CalendarioView.jsx',
  'modules/masterPlanner/views/ResumenView.jsx',
]
const SRC = new URL('../src/', import.meta.url)
for (const archivo of DEBEN_USARLO) {
  const texto = readFileSync(new URL(archivo, SRC), 'utf8')
  check(`${archivo} usa useFiltrosEnUrl`, texto.includes('useFiltrosEnUrl('))
}
// Dos listas en la misma ruta sin prefijo se pisan el `estado`.
const vistasMp = join(new URL('modules/masterPlanner/views/', SRC).pathname.replace(/^\/([A-Za-z]:)/, '$1'))
const prefijos = readdirSync(vistasMp)
  .filter(f => statSync(join(vistasMp, f)).isFile())
  .map(f => readFileSync(join(vistasMp, f), 'utf8').match(/useFiltrosEnUrl\([\s\S]*?prefijo:\s*["']([^"']+)["']/)?.[1])
  .filter(Boolean)
check('las vistas de Master Planner llevan prefijos distintos',
  prefijos.length >= 4 && new Set(prefijos).size === prefijos.length, prefijos)

if (fallas) { console.log(`\n${fallas} FALLARON`); process.exit(1) }
