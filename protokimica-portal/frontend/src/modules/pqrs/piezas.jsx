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
