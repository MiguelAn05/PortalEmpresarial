import { useMemo, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import ProyectoCard from "../components/ProyectoCard"
import { listarProyectos, archivarProyecto, eliminarProyecto } from "../api"
import { ESTADOS_PROYECTO, AREAS, puedeEditar } from "../constants"
import { useAuth } from "../../../core/AuthContext"

const FILTROS_VACIOS = { busqueda: "", estado: "", area: "" }

export default function ProyectosView({ onAbrirProyecto, onNuevoProyecto, onEditarProyecto }) {
  const queryClient = useQueryClient()
  const { user } = useAuth()
  const editable = puedeEditar(user)
  const [filtros, setFiltros] = useState(FILTROS_VACIOS)
  const [verArchivados, setVerArchivados] = useState(false)
  const [error, setError] = useState(null)

  const { data: proyectos = [], isLoading } = useQuery({
    queryKey: ["mp-proyectos", { archivados: verArchivados }],
    queryFn: () => listarProyectos({ archivados: verArchivados }),
  })

  const refrescar = () => queryClient.invalidateQueries({ queryKey: ["mp-proyectos"] })

  const mutArchivar = useMutation({
    mutationFn: ({ id, archivado }) => archivarProyecto(id, archivado),
    onSuccess: refrescar,
  })

  const mutEliminar = useMutation({
    mutationFn: (id) => eliminarProyecto(id),
    onSuccess: () => { setError(null); refrescar() },
    // El 409 del backend trae el motivo exacto (cuántas tareas lo bloquean).
    onError: (e) => setError(e?.response?.data?.detail || "No se pudo eliminar el proyecto."),
  })

  const set = (campo) => (e) => setFiltros({ ...filtros, [campo]: e.target.value })

  const visibles = useMemo(() => {
    const busqueda = filtros.busqueda.trim().toLowerCase()
    return proyectos.filter(p => {
      if (filtros.estado && p.estado !== filtros.estado) return false
      if (filtros.area && p.area !== filtros.area) return false
      if (busqueda) {
        const texto = `${p.nombre} ${p.objetivo || ''} ${p.lider_nombre || ''}`.toLowerCase()
        if (!texto.includes(busqueda)) return false
      }
      return true
    })
  }, [proyectos, filtros])

  return (
    <div className="space-y-5">
      <div className="bg-white rounded-2xl border border-[#D6E0F0] p-5 shadow-sm">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-xs font-semibold text-[#6B7EA8] uppercase mb-1">Buscar</label>
            <input
              value={filtros.busqueda} onChange={set('busqueda')}
              placeholder="Nombre, objetivo, líder..."
              className="w-full rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#1A4FA0]"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-[#6B7EA8] uppercase mb-1">Estado</label>
            <select value={filtros.estado} onChange={set('estado')} className="w-full rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm">
              <option value="">Todos</option>
              {Object.entries(ESTADOS_PROYECTO).map(([v, cfg]) => <option key={v} value={v}>{cfg.label}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold text-[#6B7EA8] uppercase mb-1">Área</label>
            <select value={filtros.area} onChange={set('area')} className="w-full rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm">
              <option value="">Todas</option>
              {AREAS.map(a => <option key={a} value={a}>{a}</option>)}
            </select>
          </div>
        </div>

        <div className="flex items-center justify-between mt-4">
          <label className="flex items-center gap-2 text-sm text-[#6B7EA8] cursor-pointer select-none">
            <input
              type="checkbox" checked={verArchivados}
              onChange={(e) => setVerArchivados(e.target.checked)}
              className="rounded border-[#D6E0F0] accent-[#1A4FA0]"
            />
            Ver proyectos archivados
          </label>
          <span className="text-xs text-[#9BACC8]">
            {visibles.length} de {proyectos.length} proyecto{proyectos.length === 1 ? '' : 's'}
          </span>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl px-4 py-3 flex justify-between gap-4">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="font-semibold shrink-0">Cerrar</button>
        </div>
      )}

      {isLoading ? (
        <div className="text-center py-16 text-[#9BACC8] text-sm">Cargando proyectos...</div>
      ) : visibles.length === 0 ? (
        <div className="bg-white rounded-2xl border border-dashed border-[#D6E0F0] p-16 text-center">
          <p className="text-[#6B7EA8] mb-4">
            {proyectos.length === 0
              ? (verArchivados ? "No hay proyectos archivados." : "Todavía no hay proyectos creados.")
              : "Ningún proyecto coincide con los filtros."}
          </p>
          {proyectos.length === 0 && !verArchivados && editable && (
            <button
              onClick={onNuevoProyecto}
              className="bg-[#F5A800] hover:bg-[#FFC840] text-[#0D2B5E] font-semibold px-6 py-3 rounded-xl shadow-sm transition"
            >
              + Crear el primer proyecto
            </button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
          {visibles.map(p => (
            <ProyectoCard
              key={p.id}
              proyecto={p}
              editable={editable}
              onAbrir={() => onAbrirProyecto(p.id)}
              onEditar={() => onEditarProyecto(p)}
              onArchivar={() => mutArchivar.mutate({ id: p.id, archivado: !p.archivado })}
              onEliminar={() => {
                if (confirm(`¿Eliminar definitivamente el proyecto "${p.nombre}"? Esta acción no se puede deshacer.`)) {
                  mutEliminar.mutate(p.id)
                }
              }}
            />
          ))}
        </div>
      )}
    </div>
  )
}
