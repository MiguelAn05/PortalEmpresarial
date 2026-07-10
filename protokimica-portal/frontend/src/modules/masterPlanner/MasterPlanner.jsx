import { useMemo, useState } from "react"
import Header from "./components/Header"
import KPICards from "./components/KPICards"
import Filters from "./components/Filters"
import ProjectsTable from "./components/ProjectsTable"
import KanbanBoard from "./components/KanbanBoard"
import ProjectDetailModal from "./components/ProjectDetailModal"
import mockProjects from "./data/mockProjects"

const FILTROS_VACIOS = { busqueda: "", area: "", estado: "", prioridad: "", año: "" }

export default function MasterPlanner() {
  const [projects, setProjects] = useState(mockProjects)
  const [filtros, setFiltros] = useState(FILTROS_VACIOS)
  const [vista, setVista] = useState("kanban")
  const [seleccionado, setSeleccionado] = useState(null)

  const filtrados = useMemo(() => {
    const q = filtros.busqueda.trim().toLowerCase()
    return projects.filter(p => {
      if (q && ![p.proyecto, p.actividad, p.responsable].join(" ").toLowerCase().includes(q)) return false
      if (filtros.area && p.area !== filtros.area) return false
      if (filtros.estado && p.estado !== filtros.estado) return false
      if (filtros.prioridad && p.prioridad !== filtros.prioridad) return false
      if (filtros.año && String(p.año) !== filtros.año) return false
      return true
    })
  }, [projects, filtros])

  const cambiarEstado = (id, nuevoEstado) => {
    setProjects(prev => prev.map(p => (p.id === id ? { ...p, estado: nuevoEstado } : p)))
  }

  return (
    <div className="space-y-6">
      <Header />
      <KPICards projects={projects} />
      <Filters filtros={filtros} onChange={setFiltros} vista={vista} onChangeVista={setVista} />

      {vista === "kanban" ? (
        <KanbanBoard
          projects={filtrados}
          onChangeEstado={cambiarEstado}
          onSelect={setSeleccionado}
        />
      ) : (
        <ProjectsTable projects={filtrados} onSelect={setSeleccionado} />
      )}

      <ProjectDetailModal project={seleccionado} onClose={() => setSeleccionado(null)} />
    </div>
  )
}
