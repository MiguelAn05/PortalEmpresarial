import { useMemo, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import Header from "./components/Header"
import KPICards from "./components/KPICards"
import Filters from "./components/Filters"
import KanbanBoard from "./components/KanbanBoard"
import ProjectsTable from "./components/ProjectsTable"
import ProjectDetailModal from "./components/ProjectDetailModal"
import ProyectoFormModal from "./components/ProyectoFormModal"
import TareaFormModal from "./components/TareaFormModal"
import { listarProyectos, listarTareas, actualizarTarea, listarUsuariosAsignables } from "./api"

const FILTROS_VACIOS = { busqueda: "", proyecto_id: "", area: "", estado: "", prioridad: "" }

export default function MasterPlanner() {
  const queryClient = useQueryClient()
  const [vista, setVista] = useState("kanban")
  const [filtros, setFiltros] = useState(FILTROS_VACIOS)
  const [tareaSeleccionada, setTareaSeleccionada] = useState(null)
  const [proyectoEnEdicion, setProyectoEnEdicion] = useState(null)
  const [mostrarFormProyecto, setMostrarFormProyecto] = useState(false)
  const [mostrarFormTarea, setMostrarFormTarea] = useState(false)

  const { data: proyectos = [], isLoading: cargandoProyectos } = useQuery({
    queryKey: ["mp-proyectos"],
    queryFn: () => listarProyectos(),
  })

  const { data: tareas = [], isLoading: cargandoTareas, isError } = useQuery({
    queryKey: ["mp-tareas"],
    queryFn: () => listarTareas(),
  })

  const { data: usuarios = [] } = useQuery({
    queryKey: ["mp-usuarios"],
    queryFn: listarUsuariosAsignables,
  })

  const mutCambiarEstado = useMutation({
    mutationFn: ({ id, estado }) => actualizarTarea(id, { estado }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["mp-tareas"] })
      queryClient.invalidateQueries({ queryKey: ["mp-proyectos"] })
    },
  })

  const tareasFiltradas = useMemo(() => {
    const busqueda = filtros.busqueda.trim().toLowerCase()
    return tareas.filter(t => {
      if (filtros.proyecto_id && String(t.proyecto_id) !== String(filtros.proyecto_id)) return false
      if (filtros.area && t.area !== filtros.area) return false
      if (filtros.estado && t.estado !== filtros.estado) return false
      if (filtros.prioridad && t.prioridad !== filtros.prioridad) return false
      if (busqueda) {
        const texto = `${t.titulo} ${t.proyecto_nombre || ''} ${t.asignado_nombre || ''}`.toLowerCase()
        if (!texto.includes(busqueda)) return false
      }
      return true
    })
  }, [tareas, filtros])

  // Si la tarea seleccionada se actualizó (ej. desde la lista tras un refetch), mantenla sincronizada
  const tareaSeleccionadaActual = tareaSeleccionada
    ? tareas.find(t => t.id === tareaSeleccionada.id) || tareaSeleccionada
    : null

  return (
    <div className="max-w-[1400px] mx-auto px-6 py-8 space-y-6">
      <Header
        onNuevoProyecto={() => { setProyectoEnEdicion(null); setMostrarFormProyecto(true) }}
        onNuevaTarea={() => setMostrarFormTarea(true)}
      />

      <KPICards tareas={tareas} />

      <Filters
        filtros={filtros}
        onChange={setFiltros}
        vista={vista}
        onChangeVista={setVista}
        proyectos={proyectos}
      />

      {(cargandoProyectos || cargandoTareas) && (
        <div className="text-center py-16 text-[#9BACC8] text-sm">Cargando Master Planner...</div>
      )}

      {isError && (
        <div className="text-center py-16 text-red-500 text-sm">
          No se pudo cargar la información. Intenta recargar la página.
        </div>
      )}

      {!cargandoProyectos && !cargandoTareas && !isError && (
        <>
          {proyectos.length === 0 ? (
            <div className="bg-white rounded-2xl border border-dashed border-[#D6E0F0] p-16 text-center">
              <p className="text-[#6B7EA8] mb-4">Todavía no hay proyectos creados.</p>
              <button
                onClick={() => { setProyectoEnEdicion(null); setMostrarFormProyecto(true) }}
                className="bg-[#F5A800] hover:bg-[#FFC840] text-[#0D2B5E] font-semibold px-6 py-3 rounded-xl shadow-sm transition"
              >
                + Crear el primer proyecto
              </button>
            </div>
          ) : vista === "kanban" ? (
            <KanbanBoard
              tareas={tareasFiltradas}
              onChangeEstado={(id, estado) => mutCambiarEstado.mutate({ id, estado })}
              onSelect={setTareaSeleccionada}
            />
          ) : (
            <ProjectsTable tareas={tareasFiltradas} onSelect={setTareaSeleccionada} />
          )}
        </>
      )}

      {tareaSeleccionadaActual && (
        <ProjectDetailModal
          tarea={tareaSeleccionadaActual}
          usuarios={usuarios}
          onClose={() => setTareaSeleccionada(null)}
        />
      )}

      {mostrarFormProyecto && (
        <ProyectoFormModal
          proyecto={proyectoEnEdicion}
          usuarios={usuarios}
          onClose={() => setMostrarFormProyecto(false)}
        />
      )}

      {mostrarFormTarea && (
        <TareaFormModal
          proyectos={proyectos}
          usuarios={usuarios}
          onClose={() => setMostrarFormTarea(false)}
        />
      )}
    </div>
  )
}
