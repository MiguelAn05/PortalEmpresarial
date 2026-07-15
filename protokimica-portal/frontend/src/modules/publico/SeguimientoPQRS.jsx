import { useState } from 'react'
import api from '../../core/api.js'

const ESTADOS = {
  recibido:   { label: 'Recibido',   icon: '📥', color: 'text-gray-600',   bg: 'bg-gray-100'    },
  asignado:   { label: 'Asignado',   icon: '👤', color: 'text-blue-700',   bg: 'bg-blue-100'    },
  en_proceso: { label: 'En proceso', icon: '⚙️', color: 'text-yellow-700', bg: 'bg-yellow-100'  },
  resuelto:   { label: 'Resuelto',   icon: '✅', color: 'text-teal-700',   bg: 'bg-teal-100'    },
  cerrado:    { label: 'Cerrado',    icon: '🔒', color: 'text-green-700',  bg: 'bg-green-100'   },
}

const TIPOS = {
  peticion:   'Petición',
  queja:      'Queja',
  reclamo:    'Reclamo',
  sugerencia: 'Sugerencia',
  felicitacion: 'Felicitacion'
}

function formatFecha(fecha) {
  return new Date(fecha).toLocaleString('es-CO', {
    day: '2-digit', month: 'long', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

function SLAInfo({ fechaLimite, cerrado }) {
  if (!fechaLimite || cerrado) return null
  const diff = new Date(fechaLimite) - new Date()
  const dias = Math.ceil(diff / (1000 * 60 * 60 * 24))

  if (dias < 0) return (
    <div className="bg-red-50 border border-red-200 rounded-xl p-3 text-sm text-red-700 font-medium">
      ⚠️ El plazo de respuesta está vencido. Estamos trabajando en tu caso.
    </div>
  )
  if (dias <= 2) return (
    <div className="bg-orange-50 border border-orange-200 rounded-xl p-3 text-sm text-orange-700 font-medium">
      ⏰ Fecha límite de respuesta: {formatFecha(fechaLimite)}
    </div>
  )
  return (
    <div className="bg-green-50 border border-green-200 rounded-xl p-3 text-sm text-green-700">
      ✅ Fecha límite de respuesta: {formatFecha(fechaLimite)}
    </div>
  )
}

export default function SeguimientoPQRS() {
  const [codigo, setCodigo]   = useState('')
  const [pqrs, setPqrs]       = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState('')

  const consultar = async () => {
    if (!codigo.trim()) {
      setError('Ingresa tu código de seguimiento.')
      return
    }
    setLoading(true)
    setError('')
    setPqrs(null)
    try {
      const { data } = await api.get(`/public/pqrs/${codigo.trim().toUpperCase()}`)
      setPqrs(data)
    } catch (err) {
      setError(
        err.response?.status === 404
          ? 'No encontramos ninguna solicitud con ese código. Verifica que esté escrito correctamente.'
          : 'Error al consultar. Intenta de nuevo.'
      )
    } finally {
      setLoading(false)
    }
  }

  const estado = pqrs ? (ESTADOS[pqrs.estado] || ESTADOS.recibido) : null

  return (
    <div className="min-h-screen bg-[#F0F4FA] p-4 pb-10">
      <div className="w-full max-w-lg mx-auto">

        {/* Header */}
        <div className="text-center py-6">
         <div className="flex justify-center mb-3">
         <img
          src="/logo.png"
          alt="Protokimica"
          className="h-16 w-auto object-contain"
         />
       </div>
       <h1 className="text-xl font-bold text-[#0D2B5E]">
         Protokimica
       </h1>
        <p className="text-sm text-[#6B7EA8] mt-1">
         Consulta el estado de tu solicitud
        </p>
    </div>

        {/* Buscador */}
        <div className="bg-white rounded-2xl shadow-sm border border-[#D6E0F0] p-6 mb-5">
          <label className="block text-xs font-semibold text-[#6B7EA8] uppercase tracking-wide mb-2">
            Código de seguimiento
          </label>
          <div className="flex gap-2">
            <input
              value={codigo}
              onChange={(e) => { setCodigo(e.target.value); setError('') }}
              onKeyDown={(e) => e.key === 'Enter' && consultar()}
              placeholder="Ej: PK-2026-4821"
              className="flex-1 px-4 py-3 rounded-xl border border-[#D6E0F0] text-sm text-[#1A2B47] placeholder-[#9BACC8] focus:outline-none focus:ring-2 focus:ring-[#1A4FA0] transition font-mono uppercase"
            />
            <button
              onClick={consultar}
              disabled={loading}
              className="bg-[#F5A800] hover:bg-[#FFC840] text-[#0D2B5E] font-bold px-5 py-3 rounded-xl text-sm transition disabled:opacity-60 flex-shrink-0"
            >
              {loading ? '...' : 'Buscar'}
            </button>
          </div>
          {error && (
            <p className="text-sm text-red-600 mt-3">{error}</p>
          )}
        </div>

        {/* Resultado */}
        {pqrs && (
          <div className="space-y-4">

            {/* Estado actual */}
            <div className="bg-white rounded-2xl shadow-sm border border-[#D6E0F0] p-6">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <div className="text-xs text-[#6B7EA8] font-semibold uppercase tracking-wide">
                    Código
                  </div>
                  <div className="font-black text-[#0D2B5E] text-lg tracking-wider font-mono">
                    {pqrs.codigo_seguimiento}
                  </div>
                </div>
                <div className={`flex items-center gap-2 px-4 py-2 rounded-full ${estado.bg}`}>
                  <span>{estado.icon}</span>
                  <span className={`font-bold text-sm ${estado.color}`}>{estado.label}</span>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4 text-sm mb-4">
                <div>
                  <span className="text-xs text-[#6B7EA8] block font-semibold uppercase tracking-wide">Tipo</span>
                  <span className="font-medium text-[#1A2B47]">{TIPOS[pqrs.tipo] || pqrs.tipo}</span>
                </div>
                <div>
                  <span className="text-xs text-[#6B7EA8] block font-semibold uppercase tracking-wide">Área</span>
                  <span className="font-medium text-[#1A2B47]">{pqrs.area_responsable || 'Por asignar'}</span>
                </div>
                <div>
                  <span className="text-xs text-[#6B7EA8] block font-semibold uppercase tracking-wide">Radicada</span>
                  <span className="font-medium text-[#1A2B47]">{formatFecha(pqrs.fecha_creacion)}</span>
                </div>
                {pqrs.fecha_cierre && (
                  <div>
                    <span className="text-xs text-[#6B7EA8] block font-semibold uppercase tracking-wide">Cerrada</span>
                    <span className="font-medium text-[#1A2B47]">{formatFecha(pqrs.fecha_cierre)}</span>
                  </div>
                )}
              </div>

              <SLAInfo fechaLimite={pqrs.fecha_limite_sla} cerrado={pqrs.estado === 'cerrado'} />
            </div>

            {/* Timeline de eventos */}
            {pqrs.historial?.length > 0 && (
              <div className="bg-white rounded-2xl shadow-sm border border-[#D6E0F0] p-6">
                <h3 className="font-bold text-[#0D2B5E] mb-4 text-sm">
                  📡 Historial de tu solicitud
                </h3>
                <div className="relative">
                  <div className="absolute left-3.5 top-0 bottom-0 w-px bg-[#D6E0F0]" />
                  <div className="space-y-4">
                    {[...pqrs.historial].reverse().map((evento, idx) => (
                      <div key={idx} className="flex gap-4">
                        <div className="w-7 h-7 rounded-full bg-[#0D2B5E] border-2 border-white shadow flex items-center justify-center flex-shrink-0 z-10">
                          <div className="w-2 h-2 rounded-full bg-[#F5A800]" />
                        </div>
                        <div className="flex-1 pb-2">
                          <div className="text-sm font-semibold text-[#1A2B47]">
                            {evento.comentario || 'Actualización de estado'}
                          </div>
                          <div className="text-xs text-[#9BACC8] mt-0.5">
                            {formatFecha(evento.fecha)}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* CTA si está cerrada */}
            {pqrs.estado === 'cerrado' && (
              <a
                href={`/encuesta/${pqrs.codigo_seguimiento}`}
                className="block bg-[#FFF4E0] border border-[#F5A800]/30 rounded-2xl p-5 text-center hover:bg-[#FFF0D4] transition"
              >
                <div className="text-2xl mb-2">⭐</div>
                <p className="text-sm font-semibold text-[#0D2B5E] mb-1">
                  Tu solicitud fue cerrada
                </p>
                <p className="text-xs text-[#6B7EA8]">
                  Cuéntanos cómo te fue — toma menos de un minuto →
                </p>
              </a>
            )}

            {/* Radicar otra */}
            <div className="text-center">
              
                <a href="/formulario"
                className="text-sm text-[#1A4FA0] font-semibold hover:underline"
              >
                ¿Tienes otra solicitud? Radícala aquí →
              </a>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}