import { useMemo, useState } from "react"
import {
  DIAS_SEMANA, MESES, ESTADOS_TAREA, ALERTAS,
  alertaVencimiento, formatHora, tieneHora,
  inicioDia, lunesDeLaSemana, mismoDia, rangoTarea, rejillaMes, sumarDias,
} from "../constants"
import { calcularBarras, contarOcultasPorDia } from "../calendarioLayout"
import CalendarioHoras from "./CalendarioHoras"

const FILAS_VISIBLES_POR_DIA = 3
const ALTO_CARRIL = 24 // px que ocupa cada carril de barras

const MODOS = [
  { id: 'mes',    label: 'Mes' },
  { id: 'semana', label: 'Semana' },
  { id: 'dia',    label: 'Día' },
]

/**
 * Calendario con tres modos:
 *
 *  - Mes: cada tarea es una barra continua de su fecha de inicio a su fecha
 *    de fin, para ver la carga a lo largo del mes. El layout se calcula por
 *    semana asignando a cada tarea un "carril" que respeta de lunes a
 *    domingo, para que la barra se lea como una sola pieza.
 *  - Semana y Día: rejilla de horas al estilo Teams (ver CalendarioHoras),
 *    donde sí importa a qué hora ocurre cada cosa.
 *
 * Las tareas sin fechas no se pueden ubicar; se avisa al pie cuántas son.
 */
