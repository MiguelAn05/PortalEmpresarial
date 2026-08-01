import { useMemo } from "react"
import {
  MESES, ESTADOS_TAREA, ALERTAS,
  alertaVencimiento, colorAvance, formatFecha,
  inicioDia, mismoDia, rangoTarea, sumarDias,
} from "../constants"
import { agruparPorMes } from "../calendarioLayout"

const ANCHO_DIA = 26      // px por día
const ANCHO_ETIQUETA = 260 // px de la columna fija de títulos
const MARGEN_DIAS = 2     // aire a los lados del rango

/**
 * Cronograma horizontal: una barra por tarea entre su fecha de inicio y su
 * fecha de fin, con el avance sombreado adentro. Es la lectura que en el
 * Excel DE-F-10 se hacía a mano.
 *
 * El rango de fechas se calcula solo, a partir de las tareas que tienen
 * fechas; las que no tienen no se pueden ubicar y se listan aparte.
 */
export default function GanttView({ tareas, onSelect, mostrarProyecto = true }) {
  const conFechas = useMemo(
    () => tareas.filter(t => rangoTarea(t)).sort((a, b) => rangoTarea(a).desde - rangoTarea(b).desde),
    [tareas],
  )
  const sinFechas = useMemo(() => tareas.filter(t => !rangoTarea(t)), [tareas])

  const { dias, desde } = useMemo(() => {
    if (!conFechas.length) return { dias: [], desde: null }
    const rangos = conFechas.map(rangoTarea)
    const min = sumarDias(new Date(Math.min(...rangos.map(r => r.desde))), -MARGEN_DIAS)
    const max = sumarDias(new Date(Math.max(...rangos.map(r => r.hasta))), MARGEN_DIAS)
    const total = Math.round((max - min) / 86400000) + 1
    return { dias: Array.from({ length: total }, (_, i) => sumarDias(min, i)), desde: min }
  }, [conFechas])

  if (!conFechas.length) {
    return (
      <div className="bg-white rounded-2xl border border-dashed border-[#D6E0F0] p-16 text-center">
        <p className="text-[#6B7EA8]">
          El cronograma necesita tareas con fecha de inicio o de fin. Ninguna de las tareas
          visibles tiene fechas todavía.
        </p>
      </div>
    )
  }

  const anchoTotal = dias.length * ANCHO_DIA
  const hoy = inicioDia(new Date())
  const offsetHoy = Math.round((hoy - desde) / 86400000)

  return (
    <div className="bg-white rounded-2xl border border-[#D6E0F0] shadow-sm overflow-hidden">
      <div className="overflow-x-auto">
        <div style={{ minWidth: ANCHO_ETIQUETA + anchoTotal }}>

          {/* Cabecera: meses arriba, días abajo */}
          <div className="flex border-b border-[#D6E0F0] bg-[#F7F9FC] sticky top-0 z-10">
            <div className="shrink-0 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-[#6B7EA8] border-r border-[#D6E0F0]"
              style={{ width: ANCHO_ETIQUETA }}>
              Tarea
            </div>
            <div style={{ width: anchoTotal }}>
              <div className="flex h-5">
                {agruparPorMes(dias, MESES).map(({ etiqueta, cantidad }, i) => (
                  <div key={i}
                    className="text-[10px] font-semibold text-[#6B7EA8] border-r border-[#E4EBF5] px-1.5 truncate leading-5"
                    style={{ width: cantidad * ANCHO_DIA }}>
                    {etiqueta}
                  </div>
                ))}
              </div>
              <div className="flex h-6">
                {dias.map((d, i) => {
                  const finde = d.getDay() === 0 || d.getDay() === 6
                  return (
                    <div key={i}
                      className={`text-[10px] text-center leading-6 border-r border-[#EDF2F7] ${
                        mismoDia(d, hoy) ? 'bg-[#1A4FA0] text-white font-bold'
                          : finde ? 'bg-[#F0F3F8] text-[#9BACC8]' : 'text-[#9BACC8]'
                      }`}
                      style={{ width: ANCHO_DIA }}>
                      {d.getDate()}
                    </div>
                  )
                })}
              </div>
            </div>
          </div>

          {/* Filas */}
          <div className="relative">
            {/* Línea de hoy, cruzando todas las filas */}
            {offsetHoy >= 0 && offsetHoy < dias.length && (
              <div className="absolute top-0 bottom-0 w-px bg-[#1A4FA0]/40 pointer-events-none z-10"
                style={{ left: ANCHO_ETIQUETA + offsetHoy * ANCHO_DIA + ANCHO_DIA / 2 }} />
            )}

            {conFechas.map(tarea => {
              const rango = rangoTarea(tarea)
              const inicioCol = Math.round((rango.desde - desde) / 86400000)
              const largo = Math.round((rango.hasta - rango.desde) / 86400000) + 1
              const alerta = alertaVencimiento(tarea)
              const color = alerta === 'vencida' ? '#EF4444' : (ESTADOS_TAREA[tarea.estado]?.barra || '#94A3B8')

              return (
                <div key={tarea.id}
                  onClick={() => onSelect(tarea)}
                  className="flex items-center border-b border-[#EDF2F7] hover:bg-[#F9FBFD] transition cursor-pointer h-11">
                  <div className="shrink-0 px-4 border-r border-[#EDF2F7] overflow-hidden" style={{ width: ANCHO_ETIQUETA }}>
                    <p className="text-sm font-semibold text-[#1A2B47] truncate">{tarea.titulo}</p>
                    <p className="text-[11px] text-[#9BACC8] truncate">
                      {mostrarProyecto && tarea.proyecto_nombre}
                      {mostrarProyecto && tarea.asignado_nombre && ' · '}
                      {tarea.asignado_nombre}
                    </p>
                  </div>

                  <div className="relative" style={{ width: anchoTotal, height: 44 }}>
                    {/* Rejilla de fondo: marca fines de semana */}
                    <div className="absolute inset-0 flex">
                      {dias.map((d, i) => (
                        <div key={i}
                          className={`border-r border-[#F2F5FA] ${d.getDay() === 0 || d.getDay() === 6 ? 'bg-[#FAFBFD]' : ''}`}
                          style={{ width: ANCHO_DIA }} />
                      ))}
                    </div>

                    <div
                      className="absolute rounded-md overflow-hidden flex items-center"
                      title={`${formatFecha(rango.desde)} → ${formatFecha(rango.hasta)}${alerta ? ` · ${ALERTAS[alerta].label}` : ''}`}
                      style={{
                        left: inicioCol * ANCHO_DIA + 2,
                        width: largo * ANCHO_DIA - 4,
                        top: 11, height: 22, background: color,
                      }}
                    >
                      {tarea.avance_pct > 0 && (
                        <div className="absolute inset-y-0 left-0 opacity-95"
                          style={{ width: `${tarea.avance_pct}%`, background: colorAvance(tarea.avance_pct) }} />
                      )}
                      <span className="relative text-[10px] font-semibold text-white px-2 truncate">
                        {tarea.avance_pct}%
                      </span>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {sinFechas.length > 0 && (
        <div className="px-5 py-3 border-t border-[#D6E0F0] bg-[#F7F9FC]">
          <p className="text-xs text-[#6B7EA8] mb-2">
            {sinFechas.length} tarea{sinFechas.length === 1 ? '' : 's'} sin fechas — no se {sinFechas.length === 1 ? 'puede' : 'pueden'} ubicar en el cronograma:
          </p>
          <div className="flex flex-wrap gap-2">
            {sinFechas.map(t => (
              <button key={t.id} onClick={() => onSelect(t)}
                className="text-xs bg-white border border-[#D6E0F0] rounded-full px-3 py-1 hover:border-[#1A4FA0] text-[#1A2B47]">
                {t.titulo}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
