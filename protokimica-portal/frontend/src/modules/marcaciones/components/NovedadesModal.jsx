import { useEffect } from 'react'
import { formatFecha } from '../../masterPlanner/constants.js'
import { ESTADOS_MARCA } from '../constants.js'
import Boton from '../../../core/components/Boton.jsx'
import NovedadesDia from './NovedadesDia.jsx'

/**
 * Lo que se abre al pulsar «Novedades» de una persona: sus marcaciones del día
 * con la hora exacta y cada novedad con su detalle y su justificación.
 * `persona` es la fila del día que ya se tiene; al guardar, la pantalla pide
 * el día de nuevo y esta fila se actualiza sola (se busca por código).
 */
export default function NovedadesModal({ persona, fecha, puede, onVerDias, onCerrar }) {
  useEffect(() => {
    const alTeclear = (e) => { if (e.key === 'Escape') onCerrar() }
    window.addEventListener('keydown', alTeclear)
    return () => window.removeEventListener('keydown', alTeclear)
  }, [onCerrar])

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/30 p-4 print:hidden" onClick={onCerrar}>
      <div role="dialog" aria-modal="true" aria-label={`Novedades de ${persona.nombre}`}
           onClick={(e) => e.stopPropagation()}
           className="w-full max-w-lg max-h-[90vh] overflow-y-auto bg-superficie rounded-2xl shadow-xl p-5 space-y-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-bold text-acento-fuerte">{persona.nombre}</h2>
            <p className="text-xs text-texto-2 mt-0.5">
              {persona.area || 'Sin área'} · {formatFecha(fecha, { weekday: 'long', day: 'numeric', month: 'long' })}
            </p>
          </div>
          <button type="button" onClick={onCerrar} className="text-sm text-texto-2 hover:text-acento-fuerte">Cerrar</button>
        </div>

        <div className="text-sm text-texto">
          <span className="text-texto-2">Turno </span>
          <span className="cifra font-semibold">{persona.turno || persona.turno_opciones || '—'}</span>
        </div>

        {persona.marcas.length > 0 ? (
          <ol className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
            {persona.marcas.map((m, i) => (
              <li key={i}><span className="cifra font-semibold">{m.hora}</span> <span className="text-texto-2">{ESTADOS_MARCA[m.estado] ?? m.estado}</span></li>
            ))}
          </ol>
        ) : <p className="text-sm text-texto-2">No marcó nada este día.</p>}

        {persona.novedades.length === 0
          ? <p className="text-sm text-texto-2">Esta persona ya no tiene novedades este día.</p>
          : <NovedadesDia empCode={persona.emp_code} fecha={fecha} novedades={persona.novedades} puede={puede} />}

        <div className="flex justify-between gap-2 pt-1">
          <Boton tam="sm" tono="fantasma" onClick={onVerDias}>Ver sus últimos días</Boton>
          <Boton tam="sm" onClick={onCerrar}>Cerrar</Boton>
        </div>
      </div>
    </div>
  )
}
