// Pruebas de la aritmética de fechas del calendario y el cronograma.
import {
  rejillaMes, lunesDeLaSemana, rangoTarea, tareaOcupaDia, sumarDias,
  alertaVencimiento, filtrarTareas, isoADatetimeLocal, datetimeLocalAIso,
  mismoDia, inicioDia,
} from '../src/modules/masterPlanner/constants.js'
import { calcularBarras, contarOcultasPorDia, agruparPorMes, diasEntre }
  from '../src/modules/masterPlanner/calendarioLayout.js'

let fallos = []
const check = (n, cond, extra = '') => {
  console.log((cond ? '  OK   ' : '  FALLA') + `  ${n}` + (!cond && extra ? `  -> ${JSON.stringify(extra)}` : ''))
  if (!cond) fallos.push(n)
}
const d = (s) => new Date(s)
const iso = (a) => a.toISOString().slice(0, 10)

console.log('\n== Rejilla del mes ==')
// Julio 2026: el 1 cae miércoles. La rejilla debe arrancar el lunes 29 jun.
const rej = rejillaMes(d('2026-07-15T12:00:00'))
check('la rejilla tiene 42 días', rej.length === 42, rej.length)
check('arranca en lunes', rej[0].getDay() === 1, rej[0].toString())
check('arranca el 29 de junio', iso(rej[0]) === '2026-06-29', iso(rej[0]))
check('el día 1 de julio está en la rejilla', rej.some(x => iso(x) === '2026-07-01'))
check('el día 31 de julio está en la rejilla', rej.some(x => iso(x) === '2026-07-31'))
check('días consecutivos sin saltos', rej.every((x, i) => i === 0 || diasEntre(rej[i - 1], x) === 1))

// Cambio de horario / fin de mes: febrero de año bisiesto
const feb = rejillaMes(d('2024-02-10T12:00:00'))
check('febrero bisiesto incluye el 29', feb.some(x => iso(x) === '2024-02-29'))
check('lunesDeLaSemana de un domingo da el lunes anterior',
  iso(lunesDeLaSemana(d('2026-07-05T12:00:00'))) === '2026-06-29',
  iso(lunesDeLaSemana(d('2026-07-05T12:00:00'))))
check('lunesDeLaSemana de un lunes se queda igual',
  iso(lunesDeLaSemana(d('2026-07-06T12:00:00'))) === '2026-07-06')

console.log('\n== Rango de una tarea ==')
const conAmbas = { id: 1, fecha_inicio: '2026-07-06T09:00:00Z', fecha_fin: '2026-07-09T17:00:00Z' }
const soloFin = { id: 2, fecha_inicio: null, fecha_fin: '2026-07-08T17:00:00Z' }
const soloInicio = { id: 3, fecha_inicio: '2026-07-08T09:00:00Z', fecha_fin: null }
const sinFechas = { id: 4, fecha_inicio: null, fecha_fin: null }
const invertida = { id: 5, fecha_inicio: '2026-07-10T09:00:00Z', fecha_fin: '2026-07-07T09:00:00Z' }

check('sin fechas no tiene rango', rangoTarea(sinFechas) === null)
check('solo fin ocupa un día', diasEntre(rangoTarea(soloFin).desde, rangoTarea(soloFin).hasta) === 0)
check('solo inicio ocupa un día', diasEntre(rangoTarea(soloInicio).desde, rangoTarea(soloInicio).hasta) === 0)
check('con ambas ocupa 4 días', diasEntre(rangoTarea(conAmbas).desde, rangoTarea(conAmbas).hasta) === 3)
// Si alguien mete el fin antes del inicio, la barra no debe salir negativa.
check('fechas invertidas se ordenan solas',
  rangoTarea(invertida).desde <= rangoTarea(invertida).hasta, rangoTarea(invertida))
check('tareaOcupaDia acierta en un día intermedio', tareaOcupaDia(conAmbas, d('2026-07-07T23:00:00')))
check('tareaOcupaDia rechaza el día siguiente al fin', !tareaOcupaDia(conAmbas, d('2026-07-10T01:00:00')))
check('tareaOcupaDia incluye el propio día de fin', tareaOcupaDia(conAmbas, d('2026-07-09T00:30:00')))

