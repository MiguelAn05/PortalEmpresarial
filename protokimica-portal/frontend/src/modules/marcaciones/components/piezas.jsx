import { Estado } from '../../../core/components/Informe.jsx'
import { ESTADOS_MARCA, PRESENCIAS } from '../constants.js'
import { detalleEquipo, nombreEquipo } from '../resumen.js'

/** Una marcación: la hora, qué botón y en qué biométrico (la sede y la serie al pasar el cursor). */
export function Marca({ marca }) {
  const equipo = nombreEquipo(marca.dispositivo)
  return (
    <li title={detalleEquipo(marca.dispositivo)}>
      <span className="cifra font-semibold">{marca.hora}</span>{' '}
      <span className="text-texto-2">{ESTADOS_MARCA[marca.estado] ?? marca.estado}</span>
      {equipo && <span className="block text-[11px] text-texto-3 leading-tight">{equipo}</span>}
    </li>
  )
}

/** Dónde está la persona: punto y palabra, nunca solo color. */
export function Presencia({ clave }) {
  const p = PRESENCIAS[clave] ?? { label: clave, tono: 'neutro' }
  return <Estado tono={p.tono}>{p.label}</Estado>
}

/**
 * Las novedades de una persona, cada una con su texto y el detalle al pasar el
 * cursor. Una justificada sigue a la vista pero lo dice con palabras
 * («justificada»), no solo con el color.
 */
export function Novedades({ lista }) {
  if (!lista?.length) return <span className="text-texto-3">—</span>
  return (
    <ul className="flex flex-wrap gap-1.5">
      {lista.map(n => (
        <li key={n.tipo} title={n.justificacion ? `${n.detalle} — Justificada: ${n.justificacion.texto}` : n.detalle}
            className={`inline-flex items-center gap-1.5 text-xs font-medium rounded-md px-2 py-0.5 ${
              n.justificacion ? 'text-positivo bg-positivo-bg' : 'text-negativo bg-negativo-bg'}`}>
          <span className={`w-1.5 h-1.5 rounded-full ${n.justificacion ? 'bg-positivo-vivo' : 'bg-negativo-vivo'}`} aria-hidden="true" />
          {n.etiqueta}{n.justificacion && ' · justificada'}
        </li>
      ))}
    </ul>
  )
}
