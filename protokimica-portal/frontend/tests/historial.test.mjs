// Pruebas del formateo del historial de cambios.
const base = '../src/modules/masterPlanner/constants.js'
const { etiquetaCampo, valorHistorial, diasDesplazados, CAMPOS_HISTORIAL, SALUD } = await import(base)

let fallos = []
const check = (n, cond, extra = '') => {
  console.log((cond ? '  OK   ' : '  FALLA') + `  ${n}` + (!cond && extra ? `  -> ${JSON.stringify(extra)}` : ''))
  if (!cond) fallos.push(n)
}

console.log('\n== Etiquetas ==')
check('traduce fecha_fin_estimada', etiquetaCampo('fecha_fin_estimada') === 'Fecha de entrega')
check('traduce asignado_a', etiquetaCampo('asignado_a') === 'Responsable')
check('traduce lider_id', etiquetaCampo('lider_id') === 'Líder')
check('un campo desconocido se muestra tal cual', etiquetaCampo('campo_raro') === 'campo_raro')

console.log('\n== Valores ==')
check('estado de tarea se traduce', valorHistorial('estado', 'en_proceso') === 'En proceso',
  valorHistorial('estado', 'en_proceso'))
check('estado de proyecto también', valorHistorial('estado', 'en_ejecucion') === 'En ejecución',
  valorHistorial('estado', 'en_ejecucion'))
check('prioridad se traduce', valorHistorial('prioridad', 'critica') === 'Crítica')
check('el avance lleva %', valorHistorial('avance_pct', '40') === '40%')
check('archivado se lee como Sí/No', valorHistorial('archivado', 'si') === 'Sí')
check('un valor nulo dice "sin definir"', valorHistorial('area', null) === 'sin definir')
check('un valor vacío también', valorHistorial('area', '') === 'sin definir')
check('el responsable ya viene resuelto por nombre', valorHistorial('asignado_a', 'Ana Ruiz') === 'Ana Ruiz')
const fecha = valorHistorial('fecha_fin_estimada', '2026-09-30T17:00:00+00:00')
check('las fechas se formatean legibles', /2026/.test(fecha) && !/T/.test(fecha), fecha)

console.log('\n== Días desplazados ==')
const desplazo = (campo, a, b) => diasDesplazados({ campo, valor_anterior: a, valor_nuevo: b })
check('detecta un aplazamiento',
  desplazo('fecha_fin_estimada', '2026-08-15T00:00:00Z', '2026-09-30T00:00:00Z') === 46,
  desplazo('fecha_fin_estimada', '2026-08-15T00:00:00Z', '2026-09-30T00:00:00Z'))
check('detecta un adelanto (negativo)',
  desplazo('fecha_fin', '2026-09-30T00:00:00Z', '2026-09-20T00:00:00Z') === -10)
check('no aplica a campos que no son fecha',
  desplazo('estado', 'pendiente', 'en_proceso') === null)
check('si no había fecha antes, no cuenta como desplazamiento',
  desplazo('fecha_fin', null, '2026-09-30T00:00:00Z') === null)
check('valores inválidos no revientan',
  desplazo('fecha_fin', 'nada', 'tampoco') === null)
check('cambio dentro del mismo día da 0',
  desplazo('fecha_fin', '2026-09-30T08:00:00Z', '2026-09-30T09:00:00Z') === 0)

console.log('\n== Tipos declarados ==')
check('los textos largos están marcados como tal',
  ['objetivo', 'alcance', 'descripcion', 'riesgos'].every(c => CAMPOS_HISTORIAL[c].tipo === 'texto_largo'))
check('los eventos de presupuesto están marcados como evento',
  ['presupuesto_agregado', 'presupuesto_eliminado', 'presupuesto_ejecutado']
    .every(c => CAMPOS_HISTORIAL[c].tipo === 'evento'))
check('todos los campos de fecha son tipo fecha',
  ['fecha_inicio', 'fecha_fin', 'fecha_fin_estimada', 'fecha_fin_real']
    .every(c => CAMPOS_HISTORIAL[c].tipo === 'fecha'))
check('todo campo tiene etiqueta y tipo',
  Object.values(CAMPOS_HISTORIAL).every(c => c.label && c.tipo))

console.log('\n== Semáforo ==')
check('están los cinco estados de salud del backend',
  ['verde', 'amarillo', 'rojo', 'cerrado', 'sin_datos'].every(k => SALUD[k]?.label))

console.log()
if (fallos.length) { console.log(`FALLARON ${fallos.length}: ${fallos.join(', ')}`); process.exit(1) }
console.log('TODAS LAS PRUEBAS PASARON')
