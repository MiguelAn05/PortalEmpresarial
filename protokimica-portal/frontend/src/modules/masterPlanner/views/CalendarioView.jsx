import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import CalendarioTareas from "../components/CalendarioTareas"
import { listarTareas } from "../api"
import { AREAS, ESTADOS_TAREA, filtrarTareas } from "../constants"

// El calendario responde a "¿quién está haciendo qué y cuándo?", así que
// filtra por persona y proyecto, no por todo lo que filtra el tablero.
const FILTROS_VACIOS = { busqueda: "", proyecto_id: "", asignado_a: "", area: "", estado: "", prioridad: "", vencimiento: "" }

export default function CalendarioView({ proyectos, usuarios, onSelectTarea }) {
  const [filtros, setFiltros] = useState(FILTROS_VACIOS)
  const [ocultarCompletadas, setOcultarCompletadas] = useState(false)

  const { data: tareas = [], isLoading } = useQuery({
    queryKey: ["mp-tareas", { calendario: true }],
    // El calendario sí incluye subtareas: si alguien tiene una subtarea con
    // fecha, esa fecha ocupa su tiempo igual que cualquier otra tarea.
    queryFn: () => listarTareas({ incluir_subtareas: true }),
  })

  const set = (campo) => (e) => setFiltros({ ...filtros, [campo]: e.target.value })

  const visibles = useMemo(() => {
    const base = filtrarTareas(tareas, filtros)
    return ocultarCompletadas ? base.filter(t => t.estado !== 'completada') : base
  }, [tareas, filtros, ocultarCompletadas])

  if (isLoading) {
    return <div className="text-center py-16 text-[#9BACC8] text-sm">Cargando calendario...</div>
  }

  return (
    <div className="space-y-5">
      <div className="bg-white rounded-2xl border border-[#D6E0F0] p-5 shadow-sm">
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
          <div>
            <label className="block text-xs font-semibold text-[#6B7EA8] uppercase mb-1">Responsable</label>
            <select value={filtros.asignado_a} onChange={set('asignado_a')} className="w-full rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm">
              <option value="">Todos</option>
              <option value="sin_asignar">Sin asignar</option>
              {usuarios.map(u => <option key={u.id} value={u.id}>{u.nombre}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold text-[#6B7EA8] uppercase mb-1">Proyecto</label>
            <select value={filtros.proyecto_id} onChange={set('proyecto_id')} className="w-full rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm">
              <option value="">Todos</option>
              {proyectos.map(p => <option key={p.id} value={p.id}>{p.nombre}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold text-[#6B7EA8] uppercase mb-1">Área</label>
            <select value={filtros.area} onChange={set('area')} className="w-full rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm">
              <option value="">Todas</option>
              {AREAS.map(a => <option key={a} value={a}>{a}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold text-[#6B7EA8] uppercase mb-1">Estado</label>
            <select value={filtros.estado} onChange={set('estado')} className="w-full rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm">
              <option value="">Todos</option>
              {Object.entries(ESTADOS_TAREA).map(([v, cfg]) => <option key={v} value={v}>{cfg.label}</option>)}
            </select>
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 mt-4">
          <label className="flex items-center gap-2 text-sm text-[#6B7EA8] cursor-pointer select-none">
            <input
              type="checkbox" checked={ocultarCompletadas}
              onChange={(e) => setOcultarCompletadas(e.target.checked)}
              className="rounded border-[#D6E0F0] accent-[#1A4FA0]"
            />
            Ocultar completadas
          </label>
          <span className="text-xs text-[#9BACC8]">
            {visibles.length} de {tareas.length} tarea{tareas.length === 1 ? '' : 's'}
          </span>
        </div>
      </div>

      <CalendarioTareas tareas={visibles} onSelect={onSelectTarea} />
    </div>
  )
}
