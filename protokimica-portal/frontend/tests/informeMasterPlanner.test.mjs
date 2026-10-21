// El informe de Master Planner: lo poco que decide la pantalla.
//
// Los números y las diferencias contra el periodo anterior vienen del
// servidor; aquí se prueba qué periodos se ofrecen (mes y trimestre de
// CALENDARIO, en fechas locales), cómo se dicen las diferencias, el
// semáforo con su etiqueta, y que la pantalla no reste por su cuenta.
import { readFileSync } from 'node:fs'
import {
  estadoCumplimiento, informeVacio, periodosInforme, textoBase, textoPuntos, tramosCompromisos,
} from '../src/modules/masterPlanner/informe.js'
import { conOtros, marcasEje } from '../src/modules/pqrs/informe.js'

let fallos = []
const check = (n, cond, extra = '') => {
  console.log((cond ? '  OK   ' : '  FALLA') + `  ${n}` + (!cond && extra ? `  -> ${JSON.stringify(extra)}` : ''))
  if (!cond) fallos.push(n)
}

console.log('\n== Periodos de un clic ==')
// 21 de octubre de 2026 a las 8 p. m.: en UTC ya es el 22.
const p = Object.fromEntries(periodosInforme(new Date(2026, 9, 21, 20, 0)).map(x => [x.clave, x]))
check('este mes: del 1 a hoy, en fecha local', p.mes.desde === '2026-10-01' && p.mes.hasta === '2026-10-21', p.mes)
check('mes anterior: septiembre completo',
  p.mes_anterior.desde === '2026-09-01' && p.mes_anterior.hasta === '2026-09-30', p.mes_anterior)
check('este trimestre: el cuarto, desde octubre', p.trimestre.desde === '2026-10-01' && p.trimestre.hasta === '2026-10-21', p.trimestre)
check('trimestre anterior: julio a septiembre',
  p.trimestre_anterior.desde === '2026-07-01' && p.trimestre_anterior.hasta === '2026-09-30', p.trimestre_anterior)
check('este año: desde enero', p.anio.desde === '2026-01-01', p.anio)
const feb = Object.fromEntries(periodosInforme(new Date(2026, 1, 10)).map(x => [x.clave, x]))
check('en febrero, el trimestre anterior es el cuarto del año pasado',
  feb.trimestre_anterior.desde === '2025-10-01' && feb.trimestre_anterior.hasta === '2025-12-31', feb.trimestre_anterior)

console.log('\n== Las diferencias se dicen, no se calculan ==')
const sube = textoPuntos(5.2, 'Septiembre de 2026')
check('subir el cumplimiento es buena noticia', sube.tono === 'positivo' && sube.texto === '+5,2 puntos frente a septiembre de 2026', sube)
const baja = textoPuntos(-16.7, 'Septiembre de 2026')
check('bajar, mala', baja.tono === 'negativo' && baja.texto.startsWith('−16,7 puntos'), baja)
check('sin con qué comparar, nada', textoPuntos(null, 'x') === null)
check('igual, neutro', textoPuntos(0, 'Agosto').tono === 'neutro')
const pantalla = readFileSync(new URL('../src/modules/masterPlanner/InformeMasterPlanner.jsx', import.meta.url), 'utf8')
check('la pantalla no resta el periodo anterior', !/pct\s*-\s*\w*\.?pct_anterior|pct_anterior\s*-/.test(pantalla))

console.log('\n== Semáforo con etiqueta ==')
check('90 o más: al día', estadoCumplimiento(92).tono === 'positivo' && estadoCumplimiento(92).etiqueta === 'Al día')
check('entre 75 y 90: por mejorar', estadoCumplimiento(80).tono === 'alerta')
check('menos de 75: bajo', estadoCumplimiento(33.3).tono === 'negativo')
check('sin juzgadas no es un cero', estadoCumplimiento(null).tono === 'neutro')
check('el porcentaje va con su base', textoBase({ a_tiempo: 8, juzgadas: 10 }) === '8 de 10 a tiempo')
check('y sin base lo dice', textoBase({ a_tiempo: 0, juzgadas: 0 }) === 'Sin compromisos para juzgar')

console.log('\n== Compromisos ==')
const tramos = tramosCompromisos({ a_tiempo: 1, tarde: 2, vencidas: 3, pendientes: 4 })
check('cuatro tramos en orden', tramos.map(t => t.n).join() === '1,2,3,4', tramos)
check('cada tramo con tono y etiqueta', tramos.every(t => t.tono && t.etiqueta))

console.log('\n== Vacío ==')
const vacio = { resumen: { proyectos_activos: 0 }, cumplimiento: { total: 0 }, entregas: { total: 0 }, cierres: [], actividades: { esperados: 0 } }
check('sin nada que mostrar se dice', informeVacio(vacio))
check('con un cierre ya hay informe', !informeVacio({ ...vacio, cierres: [{ id: 1 }] }))

console.log('\n== Lo compartido con PQRS sigue en su lugar ==')
check('pqrs/informe.js reexporta conOtros', typeof conOtros === 'function')
check('y marcasEje', JSON.stringify(marcasEje(10)) === '[0,5,10]')

if (fallos.length) { console.log(`\n${fallos.length} FALLARON`); process.exit(1) }
