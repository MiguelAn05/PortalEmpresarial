import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  crearProyecto, actualizarProyecto,
  listarPresupuesto, agregarItemPresupuesto, eliminarItemPresupuesto,
} from "../api"
import { AREAS, ESTADOS_PROYECTO, PRIORIDADES, formatMoneda, isoADateInput } from "../constants"

const VACIO = {
  nombre: "", objetivo: "", alcance: "", lider_id: "", area: "",
  areas_participantes: [],
  estado: "planeacion", prioridad: "media", fecha_inicio: "", fecha_fin_estimada: "",
}

/** Convierte el proyecto que llega por props en los valores del formulario. */
function aFormulario(proyecto) {
  if (!proyecto) return VACIO
  return {
    nombre: proyecto.nombre || "",
    objetivo: proyecto.objetivo || "",
    alcance: proyecto.alcance || "",
    lider_id: proyecto.lider_id || "",
    area: proyecto.area || "",
    areas_participantes: proyecto.areas_participantes || [],
    estado: proyecto.estado || "planeacion",
    prioridad: proyecto.prioridad || "media",
    fecha_inicio: isoADateInput(proyecto.fecha_inicio),
    fecha_fin_estimada: isoADateInput(proyecto.fecha_fin_estimada),
  }
}

export default function ProyectoFormModal({ proyecto, usuarios = [], onClose }) {
  const queryClient = useQueryClient()
  // El modal se monta de nuevo cada vez que se abre, así que basta con
  // inicializar el estado desde las props — no hace falta sincronizarlo.
  const [form, setForm] = useState(() => aFormulario(proyecto))
  const [proyectoId, setProyectoId] = useState(proyecto?.id ?? null)
  const [itemForm, setItemForm] = useState({ concepto: "", detalle: "", valor_unitario: "", cantidad: "1" })

  const set = (campo) => (e) => setForm({ ...form, [campo]: e.target.value })

  const { data: items = [] } = useQuery({
    queryKey: ["mp-presupuesto", proyectoId],
    queryFn: () => listarPresupuesto(proyectoId),
    enabled: !!proyectoId,
  })
  const total = items.reduce((s, i) => s + i.valor_total, 0)

  const mutGuardar = useMutation({
    mutationFn: () => {
      const payload = {
        ...form,
        lider_id: form.lider_id ? Number(form.lider_id) : null,
        fecha_inicio: form.fecha_inicio || null,
        fecha_fin_estimada: form.fecha_fin_estimada || null,
      }
      return proyectoId ? actualizarProyecto(proyectoId, payload) : crearProyecto(payload)
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["mp-proyectos"] })
      queryClient.invalidateQueries({ queryKey: ["mp-proyecto", data.id] })
      setProyectoId(data.id) // deja el modal abierto en modo edición para poder cargar presupuesto
    },
  })

  const mutAgregarItem = useMutation({
    mutationFn: () => agregarItemPresupuesto(proyectoId, {
      ...itemForm,
      valor_unitario: Number(itemForm.valor_unitario) || 0,
      cantidad: Number(itemForm.cantidad) || 1,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["mp-presupuesto", proyectoId] })
      queryClient.invalidateQueries({ queryKey: ["mp-proyectos"] })
      queryClient.invalidateQueries({ queryKey: ["mp-proyecto", proyectoId] })
      setItemForm({ concepto: "", detalle: "", valor_unitario: "", cantidad: "1" })
    },
  })

  const mutEliminarItem = useMutation({
    mutationFn: (itemId) => eliminarItemPresupuesto(itemId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["mp-presupuesto", proyectoId] })
      queryClient.invalidateQueries({ queryKey: ["mp-proyectos"] })
      queryClient.invalidateQueries({ queryKey: ["mp-proyecto", proyectoId] })
    },
  })

  return (
    <div className="fixed inset-0 bg-[#0D2B5E]/40 backdrop-blur-sm flex items-center justify-center p-4 z-50" onClick={onClose}>
      <div className="bg-white rounded-2xl w-full max-w-xl max-h-[90vh] overflow-y-auto shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="bg-gradient-to-r from-[#0D2B5E] to-[#1A4FA0] rounded-t-2xl p-6 text-white sticky top-0">
          <button onClick={onClose} className="absolute top-4 right-4 text-white/70 hover:text-white text-xl leading-none">✕</button>
          <h2 className="text-lg font-bold">{proyectoId ? "Editar proyecto" : "Nuevo proyecto"}</h2>
        </div>

        <div className="p-6 space-y-4">
          <div>
            <label className="block text-xs font-semibold text-[#6B7EA8] uppercase mb-1">Nombre del proyecto</label>
            <input value={form.nombre} onChange={set('nombre')} className="w-full rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm" />
          </div>

          <div>
            <label className="block text-xs font-semibold text-[#6B7EA8] uppercase mb-1">Objetivo</label>
            <textarea value={form.objetivo} onChange={set('objetivo')} rows={2} className="w-full rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm resize-none" />
          </div>

          <div>
            <label className="block text-xs font-semibold text-[#6B7EA8] uppercase mb-1">Alcance</label>
            <textarea value={form.alcance} onChange={set('alcance')} rows={2} className="w-full rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm resize-none" />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-[#6B7EA8] uppercase mb-1">Líder</label>
              <select value={form.lider_id} onChange={set('lider_id')} className="w-full rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm">
                <option value="">Sin asignar</option>
                {usuarios.map(u => <option key={u.id} value={u.id}>{u.nombre}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-[#6B7EA8] uppercase mb-1">Área responsable</label>
              <select value={form.area} onChange={set('area')} className="w-full rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm">
                <option value="">Sin definir</option>
                {AREAS.map(a => <option key={a} value={a}>{a}</option>)}
              </select>
            </div>
          </div>

          {/* Áreas participantes: dan visibilidad, no presupuesto. El
              presupuesto se le atribuye siempre al área responsable, si no
              los totales por área saldrían duplicados. */}
          <div>
            <label className="block text-xs font-semibold text-[#6B7EA8] uppercase mb-1">
              Otras áreas que participan
            </label>
            <div className="flex flex-wrap gap-2">
              {AREAS.filter(a => a !== form.area).map(a => {
                const activa = form.areas_participantes.includes(a)
                return (
                  <button
                    key={a} type="button"
                    onClick={() => setForm({
                      ...form,
                      areas_participantes: activa
                        ? form.areas_participantes.filter(x => x !== a)
                        : [...form.areas_participantes, a],
                    })}
                    className={`text-xs font-semibold rounded-full px-3 py-1.5 border transition ${
                      activa
                        ? 'bg-[#EAF0FB] border-[#1A4FA0] text-[#1A4FA0]'
                        : 'bg-white border-[#D6E0F0] text-[#6B7EA8] hover:border-[#1A4FA0]'
                    }`}
                  >
                    {activa && '✓ '}{a}
                  </button>
                )
              })}
            </div>
            <p className="text-[11px] text-[#9BACC8] mt-1.5">
              Su gente podrá ver el proyecto. El presupuesto sigue contando solo para el área responsable.
            </p>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-[#6B7EA8] uppercase mb-1">Estado</label>
              <select value={form.estado} onChange={set('estado')} className="w-full rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm">
                {Object.entries(ESTADOS_PROYECTO).map(([v, cfg]) => <option key={v} value={v}>{cfg.label}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-[#6B7EA8] uppercase mb-1">Prioridad</label>
              <select value={form.prioridad} onChange={set('prioridad')} className="w-full rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm">
                {Object.entries(PRIORIDADES).map(([v, cfg]) => <option key={v} value={v}>{cfg.label}</option>)}
              </select>
            </div>
          </div>

          {/* Las fechas del proyecto van a nivel de día; la hora solo importa
              en las tareas, que son las que se ubican en el calendario. */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-[#6B7EA8] uppercase mb-1">Inicio</label>
              <input type="date" value={form.fecha_inicio} onChange={set('fecha_inicio')} className="w-full rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm" />
            </div>
            <div>
              <label className="block text-xs font-semibold text-[#6B7EA8] uppercase mb-1">Fin estimado</label>
              <input type="date" value={form.fecha_fin_estimada} onChange={set('fecha_fin_estimada')} className="w-full rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm" />
            </div>
          </div>

          <button
            onClick={() => mutGuardar.mutate()}
            disabled={!form.nombre || mutGuardar.isPending}
            className="w-full bg-[#1A4FA0] hover:bg-[#0D2B5E] disabled:opacity-40 text-white font-semibold py-2.5 rounded-lg transition"
          >
            {proyectoId ? "Guardar cambios" : "Crear proyecto y continuar"}
          </button>

          {/* Presupuesto: solo disponible una vez el proyecto existe */}
          {proyectoId && (
            <div className="border-t border-[#EDF2F7] pt-5 mt-2">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-bold text-[#0D2B5E]">Presupuesto</h3>
                <span className="text-sm font-bold text-[#0D2B5E]">{formatMoneda(total)}</span>
              </div>

              <div className="space-y-2 mb-3">
                {items.map(item => (
                  <div key={item.id} className="flex items-center justify-between bg-[#F7F9FC] rounded-lg px-3 py-2 text-sm">
                    <div>
                      <p className="font-medium text-[#1A2B47]">{item.concepto}</p>
                      <p className="text-xs text-[#6B7EA8]">{item.cantidad} × {formatMoneda(item.valor_unitario)} = {formatMoneda(item.valor_total)}</p>
                    </div>
                    <button onClick={() => mutEliminarItem.mutate(item.id)} className="text-red-500 hover:text-red-700 text-xs font-semibold">
                      Quitar
                    </button>
                  </div>
                ))}
                {items.length === 0 && <p className="text-xs text-[#9BACC8] text-center py-3">Sin ítems de presupuesto aún.</p>}
              </div>

              <div className="grid grid-cols-4 gap-2">
                <input
                  placeholder="Concepto" value={itemForm.concepto}
                  onChange={(e) => setItemForm({ ...itemForm, concepto: e.target.value })}
                  className="col-span-2 rounded-lg border border-[#D6E0F0] px-2 py-1.5 text-xs"
                />
                <input
                  placeholder="Valor unitario" type="number" value={itemForm.valor_unitario}
                  onChange={(e) => setItemForm({ ...itemForm, valor_unitario: e.target.value })}
                  className="rounded-lg border border-[#D6E0F0] px-2 py-1.5 text-xs"
                />
                <input
                  placeholder="Cant." type="number" value={itemForm.cantidad}
                  onChange={(e) => setItemForm({ ...itemForm, cantidad: e.target.value })}
                  className="rounded-lg border border-[#D6E0F0] px-2 py-1.5 text-xs"
                />
              </div>
              <button
                onClick={() => mutAgregarItem.mutate()}
                disabled={!itemForm.concepto || mutAgregarItem.isPending}
                className="w-full mt-2 border border-[#D6E0F0] hover:bg-gray-50 disabled:opacity-40 text-xs font-semibold text-[#0D2B5E] py-2 rounded-lg transition"
              >
                + Agregar ítem
              </button>

              <button
                onClick={onClose}
                className="w-full mt-4 bg-[#F7F9FC] hover:bg-[#EAF0FB] text-sm font-semibold text-[#0D2B5E] py-2.5 rounded-lg transition"
              >
                Listo
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
