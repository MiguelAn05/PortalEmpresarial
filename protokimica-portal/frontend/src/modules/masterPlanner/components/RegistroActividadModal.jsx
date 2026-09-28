/**
 * El registro de una actividad: el mes día por día.
 *
 * **No es una lista de días registrados.** Esa lista crecía sin final —a los
 * seis meses son ciento veinte renglones iguales— y no respondía la pregunta
 * que uno tiene, que es «¿voy al día?». Un mes cabe en un bloque, se lee de
 * un vistazo y no crece nunca: son treinta y un cuadros como mucho.
 *
 * Qué significa cada día lo decide el SERVIDOR (`no_aplica`, `cumplido`,
 * `pendiente`, `sin_registrar`). Aquí no se calcula ninguna fecha: la regla
 * de días hábiles, festivos y frecuencia vive en un solo sitio, y repetida
 * en el navegador diría otra cosa el día que se agregue un festivo.
 */
import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  mesDeActividad, registrarActividad, quitarRegistroActividad,
} from "../api"
import { DIAS_SEMANA, comoFecha, formatFecha } from "../constants"
import { mensajeDeError } from "../../../core/errores.js"
import {
  IconoCerrar, IconoChevron, IconoRepetir,
} from "../../../core/components/Iconos.jsx"

const MESES = [
  'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
  'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
]

// Cómo se ve cada estado. El color nunca va solo: cada cuadro lleva su
// `title` con el día y lo que pasó, y la leyenda de abajo lo dice en
// palabras — el verde y el ámbar de la marca no se leen en voz alta.
const ESTADOS = {
  cumplido:      { fondo: 'bg-positivo-vivo text-white border-positivo-vivo', label: 'Registrado' },
  sin_registrar: { fondo: 'bg-negativo-bg text-negativo border-negativo/30',  label: 'Sin registrar' },
  pendiente:     { fondo: 'bg-alerta-bg text-alerta border-ambar/40',         label: 'Falta hoy' },
  no_aplica:     { fondo: 'bg-superficie-2 text-texto-3 border-borde',        label: 'No tocaba' },
}

