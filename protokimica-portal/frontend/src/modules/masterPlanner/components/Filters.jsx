import { ESTADOS_TAREA, PRIORIDADES, AREAS } from "../constants"
import {
  IconoCronograma, IconoProyectos, IconoTabla,
} from '../../../core/components/Iconos.jsx'

const VISTAS = [
  { id: 'kanban',     label: 'Kanban',     Icono: IconoProyectos  },
  { id: 'tabla',      label: 'Tabla',      Icono: IconoTabla      },
  { id: 'cronograma', label: 'Cronograma', Icono: IconoCronograma },
]

/**
 * Filtros del listado de tareas. `proyectos` es opcional: dentro de un
 * proyecto no tiene sentido volver a filtrar por proyecto.
 */
export default function Filters({
  filtros, onChange, vista, onChangeVista,
  proyectos = null, usuarios = [], totalVisible, totalGeneral,
}) {
  const set = (campo) => (e) => onChange({ ...filtros, [campo]: e.target.value })
  const hayFiltros = Object.values(filtros).some(v => v !== "")

  return (
    <div className="bg-white rounded-2xl border border-borde p-5 shadow-sm">
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-6 gap-4">

        <div className="xl:col-span-2">
          <label className="block text-xs font-semibold text-texto-2 uppercase mb-1">Buscar</label>
          <input
            value={filtros.busqueda}
            onChange={set('busqueda')}
            placeholder="Tarea, proyecto, asignado..."
            className="w-full rounded-lg border border-borde px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-acento"
          />
        </div>

        {proyectos && (
          <div>
            <label className="block text-xs font-semibold text-texto-2 uppercase mb-1">Proyecto</label>
            <select value={filtros.proyecto_id} onChange={set('proyecto_id')} className="w-full rounded-lg border border-borde px-3 py-2 text-sm">
              <option value="">Todos</option>
              {proyectos.map(p => <option key={p.id} value={p.id}>{p.nombre}</option>)}
            </select>
          </div>
        )}

        <div>
          <label className="block text-xs font-semibold text-texto-2 uppercase mb-1">Responsable</label>
          <select value={filtros.asignado_a} onChange={set('asignado_a')} className="w-full rounded-lg border border-borde px-3 py-2 text-sm">
            <option value="">Todos</option>
            <option value="sin_asignar">Sin asignar</option>
            {usuarios.map(u => <option key={u.id} value={u.id}>{u.nombre}</option>)}
          </select>
        </div>

        <div>
          <label className="block text-xs font-semibold text-texto-2 uppercase mb-1">Área</label>
          <select value={filtros.area} onChange={set('area')} className="w-full rounded-lg border border-borde px-3 py-2 text-sm">
            <option value="">Todas</option>
            {AREAS.map(a => <option key={a} value={a}>{a}</option>)}
          </select>
        </div>

        <div>
          <label className="block text-xs font-semibold text-texto-2 uppercase mb-1">Estado</label>
          <select value={filtros.estado} onChange={set('estado')} className="w-full rounded-lg border border-borde px-3 py-2 text-sm">
            <option value="">Todos</option>
            {Object.entries(ESTADOS_TAREA).map(([valor, cfg]) => <option key={valor} value={valor}>{cfg.label}</option>)}
          </select>
        </div>

        <div>
          <label className="block text-xs font-semibold text-texto-2 uppercase mb-1">Prioridad</label>
          <select value={filtros.prioridad} onChange={set('prioridad')} className="w-full rounded-lg border border-borde px-3 py-2 text-sm">
            <option value="">Todas</option>
            {Object.entries(PRIORIDADES).map(([valor, cfg]) => <option key={valor} value={valor}>{cfg.label}</option>)}
          </select>
        </div>

        <div>
          <label className="block text-xs font-semibold text-texto-2 uppercase mb-1">Vencimiento</label>
          <select value={filtros.vencimiento} onChange={set('vencimiento')} className="w-full rounded-lg border border-borde px-3 py-2 text-sm">
            <option value="">Todas</option>
            <option value="vencida">Solo vencidas</option>
            <option value="por_vencer">Solo por vencer</option>
            <option value="en_riesgo">Vencidas y por vencer</option>
            <option value="sin_fecha">Sin fecha de fin</option>
          </select>
        </div>
      </div>

      <div className="flex flex-wrap justify-between items-center gap-3 mt-5">
        <div className="inline-flex rounded-lg border border-borde p-1 bg-superficie-2">
          {VISTAS.map(v => (
            <button
              key={v.id}
              onClick={() => onChangeVista(v.id)}
              className={`flex items-center gap-2 px-3.5 py-1.5 rounded-md text-sm font-medium
                transition-colors duration-150 ease-suave ${
                vista === v.id
                  ? 'bg-superficie text-texto shadow-sm'
                  : 'text-texto-2 hover:text-texto'
              }`}
            >
              <v.Icono tam={15} />
              {v.label}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-3">
          <span className="text-xs text-texto-3">
            {totalVisible} de {totalGeneral} tarea{totalGeneral === 1 ? '' : 's'}
          </span>
          {hayFiltros && (
            <button
              onClick={() => onChange(Object.fromEntries(Object.keys(filtros).map(k => [k, ""])))}
              className="text-xs font-semibold text-acento hover:underline"
            >
              Limpiar filtros
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
