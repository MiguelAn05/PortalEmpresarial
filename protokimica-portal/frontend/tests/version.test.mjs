// Comparar versiones y decidir si hay que avisar. Es logica chiquita pero se
// equivoca de forma silenciosa: comparar como texto pone 0.9.0 por encima de
// 0.11.0 y el aviso de "recarga" nunca sale.
import { readFileSync } from 'node:fs'
import {
  VERSION_APP, compararVersiones, servidorAdelantado, hayNovedades,
} from '../src/core/version.js'

let fallos = []
const check = (n, cond, extra = '') => {
  console.log((cond ? '  OK   ' : '  FALLA') + `  ${n}` + (!cond && extra ? `  -> ${JSON.stringify(extra)}` : ''))
  if (!cond) fallos.push(n)
}

console.log('\n== Una sola fuente ==')
const PY = readFileSync(new URL('../../backend/app/core/version.py', import.meta.url), 'utf8')
const VITE = readFileSync(new URL('../vite.config.js', import.meta.url), 'utf8')
check('el backend declara una VERSION', /^VERSION = "\d+\.\d+\.\d+"/m.test(PY),
  (PY.match(/^VERSION = .*/m) || [])[0])
// Si alguien cambia la forma de la constante, el build se queda con la
// version vieja sin avisar. Esta prueba es lo que lo impide.
check('vite la lee de ahi y no de otro lado',
  VITE.includes('backend/app/core/version.py') && VITE.includes('__VERSION__'))
check('corriendo en node, sin build, no revienta', VERSION_APP === 'dev', VERSION_APP)

console.log('\n== Comparar versiones ==')
check('iguales dan 0', compararVersiones('1.2.3', '1.2.3') === 0)
check('mayor gana', compararVersiones('1.0.0', '0.99.99') > 0)
check('menor pierde', compararVersiones('0.10.0', '0.11.0') < 0)
// El caso que rompe la comparacion de texto.
check('0.9.0 es ANTERIOR a 0.11.0', compararVersiones('0.9.0', '0.11.0') < 0)
check('y 0.11.0 posterior a 0.9.0', compararVersiones('0.11.0', '0.9.0') > 0)
check('el parche cuenta', compararVersiones('0.6.1', '0.6.0') > 0)
check('faltar partes se lee como cero', compararVersiones('1.2', '1.2.0') === 0)
check('basura no revienta', compararVersiones(null, undefined) === 0)

console.log('\n== Avisar que el servidor va adelante ==')
check('servidor mas nuevo -> avisa', servidorAdelantado('0.12.0', '0.11.0') === true)
check('iguales -> no molesta', servidorAdelantado('0.11.0', '0.11.0') === false)
// Pasa cuando el dist commiteado es mas nuevo que el backend desplegado: es
// un problema, pero no uno que recargar arregle.
check('navegador mas nuevo -> tampoco', servidorAdelantado('0.10.0', '0.11.0') === false)
check('sin respuesta del servidor -> no', servidorAdelantado(null, '0.11.0') === false)
check('en desarrollo nunca avisa', servidorAdelantado('9.9.9', 'dev') === false)

console.log('\n== Punto de novedades ==')
check('subio de version -> hay novedades', hayNovedades('0.12.0', '0.11.0') === true)
check('ya la vio -> no', hayNovedades('0.11.0', '0.11.0') === false)
// Estrenar el portal con un aviso de "novedades" de nada no tiene sentido.
check('la primera vez no molesta', hayNovedades('0.11.0', null) === false)
check('sin version del servidor no inventa', hayNovedades(null, '0.11.0') === false)

console.log()
if (fallos.length) { console.log(`FALLARON ${fallos.length}: ${fallos.join(', ')}`); process.exit(1) }
console.log('TODAS LAS PRUEBAS PASARON')
