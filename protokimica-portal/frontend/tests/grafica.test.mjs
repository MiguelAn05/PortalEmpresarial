// La geometria de la grafica del inicio: escala, barras y contorno.
// Es lo que se rompe sin avisar — una barra recortada sigue viendose bien.
import {
  escalaY, maximoDeLaSerie, hayMovimiento, geometriaBarras, contornoBarra,
} from '../src/modules/inicio/grafica.js'

let fallos = []
const check = (n, cond, extra = '') => {
  console.log((cond ? '  OK   ' : '  FALLA') + `  ${n}` + (!cond && extra ? `  -> ${JSON.stringify(extra)}` : ''))
  if (!cond) fallos.push(n)
}

const serie = [
  { etiqueta: 'Ene', aprobado: 10_000_000, pagado: 6_000_000 },
  { etiqueta: 'Feb', aprobado: 20_000_000, pagado: 18_000_000 },
  { etiqueta: 'Mar', aprobado: 0, pagado: 0 },
]

console.log('\n== Escala del eje ==')
// Lo critico: el tope NUNCA puede quedar por debajo del dato, o la barra
// mas alta se sale del area de dibujo y nadie lo nota.
for (const valor of [1, 7, 99, 100, 36_400_000, 67_500_770, 1_250_000_000]) {
  check(`el tope cubre ${valor}`, escalaY(valor).tope >= valor, escalaY(valor).tope)
}
check('los cortes van de cero al tope', (() => {
  const { tope, ticks } = escalaY(36_400_000)
  return ticks[0] === 0 && ticks.at(-1) === tope
})())
check('el tope es un numero redondo', escalaY(36_400_000).tope === 40_000_000)
check('sin datos no inventa escala', escalaY(0).tope === 0)
check('un negativo no rompe nada', escalaY(-5).tope === 0)
check('un texto tampoco', escalaY('mucho').tope === 0)

console.log('\n== Maximo de la serie ==')
check('mira las dos medidas', maximoDeLaSerie(serie) === 20_000_000)
check('sin serie da cero', maximoDeLaSerie(null) === 0)
check('un mes sin movimiento no es "sin datos"', hayMovimiento(serie) === true)
check('todo en cero si es sin movimiento',
  hayMovimiento([{ aprobado: 0, pagado: 0 }]) === false)

console.log('\n== Geometria de las barras ==')
const alto = 200
const barras = geometriaBarras(serie, { ancho: 300, alto })
check('una entrada por mes', barras.length === 3)
check('ninguna barra se sale por arriba',
  barras.every(b => b.aprobadoRect.y >= 0 && b.pagadoRect.y >= 0))
check('ninguna barra pasa de la linea base',
  barras.every(b => b.aprobadoRect.y + b.aprobadoRect.alto <= alto + 0.001))
// Lado a lado, no una encima de la otra: superponerlas afirmaria que lo
// pagado sale de lo aprobado ESE mes, y no es cierto.
check('las dos barras del mes no se pisan',
  barras.every(b => b.aprobadoRect.x + b.aprobadoRect.ancho <= b.pagadoRect.x))
check('el mes sin movimiento mide cero',
  barras[2].aprobadoRect.alto === 0 && barras[2].pagadoRect.alto === 0)
check('la barra mas alta llega al area util',
  barras[1].aprobadoRect.alto === alto, barras[1].aprobadoRect.alto)
check('conserva la etiqueta del mes', barras[0].etiqueta === 'Ene')

console.log('\n== Casos que dejaban la pantalla en blanco ==')
check('serie vacia no revienta', geometriaBarras([], { ancho: 300, alto: 200 }).length === 0)
check('serie nula tampoco', geometriaBarras(null, { ancho: 300, alto: 200 }).length === 0)
check('ancho cero no revienta', geometriaBarras(serie, { ancho: 0, alto: 200 }).length === 0)
const todoCero = geometriaBarras(
  [{ etiqueta: 'Ene', aprobado: 0, pagado: 0 }], { ancho: 300, alto: 200 })
check('todo en cero da alturas finitas, no NaN',
  Number.isFinite(todoCero[0].aprobadoRect.alto) && todoCero[0].aprobadoRect.alto === 0,
  todoCero[0].aprobadoRect)

console.log('\n== Contorno de la barra ==')
const d = contornoBarra({ x: 10, y: 100, ancho: 14, alto: 100 })
check('empieza en la linea base', d.startsWith('M10 200'))
check('cierra la figura', d.endsWith('Z'))
check('una barra de alto cero no dibuja nada',
  contornoBarra({ x: 0, y: 0, ancho: 14, alto: 0 }) === '')
// Con una barra mas baja que el radio, el arco se pasaria de largo y la
// figura saldria torcida.
check('una barra muy baja no se deforma',
  !contornoBarra({ x: 0, y: 0, ancho: 14, alto: 2 }).includes('A3 3'))

console.log()
if (fallos.length) { console.log(`FALLARON ${fallos.length}: ${fallos.join(', ')}`); process.exit(1) }
console.log('TODAS LAS PRUEBAS PASARON')
