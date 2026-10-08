// El flujo de conceptos de una PQRS, del lado de la pantalla.
//
// Quién sigue y cuándo se detiene lo decide el servidor; aquí se prueba que
// editar la lista antes de mandarla no pierda ni duplique pasos, y que los
// nombres de estados, clases y canales sean los mismos del servidor.
import { readFileSync } from 'node:fs'
import {
  APLICA_A, CLASES_PASO, ESTADOS_FLUJO, ESTADOS_PASO, MAX_PASOS,
  agregar, mover, paraEnviar, quitar, ultimoDetenido,
} from '../src/modules/pqrs/flujo.js'

let fallos = []
const check = (n, cond, extra = '') => {
  console.log((cond ? '  OK   ' : '  FALLA') + `  ${n}` + (!cond && extra ? `  -> ${JSON.stringify(extra)}` : ''))
  if (!cond) fallos.push(n)
}

const A = { tipo_autorizacion_id: 1, concepto: 'Analista Financiera', origen: 'concepto', id: 10 }
const B = { tipo_autorizacion_id: 2, concepto: 'Analista Contable', origen: 'concepto' }
const C = { tipo_autorizacion_id: 3, concepto: 'Cartera', origen: 'concepto' }

console.log('\n== Editar la lista ==')
check('subir el segundo', mover([A, B, C], 1, -1).map(p => p.tipo_autorizacion_id).join() === '2,1,3')
check('el primero no sube más', mover([A, B, C], 0, -1).map(p => p.tipo_autorizacion_id).join() === '1,2,3')
check('el último no baja más', mover([A, B, C], 2, 1).map(p => p.tipo_autorizacion_id).join() === '1,2,3')
check('no cambia la lista original', [A, B, C].map(p => p.tipo_autorizacion_id).join() === '1,2,3')
check('quitar', quitar([A, B, C], 1).map(p => p.tipo_autorizacion_id).join() === '1,3')
const tipoNuevo = { id: 4, nombre: 'Producción', area_autorizadora: 'Producción' }
const conNuevo = agregar([A, B], tipoNuevo)
check('agregar va al final y queda marcado como agregado',
  conNuevo.length === 3 && conNuevo[2].tipo_autorizacion_id === 4 && conNuevo[2].origen === 'agregado', conNuevo)
check('un concepto que ya está no se repite', agregar([A, B], { id: 1, nombre: 'x' }).length === 2)
check('sin tipo no agrega nada', agregar([A], null).length === 1)
const llena = Array.from({ length: MAX_PASOS }, (_, i) => ({ tipo_autorizacion_id: i + 100 }))
check('con el tope lleno no agrega', agregar(llena, tipoNuevo).length === MAX_PASOS)

console.log('\n== Lo que viaja ==')
check('solo id (si existía), concepto y origen',
  JSON.stringify(paraEnviar([A, B])) === JSON.stringify([
    { id: 10, tipo_autorizacion_id: 1, origen: 'concepto' },
    { tipo_autorizacion_id: 2, origen: 'concepto' },
  ]), paraEnviar([A, B]))
check('sin origen viaja como agregado', paraEnviar([{ tipo_autorizacion_id: 9 }])[0].origen === 'agregado')

console.log('\n== Volver a pedir repite el último detenido ==')
const pasos = [
  { concepto: 'Logística', estado: 'rechazado' }, { concepto: 'Técnica', estado: 'aprobado' },
  { concepto: 'Financiera', estado: 'devuelto' }, { concepto: 'Contable', estado: 'pendiente' },
]
check('el último rechazado o devuelto', ultimoDetenido(pasos)?.concepto === 'Financiera')
check('sin ninguno, nada', ultimoDetenido([{ estado: 'aprobado' }]) === null)

console.log('\n== Los mismos nombres que el servidor ==')
const MODELO = readFileSync(new URL('../../backend/app/models/pqrs.py', import.meta.url), 'utf8')
const FLUJO = readFileSync(new URL('../../backend/app/modules/pqrs/flujo.py', import.meta.url), 'utf8')
const ROUTER = readFileSync(new URL('../../backend/app/modules/pqrs/router_flujo.py', import.meta.url), 'utf8')
const tupla = (texto, nombre) => [...texto.match(new RegExp(`${nombre} = \\(([^)]*)\\)`))[1].matchAll(/"([a-z_]+)"/g)].map(m => m[1])
check('estados de paso', JSON.stringify(tupla(MODELO, 'ESTADOS_PASO').sort()) === JSON.stringify(Object.keys(ESTADOS_PASO).sort()),
  tupla(MODELO, 'ESTADOS_PASO'))
check('clases de paso', JSON.stringify(tupla(MODELO, 'CLASES_PASO').sort()) === JSON.stringify(Object.keys(CLASES_PASO).sort()),
  tupla(MODELO, 'CLASES_PASO'))
check('canales de una plantilla',
  JSON.stringify(tupla(FLUJO, 'TIPOS_CANAL').sort()) === JSON.stringify(Object.keys(APLICA_A).filter(Boolean).sort()),
  tupla(FLUJO, 'TIPOS_CANAL'))
const estadosFlujo = ['sin_flujo', 'en_curso', 'detenida', 'lista', 'completa']
check('estados del flujo, los que dice estado_cadena()',
  estadosFlujo.every(e => FLUJO.includes(e) && ESTADOS_FLUJO[e]), Object.keys(ESTADOS_FLUJO))
check('el tope de pasos', (ROUTER.match(/max_length=(\d+)\)/) || [])[1] === String(MAX_PASOS))

console.log()
if (fallos.length) { console.log(`FALLARON ${fallos.length}: ${fallos.join(', ')}`); process.exit(1) }
console.log('TODAS LAS PRUEBAS PASARON')
