import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import StatusBadge from "./StatusBadge"
import PriorityBadge from "./PriorityBadge"
import Avatar from "./Avatar"
import { listarActualizaciones, agregarActualizacion, actualizarTarea, eliminarTarea } from "../api"
import { ESTADOS_TAREA, PRIORIDADES, AREAS, colorAvance, formatFecha } from "../constants"

export default function ProjectDetailModal({ tarea, usuarios = [], onClose }) {
  const queryClient = useQueryClient()
  const [editando, setEditando] = useState(false)
  const [form, setForm] = useState({
    titulo: tarea.titulo,
    descripcion: tarea.descripcion || "",
    area: tarea.area || "",
    riesgos: tarea.riesgos || "",
    prioridad: tarea.prioridad,
    fecha_inicio: tarea.fecha_inicio?.slice(0, 10) || "",
    fecha_fin: tarea.fecha_fin?.slice(0, 10) || "",
  })
  const [comentario, setComentario] = useState("")
  const [avanceNuevo, setAvanceNuevo] = useState("")
  const [evidencia, setEvidencia] = useState(null)

  const { data: actualizaciones = [] } = useQuery({
    queryKey: ["mp-actualizaciones", tarea.id],
    queryFn: () => listarActualizaciones(tarea.id),
  })

  const invalidar = () => {
    queryClient.invalidateQueries({ queryKey: ["mp-tareas"] })
    queryClient.invalidateQueries({ queryKey: ["mp-proyectos"] })
  }

  const mutCampo = useMutation({
    mutationFn: (payload) => actualizarTarea(tarea.id, payload),
    onSuccess: (data) => { Object.assign(tarea, data); invalidar() },
  })

  const mutGuardarEdicion = useMutation({
    mutationFn: () => actualizarTarea(tarea.id, form),
    onSuccess: (data) => { Object.assign(tarea, data); invalidar(); setEditando(false) },
  })

  const mutActualizacion = useMutation({
    mutationFn: () => {
      const fd = new FormData()
      if (comentario) fd.append('comentario', comentario)
      if (avanceNuevo !== '') fd.append('avance_pct_nuevo', avanceNuevo)
      if (evidencia) fd.append('evidencia', evidencia)
      return agregarActualizacion(tarea.id, fd)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["mp-actualizaciones", tarea.id] })
      invalidar()
      setComentario(""); setAvanceNuevo(""); setEvidencia(null)
    },
  })

  const mutEliminar = useMutation({
    mutationFn: () => eliminarTarea(tarea.id),
    onSuccess: () => { invalidar(); onClose() },
  })

  return (
    <div className="fixed inset-0 bg-[#0D2B5E]/40 backdrop-blur-sm flex items-center justify-center p-4 z-50" onClick={onClose}>
      <div className="bg-white rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto shadow-xl" onClick={(e) => e.stopPropagation()}>

        <div className="bg-gradient-to-r from-[#0D2B5E] to-[#1A4FA0] rounded-t-2xl p-6 text-white sticky top-0 z-10">
          <button onClick={onClose} className="absolute top-4 right-4 text-white/70 hover:text-white text-xl leading-none">✕</button>
          <p className="text-xs uppercase tracking-wide text-white/70 mb-1">{tarea.proyecto_nombre}</p>
          <h2 className="text-xl font-bold pr-8">{tarea.titulo}</h2>
        </div>

        <div className="p-6 space-y-6">

          {/* Acciones rápidas: estado y asignado, cambian al instante */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-[#6B7EA8] uppercase mb-1">Estado</label>
              <select
                value={tarea.estado}
                onChange={(e) => mutCampo.mutate({ estado: e.target.value })}
                className="w-full rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm"
              >
                {Object.entries(ESTADOS_TAREA).map(([v, cfg]) => <option key={v} value={v}>{cfg.label}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-[#6B7EA8] uppercase mb-1">Asignado a</label>
              <select
                value={tarea.asignado_a || ""}
                onChange={(e) => mutCampo.mutate({ asignado_a: e.target.value ? Number(e.target.value) : null })}
                className="w-full rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm"
              >
                <option value="">Sin asignar</option>
                {usuarios.map(u => <option key={u.id} value={u.id}>{u.nombre}</option>)}
              </select>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="flex-1 bg-gray-200 rounded-full h-2.5">
              <div className="h-2.5 rounded-full" style={{ width: `${tarea.avance_pct}%`, background: colorAvance(tarea.avance_pct) }} />
            </div>
            <span className="text-sm font-bold text-[#0D2B5E]">{tarea.avance_pct}%</span>
          </div>

          {/* Detalle: modo lectura o edición */}
          {!editando ? (
            <div className="bg-[#F7F9FC] rounded-xl p-4 space-y-3">
              <div className="flex justify-between items-start">
                <div className="flex gap-2">
                  <PriorityBadge priority={tarea.prioridad} />
                  {tarea.area && <span className="px-3 py-1 rounded-full text-xs font-semibold bg-white border border-[#D6E0F0] text-[#6B7EA8]">{tarea.area}</span>}
                </div>
                <button onClick={() => setEditando(true)} className="text-xs font-semibold text-[#1A4FA0] hover:underline">
                  Editar detalles
                </button>
              </div>
              {tarea.descripcion && <p className="text-sm text-[#1A2B47]">{tarea.descripcion}</p>}
              {tarea.riesgos && (
                <p className="text-sm text-red-700 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
                  ⚠️ {tarea.riesgos}
                </p>
              )}
              <div className="flex justify-between text-xs text-[#6B7EA8] pt-1">
                <span>Inicio: {formatFecha(tarea.fecha_inicio)}</span>
                <span>Fin: {formatFecha(tarea.fecha_fin)}</span>
              </div>
            </div>
          ) : (
            <div className="bg-[#F7F9FC] rounded-xl p-4 space-y-3">
              <input value={form.titulo} onChange={(e) => setForm({ ...form, titulo: e.target.value })}
                className="w-full rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm font-semibold" placeholder="Título" />
              <textarea value={form.descripcion} onChange={(e) => setForm({ ...form, descripcion: e.target.value })}
                rows={2} className="w-full rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm resize-none" placeholder="Descripción" />
              <textarea value={form.riesgos} onChange={(e) => setForm({ ...form, riesgos: e.target.value })}
                rows={2} className="w-full rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm resize-none" placeholder="Riesgos" />
              <div className="grid grid-cols-2 gap-3">
                <select value={form.area} onChange={(e) => setForm({ ...form, area: e.target.value })} className="rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm">
                  <option value="">Área</option>
                  {AREAS.map(a => <option key={a} value={a}>{a}</option>)}
                </select>
                <select value={form.prioridad} onChange={(e) => setForm({ ...form, prioridad: e.target.value })} className="rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm">
                  {Object.entries(PRIORIDADES).map(([v, cfg]) => <option key={v} value={v}>{cfg.label}</option>)}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <input type="date" value={form.fecha_inicio} onChange={(e) => setForm({ ...form, fecha_inicio: e.target.value })} className="rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm" />
                <input type="date" value={form.fecha_fin} onChange={(e) => setForm({ ...form, fecha_fin: e.target.value })} className="rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm" />
              </div>
              <div className="flex gap-2">
                <button onClick={() => setEditando(false)} className="flex-1 border border-[#D6E0F0] text-sm font-semibold py-2 rounded-lg hover:bg-gray-50">Cancelar</button>
                <button onClick={() => mutGuardarEdicion.mutate()} disabled={mutGuardarEdicion.isPending} className="flex-1 bg-[#1A4FA0] hover:bg-[#0D2B5E] text-white text-sm font-semibold py-2 rounded-lg">Guardar</button>
              </div>
            </div>
          )}

          {/* Línea de tiempo de actualizaciones */}
          <div>
            <h3 className="text-sm font-bold text-[#0D2B5E] mb-3">Actualizaciones de avance</h3>

            <div className="bg-[#F7F9FC] rounded-xl p-4 mb-4 space-y-2">
              <textarea
                value={comentario} onChange={(e) => setComentario(e.target.value)}
                placeholder="¿Qué avanzó desde la última actualización?"
                rows={2} className="w-full rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm resize-none"
              />
              <div className="flex items-center gap-3">
                <input
                  type="number" min={0} max={100} value={avanceNuevo}
                  onChange={(e) => setAvanceNuevo(e.target.value)}
                  placeholder="% avance"
                  className="w-28 rounded-lg border border-[#D6E0F0] px-3 py-1.5 text-sm"
                />
                <input
                  type="file" accept=".jpg,.jpeg,.png,.webp,.pdf"
                  onChange={(e) => setEvidencia(e.target.files?.[0] || null)}
                  className="flex-1 text-xs text-[#6B7EA8] file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-[#EAF0FB] file:text-[#1A4FA0] hover:file:bg-[#D6E0F0]"
                />
              </div>
              {evidencia && <p className="text-xs text-[#6B7EA8]">📎 {evidencia.name}</p>}
              <button
                onClick={() => mutActualizacion.mutate()}
                disabled={(!comentario && avanceNuevo === '' && !evidencia) || mutActualizacion.isPending}
                className="w-full bg-[#1A4FA0] hover:bg-[#0D2B5E] disabled:opacity-40 text-white text-sm font-semibold py-2 rounded-lg transition"
              >
                Publicar actualización
              </button>
            </div>

            <div className="space-y-3">
              {actualizaciones.length === 0 && (
                <p className="text-xs text-[#9BACC8] text-center py-4">Aún no hay actualizaciones registradas.</p>
              )}
              {actualizaciones.map(act => (
                <div key={act.id} className="border-l-2 border-[#D6E0F0] pl-4 py-1">
                  <div className="flex items-center justify-between mb-1">
                    <Avatar name={act.usuario_nombre} compact />
                    <span className="text-[11px] text-[#9BACC8]">{formatFecha(act.fecha, { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}</span>
                  </div>
                  {act.avance_pct_nuevo !== null && act.avance_pct_nuevo !== undefined && (
                    <span className="inline-block text-[11px] font-semibold text-[#1A4FA0] bg-[#EAF0FB] rounded-full px-2 py-0.5 mb-1">
                      Avance actualizado a {act.avance_pct_nuevo}%
                    </span>
                  )}
                  {act.comentario && <p className="text-sm text-[#1A2B47]">{act.comentario}</p>}
                  {act.adjunto_evidencia && (
                    /\.(jpg|jpeg|png|webp)$/i.test(act.adjunto_evidencia) ? (
                      <a href={act.adjunto_evidencia} target="_blank" rel="noreferrer" className="inline-block mt-2">
                        <img src={act.adjunto_evidencia} alt="Evidencia" className="max-h-32 rounded-lg border border-[#D6E0F0]" />
                      </a>
                    ) : (
                      <a href={act.adjunto_evidencia} target="_blank" rel="noreferrer" className="inline-block mt-2 text-xs text-[#1A4FA0] font-semibold underline">
                        📎 Ver evidencia adjunta
                      </a>
                    )
                  )}
                </div>
              ))}
            </div>
          </div>

          <button
            onClick={() => { if (confirm('¿Eliminar esta tarea? Esta acción no se puede deshacer.')) mutEliminar.mutate() }}
            className="text-xs text-red-500 hover:text-red-700 font-semibold"
          >
            Eliminar tarea
          </button>
        </div>
      </div>
    </div>
  )
}
