import { useEffect, useRef, useState } from "react"
import PriorityBadge from "./PriorityBadge"
import Avatar from "./Avatar"
import { ESTADOS_PROYECTO, colorAvance, formatFecha, formatMoneda } from "../constants"

/**
 * Tarjeta de un PROYECTO (no de una tarea). Al hacer clic se entra al
 * proyecto y ahí sí aparecen sus tareas.
 */
export default function ProyectoCard({ proyecto, onAbrir, onEditar, onArchivar, onEliminar }) {
  const [menuAbierto, setMenuAbierto] = useState(false)
  const menuRef = useRef(null)

  useEffect(() => {
    if (!menuAbierto) return
    const cerrar = (e) => { if (!menuRef.current?.contains(e.target)) setMenuAbierto(false) }
    document.addEventListener('mousedown', cerrar)
    return () => document.removeEventListener('mousedown', cerrar)
  }, [menuAbierto])

  const estado = ESTADOS_PROYECTO[proyecto.estado] || { label: proyecto.estado, color: 'bg-gray-100 text-gray-700' }
  const avance = proyecto.avance_pct ?? 0

  const accion = (fn) => (e) => { e.stopPropagation(); setMenuAbierto(false); fn() }

  return (
    <div
      onClick={onAbrir}
      className={`bg-white rounded-2xl border p-5 shadow-sm hover:shadow-md hover:border-[#1A4FA0]/40 transition cursor-pointer flex flex-col ${
        proyecto.archivado ? 'border-[#D6E0F0] opacity-70' : 'border-[#D6E0F0]'
      }`}
    >
      <div className="flex items-start justify-between gap-2 mb-3">
        <div className="flex flex-wrap gap-2">
          <span className={`px-3 py-1 rounded-full text-xs font-semibold ${estado.color}`}>{estado.label}</span>
          <PriorityBadge priority={proyecto.prioridad} />
          {proyecto.archivado && (
            <span className="px-3 py-1 rounded-full text-xs font-semibold bg-gray-100 text-gray-500">Archivado</span>
          )}
        </div>

        <div className="relative" ref={menuRef}>
          <button
            onClick={(e) => { e.stopPropagation(); setMenuAbierto(v => !v) }}
            aria-label="Acciones del proyecto"
            className="w-8 h-8 rounded-lg hover:bg-[#F0F4FA] text-[#6B7EA8] font-bold leading-none"
          >
            ⋮
          </button>
          {menuAbierto && (
            <div className="absolute right-0 top-9 z-20 w-56 bg-white rounded-xl border border-[#D6E0F0] shadow-lg py-1 text-sm">
              <button onClick={accion(onEditar)} className="w-full text-left px-4 py-2 hover:bg-[#F7F9FC] text-[#1A2B47]">
                Editar proyecto
              </button>
              <button onClick={accion(onArchivar)} className="w-full text-left px-4 py-2 hover:bg-[#F7F9FC] text-[#1A2B47]">
                {proyecto.archivado ? 'Restaurar del archivo' : 'Archivar proyecto'}
              </button>
              <div className="border-t border-[#EDF2F7] my-1" />
              <button
                onClick={accion(onEliminar)}
                disabled={proyecto.total_tareas > 0}
                title={proyecto.total_tareas > 0
                  ? `No se puede: tiene ${proyecto.total_tareas} tarea(s). Archívalo o borra sus tareas primero.`
                  : undefined}
                className="w-full text-left px-4 py-2 hover:bg-red-50 text-red-600 disabled:text-gray-300 disabled:hover:bg-transparent disabled:cursor-not-allowed"
              >
                Eliminar definitivamente
              </button>
            </div>
          )}
        </div>
      </div>

      <h3 className="text-base font-bold text-[#0D2B5E] leading-snug mb-1">{proyecto.nombre}</h3>
      {proyecto.objetivo && (
        <p className="text-xs text-[#6B7EA8] line-clamp-2 mb-3">{proyecto.objetivo}</p>
      )}

      <div className="mt-auto space-y-3 pt-2">
        <div>
          <div className="flex justify-between text-xs text-[#6B7EA8] mb-1">
            <span>{proyecto.tareas_completadas} de {proyecto.total_tareas} tareas</span>
            <span className="font-semibold text-[#0D2B5E]">{avance}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div className="h-2 rounded-full transition-all" style={{ width: `${avance}%`, background: colorAvance(avance) }} />
          </div>
        </div>

        <div className="flex items-center justify-between">
          <Avatar name={proyecto.lider_nombre} compact />
          {proyecto.area && (
            <span className="text-[11px] text-[#6B7EA8] bg-[#F7F9FC] border border-[#D6E0F0] rounded-full px-2 py-0.5">
              {proyecto.area}
            </span>
          )}
        </div>

        <div className="flex items-center justify-between text-[11px] text-[#9BACC8] border-t border-[#EDF2F7] pt-2.5">
          <span>{formatFecha(proyecto.fecha_inicio, { day: '2-digit', month: 'short' })} → {formatFecha(proyecto.fecha_fin_estimada, { day: '2-digit', month: 'short' })}</span>
          {proyecto.presupuesto_total > 0 && (
            <span className="font-semibold text-[#6B7EA8]">{formatMoneda(proyecto.presupuesto_total)}</span>
          )}
        </div>
      </div>
    </div>
  )
}
