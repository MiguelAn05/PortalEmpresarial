import { useMemo, useState } from "react"
import {
  SEMAFOROS, COLOR_SERIE, COLOR_META, MESES_CORTOS, formatValor,
} from "../constants"

/**
 * Gráficas del módulo, en SVG puro — sin librería externa, porque el servidor
 * no puede reinstalar dependencias con fiabilidad y una línea y unas barras no
 * justifican 200 KB de bundle.
 *
 * Criterios que se respetan en todas:
 *  - Una sola serie por gráfica: un color, sin leyenda (el título ya dice qué
 *    es) y sin doble eje.
 *  - La meta es una anotación de referencia, no una segunda serie.
 *  - El semáforo nunca va solo en color: siempre lleva punto + etiqueta.
 *  - Rejilla y ejes recesivos; etiquetas de valor solo donde aportan.
 */

// ── Tendencia mensual ─────────────────────────────────────────

const ANCHO = 640
const ALTO = 220
const MARGEN = { arriba: 16, derecha: 16, abajo: 28, izquierda: 48 }

export function GraficaTendencia({ serie, unidad, meta, mesActual }) {
  const [encima, setEncima] = useState(null)

  const puntos = useMemo(
    () => serie.map((p, i) => ({ ...p, i })).filter(p => p.valor !== null),
    [serie],
  )

  const escala = useMemo(() => {
    const valores = puntos.map(p => p.valor)
    if (meta !== null && meta !== undefined) valores.push(meta)
    if (!valores.length) return null

    let min = Math.min(...valores, 0)
    let max = Math.max(...valores)
    if (min === max) { max = min + 1 }
    // Un respiro arriba para que la línea no toque el borde.
    const holgura = (max - min) * 0.12
    return { min, max: max + holgura }
  }, [puntos, meta])

  if (!escala || puntos.length === 0) {
    return (
      <div className="h-[220px] flex items-center justify-center text-sm text-texto-3 border border-dashed border-borde rounded-xl">
        Todavía no hay mediciones registradas en el año.
      </div>
    )
  }

  const anchoUtil = ANCHO - MARGEN.izquierda - MARGEN.derecha
  const altoUtil = ALTO - MARGEN.arriba - MARGEN.abajo
  const x = (i) => MARGEN.izquierda + (i / 11) * anchoUtil
  const y = (v) => MARGEN.arriba + altoUtil - ((v - escala.min) / (escala.max - escala.min)) * altoUtil

  // Se rompe la línea donde falta un mes: unir por encima de un hueco
  // inventaría una tendencia que no se midió.
  const tramos = []
  let tramo = []
  serie.forEach((p, i) => {
    if (p.valor === null) { if (tramo.length) { tramos.push(tramo); tramo = [] } }
    else tramo.push({ ...p, i })
  })
  if (tramo.length) tramos.push(tramo)

  const ticks = [escala.min, (escala.min + escala.max) / 2, escala.max]
  const ultimo = puntos[puntos.length - 1]

  return (
    <div className="relative">
      <svg viewBox={`0 0 ${ANCHO} ${ALTO}`} className="w-full" role="img"
        aria-label="Tendencia mensual del indicador">
        {/* Rejilla recesiva */}
        {ticks.map((t, i) => (
          <g key={i}>
            <line x1={MARGEN.izquierda} x2={ANCHO - MARGEN.derecha} y1={y(t)} y2={y(t)}
              stroke="var(--color-borde)" strokeWidth="1" />
            <text x={MARGEN.izquierda - 8} y={y(t) + 4} textAnchor="end"
              className="fill-texto-3" style={{ fontSize: 10 }}>
              {formatValor(Math.round(t * 10) / 10, unidad)}
            </text>
          </g>
        ))}

        {/* La meta es una anotación, no una serie */}
        {meta !== null && meta !== undefined && (
          <g>
            <line x1={MARGEN.izquierda} x2={ANCHO - MARGEN.derecha} y1={y(meta)} y2={y(meta)}
              stroke={COLOR_META} strokeWidth="1.5" strokeDasharray="5 4" />
            <text x={ANCHO - MARGEN.derecha} y={y(meta) - 5} textAnchor="end"
              className="fill-texto-2" style={{ fontSize: 10, fontWeight: 600 }}>
              Meta {formatValor(meta, unidad)}
            </text>
          </g>
        )}

        {/* Meses */}
        {MESES_CORTOS.map((m, i) => (
          <text key={i} x={x(i)} y={ALTO - 8} textAnchor="middle"
            className={i + 1 === mesActual ? "fill-acento-fuerte" : "fill-texto-3"}
            style={{ fontSize: 10, fontWeight: i + 1 === mesActual ? 700 : 400 }}>
            {m}
          </text>
        ))}

        {/* La serie */}
        {tramos.map((t, i) => (
          <polyline key={i} fill="none" stroke={COLOR_SERIE} strokeWidth="2"
            strokeLinejoin="round" strokeLinecap="round"
            points={t.map(p => `${x(p.i)},${y(p.valor)}`).join(' ')} />
        ))}

        {puntos.map(p => {
          const cfg = SEMAFOROS[p.semaforo] || SEMAFOROS.sin_datos
          const activo = encima?.i === p.i
          return (
            <g key={p.i}>
              {/* Zona sensible más grande que el punto, para que sea fácil apuntarle */}
              <rect x={x(p.i) - anchoUtil / 24} y={MARGEN.arriba}
                width={anchoUtil / 12} height={altoUtil}
                fill="transparent" style={{ cursor: 'pointer' }}
                onMouseEnter={() => setEncima(p)} onMouseLeave={() => setEncima(null)} />
              {activo && (
                <line x1={x(p.i)} x2={x(p.i)} y1={MARGEN.arriba} y2={MARGEN.arriba + altoUtil}
                  stroke="var(--color-borde-fuerte)" strokeWidth="1" />
              )}
              {/* Anillo blanco: separa el punto de la línea al superponerse */}
              <circle cx={x(p.i)} cy={y(p.valor)} r={activo ? 6.5 : 4.5}
                fill={cfg.punto} stroke="var(--color-superficie)" strokeWidth="2" />
            </g>
          )
        })}

        {/* Etiqueta directa solo en el último punto, no en todos */}
        {ultimo && !encima && (
          <text x={x(ultimo.i)} y={y(ultimo.valor) - 12} textAnchor="middle"
            className="fill-acento-fuerte" style={{ fontSize: 11, fontWeight: 700 }}>
            {formatValor(ultimo.valor, unidad)}
          </text>
        )}
      </svg>

      {encima && (
        <div className="absolute top-0 left-1/2 -translate-x-1/2 bg-acento-fuerte text-white text-xs rounded-lg px-3 py-2 shadow-lg pointer-events-none whitespace-nowrap">
          <p className="font-semibold">{MESES_CORTOS[encima.i]} · {formatValor(encima.valor, unidad)}</p>
          <p className="text-white/70 flex items-center gap-1.5 mt-0.5">
            <span className="w-2 h-2 rounded-full inline-block"
              style={{ background: (SEMAFOROS[encima.semaforo] || SEMAFOROS.sin_datos).punto }} />
            {(SEMAFOROS[encima.semaforo] || SEMAFOROS.sin_datos).label}
          </p>
          {encima.numerador !== null && encima.denominador !== null && (
            <p className="text-white/70 mt-0.5">{encima.numerador} de {encima.denominador}</p>
          )}
        </div>
      )}
    </div>
  )
}

