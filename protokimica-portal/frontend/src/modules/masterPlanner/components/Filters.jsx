const AREAS = ["TI", "Comercial", "Calidad", "Logística", "Servicio al cliente", "Talento Humano"]
const ESTADOS = ["Planeación", "En ejecución", "En riesgo", "Pausado", "Finalizado"]
const PRIORIDADES = ["Alta", "Media", "Baja"]

export default function Filters({ filtros, onChange, vista, onChangeVista }) {
  const set = (campo) => (e) => onChange({ ...filtros, [campo]: e.target.value })

  return (
    <div className="bg-white rounded-2xl border border-[#D6E0F0] p-5 shadow-sm">
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-6 gap-4">

        <div className="xl:col-span-2">
          <label className="block text-xs font-semibold text-[#6B7EA8] uppercase mb-1">Buscar</label>
          <input
            value={filtros.busqueda}
            onChange={set('busqueda')}
            placeholder="Proyecto, actividad, responsable..."
            className="w-full rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#1A4FA0]"
          />
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
            {ESTADOS.map(e => <option key={e} value={e}>{e}</option>)}
          </select>
        </div>

        <div>
          <label className="block text-xs font-semibold text-[#6B7EA8] uppercase mb-1">Prioridad</label>
          <select value={filtros.prioridad} onChange={set('prioridad')} className="w-full rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm">
            <option value="">Todas</option>
            {PRIORIDADES.map(p => <option key={p} value={p}>{p}</option>)}
          </select>
        </div>

        <div>
          <label className="block text-xs font-semibold text-[#6B7EA8] uppercase mb-1">Año</label>
          <select value={filtros.año} onChange={set('año')} className="w-full rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm">
            <option value="">Todos</option>
            <option value="2026">2026</option>
            <option value="2025">2025</option>
          </select>
        </div>
      </div>

      <div className="flex justify-between items-center mt-5">
        <div className="inline-flex rounded-lg border border-[#D6E0F0] p-1 bg-[#F7F9FC]">
          <button
            onClick={() => onChangeVista('kanban')}
            className={`px-4 py-1.5 rounded-md text-sm font-semibold transition ${
              vista === 'kanban' ? 'bg-white text-[#0D2B5E] shadow-sm' : 'text-[#6B7EA8]'
            }`}
          >
            🗂️ Kanban
          </button>
          <button
            onClick={() => onChangeVista('tabla')}
            className={`px-4 py-1.5 rounded-md text-sm font-semibold transition ${
              vista === 'tabla' ? 'bg-white text-[#0D2B5E] shadow-sm' : 'text-[#6B7EA8]'
            }`}
          >
            📋 Tabla
          </button>
        </div>

        <button
          title="Próximamente"
          className="px-4 py-2 rounded-lg border border-[#D6E0F0] text-sm font-medium hover:bg-gray-50"
        >
          Exportar
        </button>
      </div>
    </div>
  )
}
