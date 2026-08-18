import PriorityBadge from "./PriorityBadge"
import Avatar from "./Avatar"
import { ALERTAS, alertaVencimiento, colorAvance, formatFecha, formatHora, tieneHora } from "../constants"
import { IconoTarea } from '../../../core/components/Iconos.jsx'

export default function TareaCard({ tarea, draggable, onDragStart, onDragEnd, onClick, mostrarProyecto = true }) {
  const alerta = alertaVencimiento(tarea)
  const cfgAlerta = alerta ? ALERTAS[alerta] : null

  return (
    <div
      draggable={draggable}
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      onClick={onClick}
      className={`bg-white rounded-xl border border-borde p-3.5 shadow-sm hover:shadow-md hover:border-acento/40 transition cursor-pointer active:cursor-grabbing ${cfgAlerta?.borde || ''}`}
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        {mostrarProyecto ? (
          <span className="text-[10px] font-semibold uppercase tracking-wide text-texto-2 truncate">
            {tarea.proyecto_nombre}
          </span>
        ) : <span />}
        <PriorityBadge priority={tarea.prioridad} />
      </div>

      <p className="text-sm font-semibold text-texto leading-snug mb-2">
        {tarea.titulo}
      </p>

      {cfgAlerta && (
        <span className={`inline-block mb-2 text-[10px] font-semibold border rounded-full px-2 py-0.5 ${cfgAlerta.chip}`}>
          {cfgAlerta.label}
        </span>
      )}

      <div className="flex items-center gap-2 mb-3">
        <div className="flex-1 bg-superficie-2 rounded-full h-1.5">
          <div
            className="h-1.5 rounded-full"
            style={{ width: `${tarea.avance_pct}%`, background: colorAvance(tarea.avance_pct) }}
          />
        </div>
        <span className="text-[11px] font-semibold text-texto-2">{tarea.avance_pct}%</span>
      </div>

      {tarea.total_subtareas > 0 && (
        <p className="text-[11px] text-texto-2 mb-2">
          <IconoTarea tam={12} className="inline mr-1 -mt-0.5" />{tarea.subtareas_completadas}/{tarea.total_subtareas} subtareas
        </p>
      )}

      <div className="flex items-center justify-between">
        <Avatar name={tarea.asignado_nombre} compact />
        {tarea.fecha_fin && (
          <span className={`text-[11px] ${cfgAlerta?.texto || 'text-texto-3'}`}>
            {formatFecha(tarea.fecha_fin, { day: '2-digit', month: 'short' })}
            {tieneHora(tarea.fecha_fin) && ` · ${formatHora(tarea.fecha_fin)}`}
          </span>
        )}
      </div>
    </div>
  )
}