console.log('\n== Carriles de las barras ==')
const semana = Array.from({ length: 7 }, (_, i) => sumarDias(lunesDeLaSemana(d('2026-07-06T12:00:00')), i))
check('la semana de prueba arranca el lunes 6', iso(semana[0]) === '2026-07-06', iso(semana[0]))

const barras1 = calcularBarras([conAmbas, soloFin, soloInicio, sinFechas], semana)
check('las tareas sin fechas no generan barra', barras1.length === 3, barras1.length)

const larga = barras1.find(b => b.tarea.id === 1)
check('la barra larga va del lunes(0) al jueves(3)', larga.desdeCol === 0 && larga.hastaCol === 3, larga)
check('la barra larga toma el carril 0', larga.carril === 0, larga.carril)
check('no se marca como continuada', !larga.continuaAntes && !larga.continuaDespues, larga)

// soloFin (mié 8) y soloInicio (mié 8) se solapan con la larga -> carriles distintos
const carriles = barras1.map(b => b.carril)
check('tres barras solapadas usan tres carriles', new Set(carriles).size === 3, carriles)

// Dos barras que NO se solapan deben compartir carril.
const lunMar = { id: 10, fecha_inicio: '2026-07-06T08:00:00Z', fecha_fin: '2026-07-07T08:00:00Z' }
const jueVie = { id: 11, fecha_inicio: '2026-07-09T08:00:00Z', fecha_fin: '2026-07-10T08:00:00Z' }
const barras2 = calcularBarras([lunMar, jueVie], semana)
check('barras que no se solapan comparten carril',
  barras2[0].carril === 0 && barras2[1].carril === 0, barras2.map(b => b.carril))

// Barra que cruza el borde de la semana
const cruzada = { id: 12, fecha_inicio: '2026-07-01T08:00:00Z', fecha_fin: '2026-07-20T08:00:00Z' }
const [bc] = calcularBarras([cruzada], semana)
check('barra que cruza se recorta a la semana', bc.desdeCol === 0 && bc.hastaCol === 6, bc)
check('se marca que viene de antes', bc.continuaAntes === true)
check('se marca que sigue después', bc.continuaDespues === true)

// Tarea totalmente fuera de la semana
check('tarea fuera de la semana no genera barra',
  calcularBarras([{ id: 13, fecha_inicio: '2026-09-01T08:00:00Z', fecha_fin: '2026-09-02T08:00:00Z' }], semana).length === 0)

// Layout estable entre llamadas (mismo orden de entrada distinto)
const a = calcularBarras([conAmbas, soloFin, soloInicio], semana).map(b => [b.tarea.id, b.carril])
const b = calcularBarras([soloInicio, conAmbas, soloFin], semana).map(x => [x.tarea.id, x.carril])
check('el layout no depende del orden de entrada', JSON.stringify(a) === JSON.stringify(b), { a, b })

console.log('\n== Conteo de ocultas ==')
const ocultas = contarOcultasPorDia(barras1, 1) // solo se muestra el carril 0
check('el miércoles esconde 2 barras', ocultas[2] === 2, ocultas)
check('el lunes no esconde ninguna', ocultas[0] === 0, ocultas)
check('sin límite alcanzado no hay ocultas', contarOcultasPorDia(barras1, 9).every(n => n === 0))

console.log('\n== Cabecera de meses del cronograma ==')
const MESES = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']
const tramo = Array.from({ length: 5 }, (_, i) => sumarDias(d('2026-07-30T12:00:00'), i))
const grupos = agruparPorMes(tramo, MESES)
check('agrupa en dos meses', grupos.length === 2, grupos)
check('julio aporta 2 días', grupos[0].cantidad === 2, grupos)
check('agosto aporta 3 días', grupos[1].cantidad === 3, grupos)
check('las cantidades suman el total', grupos.reduce((s, g) => s + g.cantidad, 0) === 5)

