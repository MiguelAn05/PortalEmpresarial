import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import Header from "./components/Header"
import ProyectosView from "./views/ProyectosView"
import ProyectoDetalle from "./views/ProyectoDetalle"
import TareasView from "./views/TareasView"
import CalendarioView from "./views/CalendarioView"
import TareaDetailModal from "./components/TareaDetailModal"
import ProyectoFormModal from "./components/ProyectoFormModal"
import TareaFormModal from "./components/TareaFormModal"
import { listarProyectos, listarUsuariosAsignables } from "./api"

/**
 * Shell del módulo. Tres pestañas:
 *  - Proyectos: la lista de proyectos; al entrar a uno se ven SUS tareas.
 *  - Tareas: mirada transversal a todas las tareas de todos los proyectos.
 *  - Calendario: quién está haciendo qué y cuándo.
 *
 * Los modales viven aquí (no dentro de cada vista) para que abrir una tarea
 * desde el tablero, la tabla, el cronograma o el calendario sea lo mismo.
 */
export default function MasterPlanner() {
  const [vista, setVista] = useState("proyectos")
  const [proyectoAbierto, setProyectoAbierto] = useState(null)
  const [tareaSeleccionadaId, setTareaSeleccionadaId] = useState(null)
  const [proyectoEnEdicion, setProyectoEnEdicion] = useState(null)
  const [mostrarFormProyecto, setMostrarFormProyecto] = useState(false)
  const [formTarea, setFormTarea] = useState(null) // null | { proyectoId }

  // Lista de proyectos activos: alimenta los dropdowns de los formularios y
  // los filtros. La vista de Proyectos hace su propia consulta porque además
  // puede pedir los archivados.
  const { data: proyectos = [] } = useQuery({
    queryKey: ["mp-proyectos", { archivados: false }],
    queryFn: () => listarProyectos({ archivados: false }),
  })

  const { data: usuarios = [] } = useQuery({
    queryKey: ["mp-usuarios"],
    queryFn: listarUsuariosAsignables,
  })

  const abrirFormProyecto = (proyecto = null) => {
    setProyectoEnEdicion(proyecto)
    setMostrarFormProyecto(true)
  }

  const cambiarVista = (nueva) => {
    setProyectoAbierto(null) // salir del drill-down al cambiar de pestaña
    setVista(nueva)
  }

  return (
    <div className="max-w-[1400px] mx-auto px-6 py-8 space-y-6">
      <Header
        vista={vista}
        onChangeVista={cambiarVista}
        onNuevoProyecto={() => abrirFormProyecto(null)}
        onNuevaTarea={() => setFormTarea({ proyectoId: proyectoAbierto })}
      />

      {vista === "proyectos" && (
        proyectoAbierto ? (
          <ProyectoDetalle
            proyectoId={proyectoAbierto}
            usuarios={usuarios}
            onVolver={() => setProyectoAbierto(null)}
            onSelectTarea={(t) => setTareaSeleccionadaId(t.id)}
            onNuevaTarea={() => setFormTarea({ proyectoId: proyectoAbierto })}
            onEditar={(p) => abrirFormProyecto(p)}
          />
        ) : (
          <ProyectosView
            onAbrirProyecto={setProyectoAbierto}
            onNuevoProyecto={() => abrirFormProyecto(null)}
            onEditarProyecto={(p) => abrirFormProyecto(p)}
          />
        )
      )}

      {vista === "tareas" && (
        <TareasView
          proyectos={proyectos}
          usuarios={usuarios}
          onSelectTarea={(t) => setTareaSeleccionadaId(t.id)}
          onNuevaTarea={() => setFormTarea({ proyectoId: null })}
        />
      )}

      {vista === "calendario" && (
        <CalendarioView
          proyectos={proyectos}
          usuarios={usuarios}
          onSelectTarea={(t) => setTareaSeleccionadaId(t.id)}
        />
      )}

      {tareaSeleccionadaId && (
        <TareaDetailModal
          tareaId={tareaSeleccionadaId}
          usuarios={usuarios}
          onClose={() => setTareaSeleccionadaId(null)}
        />
      )}

      {mostrarFormProyecto && (
        <ProyectoFormModal
          proyecto={proyectoEnEdicion}
          usuarios={usuarios}
          onClose={() => { setMostrarFormProyecto(false); setProyectoEnEdicion(null) }}
        />
      )}

      {formTarea && (
        <TareaFormModal
          proyectos={proyectos}
          usuarios={usuarios}
          proyectoIdInicial={formTarea.proyectoId}
          onClose={() => setFormTarea(null)}
        />
      )}
    </div>
  )
}
