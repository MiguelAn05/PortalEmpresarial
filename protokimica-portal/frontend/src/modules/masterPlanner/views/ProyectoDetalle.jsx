import { useMemo, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import KanbanBoard from "../components/KanbanBoard"
import TareasTable from "../components/TareasTable"
import GanttView from "../components/GanttView"
import CalendarioTareas from "../components/CalendarioTareas"
import KPICards from "../components/KPICards"
import PriorityBadge from "../components/PriorityBadge"
import Avatar from "../components/Avatar"
import {
  obtenerProyecto, listarTareasDeProyecto, actualizarTarea, actualizarProyecto,
  listarPresupuesto, agregarItemPresupuesto, eliminarItemPresupuesto,
} from "../api"
import {
  ESTADOS_PROYECTO, ESTADOS_TAREA, PRIORIDADES,
  FILTROS_TAREAS_VACIOS, filtrarTareas, alertaVencimiento,
  colorAvance, formatFecha, formatMoneda,
} from "../constants"

const SUBVISTAS = [
  { id: 'tablero',     label: '🗂️ Tablero' },
  { id: 'tabla',       label: '📋 Tabla' },
  { id: 'cronograma',  label: '📊 Cronograma' },
  { id: 'calendario',  label: '🗓️ Calendario' },
  { id: 'presupuesto', label: '💰 Presupuesto' },
  { id: 'informacion', label: 'ℹ️ Información' },
]

export default function ProyectoDetalle({ proyectoId, usuarios, onVolver, onSelectTarea, onNuevaTarea, onEditar }) {
  const queryClient = useQueryClient()
  const [subvista, setSubvista] = useState('tablero')
  const [filtros, setFiltros] = useState(FILTROS_TAREAS_VACIOS)

  const { data: proyecto, isLoading: cargandoProyecto } = useQuery({
    queryKey: ["mp-proyecto", proyectoId],
    queryFn: () => obtenerProyecto(proyectoId),
  })

  const { data: tareas = [], isLoading: cargandoTareas } = useQuery({
    queryKey: ["mp-tareas", { proyecto: proyectoId }],
    queryFn: () => listarTareasDeProyecto(proyectoId),
  })

  const invalidar = () => {
    queryClient.invalidateQueries({ queryKey: ["mp-tareas"] })
    queryClient.invalidateQueries({ queryKey: ["mp-proyecto", proyectoId] })
    queryClient.invalidateQueries({ queryKey: ["mp-proyectos"] })
  }

  const mutCambiarEstadoTarea = useMutation({
    mutationFn: ({ id, estado }) => actualizarTarea(id, { estado }),
    onSuccess: invalidar,
  })

  const mutCampoProyecto = useMutation({
    mutationFn: (payload) => actualizarProyecto(proyectoId, payload),
    onSuccess: invalidar,
  })

  const visibles = useMemo(() => filtrarTareas(tareas, filtros), [tareas, filtros])
  const set = (campo) => (e) => setFiltros({ ...filtros, [campo]: e.target.value })
  const hayFiltros = Object.values(filtros).some(v => v !== "")

  if (cargandoProyecto || !proyecto) {
    return <div className="text-center py-16 text-[#9BACC8] text-sm">Cargando proyecto...</div>
  }

  const estadoCfg = ESTADOS_PROYECTO[proyecto.estado] || {}
  const vencidas = tareas.filter(t => alertaVencimiento(t) === 'vencida').length
  const necesitaFiltros = ['tablero', 'tabla', 'cronograma', 'calendario'].includes(subvista)

  return (
    <div className="space-y-5">
      <button onClick={onVolver} className="text-sm font-semibold text-[#1A4FA0] hover:underline">
        ← Volver a proyectos
      </button>

      {/* Cabecera del proyecto */}
      <div className="bg-white rounded-2xl border border-[#D6E0F0] shadow-sm overflow-hidden">
        <div className="p-6">
          <div className="flex flex-wrap justify-between items-start gap-4">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2 mb-2">
                <select
                  value={proyecto.estado}
                  onChange={(e) => mutCampoProyecto.mutate({ estado: e.target.value })}
                  className={`text-xs font-semibold rounded-full px-3 py-1 border-0 cursor-pointer ${estadoCfg.color || 'bg-gray-100'}`}
                >
                  {Object.entries(ESTADOS_PROYECTO).map(([v, cfg]) => <option key={v} value={v}>{cfg.label}</option>)}
                </select>
                <PriorityBadge priority={proyecto.prioridad} />
                {proyecto.area && (
                  <span className="px-3 py-1 rounded-full text-xs font-semibold bg-[#F7F9FC] border border-[#D6E0F0] text-[#6B7EA8]">
                    {proyecto.area}
                  </span>
                )}
                {proyecto.archivado && (
                  <span className="px-3 py-1 rounded-full text-xs font-semibold bg-gray-100 text-gray-500">Archivado</span>
                )}
              </div>
              <h2 className="text-2xl font-bold text-[#0D2B5E]">{proyecto.nombre}</h2>
              {proyecto.objetivo && <p className="text-sm text-[#6B7EA8] mt-1 max-w-2xl">{proyecto.objetivo}</p>}
            </div>

            <div className="flex gap-2 shrink-0">
              <button
                onClick={() => onEditar(proyecto)}
                className="border border-[#D6E0F0] hover:bg-gray-50 text-[#0D2B5E] text-sm font-semibold px-4 py-2.5 rounded-xl transition"
              >
                Editar proyecto
              </button>
              <button
                onClick={onNuevaTarea}
                className="bg-[#1A4FA0] hover:bg-[#0D2B5E] text-white text-sm font-semibold px-4 py-2.5 rounded-xl transition"
              >
                + Nueva tarea
              </button>
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-5 gap-5 mt-6 pt-5 border-t border-[#EDF2F7]">
            <Dato titulo="Líder"><Avatar name={proyecto.lider_nombre} compact /></Dato>
            <Dato titulo="Inicio">{formatFecha(proyecto.fecha_inicio)}</Dato>
            <Dato titulo="Fin estimado">{formatFecha(proyecto.fecha_fin_estimada)}</Dato>
            <Dato titulo="Presupuesto">{formatMoneda(proyecto.presupuesto_total)}</Dato>
            <Dato titulo={`Avance · ${proyecto.tareas_completadas}/${proyecto.total_tareas} tareas`}>
              <div className="flex items-center gap-2">
                <div className="flex-1 bg-gray-200 rounded-full h-2">
                  <div className="h-2 rounded-full" style={{ width: `${proyecto.avance_pct}%`, background: colorAvance(proyecto.avance_pct) }} />
                </div>
                <span className="text-sm font-bold text-[#0D2B5E]">{proyecto.avance_pct}%</span>
              </div>
            </Dato>
          </div>

          {vencidas > 0 && (
            <div className="mt-4 bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl px-4 py-2.5 font-semibold">
              {vencidas} tarea{vencidas === 1 ? '' : 's'} de este proyecto {vencidas === 1 ? 'está vencida' : 'están vencidas'}.
            </div>
          )}
        </div>

        <div className="border-t border-[#D6E0F0] px-6 flex gap-1 overflow-x-auto">
          {SUBVISTAS.map(v => (
            <button
              key={v.id}
              onClick={() => setSubvista(v.id)}
              className={`px-4 py-3 text-sm font-semibold border-b-2 -mb-px whitespace-nowrap transition ${
                subvista === v.id ? 'border-[#1A4FA0] text-[#0D2B5E]' : 'border-transparent text-[#6B7EA8] hover:text-[#0D2B5E]'
              }`}
            >
              {v.label}
            </button>
          ))}
        </div>
      </div>

      {/* Filtros de tareas dentro del proyecto (sin filtro de proyecto, ya estamos en uno) */}
      {necesitaFiltros && tareas.length > 0 && (
        <div className="bg-white rounded-2xl border border-[#D6E0F0] p-4 shadow-sm">
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-3">
            <input
              value={filtros.busqueda} onChange={set('busqueda')}
              placeholder="Buscar tarea..."
              className="rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#1A4FA0]"
            />
            <select value={filtros.asignado_a} onChange={set('asignado_a')} className="rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm">
              <option value="">Todos los responsables</option>
              <option value="sin_asignar">Sin asignar</option>
              {usuarios.map(u => <option key={u.id} value={u.id}>{u.nombre}</option>)}
            </select>
            <select value={filtros.estado} onChange={set('estado')} className="rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm">
              <option value="">Todos los estados</option>
              {Object.entries(ESTADOS_TAREA).map(([v, cfg]) => <option key={v} value={v}>{cfg.label}</option>)}
            </select>
            <select value={filtros.prioridad} onChange={set('prioridad')} className="rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm">
              <option value="">Todas las prioridades</option>
              {Object.entries(PRIORIDADES).map(([v, cfg]) => <option key={v} value={v}>{cfg.label}</option>)}
            </select>
            <select value={filtros.vencimiento} onChange={set('vencimiento')} className="rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm">
              <option value="">Todo vencimiento</option>
              <option value="vencida">Solo vencidas</option>
              <option value="por_vencer">Solo por vencer</option>
              <option value="en_riesgo">Vencidas y por vencer</option>
              <option value="sin_fecha">Sin fecha de fin</option>
            </select>
          </div>
          {hayFiltros && (
            <div className="flex justify-between items-center mt-3">
              <span className="text-xs text-[#9BACC8]">{visibles.length} de {tareas.length} tareas</span>
              <button onClick={() => setFiltros(FILTROS_TAREAS_VACIOS)} className="text-xs font-semibold text-[#1A4FA0] hover:underline">
                Limpiar filtros
              </button>
            </div>
          )}
        </div>
      )}

      {cargandoTareas && necesitaFiltros ? (
        <div className="text-center py-16 text-[#9BACC8] text-sm">Cargando tareas...</div>
      ) : necesitaFiltros && tareas.length === 0 ? (
        <div className="bg-white rounded-2xl border border-dashed border-[#D6E0F0] p-16 text-center">
          <p className="text-[#6B7EA8] mb-4">Este proyecto todavía no tiene tareas.</p>
          <button
            onClick={onNuevaTarea}
            className="bg-[#1A4FA0] hover:bg-[#0D2B5E] text-white font-semibold px-6 py-3 rounded-xl shadow-sm transition"
          >
            + Crear la primera tarea
          </button>
        </div>
      ) : (
        <>
          {subvista === 'tablero' && (
            <div className="space-y-5">
              <KPICards tareas={tareas} />
              <KanbanBoard
                tareas={visibles}
                mostrarProyecto={false}
                onChangeEstado={(id, estado) => mutCambiarEstadoTarea.mutate({ id, estado })}
                onSelect={onSelectTarea}
              />
            </div>
          )}
          {subvista === 'tabla' && <TareasTable tareas={visibles} onSelect={onSelectTarea} mostrarProyecto={false} />}
          {subvista === 'cronograma' && <GanttView tareas={visibles} onSelect={onSelectTarea} mostrarProyecto={false} />}
          {subvista === 'calendario' && <CalendarioTareas tareas={visibles} onSelect={onSelectTarea} />}
          {subvista === 'presupuesto' && <PanelPresupuesto proyectoId={proyectoId} onCambio={invalidar} />}
          {subvista === 'informacion' && <PanelInformacion proyecto={proyecto} onEditar={() => onEditar(proyecto)} />}
        </>
      )}
    </div>
  )
}

function Dato({ titulo, children }) {
  return (
    <div>
      <p className="text-[11px] font-semibold text-[#9BACC8] uppercase tracking-wide mb-1.5">{titulo}</p>
      <div className="text-sm text-[#1A2B47]">{children}</div>
    </div>
  )
}

function PanelInformacion({ proyecto, onEditar }) {
  return (
    <div className="bg-white rounded-2xl border border-[#D6E0F0] shadow-sm p-6 space-y-5">
      <div className="flex justify-between items-start">
        <h3 className="text-sm font-bold text-[#0D2B5E]">Información del proyecto</h3>
        <button onClick={onEditar} className="text-xs font-semibold text-[#1A4FA0] hover:underline">Editar</button>
      </div>
      <Campo titulo="Objetivo" valor={proyecto.objetivo} />
      <Campo titulo="Alcance" valor={proyecto.alcance} />
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5 pt-2 border-t border-[#EDF2F7]">
        <Campo titulo="Fecha de inicio" valor={formatFecha(proyecto.fecha_inicio)} />
        <Campo titulo="Fin estimado" valor={formatFecha(proyecto.fecha_fin_estimada)} />
        <Campo titulo="Fin real" valor={proyecto.fecha_fin_real ? formatFecha(proyecto.fecha_fin_real) : 'Aún abierto'} />
      </div>
      <p className="text-[11px] text-[#9BACC8] pt-2 border-t border-[#EDF2F7]">
        Creado el {formatFecha(proyecto.creado_en)}
      </p>
    </div>
  )
}

function Campo({ titulo, valor }) {
  return (
    <div>
      <p className="text-[11px] font-semibold text-[#9BACC8] uppercase tracking-wide mb-1">{titulo}</p>
      <p className="text-sm text-[#1A2B47] whitespace-pre-line">{valor || <span className="text-[#C3CFE2] italic">Sin definir</span>}</p>
    </div>
  )
}

function PanelPresupuesto({ proyectoId, onCambio }) {
  const queryClient = useQueryClient()
  const [itemForm, setItemForm] = useState({ concepto: "", detalle: "", valor_unitario: "", cantidad: "1" })

  const { data: items = [] } = useQuery({
    queryKey: ["mp-presupuesto", proyectoId],
    queryFn: () => listarPresupuesto(proyectoId),
  })
  const total = items.reduce((s, i) => s + i.valor_total, 0)

  const refrescar = () => {
    queryClient.invalidateQueries({ queryKey: ["mp-presupuesto", proyectoId] })
    onCambio()
  }

  const mutAgregar = useMutation({
    mutationFn: () => agregarItemPresupuesto(proyectoId, {
      ...itemForm,
      valor_unitario: Number(itemForm.valor_unitario) || 0,
      cantidad: Number(itemForm.cantidad) || 1,
    }),
    onSuccess: () => { setItemForm({ concepto: "", detalle: "", valor_unitario: "", cantidad: "1" }); refrescar() },
  })

  const mutEliminar = useMutation({
    mutationFn: (id) => eliminarItemPresupuesto(id),
    onSuccess: refrescar,
  })

  return (
    <div className="bg-white rounded-2xl border border-[#D6E0F0] shadow-sm overflow-hidden">
      <div className="flex justify-between items-center px-6 py-4 border-b border-[#D6E0F0]">
        <h3 className="text-sm font-bold text-[#0D2B5E]">Presupuesto del proyecto</h3>
        <span className="text-lg font-bold text-[#0D2B5E]">{formatMoneda(total)}</span>
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full">
          <thead className="bg-[#F7F9FC] border-b border-[#D6E0F0]">
            <tr className="text-xs uppercase tracking-wider text-[#6B7EA8]">
              <th className="text-left px-6 py-3">Concepto</th>
              <th className="text-right px-6 py-3">Valor unitario</th>
              <th className="text-right px-6 py-3">Cantidad</th>
              <th className="text-right px-6 py-3">Total</th>
              <th className="px-6 py-3" />
            </tr>
          </thead>
          <tbody>
            {items.length === 0 && (
              <tr><td colSpan={5} className="px-6 py-10 text-center text-sm text-[#9BACC8]">
                Sin ítems de presupuesto todavía.
              </td></tr>
            )}
            {items.map(item => (
              <tr key={item.id} className="border-b border-[#EDF2F7]">
                <td className="px-6 py-3">
                  <p className="text-sm font-medium text-[#1A2B47]">{item.concepto}</p>
                  {item.detalle && <p className="text-xs text-[#9BACC8]">{item.detalle}</p>}
                </td>
                <td className="px-6 py-3 text-right text-sm">{formatMoneda(item.valor_unitario)}</td>
                <td className="px-6 py-3 text-right text-sm">{item.cantidad}</td>
                <td className="px-6 py-3 text-right text-sm font-semibold">{formatMoneda(item.valor_total)}</td>
                <td className="px-6 py-3 text-right">
                  <button
                    onClick={() => { if (confirm(`¿Quitar "${item.concepto}" del presupuesto?`)) mutEliminar.mutate(item.id) }}
                    className="text-xs text-red-500 hover:text-red-700 font-semibold"
                  >
                    Quitar
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="p-6 border-t border-[#D6E0F0] bg-[#F7F9FC]">
        <p className="text-xs font-semibold text-[#6B7EA8] uppercase mb-2">Agregar ítem</p>
        <div className="grid grid-cols-1 md:grid-cols-5 gap-2">
          <input
            placeholder="Concepto" value={itemForm.concepto}
            onChange={(e) => setItemForm({ ...itemForm, concepto: e.target.value })}
            className="md:col-span-2 rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm"
          />
          <input
            placeholder="Detalle (opcional)" value={itemForm.detalle}
            onChange={(e) => setItemForm({ ...itemForm, detalle: e.target.value })}
            className="rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm"
          />
          <input
            placeholder="Valor unitario" type="number" value={itemForm.valor_unitario}
            onChange={(e) => setItemForm({ ...itemForm, valor_unitario: e.target.value })}
            className="rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm"
          />
          <input
            placeholder="Cantidad" type="number" value={itemForm.cantidad}
            onChange={(e) => setItemForm({ ...itemForm, cantidad: e.target.value })}
            className="rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm"
          />
        </div>
        <button
          onClick={() => mutAgregar.mutate()}
          disabled={!itemForm.concepto || mutAgregar.isPending}
          className="mt-3 bg-[#1A4FA0] hover:bg-[#0D2B5E] disabled:opacity-40 text-white text-sm font-semibold px-5 py-2 rounded-lg transition"
        >
          + Agregar ítem
        </button>
      </div>
    </div>
  )
}
