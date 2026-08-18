import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import api from '../../core/api.js'
import {
  IconoCheck, IconoEstrella, IconoFelicitacion, IconoReloj,
} from '../../core/components/Iconos.jsx'

const TIPOS = [
  { value: 'peticion',     label: 'Petición'     },
  { value: 'queja',        label: 'Queja'        },
  { value: 'reclamo',      label: 'Reclamo'      },
  { value: 'sugerencia',   label: 'Sugerencia'   },
  { value: 'felicitacion', label: 'Felicitación' },
]

const CALIFICACIONES = [
  { value: 5, label: 'Excelente' },
  { value: 4, label: 'Buena'     },
  { value: 3, label: 'Regular'   },
  { value: 2, label: 'Mala'      },
  { value: 1, label: 'Muy mala'  },
]

const SOLUCIONADA = [
  { value: 'si',      label: 'Sí'           },
  { value: 'parcial', label: 'Parcialmente' },
  { value: 'no',      label: 'No'           },
]

const TIEMPO_RESPUESTA = [
  { value: 'excelente', label: 'Excelente' },
  { value: 'bueno',     label: 'Bueno'     },
  { value: 'regular',   label: 'Regular'   },
  { value: 'malo',      label: 'Malo'      },
]

const RECOMENDARIA = [
  { value: true,  label: 'Sí' },
  { value: false, label: 'No' },
]

// ── Bloque genérico de selección tipo botones ───────────────────────
function OpcionesPregunta({ numero, pregunta, opciones, valor, onChange }) {
  return (
    <div className="bg-white rounded-2xl shadow-sm border border-borde p-6">
      <p className="text-sm font-semibold text-acento-fuerte mb-4">
        {numero}. {pregunta}
      </p>
      <div className="flex flex-wrap gap-2">
        {opciones.map((op) => (
          <button
            key={String(op.value)}
            type="button"
            onClick={() => onChange(op.value)}
            className={`px-4 py-2.5 rounded-xl text-sm font-semibold border transition ${
              valor === op.value
                ? 'bg-acento-fuerte border-acento-fuerte text-white'
                : 'bg-white border-borde text-texto hover:border-acento'
            }`}
          >
            {op.label}
          </button>
        ))}
      </div>
    </div>
  )
}

