// Lo que el inicio calcula sin pintar nada: plazos en palabras, orden de las
// tarjetas y el tono de los pendientes.
import {
  saludo, plazoRelativo, ordenTarjetas, tonoPendientes, primerNombre,
} from '../src/modules/inicio/resumen.js'

let fallos = []
const check = (n, cond, extra = '') => {
  console.log((cond ? '  OK   ' : '  FALLA') + `  ${n}` + (!cond && extra ? `  -> ${JSON.stringify(extra)}` : ''))
  if (!cond) fallos.push(n)
}

const a = (y, m, d, h = 9) => new Date(y, m - 1, d, h)

console.log('\n== Saludo ==')
check('a las 7 a.m. es de dias', saludo(a(2026, 8, 17, 7)) === 'Buenos días')
check('a las 11:59 todavia', saludo(new Date(2026, 7, 17, 11, 59)) === 'Buenos días')
check('al mediodia ya es tarde', saludo(a(2026, 8, 17, 12)) === 'Buenas tardes')
check('a las 8 p.m. es noche', saludo(a(2026, 8, 17, 20)) === 'Buenas noches')

console.log('\n== Plazos en palabras ==')
const hoy = a(2026, 8, 17, 15)
check('sin fecha lo dice', plazoRelativo(null, hoy).texto === 'Sin fecha')
check('sin fecha no es urgente', plazoRelativo(null, hoy).urgente === false)

// Lo mas importante: algo que vence HOY mas tarde no puede leerse "manana".
check('vence hoy a las 6 p.m. -> hoy',
  plazoRelativo(a(2026, 8, 17, 18), hoy).texto === 'Vence hoy',
  plazoRelativo(a(2026, 8, 17, 18), hoy))
check('vencio hoy a las 8 a.m. tambien dice hoy',
  plazoRelativo(a(2026, 8, 17, 8), hoy).texto === 'Vence hoy')
check('y hoy cuenta como urgente', plazoRelativo(a(2026, 8, 17, 8), hoy).urgente === true)
check('pero no como vencido', plazoRelativo(a(2026, 8, 17, 8), hoy).vencido === false)

check('manana', plazoRelativo(a(2026, 8, 18, 6), hoy).texto === 'Vence mañana')
check('manana es urgente', plazoRelativo(a(2026, 8, 18), hoy).urgente === true)
check('en tres dias', plazoRelativo(a(2026, 8, 20), hoy).texto === 'Vence en 3 días')
check('en tres dias ya no es urgente', plazoRelativo(a(2026, 8, 20), hoy).urgente === false)

check('ayer', plazoRelativo(a(2026, 8, 16), hoy).texto === 'Venció ayer')
check('ayer esta vencido', plazoRelativo(a(2026, 8, 16), hoy).vencido === true)
check('hace cuatro dias', plazoRelativo(a(2026, 8, 13), hoy).texto === 'Venció hace 4 días')
// Cruzar mes: restar dias a mano fallaria aqui.
check('cruza el cambio de mes',
  plazoRelativo(a(2026, 8, 31), a(2026, 9, 2, 10)).texto === 'Venció hace 2 días',
  plazoRelativo(a(2026, 8, 31), a(2026, 9, 2, 10)))

console.log('\n== Orden de las tarjetas ==')
check('gerencia abre con los numeros', ordenTarjetas({ rol: 'gerencia' })[0] === 'empresa')
check('un lider abre con lo suyo', ordenTarjetas({ rol: 'lider' })[0] === 'pendientes')
check('un agente tambien', ordenTarjetas({ rol: 'agente' })[0] === 'pendientes')
check('sin usuario no revienta', ordenTarjetas(null)[0] === 'pendientes')
check('siempre estan las cuatro',
  ['gerencia', 'lider', 'agente', 'admin', 'lectura']
    .every(rol => new Set(ordenTarjetas({ rol })).size === 4))

console.log('\n== Tono de los pendientes ==')
const tono = (urgente, pendiente) => tonoPendientes({ total_urgente: urgente, total_pendiente: pendiente })
check('al dia va en verde', tono(0, 0).borde.includes('#2E9E6B'))
check('y lo dice con palabras', tono(0, 0).titulo === 'Estás al día')
check('con plazos cerca va en ambar', tono(0, 3).borde.includes('#F5A800'))
check('con algo vencido va en rojo', tono(2, 5).borde.includes('#D93B3B'))
// El numero va en el titulo, no solo en el color: el color no se lee en voz alta.
check('el titulo dice cuantas hay', tono(2, 5).titulo === 'Tienes 2 cosas vencidas')
check('una sola va en singular', tono(1, 1).titulo === 'Tienes 1 cosa vencida')
check('sin datos no inventa nada', tonoPendientes(null).titulo === 'Lo que te toca hoy')

console.log('\n== Nombre para saludar ==')
check('toma el primer nombre', primerNombre('Miguel Angel Vargas') === 'Miguel')
check('aguanta espacios de mas', primerNombre('  Ana   Maria ') === 'Ana')
check('sin nombre devuelve vacio', primerNombre(null) === '')

console.log()
if (fallos.length) { console.log(`FALLARON ${fallos.length}: ${fallos.join(', ')}`); process.exit(1) }
console.log('TODAS LAS PRUEBAS PASARON')
