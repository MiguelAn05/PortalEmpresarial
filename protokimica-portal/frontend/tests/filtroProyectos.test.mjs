// Filtrar proyectos por «cerrado» o «cancelado» salía vacío: al cerrarse se
// archivan, la lista pedía los no archivados y el estado se filtraba solo en
// el navegador. El servidor ya lo resolvía (versión 0.19.4), pero la pantalla
// nunca le mandaba el estado. Esta prueba existe para que no vuelva a pasar.
import { readFileSync } from 'node:fs'
import {
  ESTADOS_TERMINALES, ESTADOS_PROYECTO, parametrosListaProyectos,
} from '../src/modules/masterPlanner/constants.js'

const MODELO = readFileSync(new URL('../../backend/app/models/master_planner.py', import.meta.url), 'utf8')
const VISTA = readFileSync(new URL('../src/modules/masterPlanner/views/ProyectosView.jsx', import.meta.url), 'utf8')

let fallos = []
const check = (n, cond, extra = '') => {
  console.log((cond ? '  OK   ' : '  FALLA') + `  ${n}` + (!cond && extra ? `  -> ${JSON.stringify(extra)}` : ''))
  if (!cond) fallos.push(n)
}

console.log('\n== Qué se le pide al servidor ==')
let p = parametrosListaProyectos({ estado: 'cerrado', verArchivados: false })
check('«cerrado» viaja en la consulta', p.estado === 'cerrado', p)
p = parametrosListaProyectos({ estado: 'cancelado', verArchivados: false })
check('«cancelado» también', p.estado === 'cancelado', p)
p = parametrosListaProyectos({ estado: 'en_ejecucion', verArchivados: false })
check('un estado activo se sigue filtrando en pantalla', !('estado' in p) && p.archivados === false, p)
p = parametrosListaProyectos({ estado: '', verArchivados: true })
check('sin estado, manda el interruptor de archivados', p.archivados === true && !('estado' in p), p)

console.log('\n== Atado al servidor ==')
const py = MODELO.match(/^ESTADOS_TERMINALES = \(([^)]*)\)/m)?.[1]
const listaPy = [...(py ?? '').matchAll(/"([^"]+)"/g)].map(m => m[1])
check('los mismos estados terminales', JSON.stringify(listaPy) === JSON.stringify(ESTADOS_TERMINALES),
  { python: listaPy, javascript: ESTADOS_TERMINALES })
check('y existen en la lista de estados', ESTADOS_TERMINALES.every(e => ESTADOS_PROYECTO[e]))

console.log('\n== La vista los usa ==')
check('ProyectosView arma la consulta con parametrosListaProyectos',
  /listarProyectos\(parametros\)/.test(VISTA) && /parametrosListaProyectos\(/.test(VISTA))

console.log()
if (fallos.length) { console.log(`FALLARON ${fallos.length}: ${fallos.join(', ')}`); process.exit(1) }
console.log('TODAS LAS PRUEBAS PASARON')
