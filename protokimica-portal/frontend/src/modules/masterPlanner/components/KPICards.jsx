import { alertaVencimiento } from "../constants"

export default function KPICards({ tareas }) {
  const total = tareas.length
  const activas = tareas.filter(t => t.estado === "pendiente" || t.estado === "en_proceso").length
  const bloqueadas = tareas.filter(t => t.estado === "bloqueada").length
  const completadas = tareas.filter(t => t.estado === "completada").length
  const vencidas = tareas.filter(t => alertaVencimiento(t) === "vencida").length
  const porVencer = tareas.filter(t => alertaVencimiento(t) === "por_vencer").length
  const avancePromedio = total
    ? Math.round(tareas.reduce((sum, t) => sum + t.avance_pct, 0) / total)
    : 0

  const cards = [
    { title: "Tareas activas", value: activas, color: "bg-blue-50", border: "border-blue-200", text: "text-blue-700", icon: "📁" },
    {
      title: "Vencidas", value: vencidas, icon: "⏰",
      // La tarjeta solo se pinta de rojo cuando de verdad hay algo vencido;
      // en cero se queda neutra para que la alerta signifique algo.
      color: vencidas ? "bg-red-50" : "bg-gray-50",
      border: vencidas ? "border-red-200" : "border-gray-200",
      text: vencidas ? "text-red-700" : "text-gray-500",
      nota: porVencer > 0 ? `${porVencer} por vencer` : null,
    },
    { title: "Bloqueadas", value: bloqueadas, color: bloqueadas ? "bg-amber-50" : "bg-gray-50", border: bloqueadas ? "border-amber-200" : "border-gray-200", text: bloqueadas ? "text-amber-700" : "text-gray-500", icon: "⚠️" },
    { title: "Completadas", value: completadas, color: "bg-green-50", border: "border-green-200", text: "text-green-700", icon: "✅" },
    { title: "Avance promedio", value: `${avancePromedio}%`, color: "bg-[#EAF0FB]", border: "border-[#D6E0F0]", text: "text-[#1A4FA0]", icon: "📈" },
  ]

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-4">
      {cards.map(card => (
        <div key={card.title} className={`${card.color} ${card.border} border rounded-2xl p-4 shadow-sm`}>
          <div className="flex justify-between items-start gap-2">
            <div className="min-w-0">
              <p className="text-xs text-gray-500 truncate">{card.title}</p>
              <h2 className={`text-2xl font-bold mt-1 ${card.text}`}>{card.value}</h2>
              {card.nota && <p className="text-[11px] text-amber-600 font-medium mt-0.5">{card.nota}</p>}
            </div>
            <div className="text-2xl shrink-0">{card.icon}</div>
          </div>
        </div>
      ))}
    </div>
  )
}
