// Tareas sin proyecto (desde la 0.70).
//
// La regla de quién las ve vive en el servidor (`master_planner/permisos.py`)
// y ahí tiene sus pruebas. Aquí: que la lista las filtre igual que las cuenta
// el Resumen, y que el formulario y la API ya no exijan un proyecto.
import { readFileSync } from 'node:fs'
import { SIN_PROYECTO, filtrarTareas, nombreProyecto } from '../src/modules/masterPlanner/constants.js'

const leer = (ruta) => readFileSync(new URL(ruta, import.meta.url), 'utf8')
const FORM = leer('../src/modules/masterPlanner/components/TareaFormModal.jsx')
const API = leer('../src/modules/masterPlanner/api.js')

let fallos = []
const check = (n, cond, extra = '') => {
  console.log((cond ? '  OK   ' : '  FALLA') + `  ${n}` + (!cond && extra ? `  -> ${JSON.stringify(extra)}` : ''))
  if (!cond) fallos.push(n)
}

const proyectos = [{ id: 1, nombre: 'Portal', area: 'TICS', areas_participantes: [] }]
const tareas = [
  { id: 10, proyecto_id: 1, proyecto_nombre: 'Portal', area: 'TICS' },
  { id: 20, proyecto_id: null, proyecto_nombre: null, area: 'Contabilidad' },
  { id: 30, proyecto_id: null, proyecto_nombre: null, area: 'TICS' },
]
const ids = (lista) => lista.map(t => t.id).join(',')

console.log('\n== Filtrar ==')
check('«Sin proyecto» trae solo las sueltas',
  ids(filtrarTareas(tareas, { proyecto_id: SIN_PROYECTO }, proyectos)) === '20,30')
check('un proyecto no trae las sueltas', ids(filtrarTareas(tareas, { proyecto_id: '1' }, proyectos)) === '10')
check('desde el Resumen, el área trae sus proyectos y sus sueltas, como lo cuenta el servidor',
  ids(filtrarTareas(tareas, { de_area: 'TICS' }, proyectos)) === '10,30',
  ids(filtrarTareas(tareas, { de_area: 'TICS' }, proyectos)))
check('y una suelta de otra área no',
  ids(filtrarTareas(tareas, { de_area: 'Contabilidad' }, proyectos)) === '20')

console.log('\n== Nombrar ==')
check('una tarea suelta dice «Sin proyecto», no un vacío', nombreProyecto(tareas[1]) === 'Sin proyecto')
check('la de proyecto, su proyecto', nombreProyecto(tareas[0]) === 'Portal')

console.log('\n== Crear ==')
check('la API crea por la ruta que acepta las dos', /api\.post\('\/master-planner\/tareas'/.test(API))
check('el formulario ofrece «Sin proyecto»', /<option value="">Sin proyecto<\/option>/.test(FORM))
check('y sin proyecto no deja crear sin área', /faltaArea/.test(FORM) && /disabled=\{!form\.titulo \|\| faltaArea/.test(FORM))
check('ya no exige que exista un proyecto', !/Primero tienes que crear un proyecto/.test(FORM))

console.log()
if (fallos.length) { console.log(`FALLARON ${fallos.length}: ${fallos.join(', ')}`); process.exit(1) }
console.log('TODAS LAS PRUEBAS PASARON')
