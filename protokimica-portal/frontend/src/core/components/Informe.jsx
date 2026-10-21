/**
 * Las piezas con que se dibuja un informe gerencial (PQRS, Master Planner):
 * una hoja para leer en pantalla y descargar en PDF con la hoja de imprimir
 * del navegador. Vivían dentro de `InformePQRS.jsx`; el segundo informe las
 * habría copiado, y dos copias de la misma tarjeta terminan viéndose
 * distinto en el mismo PDF.
 *
 * Gráficas a mano, sin librería, como en el resto del portal: una serie, un
 * color; la cifra al lado de cada barra y el detalle al pasar el cursor. El
 * estado nunca va solo en color: lleva punto y texto.
 */
import { conOtros, formatoPromedio, marcasEje } from '../informe.js'

const TONO_TEXTO = {
  positivo: 'text-positivo', alerta: 'text-alerta', negativo: 'text-negativo', neutro: 'text-texto-2',
}
const TONO_PUNTO = {
  positivo: 'bg-positivo-vivo', alerta: 'bg-ambar', negativo: 'bg-negativo-vivo', neutro: 'bg-texto-3',
}

export function Seccion({ titulo, nota, children, className = '' }) {
  return (
    <section className={`bg-white rounded-xl border border-borde p-5 evitar-corte print:shadow-none ${className}`}>
      <h3 className="font-semibold text-acento-fuerte text-sm">{titulo}</h3>
      {nota && <p className="text-xs text-texto-2 mt-0.5">{nota}</p>}
      <div className="mt-4">{children}</div>
    </section>
  )
}

export function Tarjeta({ titulo, valor, detalle, tono }) {
  return (
    <div className="bg-white rounded-xl border border-borde p-4 evitar-corte">
      <div className="text-xs font-semibold text-texto-2 uppercase tracking-wide">{titulo}</div>
      <div className="text-3xl font-bold text-texto mt-1 cifra">{valor}</div>
      {detalle && (
        <div className={`text-xs mt-1 flex items-center gap-1.5 ${TONO_TEXTO[tono] || 'text-texto-2'}`}>
          {tono && tono !== 'neutro' && <span className={`w-2 h-2 rounded-full flex-shrink-0 ${TONO_PUNTO[tono]}`} />}
          <span>{detalle}</span>
        </div>
      )}
    </div>
  )
}

/** Un estado con su punto y su texto: nunca solo el color. */
export function Estado({ tono = 'neutro', children }) {
  return (
    <span className={`inline-flex items-center gap-1.5 ${TONO_TEXTO[tono]}`}>
      <span className={`w-2 h-2 rounded-full flex-shrink-0 ${TONO_PUNTO[tono]}`} />
      {children}
    </span>
  )
}

/**
 * Barras horizontales de UNA serie. La barra más larga ocupa todo el ancho;
 * la cifra y el porcentaje van al final de cada una, y al pasar el cursor se
 * dice sobre qué total es el porcentaje. `unidad` es lo que se cuenta
 * («PQRS», «proyectos»).
 */
export function Barras({ filas, unidad, sobre = 'del total', vacio = 'Sin datos en el periodo.', max = 8 }) {
  const visibles = conOtros(filas, max)
  if (!visibles.length) return <p className="text-sm text-texto-2">{vacio}</p>
  const mayor = Math.max(...visibles.map(f => f.n), 1)
  return (
    <ul className="space-y-2.5">
      {visibles.map(f => (
        <li key={f.clave} className="group relative grid grid-cols-[minmax(0,11rem)_1fr_auto] items-center gap-3 text-sm">
          <span className="truncate text-texto" title={f.etiqueta}>{f.etiqueta}</span>
          <span className="h-2.5 rounded-full bg-superficie-2 overflow-hidden">
            <span
              className="block h-full rounded-full bg-acento group-hover:bg-acento-fuerte transition-colors"
              style={{ width: `${(f.n / mayor) * 100}%` }}
            />
          </span>
          <span className="cifra text-texto font-semibold text-right min-w-[5.5rem]">
            {f.n} <span className="text-texto-2 font-normal">· {f.pct ?? 0}%</span>
            {/* El promedio por día hábil, cuando la fila lo trae. */}
            {'por_dia_habil' in f && (
              <span className="text-texto-3 font-normal"> · {formatoPromedio(f.por_dia_habil)}/día</span>
            )}
          </span>
          <span role="tooltip" className="pointer-events-none absolute left-1/3 -top-8 z-10 hidden group-hover:block print:hidden
                                          whitespace-nowrap rounded-md bg-texto text-white text-xs px-2 py-1 shadow-md">
            {f.etiqueta}: {f.n} {unidad} · {f.pct ?? 0}% {sobre}
            {'por_dia_habil' in f && ` · ${formatoPromedio(f.por_dia_habil)} por día hábil`}
          </span>
        </li>
      ))}
    </ul>
  )
}

