import { useState } from 'react'
import { IconoDinero } from '../../../core/components/Iconos.jsx'
import { montoCorto } from '../resumen.js'
import {
  contornoBarra, escalaY, geometriaBarras, hayMovimiento, maximoDeLaSerie,
} from '../grafica.js'

/**
 * Ejecución presupuestal mes a mes: cuánto aprobó Administración y cuánto
 * desembolsó Tesorería.
 *
 * Las dos barras van LADO A LADO y no una sobre otra: lo aprobado en marzo
 * puede pagarse en mayo, así que ninguna contiene a la otra. Superpuestas
 * dirían que el pago sale de lo aprobado ese mismo mes, que es falso.
 *
 * Los colores están verificados para daltonismo (azul y verde se separan con
 * ΔE 27 en visión normal y 17 en el peor caso); el ámbar de la marca quedó
 * fuera porque no llega a 3:1 sobre blanco. Aun así el color no va solo:
 * cada serie lleva su etiqueta en la leyenda y su valor en el detalle.
 */

// Coordenadas internas del dibujo. El SVG escala solo con el ancho de la
// tarjeta; estas son las proporciones, no píxeles en pantalla.
const ANCHO = 640
const ALTO = 210
const MARGEN = { arriba: 8, derecha: 8, abajo: 26, izquierda: 52 }
const AREA = {
  ancho: ANCHO - MARGEN.izquierda - MARGEN.derecha,
  alto: ALTO - MARGEN.arriba - MARGEN.abajo,
}

const SERIES = [
  { clave: 'aprobado', etiqueta: 'Aprobado', color: 'var(--color-positivo-vivo)' },
  { clave: 'pagado', etiqueta: 'Pagado', color: 'var(--color-acento)' },
]

export default function GraficaEjecucion({ serie = [] }) {
  const [mesActivo, setMesActivo] = useState(null)

  if (!hayMovimiento(serie)) {
    return (
      <div className="flex flex-col items-center justify-center text-center py-12 px-5">
        <IconoDinero tam={22} className="text-texto-3 mb-3" />
        <p className="text-sm font-medium text-texto">Todavía no hay movimiento</p>
        <p className="text-xs text-texto-3 mt-1 max-w-xs">
          Cuando Administración apruebe presupuesto y Tesorería registre pagos,
          aquí se ve mes a mes.
        </p>
      </div>
    )
  }

  const { ticks, tope } = escalaY(maximoDeLaSerie(serie))
  const barras = geometriaBarras(serie, { ancho: AREA.ancho, alto: AREA.alto })
  const y = (valor) => MARGEN.arriba + AREA.alto - (valor / tope) * AREA.alto
  const detalle = barras.find(b => b.etiqueta === mesActivo)

  return (
    <div className="relative">
      {/* Leyenda: con dos series el color nunca puede ser la única pista. */}
      <div className="flex items-center gap-4 px-5 pb-2">
        {SERIES.map(s => (
          <span key={s.clave} className="flex items-center gap-1.5 text-[11px] text-texto-2">
            <span
              className="w-2.5 h-2.5 rounded-sm flex-shrink-0"
              style={{ background: s.color }}
              aria-hidden="true"
            />
            {s.etiqueta}
          </span>
        ))}
      </div>

      <svg
        viewBox={`0 0 ${ANCHO} ${ALTO}`}
        className="w-full h-auto"
        role="img"
        aria-label={
          `Ejecución presupuestal de los últimos ${serie.length} meses. ` +
          serie.map(p =>
            `${p.etiqueta}: aprobado ${montoCorto(p.aprobado)}, pagado ${montoCorto(p.pagado)}`
          ).join('. ')
        }
        onMouseLeave={() => setMesActivo(null)}
      >
        {/* Solo líneas horizontales, punteadas y recesivas: la rejilla ayuda
            a leer alturas, no compite con los datos. */}
        {ticks.map(valor => (
          <g key={valor}>
            <line
              x1={MARGEN.izquierda} x2={ANCHO - MARGEN.derecha}
              y1={y(valor)} y2={y(valor)}
              stroke="var(--color-borde)" strokeWidth="1"
              strokeDasharray={valor === 0 ? undefined : '3 4'}
            />
            <text
              x={MARGEN.izquierda - 8} y={y(valor) + 3.5}
              textAnchor="end" fontSize="10.5" fill="var(--color-texto-3)"
              style={{ fontVariantNumeric: 'tabular-nums' }}
            >
              {valor === 0 ? '0' : montoCorto(valor)}
            </text>
          </g>
        ))}

        <g transform={`translate(${MARGEN.izquierda} ${MARGEN.arriba})`}>
          {barras.map(barra => (
            <g
              key={barra.etiqueta}
              onMouseEnter={() => setMesActivo(barra.etiqueta)}
              onFocus={() => setMesActivo(barra.etiqueta)}
              tabIndex={0}
              className="focus:outline-none"
            >
              {/* Zona sensible de todo el mes: apuntar a una barra de 14px
                  con el mouse es un ejercicio de puntería. */}
              <rect
                x={barra.grupoX} y={0}
                width={barra.anchoGrupo} height={AREA.alto}
                fill={mesActivo === barra.etiqueta ? 'var(--color-superficie-2)' : 'transparent'}
              />
              <path d={contornoBarra(barra.aprobadoRect)} fill="var(--color-positivo-vivo)" />
              <path d={contornoBarra(barra.pagadoRect)} fill="var(--color-acento)" />
              <title>
                {`${barra.etiqueta} · aprobado ${montoCorto(barra.aprobado)} · pagado ${montoCorto(barra.pagado)}`}
              </title>
            </g>
          ))}
        </g>

        {barras.map(barra => (
          <text
            key={barra.etiqueta}
            x={MARGEN.izquierda + barra.centro}
            y={ALTO - 8}
            textAnchor="middle" fontSize="11"
            fill={mesActivo === barra.etiqueta ? 'var(--color-texto)' : 'var(--color-texto-3)'}
            fontWeight={mesActivo === barra.etiqueta ? 600 : 400}
          >
            {barra.etiqueta}
          </text>
        ))}
      </svg>

      {/* El detalle sale al pasar por encima: así ningún mes lleva números
          encima y aun así se puede consultar el valor exacto. */}
      <div className="px-5 pt-1 min-h-[34px]">
        {detalle ? (
          <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1 text-xs">
            <span className="font-semibold text-texto">{detalle.etiqueta} {detalle.anio}</span>
            {SERIES.map(s => (
              <span key={s.clave} className="flex items-center gap-1.5 text-texto-2">
                <span
                  className="w-2 h-2 rounded-sm flex-shrink-0"
                  style={{ background: s.color }}
                  aria-hidden="true"
                />
                {s.etiqueta}
                <b className="cifra font-semibold text-texto">{montoCorto(detalle[s.clave])}</b>
              </span>
            ))}
          </div>
        ) : (
          <p className="text-xs text-texto-3">
            Pasa por encima de un mes para ver las cifras exactas.
          </p>
        )}
      </div>
    </div>
  )
}
