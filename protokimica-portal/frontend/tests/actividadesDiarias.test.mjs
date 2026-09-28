// Actividades diarias: lo que se repite y no pertenece a un proyecto.
//
// La regla de qué dia tocaba vive en el SERVIDOR y ahi tiene sus pruebas
// (`test_actividades_diarias.py`): la pantalla no calcula ninguna fecha, solo
// pinta lo que llega resuelto. Lo que se prueba aqui es lo que se rompe en
// silencio del lado del navegador — los gemelos y el vocabulario.
import { readFileSync } from 'node:fs'
import {
  DIAS_ISO, DIAS_SEMANA, FRECUENCIAS, MAX_TITULO_ACTIVIDAD,
  comoFecha, formatFecha, isoDeHoy,
} from '../src/modules/masterPlanner/constants.js'

const PY_ACT = readFileSync(
  new URL('../../backend/app/modules/master_planner/actividades.py', import.meta.url), 'utf8')
const PY_SCHEMAS = readFileSync(
  new URL('../../backend/app/modules/master_planner/schemas.py', import.meta.url), 'utf8')
const PY_MODELO = readFileSync(
  new URL('../../backend/app/models/master_planner.py', import.meta.url), 'utf8')
const HEADER = readFileSync(
  new URL('../src/modules/masterPlanner/components/Header.jsx', import.meta.url), 'utf8')
const VISTA = readFileSync(
  new URL('../src/modules/masterPlanner/views/ActividadesView.jsx', import.meta.url), 'utf8')
const FORM = readFileSync(
  new URL('../src/modules/masterPlanner/components/ActividadFormModal.jsx', import.meta.url), 'utf8')

let fallos = []
const check = (n, cond, extra = '') => {
  console.log((cond ? '  OK   ' : '  FALLA') + `  ${n}` + (!cond && extra ? `  -> ${JSON.stringify(extra)}` : ''))
  if (!cond) fallos.push(n)
}

console.log('\n== Los dias de la semana son los mismos numeros ==')
// El numero ISO es lo que viaja al servidor. Si aqui «lunes» fuera 0 y alla
// 1, marcar lunes crearia una actividad que toca los domingos — y nadie lo
// notaria hasta que alguien reclamara que no le aparece.
const diasPy = [...PY_ACT.match(/DIAS_SEMANA = \{([\s\S]*?)\}/)[1]
  .matchAll(/(\d): "([^"]+)"/g)].map(m => [Number(m[1]), m[2]])
check('son siete de los dos lados',
  diasPy.length === Object.keys(DIAS_ISO).length, { python: diasPy.length, js: Object.keys(DIAS_ISO).length })
check('y cada numero es el mismo dia',
  diasPy.every(([n, nombre]) => DIAS_ISO[n] === nombre), { python: diasPy, js: DIAS_ISO })
check('lunes es 1, como manda ISO', DIAS_ISO[1] === 'Lunes')

console.log('\n== Y no se confunden con los del calendario ==')
// `DIAS_SEMANA` (lista de abreviaturas) es para pintar la rejilla; `DIAS_ISO`
// es el mapa que viaja. Dos cosas parecidas con el mismo nombre es como se
// termina mandando «Lun» donde se esperaba un 1.
check('son estructuras distintas',
  Array.isArray(DIAS_SEMANA) && !Array.isArray(DIAS_ISO))

console.log('\n== Las frecuencias son las que el servidor acepta ==')
const frecPy = [...PY_MODELO.match(/FRECUENCIAS = \(([^)]*)\)/)[1]
  .matchAll(/"([a-z]+)"/g)].map(m => m[1])
check('la pantalla no ofrece una que el servidor rechace',
  Object.keys(FRECUENCIAS).every(f => frecPy.includes(f)),
  { pantalla: Object.keys(FRECUENCIAS), servidor: frecPy })
check('ni deja una del servidor sin ofrecer',
  frecPy.every(f => f in FRECUENCIAS), { servidor: frecPy, pantalla: Object.keys(FRECUENCIAS) })

