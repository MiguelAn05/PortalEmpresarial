import { alertaVencimiento } from "../constants"
import TarjetasKPI from "../../../core/components/TarjetasKPI.jsx"

/** Tarjetas calculadas a partir de una lista de tareas ya cargada en el cliente. */
export default function KPICards({ tareas }) {
  const total = tareas.length
  const abiertas = tareas.filter(t => t.estado !== "completada").length
  const criticas = tareas.filter(t => t.estado !== "completada" && (t.prioridad === "alta" || t.prioridad === "critica")).length
  const vencidas = tareas.filter(t => alertaVencimiento(t) === "vencida").length
  const porVencer = tareas.filter(t => alertaVencimiento(t) === "por_vencer").length
  const avancePromedio = total
    ? Math.round(tareas.reduce((sum, t) => sum + t.avance_pct, 0) / total)
    : 0

  return (
    <TarjetasKPI tarjetas={[
      { label: 'Total tareas', value: total, nota: `${abiertas} sin completar` },
      { label: 'Abiertas', value: abiertas, nota: total ? `de ${total}` : 'ninguna registrada' },
      { label: 'Alta prioridad', value: criticas, nota: criticas > 0 ? 'atender primero' : 'ninguna' },
      {
        label: 'Vencidas', value: vencidas,
        alerta: vencidas > 0,
        nota: vencidas > 0
          ? (porVencer > 0 ? `y ${porVencer} por vencer` : 'fuera de plazo')
          : 'ninguna fuera de plazo',
      },
      {
        label: 'Avance promedio', value: `${avancePromedio}%`,
        nota: `${total} ${total === 1 ? 'tarea' : 'tareas'} en el cálculo`,
      },
    ]} />
  )
}
