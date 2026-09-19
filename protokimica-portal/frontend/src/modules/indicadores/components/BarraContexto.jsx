/**
 * El contexto de toda la pantalla: qué mes, qué alcance, qué se busca.
 *
 * Vive ARRIBA de las pestañas y las gobierna a las tres. Antes el mes y el
 * área estaban aquí pero el interruptor empresa/área vivía dentro de una
 * pestaña, así que cambiar de pestaña perdía parte del contexto y la misma
 * pantalla mostraba dos recortes distintos de la empresa sin avisar.
 *
 * No decide permisos: el backend responde si esta persona puede ver toda la
 * empresa (`alcance.puede_cambiar`) y aquí solo se pinta o no el
 * interruptor. Un control deshabilitado que nadie puede usar solo genera la
 * pregunta de por qué no funciona.
 */
import { IconoBuscar, IconoCerrar, IconoChevron } from '../../../core/components/Iconos.jsx'
import { MESES } from '../constants'

export default function BarraContexto({
  periodo, onPeriodo, onUltimoCerrado,
  area, onArea, areasDisponibles = [],
  alcance, onAlcance, puedeCambiarAlcance, areaPropia,
  busqueda, onBusqueda,
  resumenAlcance,
}) {
  return (
    <div className="bg-superficie border border-borde rounded-xl shadow-sm px-3 py-2.5
                    flex flex-wrap items-center gap-3">

      {/* Mes. El stepper es una sola pieza —flecha, mes, flecha— y no tres
          botones sueltos: así se lee como un control y no como una barra. */}
      <div className="flex items-center h-9 rounded-lg border border-borde-fuerte overflow-hidden">
        <button
          type="button"
          onClick={() => onPeriodo('anterior')}
          aria-label="Mes anterior"
          className="w-8 h-full grid place-items-center text-texto-2 hover:bg-superficie-2 transition"
        >
          <IconoChevron tam={14} className="rotate-180" />
        </button>
        <span className="px-3 h-full flex items-center gap-2 text-sm font-semibold
                         border-x border-borde whitespace-nowrap">
          {MESES[periodo.mes - 1]} {periodo.anio}
          {periodo.esUltimoCerrado && (
            <span className="etiqueta text-[10px]">último cerrado</span>
          )}
        </span>
        <button
          type="button"
          onClick={() => onPeriodo('siguiente')}
          aria-label="Mes siguiente"
          className="w-8 h-full grid place-items-center text-texto-2 hover:bg-superficie-2 transition"
        >
          <IconoChevron tam={14} />
        </button>
      </div>

      {!periodo.esUltimoCerrado && (
        <button
          type="button"
          onClick={onUltimoCerrado}
          className="text-xs font-semibold text-acento hover:underline"
        >
          Volver al último cerrado
        </button>
      )}

      {/* Alcance: empresa o el área de quien mira. */}
      {puedeCambiarAlcance && (
        <div className="inline-flex h-9 rounded-lg border border-borde-fuerte overflow-hidden text-sm">
          {[['empresa', 'Toda la empresa'], ['area', areaPropia || 'Mi área']].map(([valor, texto]) => (
            <button
              key={valor}
              type="button"
              onClick={() => onAlcance(valor)}
              aria-pressed={alcance === valor}
              className={`px-3 font-semibold transition ${
                alcance === valor
                  ? 'bg-acento text-white'
                  : 'text-texto-2 hover:bg-superficie-2'
              }`}
            >
              {texto}
            </button>
          ))}
        </div>
      )}

      <select
        value={area}
        onChange={(e) => onArea(e.target.value)}
        aria-label="Filtrar por área"
        className="h-9 rounded-lg border border-borde-fuerte bg-superficie px-2.5 text-sm text-texto"
      >
        <option value="">Todas las áreas</option>
        {areasDisponibles.map(a => <option key={a} value={a}>{a}</option>)}
      </select>

      <div className="flex items-center gap-2 h-9 px-2.5 rounded-lg border border-borde-fuerte
                      text-texto-3 min-w-[15rem] flex-1 max-w-sm">
        <IconoBuscar tam={14} />
        <input
          value={busqueda}
          onChange={(e) => onBusqueda(e.target.value)}
          placeholder="Buscar indicador, área o responsable…"
          aria-label="Buscar indicador, área o responsable"
          className="w-full bg-transparent border-none outline-none text-sm text-texto"
        />
        {busqueda && (
          <button
            type="button"
            onClick={() => onBusqueda('')}
            aria-label="Limpiar la búsqueda"
            className="text-texto-3 hover:text-texto-2"
          >
            <IconoCerrar tam={13} />
          </button>
        )}
      </div>

      {/* Qué se está mirando. Una lista acotada que no avisa que lo está se
          lee como «en la empresa solo hay estos». */}
      {resumenAlcance && (
        <span className="ml-auto text-xs text-texto-3 cifra">{resumenAlcance}</span>
      )}
    </div>
  )
}