export default function CalendarioTareas({ tareas, onSelect }) {
  // 'mes' usa barras por día; 'semana' y 'dia' usan la rejilla de horas
  // estilo Teams, que es donde tiene sentido ver la franja horaria.
  const [modo, setModo] = useState('mes')
  const [ancla, setAncla] = useState(() => new Date())
  const [expandido, setExpandido] = useState({}) // { 'YYYY-MM-DD': true }

  const dias = useMemo(() => {
    if (modo === 'mes') return rejillaMes(ancla)
    if (modo === 'dia') return [inicioDia(ancla)]
    return Array.from({ length: 7 }, (_, i) => sumarDias(lunesDeLaSemana(ancla), i))
  }, [modo, ancla])

  const conFechas = useMemo(() => tareas.filter(t => rangoTarea(t)), [tareas])
  const sinFechas = tareas.length - conFechas.length

  const semanas = useMemo(() => {
    const bloques = []
    for (let i = 0; i < dias.length; i += 7) bloques.push(dias.slice(i, i + 7))
    return bloques.map(semana => ({ dias: semana, barras: calcularBarras(conFechas, semana) }))
  }, [dias, conFechas])

  const navegar = (paso) => setAncla(prev => {
    if (modo === 'mes') return new Date(prev.getFullYear(), prev.getMonth() + paso, 1)
    return sumarDias(prev, paso * (modo === 'dia' ? 1 : 7))
  })

  const titulo = modo === 'mes'
    ? `${MESES[ancla.getMonth()]} ${ancla.getFullYear()}`
    : modo === 'dia'
      ? `${DIAS_SEMANA[(ancla.getDay() + 6) % 7]} ${ancla.getDate()} de ${MESES[ancla.getMonth()]} ${ancla.getFullYear()}`
      : rotuloSemana(dias)

  return (
    <div className="bg-white rounded-2xl border border-borde shadow-sm overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-4 border-b border-borde">
        <div className="flex items-center gap-2">
          <button onClick={() => navegar(-1)} aria-label="Anterior"
            className="w-8 h-8 rounded-lg border border-borde hover:bg-superficie-2 text-texto-2">‹</button>
          <button onClick={() => navegar(1)} aria-label="Siguiente"
            className="w-8 h-8 rounded-lg border border-borde hover:bg-superficie-2 text-texto-2">›</button>
          <h3 className="text-base font-bold text-acento-fuerte capitalize ml-2">{titulo}</h3>
          <button onClick={() => setAncla(new Date())}
            className="ml-2 text-xs font-semibold text-acento hover:underline">Hoy</button>
        </div>

        <div className="inline-flex rounded-lg border border-borde p-1 bg-superficie-2">
          {MODOS.map(m => (
            <button key={m.id} onClick={() => setModo(m.id)}
              className={`px-4 py-1.5 rounded-md text-sm font-semibold transition ${
                modo === m.id ? 'bg-white text-acento-fuerte shadow-sm' : 'text-texto-2'
              }`}>{m.label}</button>
          ))}
        </div>
      </div>

      {modo !== 'mes' ? (
        <CalendarioHoras dias={dias} tareas={conFechas} onSelect={onSelect} />
      ) : (
      <>

      <div className="grid grid-cols-7 border-b border-borde bg-superficie-2">
        {DIAS_SEMANA.map(d => (
          <div key={d} className="px-2 py-2 text-center text-xs font-semibold uppercase tracking-wide text-texto-2">
            {d}
          </div>
        ))}
      </div>

      <div>
        {semanas.map((semana, i) => (
          <SemanaFila
            key={i}
            semana={semana}
            mesActual={ancla.getMonth()}
            altoMinimo={128}
            expandido={expandido}
            onToggleExpandir={(clave) => setExpandido(p => ({ ...p, [clave]: !p[clave] }))}
            onSelect={onSelect}
          />
        ))}
      </div>
      </>
      )}

      <div className="px-5 py-3 border-t border-borde flex flex-wrap items-center gap-4 text-[11px] text-texto-2">
        {Object.entries(ESTADOS_TAREA).map(([v, cfg]) => (
          <span key={v} className="flex items-center gap-1.5">
            <span className="w-3 h-2 rounded-sm" style={{ background: cfg.barra }} />
            {cfg.label}
          </span>
        ))}
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-2 rounded-sm bg-negativo-vivo" /> Vencida
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
    <div className="grid grid-cols-7 border-b border-borde last:border-b-0 relative" style={{ minHeight: alto }}>
      {semana.dias.map((dia, i) => {
        const esHoy = mismoDia(dia, hoy)
        const fueraDeMes = mesActual !== null && dia.getMonth() !== mesActual
        const ocultas = ocultasPorDia[i]
        return (
          <div key={i} className={`border-r border-borde last:border-r-0 px-1.5 pt-1.5 ${fueraDeMes ? 'bg-superficie-2' : ''}`}>
            <div className="flex justify-center">
              <span className={`text-xs font-semibold w-6 h-6 flex items-center justify-center rounded-full ${
                esHoy ? 'bg-acento text-white'
                  : fueraDeMes ? 'text-borde-fuerte' : 'text-texto-2'
              }`}>
                {dia.getDate()}
              </span>
            </div>
            {ocultas > 0 && (
              <button
                onClick={() => onToggleExpandir(clave(dia))}
                className="absolute bottom-1 text-[10px] font-semibold text-acento hover:underline"
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
  const esOutlook = tarea.es_outlook
  const alerta = esOutlook ? null : alertaVencimiento(tarea)
  const color = alerta === 'vencida' ? 'var(--color-negativo-vivo)' : (ESTADOS_TAREA[tarea.estado]?.barra || 'var(--color-texto-3)')
  const ancho = hastaCol - desdeCol + 1
  const hora = tieneHora(tarea.fecha_inicio) ? formatHora(tarea.fecha_inicio) : null

  // Los eventos de Outlook no se pueden confundir con tareas: van en hueco
  // y con borde punteado, no solo en otro color. Un daltónico vería dos
  // barras idénticas si la única diferencia fuera el tono.
  const estiloOutlook = {
    background: 'var(--color-superficie-2)',
    border: '1.5px dashed var(--color-texto-2)',
    color: 'var(--color-texto-2)',
  }

  const abrir = () => {
    if (!esOutlook) return onSelect(tarea)
    if (tarea.enlace) window.open(tarea.enlace, '_blank', 'noopener,noreferrer')
  }

  const titulo = esOutlook
    ? `${tarea.titulo}${tarea.privado ? ' (evento privado)' : ''} · Outlook${tarea.enlace ? ' · clic para abrirlo' : ''}`
    : `${tarea.titulo}${tarea.asignado_nombre ? ` · ${tarea.asignado_nombre}` : ''}${alerta ? ` · ${ALERTAS[alerta].label}` : ''}`

  return (
    <button
      onClick={abrir}
      title={titulo}
      className={`absolute pointer-events-auto text-left text-[11px] font-medium px-2 py-[3px] truncate transition ${esOutlook ? 'hover:bg-superficie-2' : 'text-white hover:brightness-110'}`}
      style={{
        left: `calc(${(desdeCol * 100) / 7}% + 3px)`,
        width: `calc(${(ancho * 100) / 7}% - 6px)`,
        top: carril * ALTO_CARRIL,
        height: ALTO_CARRIL - 4,
        ...(esOutlook ? estiloOutlook : { background: color }),
        borderTopLeftRadius: continuaAntes ? 0 : 6,
        borderBottomLeftRadius: continuaAntes ? 0 : 6,
        borderTopRightRadius: continuaDespues ? 0 : 6,
        borderBottomRightRadius: continuaDespues ? 0 : 6,
      }}
    >
      {continuaAntes && '‹ '}
      {hora && <span className="opacity-80 mr-1">{hora}</span>}
      {esOutlook && <span className="opacity-70 mr-1" aria-hidden="true">◇</span>}
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
