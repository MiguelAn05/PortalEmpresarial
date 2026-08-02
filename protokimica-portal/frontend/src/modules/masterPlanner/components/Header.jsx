const PESTANAS = [
  { id: 'resumen',    label: 'Resumen',    icono: '📊' },
  { id: 'proyectos',  label: 'Proyectos',  icono: '📂' },
  { id: 'tareas',     label: 'Tareas',     icono: '✅' },
  { id: 'calendario', label: 'Calendario', icono: '🗓️' },
]

export default function Header({ vista, onChangeVista, onNuevoProyecto, onNuevaTarea, editable = true, rol }) {
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap justify-between items-start gap-4">
        <div>
          <h1 className="text-3xl font-bold text-[#0D2B5E]">Master Planner</h1>
          <p className="text-[#6B7EA8] mt-2">
            Planeación, seguimiento y control de proyectos estratégicos.
          </p>
        </div>

        <div className="flex gap-3 items-center">
          {!editable && (
            <span
              className="text-xs font-semibold text-[#6B7EA8] bg-[#F7F9FC] border border-[#D6E0F0] rounded-lg px-3 py-2"
              title="Tu rol tiene acceso de consulta: ves todo pero no modificas la planeación."
            >
              {rol === 'gerencia' ? '👁 Modo consulta (gerencia)' : '👁 Solo lectura'}
            </span>
          )}
          {editable && (<>
          <button
            onClick={onNuevaTarea}
            className="bg-white border border-[#D6E0F0] hover:bg-gray-50 text-[#0D2B5E] font-semibold px-5 py-3 rounded-xl shadow-sm transition"
          >
            + Nueva tarea
          </button>
          <button
            onClick={onNuevoProyecto}
            className="bg-[#F5A800] hover:bg-[#FFC840] text-[#0D2B5E] font-semibold px-6 py-3 rounded-xl shadow-sm transition"
          >
            + Nuevo Proyecto
          </button>
          </>)}
        </div>
      </div>

      <div className="border-b border-[#D6E0F0] flex gap-1">
        {PESTANAS.map(p => (
          <button
            key={p.id}
            onClick={() => onChangeVista(p.id)}
            className={`px-5 py-3 text-sm font-semibold border-b-2 -mb-px transition ${
              vista === p.id
                ? 'border-[#1A4FA0] text-[#0D2B5E]'
                : 'border-transparent text-[#6B7EA8] hover:text-[#0D2B5E]'
            }`}
          >
            <span className="mr-1.5">{p.icono}</span>{p.label}
          </button>
        ))}
      </div>
    </div>
  )
}
