import StatusBadge from "./StatusBadge"
import PriorityBadge from "./PriorityBadge"
import Avatar from "./Avatar"

function formatFecha(f) {
  if (!f) return '—'
  return new Date(f).toLocaleDateString('es-CO', { day: '2-digit', month: 'short', year: 'numeric' })
}

export default function ProjectsTable({ projects, onSelect }) {
  return (
    <div className="bg-white rounded-2xl border border-[#D6E0F0] shadow-sm overflow-hidden">
      <div className="overflow-x-auto">
        <table className="min-w-full">
          <thead className="bg-[#F7F9FC] border-b border-[#D6E0F0]">
            <tr className="text-xs uppercase tracking-wider text-[#6B7EA8]">
              <th className="text-left px-5 py-4">Proyecto / Actividad</th>
              <th className="text-left px-5 py-4">Área</th>
              <th className="text-left px-5 py-4">Responsable</th>
              <th className="text-left px-5 py-4">Estado</th>
              <th className="text-left px-5 py-4">Prioridad</th>
              <th className="text-left px-5 py-4">Avance</th>
              <th className="text-left px-5 py-4">Inicio</th>
              <th className="text-left px-5 py-4">Fin</th>
            </tr>
          </thead>
          <tbody>
            {projects.length === 0 && (
              <tr>
                <td colSpan={8} className="px-5 py-10 text-center text-sm text-[#9BACC8]">
                  No hay actividades que coincidan con los filtros.
                </td>
              </tr>
            )}
            {projects.map(project => (
              <tr
                key={project.id}
                onClick={() => onSelect(project)}
                className="border-b border-[#EDF2F7] hover:bg-[#F9FBFD] transition cursor-pointer"
              >
                <td className="px-5 py-4">
                  <div>
                    <p className="font-semibold text-[#0D2B5E]">{project.actividad}</p>
                    <p className="text-xs text-gray-400">{project.proyecto}</p>
                  </div>
                </td>
                <td className="px-5 py-4">{project.area}</td>
                <td className="px-5 py-4"><Avatar name={project.responsable} /></td>
                <td className="px-5 py-4"><StatusBadge status={project.estado} /></td>
                <td className="px-5 py-4"><PriorityBadge priority={project.prioridad} /></td>
                <td className="px-5 py-4">
                  <div className="flex items-center gap-3">
                    <div className="w-32 bg-gray-200 rounded-full h-2">
                      <div
                        className="h-2 rounded-full"
                        style={{
                          width: `${project.avance}%`,
                          background: project.avance < 30 ? "#EF4444" : project.avance < 70 ? "#F59E0B" : "#22C55E",
                        }}
                      />
                    </div>
                    <span className="text-sm font-semibold">{project.avance}%</span>
                  </div>
                </td>
                <td className="px-5 py-4">{formatFecha(project.inicio)}</td>
                <td className="px-5 py-4">{formatFecha(project.fin)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
