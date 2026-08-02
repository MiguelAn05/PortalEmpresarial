import { Miniatura, ChipSemaforo } from "./Graficas"
import { formatValor, formatVariacion, tonoVariacion } from "../constants"

/**
 * La ficha de un indicador en el tablero: el número grande primero, el estado
 * al lado y la tendencia de reojo. El valor es la historia — la gráfica está
 * para dar contexto, no para competir con él.
 */
export default function TarjetaIndicador({ ficha, onAbrir }) {
  const variacion = formatVariacion(ficha.variacion_mes, ficha.unidad)

  return (
    <button
      onClick={() => onAbrir(ficha)}
      className="text-left bg-white rounded-xl border border-[#D6E0F0] p-5 hover:shadow-md hover:border-[#1A4FA0]/40 transition w-full flex flex-col"
    >
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-[#0D2B5E] leading-snug">{ficha.nombre}</p>
          <p className="text-[11px] text-[#9BACC8] mt-0.5">
            {ficha.area || 'Sin área'}
            {ficha.es_automatico && ' · ⚡ automático'}
          </p>
        </div>
        <ChipSemaforo estado={ficha.semaforo} compacto />
      </div>

      <div className="flex items-end justify-between gap-3 mt-auto">
        <div>
          <p className="text-3xl font-bold text-[#0D2B5E] leading-none">
            {formatValor(ficha.valor, ficha.unidad)}
          </p>
          <div className="flex items-center gap-2 mt-1.5 text-[11px]">
            {ficha.meta !== null && (
              <span className="text-[#9BACC8]">Meta {formatValor(ficha.meta, ficha.unidad)}</span>
            )}
            {variacion && (
              <span className={`font-semibold ${tonoVariacion(ficha.variacion_mes, ficha.direccion)}`}>
                {variacion} vs. mes anterior
              </span>
            )}
          </div>
        </div>
        <Miniatura serie={ficha.serie} />
      </div>

      {ficha.valor === null && !ficha.es_automatico && (
        <p className="text-[11px] text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-2 py-1 mt-3">
          Falta registrar este mes
        </p>
      )}
    </button>
  )
}
