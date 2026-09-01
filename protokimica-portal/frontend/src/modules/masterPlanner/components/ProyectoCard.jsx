import { useEffect, useRef, useState } from "react"
import PriorityBadge from "./PriorityBadge"
import Avatar from "./Avatar"
import { ESTADOS_PROYECTO, colorAvance, formatFecha, formatMoneda } from "../constants"

/**
 * Tarjeta de un PROYECTO (no de una tarea). Al hacer clic se entra al
 * proyecto y ahí sí aparecen sus tareas.
 */
export default function ProyectoCard({ proyecto, editable = true, onAbrir, onEditar, onArchivar, onEliminar }) {
  const [menuAbierto, setMenuAbierto] = useState(false)
  const menuRef = useRef(null)

  useEffect(() => {
    if (!menuAbierto) return
    const cerrar = (e) => { if (!menuRef.current?.contains(e.target)) setMenuAbierto(false) }
    document.addEventListener('mousedown', cerrar)
    return () => document.removeEventListener('mousedown', cerrar)
  }, [menuAbierto])

  const estado = ESTADOS_PROYECTO[proyecto.estado] || { label: proyecto.estado, color: 'bg-superficie-2 text-texto-2' }
  const avance = proyecto.avance_pct ?? 0

  const accion = (fn) => (e) => { e.stopPropagation(); setMenuAbierto(false); fn() }

  return (
    <div
      onClick={onAbrir}
      className={`bg-white rounded-2xl border p-5 shadow-sm hover:shadow-md hover:border-acento/40 transition cursor-pointer flex flex-col ${
        proyecto.archivado ? 'border-borde opacity-70' : 'border-borde'
      }`}
    >
      <div className="flex items-start justify-between gap-2 mb-3">
        <div className="flex flex-wrap gap-2">
          <span className={`px-3 py-1 rounded-full text-xs font-semibold ${estado.color}`}>{estado.label}</span>
          <PriorityBadge priority={proyecto.prioridad} />
          {proyecto.archivado && (
            <span className="px-3 py-1 rounded-full text-xs font-semibold bg-superficie-2 text-texto-2">Archivado</span>
          )}
        </div>

        {editable && (
        <div className="relative" ref={menuRef}>
          <button
            onClick={(e) => { e.stopPropagation(); setMenuAbierto(v => !v) }}
            aria-label="Acciones del proyecto"
            className="w-8 h-8 rounded-lg hover:bg-fondo text-texto-2 font-bold leading-none"
          >
            ⋮
          </button>
          {menuAbierto && (
            <div className="absolute right-0 top-9 z-20 w-56 bg-white rounded-xl border border-borde shadow-lg py-1 text-sm">
              <button onClick={accion(onEditar)} className="w-full text-left px-4 py-2 hover:bg-superficie-2 text-texto">
                Editar proyecto
              </button>
              <button onClick={accion(onArchivar)} className="w-full text-left px-4 py-2 hover:bg-superficie-2 text-texto">
                {proyecto.archivado ? 'Restaurar del archivo' : 'Archivar proyecto'}
              </button>
              <div className="border-t border-borde my-1" />
              <button
                onClick={accion(onEliminar)}
                disabled={proyecto.total_tareas > 0}
                title={proyecto.total_tareas > 0
                  ? `No se puede: tiene ${proyecto.total_tareas} tarea(s). Archívalo o borra sus tareas primero.`
                  : undefined}
                className="w-full text-left px-4 py-2 hover:bg-negativo-bg text-negativo disabled:text-borde-fuerte disabled:hover:bg-transparent disabled:cursor-not-allowed"
              >
                Eliminar definitivamente
              </button>
            </div>
          )}
        </div>
        )}
      </div>

      <h3 className="text-base font-bold text-acento-fuerte leading-snug mb-1">{proyecto.nombre}</h3>
      {proyecto.objetivo && (
        <p className="text-xs text-texto-2 line-clamp-2 mb-3">{proyecto.objetivo}</p>
      )}

      <div className="mt-auto space-y-3 pt-2">
        <div>
          <div className="flex justify-between text-xs text-texto-2 mb-1">
            <span>{proyecto.tareas_completadas} de {proyecto.total_tareas} tareas</span>
            <span className="font-semibold text-acento-fuerte">{avance}%</span>
          </div>
          <div className="w-full bg-superficie-2 rounded-full h-2">
            <div className="h-2 rounded-full transition-all" style={{ width: `${avance}%`, background: colorAvance(avance) }} />
          </div>
        </div>

        <div className="flex items-center justify-between">
          <Avatar name={proyecto.lider_nombre} compact />
          <div className="flex flex-wrap gap-1 justify-end">
            {proyecto.area && (
              <span title="Área responsable"
                className="text-[11px] text-acento bg-acento-suave border border-borde rounded-full px-2 py-0.5">
                {proyecto.area}
              </span>
            )}
            {proyecto.areas_participantes?.map(a => (
              <span key={a} title="Area participante"
                className="text-[11px] text-texto-2 bg-superficie-2 border border-borde rounded-full px-2 py-0.5">
                {a}
              </span>
            ))}
          </div>
        </div>

        <div className="flex items-center justify-between text-[11px] text-texto-3 border-t border-borde pt-2.5">
          <span>{formatFecha(proyecto.fecha_inicio, { day: '2-digit', month: 'short' })} → {formatFecha(proyecto.fecha_fin_estimada, { day: '2-digit', month: 'short' })}</span>
          {proyecto.presupuesto_total > 0 && (
            <span className="font-semibold text-texto-2">{formatMoneda(proyecto.presupuesto_total)}</span>
          )}
        </div>
      </div>
    </div>
  )
}
