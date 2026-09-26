// Lo que le faltaba a una tarea de proyecto para poder seguirla: el
// entregable, las horas que se le van a dedicar y cuántas veces se le movió
// la fecha.
//
// Aquí se prueba la parte que se rompe en silencio: los topes atados al
// schema del backend y cómo se redactan los dos datos nuevos. Un tope que
// solo existe en el servidor devuelve un 422 en la cara de quien ya escribió
// el texto.
import { readFileSync } from 'node:fs'
import {
  MAX_ENTREGABLE, MAX_HORAS, textoAplazamientos, textoHoras,
} from '../src/modules/masterPlanner/constants.js'

const PY_SCHEMAS = readFileSync(
  new URL('../../backend/app/modules/master_planner/schemas.py', import.meta.url), 'utf8')
const PY_MODELO = readFileSync(
  new URL('../../backend/app/models/master_planner.py', import.meta.url), 'utf8')
const PY_HISTORIAL = readFileSync(
  new URL('../../backend/app/modules/master_planner/historial.py', import.meta.url), 'utf8')
const FORM = readFileSync(
  new URL('../src/modules/masterPlanner/components/TareaFormModal.jsx', import.meta.url), 'utf8')

let fallos = []
const check = (n, cond, extra = '') => {
  console.log((cond ? '  OK   ' : '  FALLA') + `  ${n}` + (!cond && extra ? `  -> ${JSON.stringify(extra)}` : ''))
  if (!cond) fallos.push(n)
}

const delPy = (nombre, texto) =>
  Number(texto.match(new RegExp(`^${nombre} = (\\d+)`, 'm'))?.[1])

console.log('\n== Los topes son los mismos de los dos lados ==')
check('MAX_ENTREGABLE coincide con el schema',
  MAX_ENTREGABLE === delPy('MAX_ENTREGABLE', PY_SCHEMAS),
  [MAX_ENTREGABLE, delPy('MAX_ENTREGABLE', PY_SCHEMAS)])
check('MAX_HORAS coincide con el schema',
  MAX_HORAS === delPy('MAX_HORAS', PY_SCHEMAS),
  [MAX_HORAS, delPy('MAX_HORAS', PY_SCHEMAS)])
// El entregable se guarda en un String(n): si la columna fuera mas corta que
// el tope del formulario, Postgres responderia «value too long» con un 500
// que no dice que campo era. Ya mordio en PQRS.
check('y el entregable cabe en su columna',
  new RegExp(`entregable = Column\\(String\\(${MAX_ENTREGABLE}\\)`).test(PY_MODELO),
  PY_MODELO.match(/entregable = Column\([^)]*\)/)?.[0])

console.log('\n== El formulario aplica el tope, no solo el servidor ==')
check('el input del entregable lleva maxLength',
  /maxLength=\{MAX_ENTREGABLE\}/.test(FORM))
check('y las horas su maximo',
  /max=\{MAX_HORAS\}/.test(FORM))
check('el entregable se pide al CREAR la tarea',
  /entregable/.test(FORM), 'no aparece en TareaFormModal')

console.log('\n== Cambiar el entregable o las horas queda en el historial ==')
// Cambiar el entregable es mover la porteria: lo que se iba a entregar no es
// lo que se entrego, y eso tiene que quedar con sus dos valores.
const camposTarea = PY_HISTORIAL.match(/CAMPOS_TAREA = \{([\s\S]*?)\}/)[1]
check('el entregable es auditable', /"entregable"/.test(camposTarea), camposTarea)
check('y las horas también', /"horas_estimadas"/.test(camposTarea), camposTarea)

console.log('\n== Cuántas veces se movió la fecha ==')
check('cero no se anuncia: lo que va bien no lleva adorno',
  textoAplazamientos(0) === null)
check('sin dato tampoco', textoAplazamientos(undefined) === null)
check('una vez va en singular', textoAplazamientos(1) === 'Aplazada 1 vez')
check('varias en plural', textoAplazamientos(4) === 'Aplazada 4 veces')
// Un numero suelto al lado de una fecha se lee como el dia 2.
check('nunca es un número pelado', /[A-Za-z]/.test(textoAplazamientos(2)))

console.log('\n== Y solo cuenta los movimientos de verdad ==')
// Poner la fecha por primera vez no es aplazar nada: no habia de que. Misma
// regla que usan los proyectos en resumen.py.
const contador = PY_MODELO.match(/Tarea\.veces_aplazada = column_property\(([\s\S]*?)\n\)/)[1]
check('el conteo exige que hubiera una fecha antes',
  /valor_anterior\.isnot\(None\)/.test(contador), contador)
check('y mira la fecha de fin de la tarea, no otra cosa',
  /campo == "fecha_fin"/.test(contador) && /entidad == "tarea"/.test(contador), contador)

console.log('\n== Las horas se leen como se dicen ==')
check('enteras sin decimales', textoHoras(8) === '8 h')
check('con media hora, con coma', textoHoras(2.5) === '2,5 h')
check('sin horas no inventa un cero', textoHoras(null) === null)
check('vacío tampoco', textoHoras('') === null)
// Cero es una respuesta valida: una tarea de tramite que no cuesta horas.
check('pero un cero explícito sí se muestra', textoHoras(0) === '0 h')
check('y un texto raro no revienta', textoHoras('ocho') === null)

console.log()
if (fallos.length) { console.log(`FALLARON ${fallos.length}: ${fallos.join(', ')}`); process.exit(1) }
console.log('TODAS LAS PRUEBAS PASARON')
