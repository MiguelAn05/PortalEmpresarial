// Marcaciones: lo que se puede romper en silencio en la pantalla —filtrar la
// lista, avisar de datos atrasados, armar las fechas del informe— y que las
// etiquetas coincidan con las claves del backend.
import { readFileSync } from 'node:fs'
import { PRESENCIAS, NOVEDADES, VISTAS, ESTADOS_MARCA } from '../src/modules/marcaciones/constants.js'
import {
  avisoDeAtraso, coincideConVista, contarFoco, contarPorVista, filaCumpleFoco, filasDeNovedades, filtrarPersonas,
  FOCOS_INFORME, moverDia, periodosRapidos, personaCumpleFoco, textoUltimaMarca,
} from '../src/modules/marcaciones/resumen.js'
import { puedeVerModulo, moduloDeRuta } from '../src/core/modulos.js'

let fallos = []
const check = (n, cond, extra = '') => {
  console.log((cond ? '  OK   ' : '  FALLA') + `  ${n}` + (!cond && extra ? `  -> ${JSON.stringify(extra)}` : ''))
  if (!cond) fallos.push(n)
}

const PY = readFileSync(new URL('../../backend/app/modules/marcaciones/constants.py', import.meta.url), 'utf8')
const clavesDe = (nombre) => {
  const bloque = PY.match(new RegExp(`${nombre} = \\{(.*?)\\n\\}`, 's'))?.[1] ?? ''
  return [...bloque.matchAll(/^\s*"(\w+)":/gm)].map(m => m[1])
}

console.log('\n== Las claves son las del backend ==')
check('presencias', JSON.stringify(clavesDe('PRESENCIAS')) === JSON.stringify(Object.keys(PRESENCIAS)), clavesDe('PRESENCIAS'))
check('novedades', JSON.stringify(clavesDe('NOVEDADES')) === JSON.stringify(Object.keys(NOVEDADES)), clavesDe('NOVEDADES'))
check('toda vista (salvo todos y novedades) es una presencia',
  VISTAS.every(v => ['todos', 'novedades'].includes(v.clave) || PRESENCIAS[v.clave]))

const p = (nombre, area, presencia, novedades = []) => ({ emp_code: nombre, nombre, area, presencia, novedades })
const PERSONAS = [
  p('Ana Peña', 'TICS', 'adentro'),
  p('Beto', 'TICS', 'adentro', [{ tipo: 'llegada_tarde' }]),
  p('Carla', 'Calidad', 'ausente', [{ tipo: 'ausencia' }]),
  p('Luis', 'Logística', 'en_descanso'),
  p('Eva', null, 'salio'),
]
const LIDERES = [{ lider: 'Tico', areas: ['TICS'] }, { lider: 'Cali', areas: ['Calidad', 'Logística'] }]

console.log('\n== La lista y las tarjetas usan la misma regla ==')
check('todos', filtrarPersonas(PERSONAS, {}).length === 5)
check('adentro', filtrarPersonas(PERSONAS, { vista: 'adentro' }).length === 2)
check('novedades', filtrarPersonas(PERSONAS, { vista: 'novedades' }).map(x => x.nombre).join() === 'Beto,Carla')
check('el conteo de cada vista coincide con la lista', VISTAS.every(v =>
  contarPorVista(PERSONAS)[v.clave] === filtrarPersonas(PERSONAS, { vista: v.clave }).length))
check('coincideConVista sin vista deja pasar', coincideConVista(PERSONAS[0], ''))

console.log('\n== Área, líder y buscador ==')
check('por área', filtrarPersonas(PERSONAS, { area: 'TICS' }).length === 2)
check('sin área se llama «Sin área»', filtrarPersonas(PERSONAS, { area: 'Sin área' }).map(x => x.nombre).join() === 'Eva')
check('por líder: sus áreas', filtrarPersonas(PERSONAS, { lider: 'Cali' }, LIDERES).map(x => x.nombre).join() === 'Carla,Luis')
check('líder desconocido no filtra por líder', filtrarPersonas(PERSONAS, { lider: 'Nadie' }, LIDERES).length === 5)
check('el buscador ignora tildes y mayúsculas', filtrarPersonas(PERSONAS, { buscar: 'PENA' }).length === 1)
check('combina filtros', filtrarPersonas(PERSONAS, { area: 'TICS', vista: 'novedades' }).map(x => x.nombre).join() === 'Beto')

console.log('\n== Textos ==')
check('última marcación', textoUltimaMarca({ hora: '12:40', estado: '3' }) === '12:40 · Regresa de descanso')
check('sin marcación', textoUltimaMarca(null) === '—')
check('estados del reloj', Object.keys(ESTADOS_MARCA).length === 6)

