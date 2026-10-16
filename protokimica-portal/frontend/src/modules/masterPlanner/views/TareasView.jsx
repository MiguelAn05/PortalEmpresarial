import { useMemo } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import KPICards from "../components/KPICards"
import Filters from "../components/Filters"
import KanbanBoard from "../components/KanbanBoard"
import TareasTable from "../components/TareasTable"
import GanttView from "../components/GanttView"
import { listarTareas, actualizarTarea } from "../api"
import { FILTROS_TAREAS_VACIOS, filtrarTareas, puedeEditar } from "../constants"
import { useAuth } from "../../../core/useAuth.js"
import { useFiltrosEnUrl } from '../../../core/useFiltrosEnUrl.js'

/** Vista global: todas las tareas de todos los proyectos activos. */
export default function TareasView({ proyectos, usuarios, onSelectTarea, onNuevaTarea }) {
  const queryClient = useQueryClient()
  const { user } = useAuth()
  const editable = puedeEditar(user)
  // En la URL, con prefijo propio (ver ProyectosView).
  const [filtrosUrl, cambiarFiltros] = useFiltrosEnUrl({ ...FILTROS_TAREAS_VACIOS, vista: 'kanban' }, { prefijo: 't_' })
  const vista = filtrosUrl.vista
  // Solo los filtros: el panel cuenta sus claves para saber si hay alguno puesto.
  const filtros = useMemo(
    () => Object.fromEntries(Object.keys(FILTROS_TAREAS_VACIOS).map(k => [k, filtrosUrl[k]])),
    [filtrosUrl],
  )
  const setVista = (v) => cambiarFiltros({ vista: v })
  const setFiltros = (nuevos) => cambiarFiltros(nuevos)

  const { data: tareas = [], isLoading, isError } = useQuery({
    queryKey: ["mp-tareas"],
    queryFn: () => listarTareas(),
  })

  const mutCambiarEstado = useMutation({
    mutationFn: ({ id, estado }) => actualizarTarea(id, { estado }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["mp-tareas"] })
      queryClient.invalidateQueries({ queryKey: ["mp-proyectos"] })
    },
  })

  const visibles = useMemo(() => filtrarTareas(tareas, filtros), [tareas, filtros])

  if (isError) {
    return (
      <div className="text-center py-16 text-negativo text-sm">
        No se pudo cargar la información. Intenta recargar la página.
      </div>
    )
  }

  if (isLoading) {
    return <div className="text-center py-16 text-texto-3 text-sm">Cargando tareas...</div>
  }

  if (proyectos.length === 0) {
    return (
      <div className="bg-white rounded-2xl border border-dashed border-borde p-16 text-center">
        <p className="text-texto-2">
          Las tareas viven dentro de un proyecto. Crea un proyecto primero en la pestaña Proyectos.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-5">
      <KPICards tareas={tareas} />

      <Filters
        filtros={filtros}
        onChange={setFiltros}
        vista={vista}
        onChangeVista={setVista}
        proyectos={proyectos}
        usuarios={usuarios}
        totalVisible={visibles.length}
        totalGeneral={tareas.length}
      />

      {tareas.length === 0 ? (
        <div className="bg-white rounded-2xl border border-dashed border-borde p-16 text-center">
          <p className="text-texto-2 mb-4">Todavía no hay tareas creadas.</p>
          {editable && (
            <button
              onClick={onNuevaTarea}
              className="bg-acento hover:bg-acento-fuerte text-white font-semibold px-6 py-3 rounded-xl shadow-sm transition"
            >
              + Crear la primera tarea
            </button>
          )}
        </div>
      ) : vista === "kanban" ? (
        <KanbanBoard
          tareas={visibles}
          arrastrable={editable}
          onChangeEstado={(id, estado) => mutCambiarEstado.mutate({ id, estado })}
          onSelect={onSelectTarea}
        />
      ) : vista === "tabla" ? (
        <TareasTable tareas={visibles} onSelect={onSelectTarea} />
      ) : (
        <GanttView tareas={visibles} onSelect={onSelectTarea} />
      )}
    </div>
  )
}
