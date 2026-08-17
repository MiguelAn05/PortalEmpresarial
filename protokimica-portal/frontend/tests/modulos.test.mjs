// El acceso por modulo vive en dos archivos —Python y JavaScript— porque el
// frontend no puede importar Python. Si se desincronizan, el menu muestra algo
// que el servidor rechaza con 403, o esconde algo que si se podia abrir.
import { readFileSync } from 'node:fs'
import {
  ACCESO_POR_MODULO, RUTA_DE_MODULO, puedeVerModulo, modulosDe, moduloDeRuta,
} from '../src/core/modulos.js'

const PY = readFileSync(new URL('../../backend/app/core/modulos.py', import.meta.url), 'utf8')

let fallos = []
const check = (n, cond, extra = '') => {
  console.log((cond ? '  OK   ' : '  FALLA') + `  ${n}` + (!cond && extra ? `  -> ${JSON.stringify(extra)}` : ''))
  if (!cond) fallos.push(n)
}

/** Lee `ACCESO_POR_MODULO: dict[...] = { "x": {"a","b"}, ... }` del Python. */
function matrizDelPython() {
  const bloque = PY.match(/ACCESO_POR_MODULO[^=]*= \{(.*?)\n\}/s)
  if (!bloque) throw new Error('No se encontro ACCESO_POR_MODULO en modulos.py')
  const matriz = {}
  for (const linea of bloque[1].split('\n')) {
    const m = linea.match(/^\s*"(\w+)":\s*\{(.+)\},?\s*$/)
    if (!m) continue   // comentarios y lineas en blanco
    matriz[m[1]] = [...m[2].matchAll(/"(\w+)"/g)].map(x => x[1])
  }
  return matriz
}

console.log('\n== Backend y frontend dicen lo mismo ==')
const py = matrizDelPython()
check('los modulos son los mismos',
  JSON.stringify(Object.keys(py)) === JSON.stringify(Object.keys(ACCESO_POR_MODULO)),
  { python: Object.keys(py), javascript: Object.keys(ACCESO_POR_MODULO) })
check('y en el mismo orden (es el orden del menu)',
  Object.keys(py).join('|') === Object.keys(ACCESO_POR_MODULO).join('|'))

for (const modulo of Object.keys(py)) {
  const enPy = [...(py[modulo] || [])].sort()
  const enJs = [...(ACCESO_POR_MODULO[modulo] || [])].sort()
  check(`'${modulo}' permite los mismos roles`,
    JSON.stringify(enPy) === JSON.stringify(enJs), { python: enPy, javascript: enJs })
}

console.log('\n== La matriz tiene sentido ==')
check('todo modulo tiene ruta',
  Object.keys(ACCESO_POR_MODULO).every(m => RUTA_DE_MODULO[m]),
  Object.keys(ACCESO_POR_MODULO).filter(m => !RUTA_DE_MODULO[m]))
check('admin entra a todo',
  Object.keys(ACCESO_POR_MODULO).every(m => puedeVerModulo({ rol: 'admin' }, m)))
check('nadie mas entra a configuracion',
  ['gerencia', 'lider', 'agente', 'lectura'].every(rol => !puedeVerModulo({ rol }, 'admin')))
check('todos entran al inicio',
  ['admin', 'gerencia', 'lider', 'agente', 'lectura']
    .every(rol => puedeVerModulo({ rol }, 'inicio')))

console.log('\n== Quien ve indicadores ==')
check('un agente no', !puedeVerModulo({ rol: 'agente' }, 'indicadores'))
check('solo lectura tampoco', !puedeVerModulo({ rol: 'lectura' }, 'indicadores'))
check('un lider si —le toca registrarlos', puedeVerModulo({ rol: 'lider' }, 'indicadores'))
check('gerencia si', puedeVerModulo({ rol: 'gerencia' }, 'indicadores'))
check('pero un agente si organiza su trabajo',
  puedeVerModulo({ rol: 'agente' }, 'pqrs') && puedeVerModulo({ rol: 'agente' }, 'master_planner'))

console.log('\n== Modulos de un usuario ==')
check('un agente no tiene indicadores en su menu',
  !modulosDe({ rol: 'agente' }).includes('indicadores'), modulosDe({ rol: 'agente' }))
check('gerencia si, pero sin administracion',
  modulosDe({ rol: 'gerencia' }).includes('indicadores')
  && !modulosDe({ rol: 'gerencia' }).includes('admin'), modulosDe({ rol: 'gerencia' }))
check('sin usuario no hay modulos', modulosDe(null).length === 0)
check('un rol inventado no abre nada', modulosDe({ rol: 'x' }).length === 0)

console.log('\n== De ruta a modulo ==')
check('la raiz es el inicio', moduloDeRuta('/') === 'inicio')
check('/pqrs es pqrs', moduloDeRuta('/pqrs') === 'pqrs')
// Sin esto, el detalle de una PQRS quedaria sin proteger.
check('el detalle tambien: /pqrs/12', moduloDeRuta('/pqrs/12') === 'pqrs')
check('/master-planner es master_planner', moduloDeRuta('/master-planner') === 'master_planner')
check('una ruta desconocida no se bloquea', moduloDeRuta('/documentos') === null)
// '/pqrs-publico' NO es '/pqrs': el prefijo tiene que terminar en la ruta o en '/'.
check('un prefijo parecido no cuenta', moduloDeRuta('/pqrs-publico') === null)

console.log()
if (fallos.length) { console.log(`FALLARON ${fallos.length}: ${fallos.join(', ')}`); process.exit(1) }
console.log('TODAS LAS PRUEBAS PASARON')
