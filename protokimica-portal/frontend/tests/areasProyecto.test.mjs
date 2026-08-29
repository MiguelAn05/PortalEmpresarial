// Filtrar proyectos por área cuenta también las áreas participantes.
const BASE = '../src/modules/masterPlanner/constants.js'
const { perteneceAlArea } = await import(BASE)

let fallos = []
const check = (n, cond, extra = '') => {
  console.log((cond ? '  OK   ' : '  FALLA') + `  ${n}` + (!cond && extra ? `  -> ${JSON.stringify(extra)}` : ''))
  if (!cond) fallos.push(n)
}

const wms = { nombre: 'Portal WMS', area: 'TICS', areas_participantes: ['Mercadeo', 'Comercial'] }
const solo = { nombre: 'Servidores', area: 'TICS', areas_participantes: [] }

console.log('\n== A qué área pertenece un proyecto ==')
check('el área responsable lo ve', perteneceAlArea(wms, 'TICS'))
check('un área participante también', perteneceAlArea(wms, 'Mercadeo'))
check('y la otra participante', perteneceAlArea(wms, 'Comercial'))
check('un área ajena no', perteneceAlArea(wms, 'Calidad') === false)
check('sin participantes solo cuenta la responsable',
  perteneceAlArea(solo, 'TICS') && perteneceAlArea(solo, 'Mercadeo') === false)

console.log('\n== Casos límite ==')
check('sin filtro pasan todos', perteneceAlArea(wms, ''))
check('filtro nulo pasa todos', perteneceAlArea(wms, null))
check('un proyecto sin áreas no revienta',
  perteneceAlArea({ nombre: 'X' }, 'TICS') === false)
check('un proyecto indefinido tampoco',
  perteneceAlArea(undefined, 'TICS') === false)
check('sin lista de participantes no revienta',
  perteneceAlArea({ area: 'TICS' }, 'Mercadeo') === false)

console.log()
if (fallos.length) { console.log(`FALLARON ${fallos.length}: ${fallos.join(', ')}`); process.exit(1) }
console.log('TODAS LAS PRUEBAS PASARON')