export default function EncuestaPQRS() {
  const { codigo } = useParams()

  const [estado, setEstado]     = useState('cargando') // cargando | disponible | ya_respondida | no_disponible | error
  const [contexto, setContexto] = useState(null)
  const [enviando, setEnviando] = useState(false)
  const [error, setError]       = useState('')

  const [form, setForm] = useState({
    tipo_solicitud: '',
    calificacion: 0,
    solucionada: '',
    calificacion_tiempo_respuesta: '',
    recomendaria: null,
    comentario: '',
  })

  useEffect(() => {
    const consultar = async () => {
      try {
        const { data } = await api.get(`/public/encuesta/${codigo.trim().toUpperCase()}`)
        if (data.ya_respondida) setEstado('ya_respondida')
        else if (data.disponible) { setContexto(data); setEstado('disponible') }
        else setEstado('no_disponible')
      } catch {
        setEstado('error')
      }
    }
    consultar()
  }, [codigo])

  const actualizar = (campo, valor) => setForm((f) => ({ ...f, [campo]: valor }))

  const formCompleto =
    form.tipo_solicitud &&
    form.calificacion > 0 &&
    form.solucionada &&
    form.calificacion_tiempo_respuesta &&
    form.recomendaria !== null

  const enviar = async () => {
    if (!formCompleto) {
      setError('Por favor responde todas las preguntas obligatorias.')
      return
    }
    setEnviando(true)
    setError('')
    try {
      await api.post(`/public/encuesta/${codigo.trim().toUpperCase()}`, form)
      setEstado('enviada')
    } catch (err) {
      setError(err.response?.data?.detail || 'No pudimos registrar tu respuesta. Intenta de nuevo.')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="min-h-screen bg-fondo p-4 pb-10">
      <div className="w-full max-w-lg mx-auto">

        {/* Header */}
        <div className="text-center py-6">
          <div className="flex justify-center mb-3">
            <img src="/logo.png" alt="Protokimica" className="h-16 w-auto object-contain" />
          </div>
          <h1 className="text-xl font-bold text-acento-fuerte">Encuesta de satisfacción</h1>
          <p className="text-sm text-texto-2 mt-1">
            Gracias por permitirnos atender su solicitud. Su opinión nos ayuda a mejorar.
          </p>
        </div>

        {estado === 'cargando' && (
          <div className="bg-white rounded-2xl shadow-sm border border-borde p-6 text-center text-sm text-texto-2">
            Cargando...
          </div>
        )}

        {estado === 'error' && (
          <div className="bg-white rounded-2xl shadow-sm border border-borde p-6 text-center text-sm text-negativo">
            No encontramos ninguna solicitud con ese código.
          </div>
        )}

        {estado === 'no_disponible' && (
          <div className="bg-superficie rounded-2xl shadow-sm border border-borde p-6 text-center">
            <div className="flex justify-center mb-2 text-texto-3">
              <IconoReloj tam={22} />
            </div>
            <p className="text-sm text-texto">
              Esta solicitud aún no tiene una encuesta disponible.
            </p>
          </div>
        )}

        {estado === 'ya_respondida' && (
          <div className="bg-superficie rounded-2xl shadow-sm border border-borde p-6 text-center">
            <div className="flex justify-center mb-2">
              <span className="w-11 h-11 rounded-full bg-positivo-bg text-positivo
                flex items-center justify-center">
                <IconoCheck tam={22} />
              </span>
            </div>
            <p className="text-sm font-semibold text-texto mb-1">
              Ya registramos tu respuesta
            </p>
            <p className="text-xs text-texto-2">¡Gracias por tu tiempo!</p>
          </div>
        )}

        {estado === 'enviada' && (
          <div className="bg-superficie rounded-2xl shadow-sm border border-borde p-6 text-center">
            <div className="flex justify-center mb-2">
              <span className="w-11 h-11 rounded-full bg-positivo-bg text-positivo
                flex items-center justify-center">
                <IconoFelicitacion tam={22} />
              </span>
            </div>
            <p className="text-sm font-semibold text-texto mb-1">
              ¡Gracias por su tiempo!
            </p>
            <p className="text-xs text-texto-2">
              Sus respuestas nos ayudan a mejorar nuestro servicio.
            </p>
          </div>
        )}

        {estado === 'disponible' && (
          <div className="space-y-4">
            {contexto?.cliente_nombre && (
              <p className="text-center text-xs text-texto-2">
                Hola {contexto.cliente_nombre}, cuéntanos cómo te fue.
              </p>
            )}

            <OpcionesPregunta
              numero={1}
              pregunta="¿Qué tipo de solicitud presentó?"
              opciones={TIPOS}
              valor={form.tipo_solicitud}
              onChange={(v) => actualizar('tipo_solicitud', v)}
            />

            {/* Calificación con estrellas */}
            <div className="bg-white rounded-2xl shadow-sm border border-borde p-6">
              <p className="text-sm font-semibold text-acento-fuerte mb-4">
                2. ¿Cómo califica la atención recibida?
              </p>
              <div className="flex justify-between items-center">
                {CALIFICACIONES.map((c) => (
                  <button
                    key={c.value}
                    type="button"
                    onClick={() => actualizar('calificacion', c.value)}
                    className="flex flex-col items-center gap-1 group"
                  >
                    <IconoEstrella
                      tam={30}
                      relleno={c.value <= form.calificacion}
                      className={`transition-colors duration-150 ease-suave ${
                        c.value <= form.calificacion
                          ? 'text-ambar'
                          : 'text-borde-fuerte group-hover:text-ambar/60'
                      }`}
                    />
                    <span className="text-[10px] text-texto-2 text-center leading-tight">{c.label}</span>
                  </button>
                ))}
              </div>
            </div>

            <OpcionesPregunta
              numero={3}
              pregunta="¿Su solicitud fue solucionada de manera satisfactoria?"
              opciones={SOLUCIONADA}
              valor={form.solucionada}
              onChange={(v) => actualizar('solucionada', v)}
            />

            <OpcionesPregunta
              numero={4}
              pregunta="¿Cómo califica el tiempo de respuesta?"
              opciones={TIEMPO_RESPUESTA}
              valor={form.calificacion_tiempo_respuesta}
              onChange={(v) => actualizar('calificacion_tiempo_respuesta', v)}
            />

            <OpcionesPregunta
              numero={5}
              pregunta="¿Recomendaría a Protokimica por la atención recibida?"
              opciones={RECOMENDARIA}
              valor={form.recomendaria}
              onChange={(v) => actualizar('recomendaria', v)}
            />

            {/* Comentario opcional */}
            <div className="bg-white rounded-2xl shadow-sm border border-borde p-6">
              <p className="text-sm font-semibold text-acento-fuerte mb-3">
                6. ¿Tiene algún comentario o sugerencia para mejorar nuestro servicio? <span className="font-normal text-texto-2">(Opcional)</span>
              </p>
              <textarea
                value={form.comentario}
                onChange={(e) => actualizar('comentario', e.target.value)}
                rows={4}
                placeholder="Escribe aquí tu comentario..."
                className="w-full px-4 py-3 rounded-xl border border-borde text-sm text-texto placeholder-texto-3 focus:outline-none focus:ring-2 focus:ring-acento resize-none"
              />
            </div>

            {error && (
              <p className="text-sm text-negativo text-center">{error}</p>
            )}

            <button
              onClick={enviar}
              disabled={enviando}
              className="w-full bg-ambar hover:bg-ambar-claro text-acento-fuerte font-bold py-3.5 rounded-xl text-sm transition disabled:opacity-60"
            >
              {enviando ? 'Enviando...' : 'Enviar respuestas'}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
