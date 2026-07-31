import StatusBadge from "./StatusBadge"
import PriorityBadge from "./PriorityBadge"
import Avatar from "./Avatar"
import { colorAvance, formatFecha } from "../constants"

export default function ProjectsTable({ tareas, onSelect }) {
  return (
    <div className="bg-white rounded-2xl border border-[#D6E0F0] shadow-sm overflow-hidden">
      <div className="overflow-x-auto">
        <table className="min-w-full">
          <thead className="bg-[#F7F9FC] border-b border-[#D6E0F0]">
            <tr className="text-xs uppercase tracking-wider text-[#6B7EA8]">
              <th className="text-left px-5 py-4">Proyecto / Tarea</th>
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
                <td colSpan={8} className="px-5 py-10 text-center text-sm text-[#9BACC8]">
                  No hay tareas que coincidan con los filtros.
                </td>
              </tr>
            )}
            {tareas.map(tarea => (
              <tr
                key={tarea.id}
                onClick={() => onSelect(tarea)}
                className="border-b border-[#EDF2F7] hover:bg-[#F9FBFD] transition cursor-pointer"
              >
                <td className="px-5 py-4">
                  <div>
                    <p className="font-semibold text-[#0D2B5E]">{tarea.titulo}</p>
                    <p className="text-xs text-gray-400">{tarea.proyecto_nombre}</p>
                  </div>
                </td>
                <td className="px-5 py-4">{tarea.area || '—'}</td>
                <td className="px-5 py-4"><Avatar name={tarea.asignado_nombre} /></td>
                <td className="px-5 py-4"><StatusBadge status={tarea.estado} /></td>
                <td className="px-5 py-4"><PriorityBadge priority={tarea.prioridad} /></td>
                <td className="px-5 py-4">
                  <div className="flex items-center gap-3">
                    <div className="w-32 bg-gray-200 rounded-full h-2">
                      <div
                        className="h-2 rounded-full"
                        style={{ width: `${tarea.avance_pct}%`, background: colorAvance(tarea.avance_pct) }}
                      />
                    </div>
                    <span className="text-sm font-semibold">{tarea.avance_pct}%</span>
                  </div>
                </td>
                <td className="px-5 py-4">{formatFecha(tarea.fecha_inicio)}</td>
                <td className="px-5 py-4">{formatFecha(tarea.fecha_fin)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
