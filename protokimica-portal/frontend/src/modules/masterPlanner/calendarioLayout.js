/**
 * Cálculo de posiciones de las barras del calendario. Va aparte del
 * componente porque es pura aritmética de fechas y se puede verificar sin
 * montar React.
 */
import { inicioDia, rangoTarea } from './constants.js'

export function diasEntre(a, b) {
  return Math.round((inicioDia(b) - inicioDia(a)) / 86400000)
}

/**
 * Recorta cada tarea al tramo que cae dentro de esta semana y le asigna el
 * primer carril (fila) libre. Las tareas más largas van arriba para que las
 * barras de varios días no queden picadas entre carriles.
 *
 * Devuelve, por tarea visible en la semana: columnas de inicio/fin (0-6),
 * carril, y si la barra viene de antes o sigue después de esta semana.
 */
export function calcularBarras(tareas, semana) {
  const inicioSemana = semana[0]
  const finSemana = semana[6]

  const candidatas = tareas
    .map(t => ({ tarea: t, rango: rangoTarea(t) }))
    .filter(({ rango }) => rango && rango.hasta >= inicioSemana && rango.desde <= finSemana)
    .map(({ tarea, rango }) => {
      const desdeCol = Math.max(0, diasEntre(inicioSemana, rango.desde))
      const hastaCol = Math.min(6, diasEntre(inicioSemana, rango.hasta))
      return {
        tarea, desdeCol, hastaCol,
        continuaAntes: rango.desde < inicioSemana,
        continuaDespues: rango.hasta > finSemana,
        largo: hastaCol - desdeCol,
      }
    })
    // Orden estable: primero las más largas, luego por día de inicio, y el id
    // desempata para que dos renders seguidos den exactamente el mismo layout.
    .sort((a, b) => b.largo - a.largo || a.desdeCol - b.desdeCol || a.tarea.id - b.tarea.id)

  const carriles = [] // carriles[i] = tramos [desdeCol, hastaCol] ya ocupados
  return candidatas.map(barra => {
    let carril = 0
    while (carriles[carril]?.some(([d, h]) => barra.desdeCol <= h && barra.hastaCol >= d)) carril++
    carriles[carril] = carriles[carril] || []
    carriles[carril].push([barra.desdeCol, barra.hastaCol])
    return { ...barra, carril }
  })
}

/** Cuántas barras quedan escondidas en cada día al cortar en `limite` carriles. */
export function contarOcultasPorDia(barras, limite) {
  return Array.from({ length: 7 }, (_, col) =>
    barras.filter(b => b.carril >= limite && col >= b.desdeCol && col <= b.hastaCol).length)
}

/** Agrupa días consecutivos por mes, para la cabecera del cronograma. */
export function agruparPorMes(dias, nombresMes) {
  const grupos = []
  dias.forEach(d => {
    const etiqueta = `${nombresMes[d.getMonth()]} ${d.getFullYear()}`
    const ultimo = grupos[grupos.length - 1]
    if (ultimo?.etiqueta === etiqueta) ultimo.cantidad++
    else grupos.push({ etiqueta, cantidad: 1 })
  })
  return grupos
}
