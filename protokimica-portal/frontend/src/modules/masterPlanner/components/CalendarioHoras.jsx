import { useEffect, useMemo, useRef, useState } from "react"
import {
  DIAS_SEMANA, ESTADOS_TAREA, ALERTAS,
  alertaVencimiento, formatHora, tieneHora,
  inicioDia, mismoDia, rangoTarea,
} from "../constants"

const ALTO_HORA = 48        // px por hora
const HORA_INICIO = 6       // la rejilla arranca a las 6:00
const HORA_FIN = 22         // y termina a las 22:00
const DURACION_POR_DEFECTO = 60 // minutos que ocupa una tarea sin hora de fin

/**
 * Vista de horas al estilo del calendario de Teams: una columna por día y
 * una fila por hora, con las tareas ubicadas en su franja real.
 *
 * Arriba, en una banda aparte, van las tareas "de todo el día": las que no
 * tienen hora o las que abarcan varios días. Meterlas en la rejilla no
 * tendría sentido — ocuparían la columna entera.
 */
export default function CalendarioHoras({ dias, tareas, onSelect }) {
  const contenedor = useRef(null)
  const [ahora, setAhora] = useState(() => new Date())

  // La línea de "ahora" se refresca cada minuto; sin esto se queda congelada
  // en la hora en que se abrió la pestaña.
  useEffect(() => {
    const id = setInterval(() => setAhora(new Date()), 60000)
    return () => clearInterval(id)
  }, [])

  const horas = useMemo(
    () => Array.from({ length: HORA_FIN - HORA_INICIO + 1 }, (_, i) => HORA_INICIO + i),
    [],
  )

  const { conHora, todoElDia } = useMemo(() => repartirTareas(tareas, dias), [tareas, dias])

  // Al abrir, centra la vista cerca de la hora actual en vez de a las 6 a.m.
  useEffect(() => {
    if (!contenedor.current) return
    const hora = Math.max(HORA_INICIO, Math.min(new Date().getHours() - 1, HORA_FIN))
    contenedor.current.scrollTop = (hora - HORA_INICIO) * ALTO_HORA
  }, [])

  const columnas = dias.length

  return (
    <div>
      {/* Cabecera de días */}
      <div className="flex border-b border-[#D6E0F0] bg-[#F7F9FC] sticky top-0 z-20">
        <div className="w-14 shrink-0 border-r border-[#D6E0F0]" />
        {dias.map((dia, i) => {
          const esHoy = mismoDia(dia, ahora)
          return (
            <div key={i} className="flex-1 text-center py-2 border-r border-[#EDF2F7] last:border-r-0 min-w-0">
              <p className="text-[11px] uppercase tracking-wide text-[#6B7EA8]">
                {DIAS_SEMANA[(dia.getDay() + 6) % 7]}
              </p>
              <p className={`text-sm font-bold mx-auto mt-0.5 w-7 h-7 flex items-center justify-center rounded-full ${
                esHoy ? 'bg-[#1A4FA0] text-white' : 'text-[#0D2B5E]'
              }`}>
                {dia.getDate()}
              </p>
            </div>
          )
        })}
      </div>

      {/* Banda de todo el día */}
      {todoElDia.length > 0 && (
        <div className="flex border-b border-[#D6E0F0] bg-white">
          <div className="w-14 shrink-0 border-r border-[#D6E0F0] text-[10px] text-[#9BACC8] text-right pr-2 pt-2 leading-tight">
            Todo el día
          </div>
          <div className="flex-1 py-1.5 px-1 space-y-1 min-w-0">
            {todoElDia.map(({ tarea, desdeCol, hastaCol }) => (
              <ChipTodoElDia
                key={tarea.id}
                tarea={tarea}
                desdeCol={desdeCol}
                hastaCol={hastaCol}
                columnas={columnas}
                onSelect={onSelect}
              />
            ))}
          </div>
        </div>
      )}

      {/* Rejilla de horas */}
      <div ref={contenedor} className="relative overflow-y-auto" style={{ maxHeight: 560 }}>
        <div className="flex">
          <div className="w-14 shrink-0 border-r border-[#D6E0F0]">
            {horas.map(h => (
              <div key={h} className="relative border-b border-[#F2F5FA]" style={{ height: ALTO_HORA }}>
                <span className="absolute -top-2 right-2 text-[10px] text-[#9BACC8] bg-white px-1">
                  {String(h).padStart(2, '0')}:00
                </span>
              </div>
            ))}
          </div>

          {dias.map((dia, col) => {
            const delDia = conHora.filter(b => mismoDia(b.inicio, dia))
            const bloques = repartirSolapes(delDia)
            const esHoy = mismoDia(dia, ahora)
            const minutosAhora = (ahora.getHours() - HORA_INICIO) * 60 + ahora.getMinutes()

            return (
              <div key={col} className="flex-1 relative border-r border-[#EDF2F7] last:border-r-0 min-w-0">
                {horas.map(h => (
                  <div key={h} className="border-b border-[#F2F5FA]" style={{ height: ALTO_HORA }} />
                ))}

                {esHoy && minutosAhora >= 0 && minutosAhora <= (HORA_FIN - HORA_INICIO) * 60 && (
                  <div
                    className="absolute inset-x-0 border-t-2 border-[#D93B3B] z-10 pointer-events-none"
                    style={{ top: (minutosAhora / 60) * ALTO_HORA }}
                  >
                    <span className="absolute -left-1 -top-1 w-2 h-2 rounded-full bg-[#D93B3B]" />
                  </div>
                )}

                {bloques.map(b => (
                  <BloqueHora key={b.tarea.id} bloque={b} onSelect={onSelect} />
                ))}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

function ChipTodoElDia({ tarea, desdeCol, hastaCol, columnas, onSelect }) {
  const alerta = alertaVencimiento(tarea)
  const color = alerta === 'vencida' ? '#EF4444' : (ESTADOS_TAREA[tarea.estado]?.barra || '#94A3B8')
  const ancho = hastaCol - desdeCol + 1

  return (
    <button
      onClick={() => onSelect(tarea)}
      title={`${tarea.titulo}${tarea.asignado_nombre ? ` · ${tarea.asignado_nombre}` : ''}`}
      className="block text-left text-white text-[11px] font-medium px-2 py-[3px] rounded truncate hover:brightness-110 transition"
      style={{
        marginLeft: `${(desdeCol / columnas) * 100}%`,
        width: `${(ancho / columnas) * 100}%`,
        background: color,
      }}
    >
      {tarea.titulo}
      {tarea.asignado_nombre && <span className="opacity-80"> · {tarea.asignado_nombre}</span>}
    </button>
  )
}

function BloqueHora({ bloque, onSelect }) {
  const { tarea, inicio, fin, carril, carriles } = bloque
  const alerta = alertaVencimiento(tarea)
  const color = alerta === 'vencida' ? '#EF4444' : (ESTADOS_TAREA[tarea.estado]?.barra || '#94A3B8')

  const minutosDesde = (inicio.getHours() - HORA_INICIO) * 60 + inicio.getMinutes()
  const duracion = Math.max(30, (fin - inicio) / 60000)
  const anchoPct = 100 / carriles

  return (
    <button
      onClick={() => onSelect(tarea)}
      title={`${formatHora(inicio)}–${formatHora(fin)} · ${tarea.titulo}${tarea.asignado_nombre ? ` · ${tarea.asignado_nombre}` : ''}${alerta ? ` · ${ALERTAS[alerta].label}` : ''}`}
      className="absolute text-left rounded-md px-1.5 py-1 overflow-hidden hover:brightness-110 transition border-l-[3px] z-[5]"
      style={{
        top: (minutosDesde / 60) * ALTO_HORA,
        height: Math.max(22, (duracion / 60) * ALTO_HORA - 2),
        left: `calc(${carril * anchoPct}% + 2px)`,
        width: `calc(${anchoPct}% - 4px)`,
        background: `${color}22`,
        borderLeftColor: color,
      }}
    >
      <p className="text-[11px] font-semibold text-[#1A2B47] truncate leading-tight">{tarea.titulo}</p>
      <p className="text-[10px] text-[#6B7EA8] truncate leading-tight">
        {formatHora(inicio)}
        {tarea.asignado_nombre && ` · ${tarea.asignado_nombre}`}
      </p>
    </button>
  )
}

// ── Reparto de tareas ─────────────────────────────────────────
/**
 * Separa las tareas que van en la rejilla de horas de las que van en la
 * banda superior. Van a la rejilla solo las que caben en un día y tienen
 * hora explícita; el resto se lee mejor como barra de todo el día.
 */
function repartirTareas(tareas, dias) {
  const primero = inicioDia(dias[0])
  const ultimo = inicioDia(dias[dias.length - 1])
  const conHora = []
  const todoElDia = []

  for (const tarea of tareas) {
    const rango = rangoTarea(tarea)
    if (!rango || rango.hasta < primero || rango.desde > ultimo) continue

    const unSoloDia = rango.desde.getTime() === rango.hasta.getTime()
    const referencia = tarea.fecha_inicio || tarea.fecha_fin
    const puntual = unSoloDia && tieneHora(referencia)

    if (puntual) {
      const inicio = new Date(referencia)
      // Si hay hora de fin en el mismo día se respeta; si no, se asume una
      // hora de duración para que el bloque tenga un alto legible.
      const finReal = tarea.fecha_fin ? new Date(tarea.fecha_fin) : null
      const fin = finReal && finReal > inicio && mismoDia(finReal, inicio)
        ? finReal
        : new Date(inicio.getTime() + DURACION_POR_DEFECTO * 60000)
      conHora.push({ tarea, inicio, fin })
    } else {
      todoElDia.push({
        tarea,
        desdeCol: Math.max(0, diasEntre(primero, rango.desde)),
        hastaCol: Math.min(dias.length - 1, diasEntre(primero, rango.hasta)),
      })
    }
  }
  return { conHora, todoElDia }
}

/**
 * Reparte en columnas las tareas que se pisan en el tiempo, como hace
 * Teams: dos reuniones a la misma hora salen lado a lado, no encimadas.
 */
function repartirSolapes(bloques) {
  const ordenados = [...bloques].sort((a, b) => a.inicio - b.inicio || a.tarea.id - b.tarea.id)
  const grupos = []
  let grupo = []

  for (const b of ordenados) {
    if (grupo.length && !grupo.some(x => b.inicio < x.fin && b.fin > x.inicio)) {
      grupos.push(grupo)
      grupo = []
    }
    grupo.push(b)
  }
  if (grupo.length) grupos.push(grupo)

  return grupos.flatMap(g =>
    g.map((b, i) => ({ ...b, carril: i, carriles: g.length })))
}

function diasEntre(a, b) {
  return Math.round((inicioDia(b) - inicioDia(a)) / 86400000)
}
