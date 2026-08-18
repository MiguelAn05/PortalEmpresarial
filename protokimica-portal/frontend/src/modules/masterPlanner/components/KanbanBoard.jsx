import { useState } from "react"
import TareaCard from "./TareaCard"
import { ESTADOS_TAREA } from "../constants"

const COLUMNAS = Object.entries(ESTADOS_TAREA).map(([estado, cfg]) => ({ estado, ...cfg }))

export default function KanbanBoard({ tareas, onChangeEstado, onSelect, mostrarProyecto = true, arrastrable = true }) {
  const [dragId, setDragId] = useState(null)
  const [overEstado, setOverEstado] = useState(null)

  return (
    <div className="flex gap-4 overflow-x-auto pb-2">
      {COLUMNAS.map(({ estado, label, dot }) => {
        const items = tareas.filter(t => t.estado === estado)
        const isOver = overEstado === estado

        return (
          <div
            key={estado}
            onDragOver={(e) => { e.preventDefault(); setOverEstado(estado) }}
            onDragLeave={() => setOverEstado(prev => (prev === estado ? null : prev))}
            onDrop={(e) => {
              e.preventDefault()
              if (arrastrable && dragId != null) onChangeEstado(dragId, estado)
              setDragId(null)
              setOverEstado(null)
            }}
            className={`flex-shrink-0 w-72 rounded-2xl border transition-colors ${
              isOver ? "border-acento bg-fondo" : "border-borde bg-superficie-2"
            }`}
          >
            <div className="flex items-center justify-between px-4 py-3 border-b border-borde">
              <div className="flex items-center gap-2">
                <span className={`w-2 h-2 rounded-full ${dot}`} />
                <span className="text-sm font-semibold text-acento-fuerte">{label}</span>
              </div>
              <span className="text-xs font-semibold text-texto-2 bg-white border border-borde rounded-full px-2 py-0.5">
                {items.length}
              </span>
            </div>

            <div className="p-3 space-y-3 min-h-[120px]">
              {items.length === 0 && (
                <div className="text-xs text-texto-3 text-center py-6 border border-dashed border-borde rounded-xl">
                  Sin tareas
                </div>
              )}
              {items.map(tarea => (
                <TareaCard
                  key={tarea.id}
                  tarea={tarea}
                  mostrarProyecto={mostrarProyecto}
                  draggable={arrastrable}
                  onDragStart={() => setDragId(tarea.id)}
                  onDragEnd={() => { setDragId(null); setOverEstado(null) }}
                  onClick={() => onSelect(tarea)}
                />
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}
