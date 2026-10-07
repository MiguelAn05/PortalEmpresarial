// El informe de PQRS: lo poco que decide la pantalla.
//
// Los números vienen contados del servidor; aquí se prueba qué periodos se
// ofrecen (en fechas LOCALES), cómo se dice la comparación, el semáforo de
// «a tiempo» con su etiqueta, y que «Otros» sume lo que ya llegó.
import { readFileSync } from 'node:fs'
import { conOtros, estadoATiempo, marcasEje, periodosRapidos, textoVariacion } from '../src/modules/pqrs/informe.js'

let fallos = []
const check = (n, cond, extra = '') => {
  console.log((cond ? '  OK   ' : '  FALLA') + `  ${n}` + (!cond && extra ? `  -> ${JSON.stringify(extra)}` : ''))
  if (!cond) fallos.push(n)
}

console.log('\n== Periodos de un clic ==')
// 7 de octubre de 2026 a las 8 p. m.: en UTC ya es el 8.
const p = Object.fromEntries(periodosRapidos(new Date(2026, 9, 7, 20, 0)).map(x => [x.clave, x]))
check('este mes: del 1 a hoy, en fecha local', p.mes.desde === '2026-10-01' && p.mes.hasta === '2026-10-07', p.mes)
check('mes anterior: septiembre completo', p.anterior.desde === '2026-09-01' && p.anterior.hasta === '2026-09-30', p.anterior)
check('tres meses: desde agosto', p.trimestre.desde === '2026-08-01', p.trimestre)
check('este año: desde enero', p.anio.desde === '2026-01-01', p.anio)
const enero = Object.fromEntries(periodosRapidos(new Date(2026, 0, 10)).map(x => [x.clave, x]))
check('en enero, el anterior es diciembre del año pasado',
  enero.anterior.desde === '2025-12-01' && enero.anterior.hasta === '2025-12-31', enero.anterior)

console.log('\n== La comparación con el periodo anterior ==')
const sube = textoVariacion({ total: 14, total_anterior: 10, variacion_pct: 40 }, 'Septiembre de 2026')
check('dice cuánto y contra qué', sube.texto === '+40% frente a septiembre de 2026 (10)', sube)
check('más PQRS no es buena noticia', sube.tono === 'negativo')
const baja = textoVariacion({ total: 5, total_anterior: 10, variacion_pct: -50 }, 'Septiembre de 2026')
check('bajar sí', baja.tono === 'positivo' && baja.texto.startsWith('−50%'), baja)
check('sin anterior lo dice', textoVariacion({ total: 3, total_anterior: 0, variacion_pct: null }, 'Agosto').tono === 'neutro')
check('igual es neutro', textoVariacion({ total: 4, total_anterior: 4, variacion_pct: 0 }, 'X').texto.startsWith('Igual'))
check('sin nada en ninguno, nada que decir', textoVariacion({ total: 0, total_anterior: 0 }, 'X') === null)

console.log('\n== A tiempo: siempre con etiqueta ==')
check('90% o más en término', estadoATiempo(95).tono === 'positivo' && estadoATiempo(95).etiqueta)
check('entre 75 y 90 por mejorar', estadoATiempo(80).tono === 'alerta')
check('menos de 75 fuera de término', estadoATiempo(50).tono === 'negativo')
check('sin respuestas no es un cero', estadoATiempo(null).tono === 'neutro')

console.log('\n== «Otros» suma lo que mandó el servidor ==')
const filas = Array.from({ length: 10 }, (_, i) => ({ clave: i, etiqueta: `C${i}`, n: 10 - i, pct: 10 - i }))
const cortas = conOtros(filas, 8)
check('ocho filas', cortas.length === 8, cortas.length)
check('la última es Otros con lo que sobra', cortas[7].etiqueta === 'Otros (3)' && cortas[7].n === 3 + 2 + 1, cortas[7])
check('una lista corta no se toca', conOtros(filas.slice(0, 3), 8).length === 3)
check('vacía tampoco revienta', conOtros(undefined).length === 0)

console.log('\n== Eje de la tendencia ==')
check('0, la mitad y el máximo', JSON.stringify(marcasEje(10)) === '[0,5,10]', marcasEje(10))
check('con uno, sin repetir', JSON.stringify(marcasEje(1)) === '[0,1]', marcasEje(1))
check('vacío, solo el cero', JSON.stringify(marcasEje(0)) === '[0]')

console.log('\n== Lo que se imprime ==')
const VISTA = readFileSync(new URL('../src/modules/pqrs/InformePQRS.jsx', import.meta.url), 'utf8')
const LAYOUT = readFileSync(new URL('../src/core/components/Layout.jsx', import.meta.url), 'utf8')
check('el PDF sale de la hoja de imprimir', /window\.print\(\)/.test(VISTA))
check('los controles no salen en el PDF', /print:hidden/.test(VISTA))
check('ni el menú ni la cabecera', (LAYOUT.match(/print:hidden/g) || []).length >= 2)
check('la pantalla no cuenta: no hay .length de PQRS sumando', !/\.filter\([^)]*estado/.test(VISTA))

console.log()
if (fallos.length) { console.log(`FALLARON ${fallos.length}: ${fallos.join(', ')}`); process.exit(1) }
console.log('TODAS LAS PRUEBAS PASARON')
