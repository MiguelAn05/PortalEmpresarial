import { horaOGuion, textoUltimaMarca } from '../resumen.js'
import { Novedades, Presencia } from './piezas.jsx'

/** Una fila por persona: es la lista que se lee en vivo. Pulsar abre su detalle. */
export default function TablaPersonas({ personas, onAbrir, onNovedades }) {
  if (!personas.length) {
    return <p className="text-sm text-texto-2 py-8 text-center">Nadie coincide con estos filtros.</p>
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-xs text-texto-2 uppercase tracking-wide text-left border-b border-borde">
            <th className="py-2 pr-3 font-semibold">Persona</th>
            <th className="py-2 pr-3 font-semibold">Turno</th>
            <th className="py-2 pr-3 font-semibold">Entrada</th>
            <th className="py-2 pr-3 font-semibold">Última marcación</th>
            <th className="py-2 pr-3 font-semibold">Estado</th>
            <th className="py-2 font-semibold">Novedades</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-borde">
          {personas.map(p => (
            <tr key={p.emp_code} className="hover:bg-superficie-2/60">
              <td className="py-2 pr-3">
                <button type="button" onClick={() => onAbrir(p.emp_code)}
                        className="text-left text-acento-fuerte font-semibold hover:underline">
                  {p.nombre}
                </button>
                <div className="text-[11px] text-texto-3">{p.area || 'Sin área'}</div>
              </td>
              <td className="py-2 pr-3 cifra whitespace-nowrap">
                {p.turno || <span title="Turnos posibles" className="text-texto-2">{p.turno_opciones || '—'}</span>}
              </td>
              <td className="py-2 pr-3 cifra">{horaOGuion(p.primera_entrada)}</td>
              <td className="py-2 pr-3 text-texto-2 whitespace-nowrap">{textoUltimaMarca(p.ultima_marca)}</td>
              <td className="py-2 pr-3 whitespace-nowrap"><Presencia clave={p.presencia} /></td>
              <td className="py-2">
                {p.novedades.length > 0 ? (
                  <button type="button" onClick={() => onNovedades(p)}
                          aria-label={`Ver las novedades de ${p.nombre}`}
                          title="Ver las horas exactas y justificar"
                          className="text-left rounded-md hover:ring-2 hover:ring-acento/30 focus-visible:ring-2 focus-visible:ring-acento/50 outline-none">
                    <Novedades lista={p.novedades} />
                  </button>
                ) : <Novedades lista={p.novedades} />}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
