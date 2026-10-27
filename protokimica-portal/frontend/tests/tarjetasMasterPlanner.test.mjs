// Las tarjetas de Master Planner se pulsan, como en PQRS.
//
// Lo que se prueba: la cifra de cada tarjeta y el filtro que aplica salen de
// la misma regla (`FOCOS_TAREAS`), «Limpiar filtros» también suelta la
// tarjeta, `de_area` cuenta como el Resumen del servidor (responsable o
// participante) y las vistas cuentan sobre la lista ya filtrada.
import { readFileSync } from 'node:fs'
import {
  FILTROS_TAREAS_VACIOS, FOCOS_TAREAS, contarFocosTareas, cumpleFocoTarea, filtrarTareas,
} from '../src/modules/masterPlanner/constants.js'

let fallos = []
const check = (n, cond, extra = '') => {
  console.log((cond ? '  OK   ' : '  FALLA') + `  ${n}` + (!cond && extra ? `  -> ${JSON.stringify(extra)}` : ''))
  if (!cond) fallos.push(n)
}

const ayer = new Date(Date.now() - 86400000).toISOString()
const enUnMes = new Date(Date.now() + 30 * 86400000).toISOString()
const tareas = [
  { id: 1, proyecto_id: 10, estado: 'en_proceso', prioridad: 'alta', fecha_fin: ayer, avance_pct: 20, titulo: 'a' },
  { id: 2, proyecto_id: 10, estado: 'pendiente', prioridad: 'media', fecha_fin: enUnMes, avance_pct: 0, titulo: 'b' },
  { id: 3, proyecto_id: 20, estado: 'completada', prioridad: 'critica', fecha_fin: ayer, avance_pct: 100, titulo: 'c' },
  { id: 4, proyecto_id: 20, estado: 'pendiente', prioridad: 'critica', fecha_fin: null, avance_pct: 0, titulo: 'd' },
]
const proyectos = [
  { id: 10, area: 'TICS', areas_participantes: ['Calidad'] },
  { id: 20, area: 'Calidad', areas_participantes: [] },
]

console.log('\n== La cifra y el filtro son la misma regla ==')
const cuenta = contarFocosTareas(tareas)
for (const f of FOCOS_TAREAS) {
  const filtradas = filtrarTareas(tareas, { foco: f.clave })
  check(`«${f.label}»: la tarjeta dice ${cuenta[f.clave]} y la lista muestra lo mismo`,
    filtradas.length === cuenta[f.clave], { cuenta: cuenta[f.clave], lista: filtradas.map(t => t.id) })
}
check('abiertas: todo menos lo completado', cuenta.abiertas === 3, cuenta)
check('alta prioridad: alta y crítica sin completar', cuenta.alta_prioridad === 2, cuenta)
check('vencidas: la completada no vence', cuenta.vencidas === 1, cuenta)
check('sin foco no esconde nada', tareas.every(t => cumpleFocoTarea(t, '')))
check('un foco desconocido (enlace viejo) tampoco', tareas.every(t => cumpleFocoTarea(t, 'no_existe')))

console.log('\n== «Limpiar filtros» suelta la tarjeta ==')
check('el foco está entre los filtros vacíos', FILTROS_TAREAS_VACIOS.foco === '')
check('y el área que llega del Resumen también', FILTROS_TAREAS_VACIOS.de_area === '')

console.log('\n== Desde el Resumen: las tareas de los PROYECTOS del área ==')
const deCalidad = filtrarTareas(tareas, { de_area: 'Calidad' }, proyectos)
check('Calidad participa en el 10 y es responsable del 20: las cuatro', deCalidad.length === 4, deCalidad.map(t => t.id))
const deTics = filtrarTareas(tareas, { de_area: 'TICS' }, proyectos)
check('TICS solo en el 10', deTics.map(t => t.id).join() === '1,2', deTics.map(t => t.id))
check('se combina con la tarjeta', filtrarTareas(tareas, { de_area: 'TICS', foco: 'vencidas' }, proyectos).map(t => t.id).join() === '1')

console.log('\n== Las pantallas lo usan así ==')
const leer = (r) => readFileSync(new URL(`../src/modules/masterPlanner/${r}`, import.meta.url), 'utf8')
const kpis = leer('components/KPICards.jsx')
check('las tarjetas cuentan con contarFocosTareas', kpis.includes('contarFocosTareas('))
for (const vista of ['views/TareasView.jsx', 'views/ProyectoDetalle.jsx']) {
  const texto = leer(vista)
  check(`${vista}: cuenta sin su propio recorte`, texto.includes("foco: ''") && texto.includes('<KPICards tareas={base}'))
  check(`${vista}: las tarjetas filtran`, texto.includes('onFoco='))
}
const resumen = leer('views/ResumenView.jsx')
check('el Resumen manda las tareas con de_area, no con el área de la tarea', /de_area:\s*area/.test(resumen))
check('y limpia los demás filtros de la pestaña', resumen.includes('...FILTROS_TAREAS_VACIOS, foco'))
check('«Proyectos en riesgo» recorta con los semáforos de riesgo', resumen.includes('SALUD_EN_RIESGO.includes(p.salud)'))

if (fallos.length) { console.log(`\n${fallos.length} FALLARON`); process.exit(1) }