// ── Miniatura para la tarjeta ─────────────────────────────────

/** Sparkline sin ejes: solo la forma de la tendencia, para leerla de reojo. */
export function Miniatura({ serie, ancho = 120, alto = 32 }) {
  const puntos = serie.map((p, i) => ({ ...p, i })).filter(p => p.valor !== null)
  if (puntos.length < 2) return <div style={{ height: alto }} />

  const valores = puntos.map(p => p.valor)
  const min = Math.min(...valores)
  const max = Math.max(...valores)
  const rango = max - min || 1
  const x = (i) => (i / 11) * (ancho - 4) + 2
  const y = (v) => alto - 3 - ((v - min) / rango) * (alto - 6)

  const ultimo = puntos[puntos.length - 1]
  const cfg = SEMAFOROS[ultimo.semaforo] || SEMAFOROS.sin_datos

  return (
    <svg width={ancho} height={alto} aria-hidden="true">
      <polyline fill="none" stroke={COLOR_SERIE} strokeWidth="2"
        strokeLinejoin="round" strokeLinecap="round" opacity="0.7"
        points={puntos.map(p => `${x(p.i)},${y(p.valor)}`).join(' ')} />
      <circle cx={x(ultimo.i)} cy={y(ultimo.valor)} r="3.5"
        fill={cfg.punto} stroke="var(--color-superficie)" strokeWidth="1.5" />
    </svg>
  )
}

// ── Comparación por área ──────────────────────────────────────

/**
 * Barras horizontales de cumplimiento por área. Una sola serie ⇒ un solo
 * color: pintar cada barra de un color distinto según su valor duplicaría en
 * el color lo que la longitud ya dice.
 */
export function BarrasPorArea({ areas }) {
  const [encima, setEncima] = useState(null)
  const conJuicio = areas.filter(a => a.cumplimiento_pct !== null)

  if (conJuicio.length === 0) {
    return (
      <p className="text-sm text-texto-3 text-center py-8">
        Ningún área tiene indicadores con meta definida en este periodo.
      </p>
    )
  }

  return (
    <div className="space-y-3">
      {conJuicio.map(a => (
        <div key={a.area}
          onMouseEnter={() => setEncima(a.area)} onMouseLeave={() => setEncima(null)}>
          <div className="flex justify-between items-baseline mb-1">
            <span className="text-sm font-semibold text-acento-fuerte">{a.area}</span>
            <span className="text-sm font-bold text-acento-fuerte">{a.cumplimiento_pct}%</span>
          </div>
          <div className="bg-superficie-2 rounded-full h-2.5 overflow-hidden">
            <div className="h-2.5 rounded-full transition-all"
              style={{ width: `${a.cumplimiento_pct}%`, background: COLOR_SERIE }} />
          </div>
          <p className={`text-[11px] mt-1 ${encima === a.area ? 'text-texto-2' : 'text-texto-3'}`}>
            {a.verde} cumplen · {a.amarillo} en alerta · {a.rojo} no cumplen
            {a.sin_datos > 0 && ` · ${a.sin_datos} sin dato`}
          </p>
        </div>
      ))}
    </div>
  )
}

// ── Semáforo ──────────────────────────────────────────────────

/** Punto + etiqueta. Nunca solo color: el ámbar no alcanza contraste suficiente. */
export function ChipSemaforo({ estado, compacto = false }) {
  const cfg = SEMAFOROS[estado] || SEMAFOROS.sin_datos
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border font-semibold ${cfg.chip} ${
      compacto ? 'px-2 py-0.5 text-[10px]' : 'px-3 py-1 text-xs'
    }`}>
      <span className="w-2 h-2 rounded-full shrink-0" style={{ background: cfg.punto }} />
      {cfg.label}
    </span>
  )
}
