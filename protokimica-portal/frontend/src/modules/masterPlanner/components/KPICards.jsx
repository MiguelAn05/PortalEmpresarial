const cards = [
  {
    title: "Proyectos activos",
    value: 18,
    color: "bg-blue-50",
    border: "border-blue-200",
    text: "text-blue-700",
    icon: "📁",
  },
  {
    title: "En riesgo",
    value: 4,
    color: "bg-red-50",
    border: "border-red-200",
    text: "text-red-700",
    icon: "⚠️",
  },
  {
    title: "Finalizados",
    value: 27,
    color: "bg-green-50",
    border: "border-green-200",
    text: "text-green-700",
    icon: "✅",
  },
  {
    title: "Avance promedio",
    value: "73%",
    color: "bg-amber-50",
    border: "border-amber-200",
    text: "text-amber-700",
    icon: "📈",
  },
]

export default function KPICards() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-5">

      {cards.map(card => (

        <div
          key={card.title}
          className={`${card.color} ${card.border}
          border rounded-2xl p-5 shadow-sm`}
        >

          <div className="flex justify-between items-center">

            <div>

              <p className="text-sm text-gray-500">
                {card.title}
              </p>

              <h2 className={`text-3xl font-bold mt-2 ${card.text}`}>
                {card.value}
              </h2>

            </div>

            <div className="text-4xl">
              {card.icon}
            </div>

          </div>

        </div>

      ))}

    </div>
  )
}