import { useState } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { crearTarea } from "../api"
import { AREAS, MAX_ENTREGABLE, MAX_HORAS, PRIORIDADES, datetimeLocalAIso } from "../constants"
import { useCierreSeguro } from "../../../core/components/cierreSeguro"
import { tieneDatos } from "../../../core/components/tieneDatos"
import { IconoCerrar } from '../../../core/components/Iconos.jsx'

const VACIO = {
  titulo: "", descripcion: "", area: "", asignado_a: "",
  prioridad: "media", riesgos: "", entregable: "", horas_estimadas: "",
  fecha_inicio: "", fecha_fin: "",
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
      // Vacío es «no sé cuántas», no cero: un 0 diría que no cuesta nada.
      horas_estimadas: form.horas_estimadas === "" ? null : Number(form.horas_estimadas),
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
    <div className="fixed inset-0 bg-acento-fuerte/40 backdrop-blur-sm flex items-center justify-center p-4 z-50" onClick={intentarCerrar}>
      <div className="bg-white rounded-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="bg-gradient-to-r from-acento-fuerte to-acento rounded-t-2xl p-6 text-white sticky top-0">
          <button onClick={intentarCerrar} aria-label="Cerrar" className="absolute top-4 right-4 text-white/70 hover:text-white"><IconoCerrar tam={18} /></button>
          <h2 className="text-lg font-bold">Nueva tarea</h2>
          {proyectoFijo && <p className="text-xs text-white/70 mt-1">en {proyectoFijo.nombre}</p>}
        </div>

        <div className="p-6 space-y-4">
          {proyectos.length === 0 ? (
            <p className="text-sm text-texto-2">
              Primero tienes que crear un proyecto — todavía no hay ninguno.
            </p>
          ) : (
            <>
              {!proyectoFijo && (
                <div>
                  <label className="block text-xs font-semibold text-texto-2 uppercase mb-1">Proyecto</label>
                  <select value={proyectoId} onChange={(e) => setProyectoId(e.target.value)} className="w-full rounded-lg border border-borde px-3 py-2 text-sm">
                    {proyectos.map(p => <option key={p.id} value={p.id}>{p.nombre}</option>)}
                  </select>
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold text-texto-2 uppercase mb-1">Título</label>
                <input value={form.titulo} onChange={set('titulo')} className="w-full rounded-lg border border-borde px-3 py-2 text-sm" />
              </div>

              <div>
                <label className="block text-xs font-semibold text-texto-2 uppercase mb-1">Descripción</label>
                <textarea value={form.descripcion} onChange={set('descripcion')} rows={2} className="w-full rounded-lg border border-borde px-3 py-2 text-sm resize-none" />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-texto-2 uppercase mb-1">Área</label>
                  <select value={form.area} onChange={set('area')} className="w-full rounded-lg border border-borde px-3 py-2 text-sm">
                    <option value="">Sin definir</option>
                    {AREAS.map(a => <option key={a} value={a}>{a}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-texto-2 uppercase mb-1">Asignado a</label>
                  <select value={form.asignado_a} onChange={set('asignado_a')} className="w-full rounded-lg border border-borde px-3 py-2 text-sm">
                    <option value="">Sin asignar</option>
                    {usuarios.map(u => <option key={u.id} value={u.id}>{u.nombre}</option>)}
                  </select>
                </div>
              </div>

              {/* El entregable se pide AL CREAR, no después: escrito al
                  final se escribe para justificar lo que ya se hizo. Es la
                  diferencia entre «avance del 60%» y «el informe firmado»,
                  que es lo que otra persona puede verificar sin preguntar. */}
              <div>
                <label className="block text-xs font-semibold text-texto-2 uppercase mb-1">
                  Entregable
                </label>
                <input
                  value={form.entregable} onChange={set('entregable')}
                  maxLength={MAX_ENTREGABLE}
                  placeholder="Qué tiene que quedar hecho. Ej: el informe de migración firmado"
                  className="w-full rounded-lg border border-borde px-3 py-2 text-sm"
                />
                <p className="text-xs text-texto-3 mt-1">
                  Con qué se sabe que la tarea está cumplida, sin tener que preguntar.
                </p>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-texto-2 uppercase mb-1">Prioridad</label>
                  <select value={form.prioridad} onChange={set('prioridad')} className="w-full rounded-lg border border-borde px-3 py-2 text-sm">
                    {Object.entries(PRIORIDADES).map(([v, cfg]) => <option key={v} value={v}>{cfg.label}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-texto-2 uppercase mb-1">
                    Horas estimadas
                  </label>
                  <input
                    type="number" min="0" max={MAX_HORAS} step="0.5"
                    value={form.horas_estimadas} onChange={set('horas_estimadas')}
                    placeholder="Ej: 8"
                    className="w-full rounded-lg border border-borde px-3 py-2 text-sm cifra"
                  />
                  <p className="text-xs text-texto-3 mt-1">
                    Cuántas se le va a dedicar.
                  </p>
                </div>
              </div>

              {/* Fecha y hora: la hora es lo que permite ubicar la tarea en el
                  calendario a una franja concreta del día. */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-texto-2 uppercase mb-1">Inicio</label>
                  <input type="datetime-local" value={form.fecha_inicio} onChange={set('fecha_inicio')} className="w-full rounded-lg border border-borde px-3 py-2 text-sm" />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-texto-2 uppercase mb-1">Fin</label>
                  <input type="datetime-local" value={form.fecha_fin} onChange={set('fecha_fin')} className="w-full rounded-lg border border-borde px-3 py-2 text-sm" />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-texto-2 uppercase mb-1">Riesgos (opcional)</label>
                <textarea value={form.riesgos} onChange={set('riesgos')} rows={2} className="w-full rounded-lg border border-borde px-3 py-2 text-sm resize-none" />
              </div>

              <button
                onClick={() => mutCrear.mutate()}
                disabled={!form.titulo || !proyectoId || mutCrear.isPending}
                className="w-full bg-acento hover:bg-acento-fuerte disabled:opacity-40 text-white font-semibold py-2.5 rounded-lg transition"
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