console.log('\n== Alertas de vencimiento ==')
const ahora = new Date()
const enDias = (n) => new Date(ahora.getTime() + n * 86400000).toISOString()
check('pasada y sin completar => vencida',
  alertaVencimiento({ fecha_fin: enDias(-1), estado: 'en_proceso' }) === 'vencida')
check('pasada pero completada => sin alerta',
  alertaVencimiento({ fecha_fin: enDias(-1), estado: 'completada' }) === null)
check('en 2 días => por vencer',
  alertaVencimiento({ fecha_fin: enDias(2), estado: 'pendiente' }) === 'por_vencer')
check('en 10 días => sin alerta',
  alertaVencimiento({ fecha_fin: enDias(10), estado: 'pendiente' }) === null)
check('sin fecha de fin => sin alerta',
  alertaVencimiento({ fecha_fin: null, estado: 'pendiente' }) === null)

console.log('\n== Filtros ==')
const lista = [
  { id: 1, titulo: 'Migrar BD', proyecto_id: 1, area: 'TI', estado: 'en_proceso', prioridad: 'alta', asignado_a: 5, asignado_nombre: 'Ana', fecha_fin: enDias(-2) },
  { id: 2, titulo: 'Auditoría', proyecto_id: 2, area: 'Calidad', estado: 'pendiente', prioridad: 'baja', asignado_a: null, asignado_nombre: null, fecha_fin: null },
  { id: 3, titulo: 'Informe', proyecto_id: 1, area: 'TI', estado: 'completada', prioridad: 'media', asignado_a: 5, asignado_nombre: 'Ana', fecha_fin: enDias(1) },
  { id: 4, titulo: 'Capacitación', proyecto_id: 1, area: 'TI', estado: 'pendiente', prioridad: 'media', asignado_a: null, asignado_nombre: null, fecha_fin: enDias(1) },
]
check('sin filtros devuelve todo', filtrarTareas(lista, {}).length === 4)
check('filtra por proyecto', filtrarTareas(lista, { proyecto_id: 1 }).length === 3)
check('el proyecto compara como texto', filtrarTareas(lista, { proyecto_id: '1' }).length === 3)
check('filtra por responsable', filtrarTareas(lista, { asignado_a: 5 }).length === 2)
check('filtra sin asignar', filtrarTareas(lista, { asignado_a: 'sin_asignar' }).map(t => t.id).join() === '2,4')
check('filtra vencidas', filtrarTareas(lista, { vencimiento: 'vencida' }).map(t => t.id).join() === '1')
check('filtra por vencer (la completada no cuenta)', filtrarTareas(lista, { vencimiento: 'por_vencer' }).map(t => t.id).join() === '4')
check('filtra en riesgo (ambas)', filtrarTareas(lista, { vencimiento: 'en_riesgo' }).map(t => t.id).join() === '1,4')
check('filtra sin fecha', filtrarTareas(lista, { vencimiento: 'sin_fecha' }).map(t => t.id).join() === '2')
check('busca sin distinguir mayúsculas', filtrarTareas(lista, { busqueda: 'MIGRAR' }).length === 1)
check('busca por responsable', filtrarTareas(lista, { busqueda: 'ana' }).length === 2)
check('combina filtros', filtrarTareas(lista, { area: 'TI', estado: 'completada' }).map(t => t.id).join() === '3')

console.log('\n== Ida y vuelta de fecha-hora ==')
// El input datetime-local trabaja en hora local; el backend guarda con zona.
const local = '2026-07-31T14:30'
const idaVuelta = isoADatetimeLocal(datetimeLocalAIso(local))
check('la hora sobrevive el viaje local -> ISO -> local', idaVuelta === local, idaVuelta)
check('un valor vacío da null', datetimeLocalAIso('') === null)
check('un ISO vacío da cadena vacía', isoADatetimeLocal(null) === '')
check('un valor inválido da null', datetimeLocalAIso('no es fecha') === null)

console.log()
if (fallos.length) { console.log(`FALLARON ${fallos.length}: ${fallos.join(', ')}`); process.exit(1) }
console.log('TODAS LAS PRUEBAS PASARON')