/** Columnas de una serie en el tiempo: eje con tres marcas y detalle al pasar el cursor. */
export function Tendencia({ tendencia, unidad }) {
  const puntos = tendencia?.puntos || []
  const mayor = Math.max(...puntos.map(p => p.n), 0)
  const marcas = marcasEje(mayor)
  const tope = marcas[marcas.length - 1] || 1
  // En un mes, rotular cada cinco días; por meses, todos.
  const rotular = (i) => tendencia?.escala === 'mes' || i === 0 || (i + 1) % 5 === 0
  if (!puntos.length) return null
  return (
    <div className="flex gap-2">
      <div className="relative w-6 h-40 text-[11px] text-texto-3 cifra">
        {marcas.map(m => (
          <span key={m} className="absolute right-0 -translate-y-1/2" style={{ bottom: `${(m / tope) * 100}%` }}>{m}</span>
        ))}
      </div>
      <div className="flex-1 min-w-0">
        <div className="relative h-40">
          {marcas.map(m => (
            <div key={m} className="absolute inset-x-0 border-t border-borde" style={{ bottom: `${(m / tope) * 100}%` }} />
          ))}
          <div className="absolute inset-0 flex items-end gap-[2px]">
            {puntos.map(p => (
              <div key={p.clave} className="group relative flex-1 h-full flex items-end">
                <div
                  className="w-full rounded-t bg-acento group-hover:bg-acento-fuerte transition-colors"
                  style={{ height: `${(p.n / tope) * 100}%` }}
                />
                <span role="tooltip" className="pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 mb-1 z-10 hidden group-hover:block print:hidden
                                                whitespace-nowrap rounded-md bg-texto text-white text-xs px-2 py-1 shadow-md">
                  {tendencia.escala === 'dia' ? `Día ${p.etiqueta}` : p.etiqueta}: {p.n} {unidad}
                </span>
              </div>
            ))}
          </div>
        </div>
        <div className="flex gap-[2px] mt-1.5 text-[11px] text-texto-3 cifra">
          {puntos.map((p, i) => (
            <span key={p.clave} className="flex-1 text-center">{rotular(i) ? p.etiqueta : ''}</span>
          ))}
        </div>
      </div>
    </div>
  )
}

/**
 * Una barra partida en tramos de un mismo total (salud de los proyectos,
 * cómo terminaron los compromisos), con la leyenda escrita debajo: el color
 * solo no dice nada impreso en blanco y negro.
 */
export function BarraPartida({ tramos, unidad, vacio = 'Sin datos.' }) {
  const total = tramos.reduce((s, t) => s + t.n, 0)
  if (!total) return <p className="text-sm text-texto-2">{vacio}</p>
  return (
    <div>
      <div className="flex h-3 rounded-full overflow-hidden bg-superficie-2">
        {tramos.filter(t => t.n).map(t => (
          <span key={t.clave} title={`${t.etiqueta}: ${t.n} ${unidad}`}
                className={`h-full ${TONO_PUNTO[t.tono] || 'bg-acento'}`}
                style={{ width: `${(t.n / total) * 100}%` }} />
        ))}
      </div>
      <ul className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1.5 text-sm">
        {tramos.map(t => (
          <li key={t.clave} className="flex items-center justify-between gap-2">
            <Estado tono={t.tono}><span className="text-texto">{t.etiqueta}</span></Estado>
            <span className="cifra font-semibold text-texto">
              {t.n}{t.pct != null && <span className="text-texto-2 font-normal"> · {t.pct}%</span>}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
