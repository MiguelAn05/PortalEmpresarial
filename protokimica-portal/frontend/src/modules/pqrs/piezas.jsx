/**
 * Las piezas visuales de PQRS que usan la lista y el detalle.
 *
 * Antes cada pantalla llevaba su copia de TIPOS, ESTADOS y PRIORIDADES y su
 * propio `Badge`: el día que una cambió de color, «En proceso» se veía
 * distinto en la lista y en el detalle. Aquí viven una sola vez.
 *
 * El color de una insignia es una escala de gravedad, no una paleta por
 * categoría, y siempre va con punto y palabra: el ámbar de la marca no se
 * lee solo sobre blanco.
 */
import { useState } from 'react'
import { IconoClip } from '../../core/components/Iconos.jsx'

const TONOS = {
  positivo: 'bg-positivo-bg text-positivo',
  alerta:   'bg-alerta-bg text-alerta',
  negativo: 'bg-negativo-bg text-negativo',
  info:     'bg-info-bg text-info',
  neutro:   'bg-superficie-2 text-texto-2',
}

/** Punto + palabra. `plana` quita el punto, para lo que es dato y no estado. */
export function Insignia({ tono = 'neutro', plana = false, children, className = '' }) {
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-xs font-semibold whitespace-nowrap ${TONOS[tono] || TONOS.neutro} ${className}`}>
      {!plana && <span aria-hidden="true" className="w-1.5 h-1.5 rounded-full bg-current" />}
      {children}
    </span>
  )
}

/** La insignia de un valor de TIPOS, ESTADOS o PRIORIDADES (`constants.js`). */
export function InsigniaDe({ mapa, valor, plana }) {
  const item = mapa[valor] || { label: valor, tono: 'neutro' }
  return <Insignia tono={item.tono} plana={plana}>{item.label}</Insignia>
}

/**
 * Una tarjeta con cabecera: título a la izquierda, lo que se puede hacer a la
 * derecha, y el contenido debajo de una línea. Así se ven todas las del
 * detalle, para que ninguna parezca más importante por estar pintada distinto.
 */
export function Tarjeta({ titulo, accion, children, sinRelleno = false, id, className = '' }) {
  return (
    <section id={id} className={`bg-superficie rounded-xl border border-borde shadow-sm overflow-hidden ${className}`}>
      {(titulo || accion) && (
        <div className="flex items-center justify-between gap-3 px-5 py-3 border-b border-borde">
          <h3 className="text-sm font-semibold text-texto">{titulo}</h3>
          {accion}
        </div>
      )}
      <div className={sinRelleno ? '' : 'p-5'}>{children}</div>
    </section>
  )
}

/** Una fila de dato: etiqueta fija a la izquierda, valor a la derecha. */
export function Dato({ etiqueta, children }) {
  if (children === null || children === undefined || children === '') return null
  return (
    <div className="flex gap-3 items-baseline text-sm">
      <span className="etiqueta w-24 flex-shrink-0">{etiqueta}</span>
      <span className="text-texto min-w-0 break-words">{children}</span>
    </div>
  )
}

const LARGO_RECORTE = 260

/**
 * Un mensaje de la conversación de un concepto: quién, y qué dijo. Lo usan
 * el panel (lo que te preguntan al responder) y la tarjeta «Conceptos».
 */
export function Mensaje({ quien, texto, soporte, etiquetaSoporte, fondo = 'bg-superficie-2' }) {
  const [completo, setCompleto] = useState(false)
  const largo = (texto || '').length > LARGO_RECORTE
  return (
    <div className={`rounded-lg px-3.5 py-2.5 text-sm text-texto-2 leading-relaxed ${fondo}`}>
      <span className="etiqueta block mb-1">{quien}</span>
      {texto && (
        <p className={`whitespace-pre-wrap ${largo && !completo ? 'line-clamp-3' : ''}`}>{texto}</p>
      )}
      {largo && (
        <button type="button" onClick={() => setCompleto(v => !v)} className="text-xs font-semibold text-acento mt-1.5 hover:underline">
          {completo ? 'Ver menos' : 'Ver completo'}
        </button>
      )}
      {soporte && (
        <a href={soporte} target="_blank" rel="noreferrer"
           className="flex items-center gap-1.5 text-xs text-acento font-semibold hover:underline mt-2">
          <IconoClip tam={13} /> {etiquetaSoporte}
        </a>
      )}
    </div>
  )
}