console.log('\n== El aviso de datos atrasados ==')
check('al día: sin aviso', avisoDeAtraso({ nunca: false, atrasado: false }, true) === null)
check('un día pasado no avisa', avisoDeAtraso({ nunca: false, atrasado: true, minutos_sin_datos: 500 }, false) === null)
check('atrasado en minutos', /35 minutos/.test(avisoDeAtraso({ atrasado: true, minutos_sin_datos: 35 }, true)))
check('atrasado en horas', /3 horas/.test(avisoDeAtraso({ atrasado: true, minutos_sin_datos: 200 }, true)))
check('incluye el último error', /clave inválida/.test(avisoDeAtraso({ atrasado: true, minutos_sin_datos: 20, ultimo_error: 'clave inválida' }, true)))
check('nunca ha llegado nada lo dice', /Todavía no ha llegado/.test(avisoDeAtraso({ nunca: true, atrasado: true }, true)))

console.log('\n== Fechas ==')
check('mover un día', moverDia('2026-11-05', -1) === '2026-11-04')
check('cambio de mes', moverDia('2026-11-01', -1) === '2026-10-31')
check('cambio de año', moverDia('2026-12-31', 1) === '2027-01-01')
const r = periodosRapidos(new Date(2026, 10, 5))       // jueves 5 nov 2026
const porClave = Object.fromEntries(r.map(x => [x.clave, x]))
check('hoy', porClave.hoy.desde === '2026-11-05' && porClave.hoy.hasta === '2026-11-05')
check('esta semana empieza el lunes', porClave.semana.desde === '2026-11-02', porClave.semana)
check('este mes', porClave.mes.desde === '2026-11-01')
check('mes pasado', porClave.mes_pasado.desde === '2026-10-01' && porClave.mes_pasado.hasta === '2026-10-31', porClave.mes_pasado)
const domingo = periodosRapidos(new Date(2026, 10, 8)).find(x => x.clave === 'semana')
check('en domingo la semana sigue empezando el lunes', domingo.desde === '2026-11-02', domingo)

console.log('\n== Novedades para las barras ==')
const filas = filasDeNovedades({ total_novedades: 4, novedades: { llegada_tarde: 3, ausencia: 1, exceso_break: 0 } }, NOVEDADES)
check('sin ceros y de mayor a menor', filas.map(f => f.clave).join() === 'llegada_tarde,ausencia', filas)
check('porcentaje', filas[0].pct === 75)

console.log('\n== Las tarjetas del informe filtran ==')
const FILAS_INF = [
  { emp_code: 'B', novedades: [{ tipo: 'llegada_tarde' }, { tipo: 'exceso_break' }] },
  { emp_code: 'B', novedades: [{ tipo: 'llegada_tarde' }] },
  { emp_code: 'C', novedades: [{ tipo: 'ausencia' }] },
  { emp_code: 'A', novedades: [] },
]
const POR_PERSONA = [
  { emp_code: 'B', total_novedades: 3, llegada_tarde: 2, ausencia: 0 },
  { emp_code: 'C', total_novedades: 1, llegada_tarde: 0, ausencia: 1 },
  { emp_code: 'A', total_novedades: 0, llegada_tarde: 0, ausencia: 0 },
]
check('sin foco, todo', contarFoco(FILAS_INF, '') === 4 && POR_PERSONA.every(x => personaCumpleFoco(x, '')))
check('con novedades: los días con alguna', contarFoco(FILAS_INF, 'con_novedad') === 3)
check('llegadas tarde: una por día', contarFoco(FILAS_INF, 'llegada_tarde') === 2)
check('ausencias', contarFoco(FILAS_INF, 'ausencia') === 1)
check('por persona: las que tienen ese tipo', ['con_novedad', 'llegada_tarde', 'ausencia'].map(f =>
  POR_PERSONA.filter(x => personaCumpleFoco(x, f)).map(x => x.emp_code).join()).join('|') === 'B,C|B|C')
check('cada foco es una novedad del backend (o «con novedad»)',
  Object.keys(FOCOS_INFORME).every(f => f === 'con_novedad' || NOVEDADES[f]))
check('la tabla y la cifra son la misma cuenta',
  Object.keys(FOCOS_INFORME).every(f => FILAS_INF.filter(x => filaCumpleFoco(x, f)).length === contarFoco(FILAS_INF, f)))

console.log('\n== Acceso ==')
check('el líder y el agente entran', ['lider', 'agente'].every(rol => puedeVerModulo({ rol }, 'marcaciones')))
check('lectura no, ni con la capacidad', !puedeVerModulo({ rol: 'lectura', capacidades: ['marcaciones.ver_todo'] }, 'marcaciones'))
check('la ruta pertenece al módulo', moduloDeRuta('/marcaciones/informe') === 'marcaciones')

console.log()
if (fallos.length) { console.log(`FALLARON ${fallos.length}: ${fallos.join(', ')}`); process.exit(1) }
console.log('TODAS LAS PRUEBAS PASARON')
