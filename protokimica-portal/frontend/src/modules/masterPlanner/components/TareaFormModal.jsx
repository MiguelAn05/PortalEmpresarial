import { useState } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { crearTarea } from "../api"
import { AREAS, PRIORIDADES, datetimeLocalAIso } from "../constants"
import { useCierreSeguro } from "../../../core/components/cierreSeguro"
import { tieneDatos } from "../../../core/components/tieneDatos"

const VACIO = {
  titulo: "", descripcion: "", area: "", asignado_a: "",
  prioridad: "media", riesgos: "", fecha_inicio: "", fecha_fin: "",
}

export default function TareaFormModal({ proyectos = [], usuarios = [], proyectoIdInicial = null, onClose }) {
  const queryClient = useQueryClient()
  // Si se abre desde dentro de un proyecto, ese proyecto ya viene fijo.
  const [proyectoId, setProyectoId] = useState(proyectoIdInicial ?? proyectos[0]?.id ?? "")
  const [form, setForm] = useState(VACIO)

  const hayCambios = tieneDatos(form, VACIO)
  const { intentarCerrar, dialogoDescarte } = useCierreSeguro({ hayCambios, onCerrar: onClose })

  const set = (campo) => (e) => setForm({ ...form, [campo]: e.target.value })

  const mutCrear = useMutation({
    mutationFn: () => crearTarea(proyectoId, {
      ...form,
      asignado_a: form.asignado_a ? Number(form.asignado_a) : null,
      fecha_inicio: datetimeLocalAIso(form.fecha_inicio),
      fecha_fin: datetimeLocalAIso(form.fecha_fin),
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["mp-tareas"] })
      queryClient.invalidateQueries({ queryKey: ["mp-proyectos"] })
      onClose()
    },
  })

  const proyectoFijo = proyectoIdInicial != null
    ? proyectos.find(p => p.id === proyectoIdInicial)
    : null

  return (
    <div className="fixed inset-0 bg-[#0D2B5E]/40 backdrop-blur-sm flex items-center justify-center p-4 z-50" onClick={intentarCerrar}>
      <div className="bg-white rounded-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="bg-gradient-to-r from-[#0D2B5E] to-[#1A4FA0] rounded-t-2xl p-6 text-white sticky top-0">
          <button onClick={intentarCerrar} className="absolute top-4 right-4 text-white/70 hover:text-white text-xl leading-none">✕</button>
          <h2 className="text-lg font-bold">Nueva tarea</h2>
          {proyectoFijo && <p className="text-xs text-white/70 mt-1">en {proyectoFijo.nombre}</p>}
        </div>

        <div className="p-6 space-y-4">
          {proyectos.length === 0 ? (
            <p className="text-sm text-[#6B7EA8]">
              Primero tienes que crear un proyecto — todavía no hay ninguno.
            </p>
          ) : (
            <>
              {!proyectoFijo && (
                <div>
                  <label className="block text-xs font-semibold text-[#6B7EA8] uppercase mb-1">Proyecto</label>
                  <select value={proyectoId} onChange={(e) => setProyectoId(e.target.value)} className="w-full rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm">
                    {proyectos.map(p => <option key={p.id} value={p.id}>{p.nombre}</option>)}
                  </select>
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold text-[#6B7EA8] uppercase mb-1">Título</label>
                <input value={form.titulo} onChange={set('titulo')} className="w-full rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm" />
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#6B7EA8] uppercase mb-1">Descripción</label>
                <textarea value={form.descripcion} onChange={set('descripcion')} rows={2} className="w-full rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm resize-none" />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-[#6B7EA8] uppercase mb-1">Área</label>
                  <select value={form.area} onChange={set('area')} className="w-full rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm">
                    <option value="">Sin definir</option>
                    {AREAS.map(a => <option key={a} value={a}>{a}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-[#6B7EA8] uppercase mb-1">Asignado a</label>
                  <select value={form.asignado_a} onChange={set('asignado_a')} className="w-full rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm">
                    <option value="">Sin asignar</option>
                    {usuarios.map(u => <option key={u.id} value={u.id}>{u.nombre}</option>)}
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#6B7EA8] uppercase mb-1">Prioridad</label>
                <select value={form.prioridad} onChange={set('prioridad')} className="w-full rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm">
                  {Object.entries(PRIORIDADES).map(([v, cfg]) => <option key={v} value={v}>{cfg.label}</option>)}
                </select>
              </div>

              {/* Fecha y hora: la hora es lo que permite ubicar la tarea en el
                  calendario a una franja concreta del día. */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-[#6B7EA8] uppercase mb-1">Inicio</label>
                  <input type="datetime-local" value={form.fecha_inicio} onChange={set('fecha_inicio')} className="w-full rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm" />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-[#6B7EA8] uppercase mb-1">Fin</label>
                  <input type="datetime-local" value={form.fecha_fin} onChange={set('fecha_fin')} className="w-full rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm" />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#6B7EA8] uppercase mb-1">Riesgos (opcional)</label>
                <textarea value={form.riesgos} onChange={set('riesgos')} rows={2} className="w-full rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm resize-none" />
              </div>

              <button
                onClick={() => mutCrear.mutate()}
                disabled={!form.titulo || !proyectoId || mutCrear.isPending}
                className="w-full bg-[#1A4FA0] hover:bg-[#0D2B5E] disabled:opacity-40 text-white font-semibold py-2.5 rounded-lg transition"
              >
                Crear tarea
              </button>
            </>
          )}
        </div>
      </div>

      {dialogoDescarte}
    </div>
  )
}