console.log('\n== El tope del titulo es el mismo ==')
const topePy = Number(PY_SCHEMAS.match(/^MAX_TITULO_ACTIVIDAD = (\d+)/m)?.[1])
check('coincide con el schema', MAX_TITULO_ACTIVIDAD === topePy, [MAX_TITULO_ACTIVIDAD, topePy])
check('y cabe en su columna',
  new RegExp(`titulo = Column\\(String\\(${MAX_TITULO_ACTIVIDAD}\\)`).test(PY_MODELO))
check('el formulario lo aplica', /maxLength=\{MAX_TITULO_ACTIVIDAD\}/.test(FORM))

console.log('\n== Tareas y actividades no suenan a lo mismo ==')
// «Actividad» ya estaba ocupada: en el Excel que reemplaza el modulo, una
// tarea de proyecto se llama Actividad. Dos pestanas de una palabra corta
// dejaban a la gente sin saber donde iba cada cosa.
check('la pestana de tareas dice «de proyecto»',
  /'Tareas de proyecto'/.test(HEADER), HEADER.match(/label: '[^']*Tarea[^']*'/)?.[0])
check('y existe la de actividades diarias',
  /'Actividades diarias'/.test(HEADER))
check('la vista explica que lo que termina va en la otra',
  /Tareas de proyecto/.test(VISTA) && /no termina/.test(VISTA))

console.log('\n== La pantalla no calcula fechas ==')
// La regla de dias habiles y festivos vive en un solo sitio. Si la pantalla
// la repitiera, un festivo nuevo dejaria el portal diciendo dos cosas.
const sinComentarios = VISTA.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '')
check('no decide si hoy toca: lo pregunta',
  /toca_hoy/.test(sinComentarios) && !/isoWeekday|getDay\(\)/.test(sinComentarios))
check('ni redacta la frecuencia',
  /frecuencia_texto/.test(sinComentarios))

console.log('\n== Una fecha sin hora no se pinta un dia antes ==')
// Paso de verdad: se marcaba el lunes 28 y el registro decia «domingo 27».
// `new Date('2026-09-28')` es medianoche UTC, que en Colombia (UTC-5) son las
// 7 p. m. del dia anterior. Ahora se ancla al MEDIODIA local, el unico punto
// del dia que ningun huso ni horario de verano puede mover a otra fecha.
check('el 28 se muestra como 28',
  formatFecha('2026-09-28', { day: '2-digit' }) === '28',
  formatFecha('2026-09-28', { day: '2-digit' }))
check('y cae en el dia de semana correcto',
  formatFecha('2026-09-28', { weekday: 'long' }).startsWith('lunes'),
  formatFecha('2026-09-28', { weekday: 'long' }))
// El caso que más duele: el primero de mes se iba al mes anterior, así que
// el registro aparecía en un mes al que no pertenece.
check('el primero de octubre sigue siendo octubre',
  formatFecha('2026-10-01', { day: 'numeric', month: 'numeric' }) === '1/10',
  formatFecha('2026-10-01', { day: 'numeric', month: 'numeric' }))
check('una fecha CON hora se respeta tal cual',
  comoFecha('2026-09-28T15:30:00') instanceof Date)
check('y sin fecha no revienta', formatFecha(null) === '—')

console.log('\n== Hoy en ISO es el de aqui, no el de UTC ==')
// `toISOString().slice(0,10)` da la fecha de UTC: en Colombia despues de las
// 7 p. m. ya es la de manana, y desmarcar buscaba un dia que no existe.
const ahora = new Date()
const esperado = [
  ahora.getFullYear(),
  String(ahora.getMonth() + 1).padStart(2, '0'),
  String(ahora.getDate()).padStart(2, '0'),
].join('-')
check('coincide con el dia del computador', isoDeHoy() === esperado, isoDeHoy())
check('tiene formato de fecha', /^\d{4}-\d{2}-\d{2}$/.test(isoDeHoy()), isoDeHoy())

console.log()
if (fallos.length) { console.log(`FALLARON ${fallos.length}: ${fallos.join(', ')}`); process.exit(1) }
console.log('TODAS LAS PRUEBAS PASARON')
