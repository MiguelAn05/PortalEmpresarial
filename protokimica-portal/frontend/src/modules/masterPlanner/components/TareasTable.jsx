import StatusBadge from "./StatusBadge"
import PriorityBadge from "./PriorityBadge"
import Avatar from "./Avatar"
import { ALERTAS, alertaVencimiento, colorAvance, formatFecha, formatFechaHora } from "../constants"
import { IconoTarea } from '../../../core/components/Iconos.jsx'

export default function TareasTable({ tareas, onSelect, mostrarProyecto = true }) {
  return (
    <div className="bg-white rounded-2xl border border-borde shadow-sm overflow-hidden">
      <div className="overflow-x-auto">
        <table className="min-w-full">
          <thead className="bg-superficie-2 border-b border-borde">
            <tr className="text-xs uppercase tracking-wider text-texto-2">
              <th className="text-left px-5 py-4">Tarea</th>
              <th className="text-left px-5 py-4">Área</th>
              <th className="text-left px-5 py-4">Asignado</th>
              <th className="text-left px-5 py-4">Estado</th>
              <th className="text-left px-5 py-4">Prioridad</th>
              <th className="text-left px-5 py-4">Avance</th>
              <th className="text-left px-5 py-4">Inicio</th>
              <th className="text-left px-5 py-4">Fin</th>
            </tr>
          </thead>
          <tbody>
            {tareas.length === 0 && (
              <tr>
                <td colSpan={8} className="px-5 py-10 text-center text-sm text-texto-3">
                  No hay tareas que coincidan con los filtros.
                </td>
              </tr>
            )}
            {tareas.map(tarea => {
              const alerta = alertaVencimiento(tarea)
              const cfgAlerta = alerta ? ALERTAS[alerta] : null
              return (
                <tr
                  key={tarea.id}
                  onClick={() => onSelect(tarea)}
                  className="border-b border-borde hover:bg-superficie-2 transition cursor-pointer"
                >
                  <td className="px-5 py-4">
                    <div className="flex items-start gap-2">
                      <div>
                        <p className="font-semibold text-acento-fuerte">{tarea.titulo}</p>
                        <p className="text-xs text-borde-fuerte">
                          {mostrarProyecto && tarea.proyecto_nombre}
                          {tarea.total_subtareas > 0 && (
                            <span className={mostrarProyecto ? 'ml-2' : ''}>
                              <IconoTarea tam={12} className="inline mr-1 -mt-0.5" />{tarea.subtareas_completadas}/{tarea.total_subtareas}
                            </span>
                          )}
                        </p>
                      </div>
                      {cfgAlerta && (
                        <span className={`text-[10px] font-semibold border rounded-full px-2 py-0.5 shrink-0 ${cfgAlerta.chip}`}>
                          {cfgAlerta.label}
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-5 py-4 text-sm">{tarea.area || '—'}</td>
                  <td className="px-5 py-4"><Avatar name={tarea.asignado_nombre} /></td>
                  <td className="px-5 py-4"><StatusBadge status={tarea.estado} /></td>
                  <td className="px-5 py-4"><PriorityBadge priority={tarea.prioridad} /></td>
                  <td className="px-5 py-4">
                    <div className="flex items-center gap-3">
                      <div className="w-32 bg-superficie-2 rounded-full h-2">
                        <div
                          className="h-2 rounded-full"
                          style={{ width: `${tarea.avance_pct}%`, background: colorAvance(tarea.avance_pct) }}
                        />
                      </div>
                      <span className="text-sm font-semibold">{tarea.avance_pct}%</span>
                    </div>
                  </td>
                  <td className="px-5 py-4 text-sm whitespace-nowrap">{formatFecha(tarea.fecha_inicio)}</td>
                  <td className={`px-5 py-4 text-sm whitespace-nowrap ${cfgAlerta?.texto || ''}`}>
                    {formatFechaHora(tarea.fecha_fin)}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
