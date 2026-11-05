import { Estado } from '../../../core/components/Informe.jsx'
import { PRESENCIAS } from '../constants.js'

/** Dónde está la persona: punto y palabra, nunca solo color. */
export function Presencia({ clave }) {
  const p = PRESENCIAS[clave] ?? { label: clave, tono: 'neutro' }
  return <Estado tono={p.tono}>{p.label}</Estado>
}

/** Las novedades de una persona, cada una con su texto y el detalle al pasar el cursor. */
export function Novedades({ lista }) {
  if (!lista?.length) return <span className="text-texto-3">—</span>
  return (
    <ul className="flex flex-wrap gap-1.5">
      {lista.map(n => (
        <li key={n.tipo} title={n.detalle}
            className="inline-flex items-center gap-1.5 text-xs font-medium text-negativo bg-negativo-bg rounded-md px-2 py-0.5">
          <span className="w-1.5 h-1.5 rounded-full bg-negativo-vivo" aria-hidden="true" />
          {n.etiqueta}
        </li>
      ))}
    </ul>
  )
}
