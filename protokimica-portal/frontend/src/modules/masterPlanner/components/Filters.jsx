export default function Filters() {
  return (

    <div className="bg-white rounded-2xl border border-[#D6E0F0] p-5 shadow-sm">

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-6 gap-4">

        {/* Buscar */}
        <div className="xl:col-span-2">

          <label className="block text-xs font-semibold text-[#6B7EA8] uppercase mb-1">
            Buscar
          </label>

          <input
            placeholder="Proyecto, responsable..."
            className="w-full rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm
            focus:outline-none focus:ring-2 focus:ring-[#1A4FA0]"
          />

        </div>

        {/* Área */}

        <div>

          <label className="block text-xs font-semibold text-[#6B7EA8] uppercase mb-1">
            Área
          </label>

          <select className="w-full rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm">

            <option>Todas</option>
            <option>TI</option>
            <option>Comercial</option>
            <option>Calidad</option>
            <option>HSEQ</option>
            <option>Logística</option>

          </select>

        </div>

        {/* Estado */}

        <div>

          <label className="block text-xs font-semibold text-[#6B7EA8] uppercase mb-1">
            Estado
          </label>

          <select className="w-full rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm">

            <option>Todos</option>
            <option>Planeación</option>
            <option>En ejecución</option>
            <option>En riesgo</option>
            <option>Finalizado</option>

          </select>

        </div>

        {/* Prioridad */}

        <div>

          <label className="block text-xs font-semibold text-[#6B7EA8] uppercase mb-1">
            Prioridad
          </label>

          <select className="w-full rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm">

            <option>Todas</option>
            <option>Alta</option>
            <option>Media</option>
            <option>Baja</option>

          </select>

        </div>

        {/* Año */}

        <div>

          <label className="block text-xs font-semibold text-[#6B7EA8] uppercase mb-1">
            Año
          </label>

          <select className="w-full rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm">

            <option>2026</option>
            <option>2025</option>

          </select>

        </div>

      </div>

      <div className="flex justify-end gap-3 mt-5">

        <button
          className="px-4 py-2 rounded-lg border border-[#D6E0F0]
          text-sm font-medium hover:bg-gray-50"
        >
          Exportar
        </button>

        <button
          className="px-5 py-2 rounded-lg bg-[#F5A800]
          hover:bg-[#FFC840]
          text-[#0D2B5E] font-bold text-sm"
        >
          + Nuevo Proyecto
        </button>

      </div>

    </div>

  )
}