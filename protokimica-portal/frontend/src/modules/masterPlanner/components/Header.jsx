export default function Header({ onNuevoProyecto, onNuevaTarea }) {
  return (
    <div className="flex justify-between items-start">
      <div>
        <h1 className="text-3xl font-bold text-[#0D2B5E]">Master Planner</h1>
        <p className="text-[#6B7EA8] mt-2">
          Planeación, seguimiento y control de proyectos estratégicos.
        </p>
      </div>

      <div className="flex gap-3">
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
      </div>
    </div>
  )
}
