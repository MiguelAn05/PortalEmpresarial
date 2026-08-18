import { useState } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { crearSubtarea, actualizarTarea, eliminarTarea } from "../api"
import { ALERTAS, alertaVencimiento, formatFecha, datetimeLocalAIso, puedeEditar } from "../constants"
import { useAuth } from "../../../core/AuthContext"
import { IconoCerrar } from '../../../core/components/Iconos.jsx'

/**
 * Checklist de subtareas dentro de una tarea. A propósito NO arrastra el
 * avance del padre: el % del padre se sigue registrando a mano en la línea
 * de tiempo, y las subtareas solo desglosan el trabajo.
 */
export default function SubtareasPanel({ tarea, usuarios = [], onCambio }) {
  const queryClient = useQueryClient()
  const { user } = useAuth()
  const editable = puedeEditar(user)
  const [nueva, setNueva] = useState({ titulo: "", asignado_a: "", fecha_fin: "" })
  const [abriendo, setAbriendo] = useState(false)

  const subtareas = tarea.subtareas || []
  const completadas = subtareas.filter(s => s.estado === 'completada').length

  const invalidar = () => {
    queryClient.invalidateQueries({ queryKey: ["mp-tarea", tarea.id] })
    queryClient.invalidateQueries({ queryKey: ["mp-tareas"] })
    onCambio?.()
  }

  const mutCrear = useMutation({
    mutationFn: () => crearSubtarea(tarea.id, {
      titulo: nueva.titulo,
      asignado_a: nueva.asignado_a ? Number(nueva.asignado_a) : null,
      fecha_fin: datetimeLocalAIso(nueva.fecha_fin),
    }),
    onSuccess: () => { setNueva({ titulo: "", asignado_a: "", fecha_fin: "" }); setAbriendo(false); invalidar() },
  })

  const mutAlternar = useMutation({
    mutationFn: (sub) => actualizarTarea(sub.id, {
      estado: sub.estado === 'completada' ? 'pendiente' : 'completada',
    }),
    onSuccess: invalidar,
  })

  const mutEliminar = useMutation({
    mutationFn: (id) => eliminarTarea(id),
    onSuccess: invalidar,
  })

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-bold text-acento-fuerte">
          Subtareas {subtareas.length > 0 && <span className="text-texto-2 font-semibold">({completadas}/{subtareas.length})</span>}
        </h3>
        {editable && (
          <button onClick={() => setAbriendo(v => !v)} className="text-xs font-semibold text-acento hover:underline">
            {abriendo ? 'Cancelar' : '+ Agregar subtarea'}
          </button>
        )}
      </div>

      {subtareas.length > 0 && (
        <div className="w-full bg-superficie-2 rounded-full h-1.5 mb-3">
          <div className="h-1.5 rounded-full bg-acento transition-all"
            style={{ width: `${Math.round((completadas / subtareas.length) * 100)}%` }} />
        </div>
      )}

      <div className="space-y-1.5">
        {subtareas.length === 0 && !abriendo && (
          <p className="text-xs text-texto-3 py-2">
            Sin subtareas. Sirven para desglosar una tarea grande en pasos concretos.
          </p>
        )}

        {subtareas.map(sub => {
          const hecha = sub.estado === 'completada'
          const alerta = alertaVencimiento(sub)
          return (
            <div key={sub.id} className="group flex items-center gap-2.5 bg-superficie-2 rounded-lg px-3 py-2">
              <input
                type="checkbox" checked={hecha}
                disabled={!editable}
                onChange={() => mutAlternar.mutate(sub)}
                className="w-4 h-4 rounded border-borde accent-acento cursor-pointer shrink-0 disabled:cursor-not-allowed"
              />
              <span className={`text-sm flex-1 truncate ${hecha ? 'line-through text-texto-3' : 'text-texto'}`}>
                {sub.titulo}
              </span>
              {sub.asignado_nombre && (
                <span className="text-[11px] text-texto-2 shrink-0 hidden sm:inline">{sub.asignado_nombre}</span>
              )}
              {sub.fecha_fin && (
                <span className={`text-[11px] shrink-0 ${alerta ? ALERTAS[alerta].texto : 'text-texto-3'}`}>
                  {formatFecha(sub.fecha_fin, { day: '2-digit', month: 'short' })}
                </span>
              )}
              {editable && (
                <button
                  onClick={() => { if (confirm(`¿Eliminar la subtarea "${sub.titulo}"?`)) mutEliminar.mutate(sub.id) }}
                  className="text-xs text-borde-fuerte hover:text-negativo shrink-0 opacity-0 group-hover:opacity-100 transition"
                  aria-label="Eliminar subtarea"
                >
                  <IconoCerrar tam={14} />
                </button>
              )}
            </div>
          )
        })}
      </div>

      {abriendo && (
        <div className="bg-superficie-2 rounded-xl p-3 mt-3 space-y-2">
          <input
            value={nueva.titulo}
            onChange={(e) => setNueva({ ...nueva, titulo: e.target.value })}
            onKeyDown={(e) => { if (e.key === 'Enter' && nueva.titulo) mutCrear.mutate() }}
            placeholder="¿Qué hay que hacer?"
            autoFocus
            className="w-full rounded-lg border border-borde px-3 py-2 text-sm"
          />
          <div className="grid grid-cols-2 gap-2">
            <select
              value={nueva.asignado_a}
              onChange={(e) => setNueva({ ...nueva, asignado_a: e.target.value })}
              className="rounded-lg border border-borde px-2 py-1.5 text-xs"
            >
              <option value="">Sin asignar</option>
              {usuarios.map(u => <option key={u.id} value={u.id}>{u.nombre}</option>)}
            </select>
            <input
              type="datetime-local" value={nueva.fecha_fin}
              onChange={(e) => setNueva({ ...nueva, fecha_fin: e.target.value })}
              className="rounded-lg border border-borde px-2 py-1.5 text-xs"
            />
          </div>
          <button
            onClick={() => mutCrear.mutate()}
            disabled={!nueva.titulo || mutCrear.isPending}
            className="w-full bg-acento hover:bg-acento-fuerte disabled:opacity-40 text-white text-xs font-semibold py-2 rounded-lg transition"
          >
            Agregar subtarea
          </button>
        </div>
      )}
    </div>
  )
}
