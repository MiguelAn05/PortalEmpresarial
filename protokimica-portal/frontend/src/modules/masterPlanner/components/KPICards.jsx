import { alertaVencimiento } from "../constants"

/**
 * Tarjetas de resumen. Mismo lenguaje visual que las de PQRS (borde superior
 * de color, etiqueta pequeña, número grande) para que el portal se lea igual
 * en todos los módulos.
 */
export function TarjetasKPI({ tarjetas }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-4">
      {tarjetas.map(({ label, value, color, nota, alerta }) => (
        <div
          key={label}
          className={`bg-white rounded-xl border border-[#D6E0F0] border-t-4 ${color} p-4`}
        >
          <div className="text-xs font-semibold text-[#6B7EA8] uppercase tracking-wide">{label}</div>
          <div className={`text-3xl font-bold mt-1 ${alerta ? 'text-[#D93B3B]' : 'text-[#0D2B5E]'}`}>
            {value}
          </div>
          {nota && <div className="text-[11px] text-[#9BACC8] mt-0.5">{nota}</div>}
        </div>
      ))}
    </div>
  )
}

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
      { label: 'Total tareas',   value: total,     color: 'border-t-[#0D2B5E]' },
      { label: 'Abiertas',       value: abiertas,  color: 'border-t-[#1A4FA0]' },
      { label: 'Alta prioridad', value: criticas,  color: 'border-t-[#F5A800]' },
      {
        label: 'Vencidas', value: vencidas, color: 'border-t-[#D93B3B]',
        alerta: vencidas > 0,
        nota: porVencer > 0 ? `${porVencer} por vencer` : null,
      },
      { label: 'Avance promedio', value: `${avancePromedio}%`, color: 'border-t-[#2E9E6B]' },
    ]} />
  )
}
