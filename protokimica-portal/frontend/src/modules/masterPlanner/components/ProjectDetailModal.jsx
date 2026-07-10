import StatusBadge from "./StatusBadge"
import PriorityBadge from "./PriorityBadge"
import Avatar from "./Avatar"

function formatFecha(f) {
  if (!f) return '—'
  return new Date(f).toLocaleDateString('es-CO', { day: '2-digit', month: 'long', year: 'numeric' })
}

function formatMoneda(v) {
  if (!v && v !== 0) return '—'
  return v.toLocaleString('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 })
}

function Campo({ label, children }) {
  return (
    <div>
      <div className="text-[11px] font-semibold uppercase tracking-wide text-[#6B7EA8] mb-1">{label}</div>
      <div className="text-sm text-[#1A2B47]">{children}</div>
    </div>
  )
}

export default function ProjectDetailModal({ project, onClose }) {
  if (!project) return null

  return (
    <div
      className="fixed inset-0 bg-[#0D2B5E]/40 backdrop-blur-sm flex items-center justify-center p-4 z-50"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Encabezado */}
        <div className="bg-gradient-to-r from-[#0D2B5E] to-[#1A4FA0] rounded-t-2xl p-6 text-white sticky top-0">
          <button
            onClick={onClose}
            className="absolute top-4 right-4 text-white/70 hover:text-white text-xl leading-none"
            aria-label="Cerrar"
          >
            ✕
          </button>
          <div className="text-white/60 text-xs font-semibold uppercase tracking-wide mb-1">
            {project.proyecto} · {project.año}
          </div>
          <h2 className="text-lg font-bold mb-3 pr-8">{project.actividad}</h2>
          <div className="flex gap-2 flex-wrap">
            <StatusBadge status={project.estado} />
            <PriorityBadge priority={project.prioridad} />
            <span className="bg-white/10 text-white/80 text-xs px-2.5 py-1 rounded-full">
              📁 {project.area}
            </span>
          </div>
        </div>

        <div className="p-6 space-y-6">

          {/* Avance */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs font-semibold uppercase tracking-wide text-[#6B7EA8]">Avance</span>
              <span className="text-sm font-bold text-[#0D2B5E]">{project.avance}%</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2.5">
              <div
                className="h-2.5 rounded-full"
                style={{
                  width: `${project.avance}%`,
                  background: project.avance < 30 ? "#EF4444" : project.avance < 70 ? "#F59E0B" : "#22C55E",
                }}
              />
            </div>
          </div>

          {/* Responsable + fechas */}
          <div className="grid grid-cols-3 gap-4">
            <Campo label="Responsable"><Avatar name={project.responsable} /></Campo>
            <Campo label="Inicio">{formatFecha(project.inicio)}</Campo>
            <Campo label="Fin">{formatFecha(project.fin)}</Campo>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <Campo label="Mes">{project.mes}</Campo>
            <Campo label="Presupuesto">{formatMoneda(project.presupuesto)}</Campo>
          </div>

          <div className="border-t border-[#EDF2F7] pt-5 space-y-4">
            <Campo label="Objetivo del proyecto">{project.objetivo}</Campo>
            <Campo label="Entregable">{project.entregable}</Campo>
            <Campo label="Indicadores">{project.indicadores}</Campo>
          </div>

          <div className="border-t border-[#EDF2F7] pt-5 space-y-4">
            <Campo label="Recursos asignados">{project.recursos}</Campo>
            <Campo label="Riesgos">{project.riesgos || 'Sin riesgos registrados.'}</Campo>
            <Campo label="Observaciones">{project.observaciones || 'Sin observaciones.'}</Campo>
          </div>
        </div>
      </div>
    </div>
  )
}
