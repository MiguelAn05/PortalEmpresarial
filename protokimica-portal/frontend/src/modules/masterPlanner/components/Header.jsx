import {
  IconoCalendario, IconoCarpeta, IconoOjo, IconoTablero, IconoTarea,
} from '../../../core/components/Iconos.jsx'

const PESTANAS = [
  { id: 'resumen',    label: 'Resumen',    Icono: IconoTablero    },
  { id: 'proyectos',  label: 'Proyectos',  Icono: IconoCarpeta    },
  { id: 'tareas',     label: 'Tareas',     Icono: IconoTarea      },
  { id: 'calendario', label: 'Calendario', Icono: IconoCalendario },
]

export default function Header({ vista, onChangeVista, onNuevoProyecto, onNuevaTarea, editable = true, rol }) {
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap justify-between items-start gap-4">
        <div>
          <h1 className="text-3xl font-bold text-acento-fuerte">Master Planner</h1>
          <p className="text-texto-2 mt-2">
            Planeación, seguimiento y control de proyectos estratégicos.
          </p>
        </div>

        <div className="flex gap-3 items-center">
          {!editable && (
            <span
              className="text-xs font-semibold text-texto-2 bg-superficie-2 border border-borde rounded-lg px-3 py-2"
              title="Tu rol tiene acceso de consulta: ves todo pero no modificas la planeación."
            >
              <span className="inline-flex items-center gap-1.5">
                <IconoOjo tam={14} />
                {rol === 'gerencia' ? 'Modo consulta (gerencia)' : 'Solo lectura'}
              </span>
            </span>
          )}
          {editable && (<>
          <button
            onClick={onNuevaTarea}
            className="bg-white border border-borde hover:bg-superficie-2 text-acento-fuerte font-semibold px-5 py-3 rounded-xl shadow-sm transition"
          >
            + Nueva tarea
          </button>
          <button
            onClick={onNuevoProyecto}
            className="bg-ambar hover:bg-ambar-claro text-acento-fuerte font-semibold px-6 py-3 rounded-xl shadow-sm transition"
          >
            + Nuevo Proyecto
          </button>
          </>)}
        </div>
      </div>

      <div className="border-b border-borde flex gap-1">
        {PESTANAS.map(p => (
          <button
            key={p.id}
            onClick={() => onChangeVista(p.id)}
            className={`px-5 py-3 text-sm font-semibold border-b-2 -mb-px transition ${
              vista === p.id
                ? 'border-acento text-acento-fuerte'
                : 'border-transparent text-texto-2 hover:text-acento-fuerte'
            }`}
          >
            <span className="inline-flex items-center gap-2">
              <p.Icono tam={16} />
              {p.label}
            </span>
          </button>
        ))}
      </div>
    </div>
  )
}
