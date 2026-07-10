export default function KPICards({ projects }) {
  const total = projects.length
  const activos = projects.filter(p => p.estado === "En ejecución" || p.estado === "Planeación").length
  const enRiesgo = projects.filter(p => p.estado === "En riesgo").length
  const finalizados = projects.filter(p => p.estado === "Finalizado").length
  const avancePromedio = total
    ? Math.round(projects.reduce((sum, p) => sum + p.avance, 0) / total)
    : 0

  const cards = [
    { title: "Actividades activas", value: activos, color: "bg-blue-50", border: "border-blue-200", text: "text-blue-700", icon: "📁" },
    { title: "En riesgo", value: enRiesgo, color: "bg-red-50", border: "border-red-200", text: "text-red-700", icon: "⚠️" },
    { title: "Finalizadas", value: finalizados, color: "bg-green-50", border: "border-green-200", text: "text-green-700", icon: "✅" },
    { title: "Avance promedio", value: `${avancePromedio}%`, color: "bg-amber-50", border: "border-amber-200", text: "text-amber-700", icon: "📈" },
  ]

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-5">
      {cards.map(card => (
        <div key={card.title} className={`${card.color} ${card.border} border rounded-2xl p-5 shadow-sm`}>
          <div className="flex justify-between items-center">
            <div>
              <p className="text-sm text-gray-500">{card.title}</p>
              <h2 className={`text-3xl font-bold mt-2 ${card.text}`}>{card.value}</h2>
            </div>
            <div className="text-4xl">{card.icon}</div>
          </div>
        </div>
      ))}
    </div>
  )
}