export default function RegistroActividadModal({ actividad, onClose, onCambio, onEliminar }) {
  const queryClient = useQueryClient()
  const hoy = new Date()
  const [anio, setAnio] = useState(hoy.getFullYear())
  const [mes, setMes] = useState(hoy.getMonth() + 1)

  const { data, isLoading } = useQuery({
    queryKey: ["mp-actividad-mes", actividad.id, anio, mes],
    queryFn: () => mesDeActividad(actividad.id, { anio, mes }),
  })

  const refrescar = () => {
    queryClient.invalidateQueries({ queryKey: ["mp-actividad-mes", actividad.id] })
    onCambio?.()
  }

  const mutMarcar = useMutation({
    mutationFn: (fecha) => registrarActividad(actividad.id, { fecha }),
    onSuccess: refrescar,
    onError: (err) => alert(mensajeDeError(err, 'No se pudo registrar ese día.')),
  })

  const mutQuitar = useMutation({
    mutationFn: (fecha) => quitarRegistroActividad(actividad.id, fecha),
    onSuccess: refrescar,
    onError: (err) => alert(mensajeDeError(err, 'No se pudo quitar el registro.')),
  })

  const mover = (paso) => {
    const nuevo = new Date(anio, mes - 1 + paso, 1)
    setAnio(nuevo.getFullYear())
    setMes(nuevo.getMonth() + 1)
  }

  // Los cuadros arrancan en la columna del día de la semana que cae el 1.º,
  // o el mes se lee corrido y no se puede comparar «los martes» de un
  // vistazo, que es justo para lo que sirve ver el mes.
  const primerDia = data?.dias?.[0] ? comoFecha(data.dias[0].fecha).getDay() : 0
  const huecos = (primerDia + 6) % 7   // lunes primero

  const alPulsar = (dia) => {
    if (dia.estado === 'no_aplica') return
    if (dia.estado === 'cumplido') {
      if (!window.confirm(`¿Quitar el registro del ${formatFecha(dia.fecha)}?`)) return
      mutQuitar.mutate(dia.fecha)
      return
    }
    // `pendiente` de un día futuro lo rechaza el servidor; no hace falta
    // repetir aquí esa cuenta, solo no ofrecerla como si fuera a funcionar.
    if (comoFecha(dia.fecha) > hoy) return
    mutMarcar.mutate(dia.fecha)
  }

  return (
    <div
      className="fixed inset-0 bg-acento-fuerte/40 backdrop-blur-sm flex items-start
        justify-center p-4 z-50 overflow-y-auto"
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="bg-white rounded-2xl w-full max-w-lg my-8 shadow-xl overflow-hidden"
      >
        <header className="bg-gradient-to-r from-acento-fuerte to-acento p-6 text-white relative">
          <button
            onClick={onClose} aria-label="Cerrar"
            className="absolute top-4 right-4 text-white/70 hover:text-white"
          >
            <IconoCerrar tam={18} />
          </button>
          <h2 className="text-lg font-bold pr-8">{actividad.titulo}</h2>
          <p className="text-xs text-white/80 mt-1">
            {actividad.frecuencia_texto} · {actividad.asignado_nombre}
          </p>
        </header>

        <div className="p-6 space-y-5">
          {/* Mes a mes: el registro no se acaba, pero siempre se mira un mes. */}
          <div className="flex items-center justify-between">
            <button
              onClick={() => mover(-1)} aria-label="Mes anterior"
              className="w-8 h-8 flex items-center justify-center rounded-lg text-texto-2
                hover:bg-superficie-2 transition-colors duration-150"
            >
              <IconoChevron tam={16} className="rotate-180" />
            </button>
            <span className="text-sm font-semibold text-texto capitalize">
              {MESES[mes - 1]} {anio}
            </span>
            <button
              onClick={() => mover(1)} aria-label="Mes siguiente"
              className="w-8 h-8 flex items-center justify-center rounded-lg text-texto-2
                hover:bg-superficie-2 transition-colors duration-150"
            >
              <IconoChevron tam={16} />
            </button>
          </div>

          {isLoading || !data ? (
            <p className="text-sm text-texto-2 text-center py-8">Cargando…</p>
          ) : (
            <>
              <div className="bg-superficie-2 rounded-xl p-4">
                {data.esperados_hasta_hoy === 0 ? (
                  <span className="text-sm text-texto-2">
                    Todavía no tocaba ninguna vez en este mes.
                  </span>
                ) : (
                  <>
                    <span className="cifra text-2xl font-semibold text-texto">
                      {data.cumplidos_hasta_hoy}/{data.esperados_hasta_hoy}
                    </span>
                    <span className="text-sm text-texto-2 ml-2">
                      registradas{data.pct !== null && ` · ${data.pct}%`}
                    </span>
                    {data.esperados > data.esperados_hasta_hoy && (
                      <span className="block text-xs text-texto-3 mt-1">
                        Faltan {data.esperados - data.esperados_hasta_hoy} veces
                        por venir este mes.
                      </span>
                    )}
                  </>
                )}
              </div>

              <div>
                <div className="grid grid-cols-7 gap-1 mb-1">
                  {DIAS_SEMANA.map(d => (
                    <span key={d} className="text-[10px] text-texto-3 text-center font-semibold">
                      {d}
                    </span>
                  ))}
                </div>
                <div className="grid grid-cols-7 gap-1">
                  {Array.from({ length: huecos }, (_, i) => <span key={`h${i}`} />)}
                  {data.dias.map(dia => {
                    const cfg = ESTADOS[dia.estado] ?? ESTADOS.no_aplica
                    const numero = comoFecha(dia.fecha).getDate()
                    const detalle = [
                      formatFecha(dia.fecha, { weekday: 'long', day: '2-digit', month: 'long' }),
                      cfg.label,
                      dia.usuario_nombre,
                      dia.comentario,
                    ].filter(Boolean).join(' · ')

                    return (
                      <button
                        key={dia.fecha}
                        onClick={() => alPulsar(dia)}
                        disabled={dia.estado === 'no_aplica'}
                        title={detalle}
                        aria-label={detalle}
                        className={`aspect-square rounded-md border text-xs font-semibold
                          flex items-center justify-center transition-colors duration-150
                          disabled:cursor-default ${cfg.fondo}`}
                      >
                        {numero}
                      </button>
                    )
                  })}
                </div>
              </div>

              {/* El color nunca va solo. */}
              <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-texto-3">
                {Object.entries(ESTADOS).map(([clave, cfg]) => (
                  <span key={clave} className="inline-flex items-center gap-1.5">
                    <i className={`inline-block w-2.5 h-2.5 rounded-sm border ${cfg.fondo}`}
                       aria-hidden="true" />
                    {cfg.label}
                  </span>
                ))}
              </div>

              <p className="text-[11px] text-texto-3">
                Se puede marcar un día pasado que se olvidó, y quitar el de un
                día marcado por error. El mes en curso se mide hasta ayer.
              </p>
            </>
          )}

          {/* Eliminar solo cuando no hay nada registrado: con registros el
              servidor responde 409 y pide desactivarla, porque son la
              constancia de que alguien hizo su trabajo. */}
          {onEliminar && data?.cumplidos === 0 && data?.esperados_hasta_hoy === 0 && (
            <button
              onClick={() => {
                if (!window.confirm(
                  `¿Eliminar «${actividad.titulo}»?\n\n` +
                  'Si ya tiene días registrados el portal no va a dejar: en ese ' +
                  'caso desactívala, que la saca de la lista sin borrar el histórico.'
                )) return
                onEliminar(actividad)
              }}
              className="text-xs font-semibold text-negativo hover:underline
                inline-flex items-center gap-1.5"
            >
              <IconoRepetir tam={13} /> Eliminar esta actividad
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
