import { useMemo, useState } from "react"
import {
  DIAS_SEMANA, MESES, ESTADOS_TAREA, ALERTAS,
  alertaVencimiento, formatHora, tieneHora,
  inicioDia, lunesDeLaSemana, mismoDia, rangoTarea, rejillaMes, sumarDias,
} from "../constants"
import { calcularBarras, contarOcultasPorDia } from "../calendarioLayout"

const FILAS_VISIBLES_POR_DIA = 3
const ALTO_CARRIL = 24 // px que ocupa cada carril de barras

/**
 * Calendario tipo Notion: cada tarea es una barra continua desde su fecha
 * de inicio hasta su fecha de fin, así se ve la carga real de cada persona
 * y no solo el día de entrega. Las tareas sin fechas no aparecen (se avisa
 * al pie cuántas quedaron fuera).
 *
 * El layout se calcula por semana: a cada tarea se le asigna un "carril"
 * (fila) que respeta a lo largo de toda la semana, para que la barra se
 * lea como una sola pieza en vez de saltar de altura entre días.
 */
export default function CalendarioTareas({ tareas, onSelect }) {
  const [modo, setModo] = useState('mes')       // mes | semana
  const [ancla, setAncla] = useState(() => new Date())
  const [expandido, setExpandido] = useState({}) // { 'YYYY-MM-DD': true }

  const dias = useMemo(
    () => (modo === 'mes'
      ? rejillaMes(ancla)
      : Array.from({ length: 7 }, (_, i) => sumarDias(lunesDeLaSemana(ancla), i))),
    [modo, ancla],
  )

  const conFechas = useMemo(() => tareas.filter(t => rangoTarea(t)), [tareas])
  const sinFechas = tareas.length - conFechas.length

  const semanas = useMemo(() => {
    const bloques = []
    for (let i = 0; i < dias.length; i += 7) bloques.push(dias.slice(i, i + 7))
    return bloques.map(semana => ({ dias: semana, barras: calcularBarras(conFechas, semana) }))
  }, [dias, conFechas])

  const navegar = (paso) => setAncla(prev =>
    modo === 'mes'
      ? new Date(prev.getFullYear(), prev.getMonth() + paso, 1)
      : sumarDias(prev, paso * 7))

  const titulo = modo === 'mes'
    ? `${MESES[ancla.getMonth()]} ${ancla.getFullYear()}`
    : rotuloSemana(dias)

  return (
    <div className="bg-white rounded-2xl border border-[#D6E0F0] shadow-sm overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-4 border-b border-[#D6E0F0]">
        <div className="flex items-center gap-2">
          <button onClick={() => navegar(-1)} aria-label="Anterior"
            className="w-8 h-8 rounded-lg border border-[#D6E0F0] hover:bg-[#F7F9FC] text-[#6B7EA8]">‹</button>
          <button onClick={() => navegar(1)} aria-label="Siguiente"
            className="w-8 h-8 rounded-lg border border-[#D6E0F0] hover:bg-[#F7F9FC] text-[#6B7EA8]">›</button>
          <h3 className="text-base font-bold text-[#0D2B5E] capitalize ml-2">{titulo}</h3>
          <button onClick={() => setAncla(new Date())}
            className="ml-2 text-xs font-semibold text-[#1A4FA0] hover:underline">Hoy</button>
        </div>

        <div className="inline-flex rounded-lg border border-[#D6E0F0] p-1 bg-[#F7F9FC]">
          {['mes', 'semana'].map(m => (
            <button key={m} onClick={() => setModo(m)}
              className={`px-4 py-1.5 rounded-md text-sm font-semibold capitalize transition ${
                modo === m ? 'bg-white text-[#0D2B5E] shadow-sm' : 'text-[#6B7EA8]'
              }`}>{m}</button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-7 border-b border-[#D6E0F0] bg-[#F7F9FC]">
        {DIAS_SEMANA.map(d => (
          <div key={d} className="px-2 py-2 text-center text-xs font-semibold uppercase tracking-wide text-[#6B7EA8]">
            {d}
          </div>
        ))}
      </div>

      <div>
        {semanas.map((semana, i) => (
          <SemanaFila
            key={i}
            semana={semana}
            mesActual={modo === 'mes' ? ancla.getMonth() : null}
            altoMinimo={modo === 'semana' ? 320 : 128}
            expandido={expandido}
            onToggleExpandir={(clave) => setExpandido(p => ({ ...p, [clave]: !p[clave] }))}
            onSelect={onSelect}
          />
        ))}
      </div>

      <div className="px-5 py-3 border-t border-[#D6E0F0] flex flex-wrap items-center gap-4 text-[11px] text-[#6B7EA8]">
        {Object.entries(ESTADOS_TAREA).map(([v, cfg]) => (
          <span key={v} className="flex items-center gap-1.5">
            <span className="w-3 h-2 rounded-sm" style={{ background: cfg.barra }} />
            {cfg.label}
          </span>
        ))}
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-2 rounded-sm bg-red-500" /> Vencida
        </span>
        {sinFechas > 0 && (
          <span className="ml-auto italic">
            {sinFechas} tarea{sinFechas === 1 ? '' : 's'} sin fechas — no {sinFechas === 1 ? 'aparece' : 'aparecen'} en el calendario.
          </span>
        )}
      </div>
    </div>
  )
}

function SemanaFila({ semana, mesActual, altoMinimo, expandido, onToggleExpandir, onSelect }) {
  const hoy = inicioDia(new Date())
  // Cuántos carriles caben antes de cortar; si algún día está expandido, se
  // muestran todos los de esa semana.
  const hayExpandido = semana.dias.some(d => expandido[clave(d)])
  const carrilesUsados = semana.barras.length ? Math.max(...semana.barras.map(b => b.carril)) + 1 : 0
  const limite = hayExpandido ? carrilesUsados : Math.min(carrilesUsados, FILAS_VISIBLES_POR_DIA)

  const visibles = semana.barras.filter(b => b.carril < limite)
  const ocultasPorDia = contarOcultasPorDia(semana.barras, limite)

  // Las barras son absolutas, así que no empujan el alto de la fila: hay que
  // reservarlo a mano o al expandir un día las barras se salen de la celda.
  // 32px de cabecera del número + 24px por carril + 20px para el "+N más".
  const alto = Math.max(altoMinimo, 32 + limite * ALTO_CARRIL + 20)

  return (
    <div className="grid grid-cols-7 border-b border-[#EDF2F7] last:border-b-0 relative" style={{ minHeight: alto }}>
      {semana.dias.map((dia, i) => {
        const esHoy = mismoDia(dia, hoy)
        const fueraDeMes = mesActual !== null && dia.getMonth() !== mesActual
        const ocultas = ocultasPorDia[i]
        return (
          <div key={i} className={`border-r border-[#EDF2F7] last:border-r-0 px-1.5 pt-1.5 ${fueraDeMes ? 'bg-[#FAFBFD]' : ''}`}>
            <div className="flex justify-center">
              <span className={`text-xs font-semibold w-6 h-6 flex items-center justify-center rounded-full ${
                esHoy ? 'bg-[#1A4FA0] text-white'
                  : fueraDeMes ? 'text-[#C3CFE2]' : 'text-[#6B7EA8]'
              }`}>
                {dia.getDate()}
              </span>
            </div>
            {ocultas > 0 && (
              <button
                onClick={() => onToggleExpandir(clave(dia))}
                className="absolute bottom-1 text-[10px] font-semibold text-[#1A4FA0] hover:underline"
                style={{ left: `calc(${(i * 100) / 7}% + 8px)` }}
              >
                +{ocultas} más
              </button>
            )}
          </div>
        )
      })}

      {/* Las barras van encima de la rejilla, posicionadas en porcentaje de ancho. */}
      <div className="absolute inset-x-0 top-8 bottom-0 pointer-events-none">
        {visibles.map(barra => (
          <BarraTarea key={`${barra.tarea.id}-${barra.desdeCol}`} barra={barra} onSelect={onSelect} />
        ))}
      </div>
    </div>
  )
}

function BarraTarea({ barra, onSelect }) {
  const { tarea, desdeCol, hastaCol, carril, continuaAntes, continuaDespues } = barra
  const alerta = alertaVencimiento(tarea)
  const color = alerta === 'vencida' ? '#EF4444' : (ESTADOS_TAREA[tarea.estado]?.barra || '#94A3B8')
  const ancho = hastaCol - desdeCol + 1
  const hora = tieneHora(tarea.fecha_inicio) ? formatHora(tarea.fecha_inicio) : null

  return (
    <button
      onClick={() => onSelect(tarea)}
      title={`${tarea.titulo}${tarea.asignado_nombre ? ` · ${tarea.asignado_nombre}` : ''}${alerta ? ` · ${ALERTAS[alerta].label}` : ''}`}
      className="absolute pointer-events-auto text-left text-white text-[11px] font-medium px-2 py-[3px] truncate hover:brightness-110 transition"
      style={{
        left: `calc(${(desdeCol * 100) / 7}% + 3px)`,
        width: `calc(${(ancho * 100) / 7}% - 6px)`,
        top: carril * ALTO_CARRIL,
        height: ALTO_CARRIL - 4,
        background: color,
        borderTopLeftRadius: continuaAntes ? 0 : 6,
        borderBottomLeftRadius: continuaAntes ? 0 : 6,
        borderTopRightRadius: continuaDespues ? 0 : 6,
        borderBottomRightRadius: continuaDespues ? 0 : 6,
      }}
    >
      {continuaAntes && '‹ '}
      {hora && <span className="opacity-80 mr-1">{hora}</span>}
      {tarea.titulo}
      {tarea.asignado_nombre && <span className="opacity-80"> · {tarea.asignado_nombre}</span>}
    </button>
  )
}

function clave(d) {
  return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`
}

function rotuloSemana(dias) {
  const a = dias[0], b = dias[6]
  const mismoMes = a.getMonth() === b.getMonth()
  return mismoMes
    ? `${a.getDate()} – ${b.getDate()} de ${MESES[a.getMonth()]} ${a.getFullYear()}`
    : `${a.getDate()} ${MESES[a.getMonth()].slice(0, 3)} – ${b.getDate()} ${MESES[b.getMonth()].slice(0, 3)} ${b.getFullYear()}`
}
