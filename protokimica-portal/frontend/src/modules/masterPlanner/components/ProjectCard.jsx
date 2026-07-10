import PriorityBadge from "./PriorityBadge"
import Avatar from "./Avatar"

export default function ProjectCard({ project, draggable, onDragStart, onDragEnd, onClick }) {
  return (
    <div
      draggable={draggable}
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      onClick={onClick}
      className="bg-white rounded-xl border border-[#D6E0F0] p-3.5 shadow-sm hover:shadow-md hover:border-[#1A4FA0]/40 transition cursor-pointer active:cursor-grabbing"
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <span className="text-[10px] font-semibold uppercase tracking-wide text-[#6B7EA8]">
          {project.proyecto}
        </span>
        <PriorityBadge priority={project.prioridad} />
      </div>

      <p className="text-sm font-semibold text-[#1A2B47] leading-snug mb-3">
        {project.actividad}
      </p>

      <div className="flex items-center gap-2 mb-3">
        <div className="flex-1 bg-gray-200 rounded-full h-1.5">
          <div
            className="h-1.5 rounded-full"
            style={{
              width: `${project.avance}%`,
              background: project.avance < 30 ? "#EF4444" : project.avance < 70 ? "#F59E0B" : "#22C55E",
            }}
          />
        </div>
        <span className="text-[11px] font-semibold text-[#6B7EA8]">{project.avance}%</span>
      </div>

      <div className="flex items-center justify-between">
        <Avatar name={project.responsable} compact />
        <span className="text-[11px] text-[#9BACC8]">
          {new Date(project.fin).toLocaleDateString('es-CO', { day: '2-digit', month: 'short' })}
        </span>
      </div>
    </div>
  )
}
