import { useState } from "react"
import ProjectCard from "./ProjectCard"

const COLUMNAS = [
  { estado: "Planeación",   dot: "bg-blue-400" },
  { estado: "En ejecución", dot: "bg-emerald-400" },
  { estado: "En riesgo",    dot: "bg-red-400" },
  { estado: "Pausado",      dot: "bg-yellow-400" },
  { estado: "Finalizado",   dot: "bg-gray-400" },
]

export default function KanbanBoard({ projects, onChangeEstado, onSelect }) {
  const [dragId, setDragId] = useState(null)
  const [overEstado, setOverEstado] = useState(null)

  return (
    <div className="flex gap-4 overflow-x-auto pb-2">
      {COLUMNAS.map(({ estado, dot }) => {
        const items = projects.filter(p => p.estado === estado)
        const isOver = overEstado === estado

        return (
          <div
            key={estado}
            onDragOver={(e) => { e.preventDefault(); setOverEstado(estado) }}
            onDragLeave={() => setOverEstado(prev => (prev === estado ? null : prev))}
            onDrop={(e) => {
              e.preventDefault()
              if (dragId != null) onChangeEstado(dragId, estado)
              setDragId(null)
              setOverEstado(null)
            }}
            className={`flex-shrink-0 w-72 rounded-2xl border transition-colors ${
              isOver ? "border-[#1A4FA0] bg-[#F0F4FA]" : "border-[#D6E0F0] bg-[#F7F9FC]"
            }`}
          >
            <div className="flex items-center justify-between px-4 py-3 border-b border-[#D6E0F0]">
              <div className="flex items-center gap-2">
                <span className={`w-2 h-2 rounded-full ${dot}`} />
                <span className="text-sm font-semibold text-[#0D2B5E]">{estado}</span>
              </div>
              <span className="text-xs font-semibold text-[#6B7EA8] bg-white border border-[#D6E0F0] rounded-full px-2 py-0.5">
                {items.length}
              </span>
            </div>

            <div className="p-3 space-y-3 min-h-[120px]">
              {items.length === 0 && (
                <div className="text-xs text-[#9BACC8] text-center py-6 border border-dashed border-[#D6E0F0] rounded-xl">
                  Sin actividades
                </div>
              )}
              {items.map(item => (
                <ProjectCard
                  key={item.id}
                  project={item}
                  draggable
                  onDragStart={() => setDragId(item.id)}
                  onDragEnd={() => { setDragId(null); setOverEstado(null) }}
                  onClick={() => onSelect(item)}
                />
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}
