import { alertaVencimiento, contarFocosTareas } from "../constants"
import TarjetasKPI from "../../../core/components/TarjetasKPI.jsx"

/**
 * Tarjetas calculadas a partir de una lista de tareas ya cargada en el cliente.
 *
 * Con `onFoco` son filtros, como en PQRS: «Abiertas», «Alta prioridad» y
 * «Vencidas» recortan la lista de abajo, y «Total» suelta el recorte. La
 * cifra sale de `FOCOS_TAREAS`, la misma regla con que se filtra, y se
 * cuenta sobre `tareas` tal como llega —ya con los demás filtros puestos—:
 * una tarjeta que dice 4 y al pulsarla muestra 1 se desmiente sola.
 * «Avance promedio» no lleva a ningún lado y no se pulsa.
 */
export default function KPICards({ tareas, foco = "", onFoco }) {
  const total = tareas.length
  const { abiertas, alta_prioridad: criticas, vencidas } = contarFocosTareas(tareas)
  const porVencer = tareas.filter(t => alertaVencimiento(t) === "por_vencer").length
  const avancePromedio = total
    ? Math.round(tareas.reduce((sum, t) => sum + t.avance_pct, 0) / total)
    : 0

  // Pulsar la tarjeta activa la suelta.
  const filtro = (clave) => onFoco
    ? { activa: foco === clave, onClick: () => onFoco(foco === clave ? "" : clave) }
    : {}

  return (
    <TarjetasKPI tarjetas={[
      {
        label: 'Total tareas', value: total, nota: `${abiertas} sin completar`,
        ...(onFoco ? { activa: !foco, onClick: () => onFoco("") } : {}),
      },
      { label: 'Abiertas', value: abiertas, nota: total ? `de ${total}` : 'ninguna registrada', ...filtro('abiertas') },
      {
        label: 'Alta prioridad', value: criticas, nota: criticas > 0 ? 'atender primero' : 'ninguna',
        ...filtro('alta_prioridad'),
      },
      {
        label: 'Vencidas', value: vencidas,
        alerta: vencidas > 0,
        nota: vencidas > 0
          ? (porVencer > 0 ? `y ${porVencer} por vencer` : 'fuera de plazo')
          : 'ninguna fuera de plazo',
        ...filtro('vencidas'),
      },
      {
        label: 'Avance promedio', value: `${avancePromedio}%`,
        nota: `${total} ${total === 1 ? 'tarea' : 'tareas'} en el cálculo`,
      },
    ]} />
  )
}
