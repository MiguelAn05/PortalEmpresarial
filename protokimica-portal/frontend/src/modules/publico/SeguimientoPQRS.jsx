import { useState } from 'react'
import api from '../../core/api.js'
import {
  IconoAdmin, IconoAlDia, IconoAlerta, IconoCandado, IconoEstrella,
  IconoHistorial, IconoPQRS, IconoReloj, IconoUsuario,
} from '../../core/components/Iconos.jsx'

// El estado se dice con palabra, forma y color — en ese orden de importancia.
// Quien consulta esto es un cliente que quizá nunca vio el portal antes.
const ESTADOS = {
  recibido:   { label: 'Recibido',   Icono: IconoPQRS,     color: 'text-texto-2',  bg: 'bg-superficie-2' },
  asignado:   { label: 'Asignado',   Icono: IconoUsuario,  color: 'text-info',     bg: 'bg-info-bg'      },
  en_proceso: { label: 'En proceso', Icono: IconoAdmin,    color: 'text-alerta',   bg: 'bg-alerta-bg'    },
  resuelto:   { label: 'Resuelto',   Icono: IconoAlDia,    color: 'text-positivo', bg: 'bg-positivo-bg'  },
  cerrado:    { label: 'Cerrado',    Icono: IconoCandado,  color: 'text-positivo', bg: 'bg-positivo-bg'  },
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
    <div className="flex items-start gap-2.5 bg-negativo-bg border border-negativo/20
      rounded-xl p-3 text-sm text-negativo font-medium">
      <IconoAlerta tam={17} className="mt-0.5 flex-shrink-0" />
      <span>El plazo de respuesta está vencido. Estamos trabajando en tu caso.</span>
    </div>
  )
  if (dias <= 2) return (
    <div className="flex items-start gap-2.5 bg-alerta-bg border border-ambar/30
      rounded-xl p-3 text-sm text-alerta font-medium">
      <IconoReloj tam={17} className="mt-0.5 flex-shrink-0" />
      <span>Fecha límite de respuesta: {formatFecha(fechaLimite)}</span>
    </div>
  )
  return (
    <div className="flex items-start gap-2.5 bg-positivo-bg border border-positivo/20
      rounded-xl p-3 text-sm text-positivo">
      <IconoAlDia tam={17} className="mt-0.5 flex-shrink-0" />
      <span>Fecha límite de respuesta: {formatFecha(fechaLimite)}</span>
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
    <div className="min-h-screen bg-fondo p-4 pb-10">
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
       <h1 className="text-xl font-bold text-acento-fuerte">
         Protokimica
       </h1>
        <p className="text-sm text-texto-2 mt-1">
         Consulta el estado de tu solicitud
        </p>
    </div>

        {/* Buscador */}
        <div className="bg-white rounded-2xl shadow-sm border border-borde p-6 mb-5">
          <label className="block text-xs font-semibold text-texto-2 uppercase tracking-wide mb-2">
            Código de seguimiento
          </label>
          <div className="flex gap-2">
            <input
              value={codigo}
              onChange={(e) => { setCodigo(e.target.value); setError('') }}
              onKeyDown={(e) => e.key === 'Enter' && consultar()}
              placeholder="Ej: PK-2026-4821"
              className="flex-1 px-4 py-3 rounded-xl border border-borde text-sm text-texto placeholder-texto-3 focus:outline-none focus:ring-2 focus:ring-acento transition font-mono uppercase"
            />
            <button
              onClick={consultar}
              disabled={loading}
              className="bg-ambar hover:bg-ambar-claro text-acento-fuerte font-bold px-5 py-3 rounded-xl text-sm transition disabled:opacity-60 flex-shrink-0"
            >
              {loading ? '...' : 'Buscar'}
            </button>
          </div>
          {error && (
            <p className="text-sm text-negativo mt-3">{error}</p>
          )}
        </div>

        {/* Resultado */}
        {pqrs && (
          <div className="space-y-4">

            {/* Estado actual */}
            <div className="bg-white rounded-2xl shadow-sm border border-borde p-6">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <div className="text-xs text-texto-2 font-semibold uppercase tracking-wide">
                    Código
                  </div>
                  <div className="font-black text-acento-fuerte text-lg tracking-wider font-mono">
                    {pqrs.codigo_seguimiento}
                  </div>
                </div>
                <div className={`flex items-center gap-2 px-3.5 py-2 rounded-full
                  ${estado.bg} ${estado.color}`}>
                  <estado.Icono tam={16} />
                  <span className="font-semibold text-sm">{estado.label}</span>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4 text-sm mb-4">
                <div>
                  <span className="text-xs text-texto-2 block font-semibold uppercase tracking-wide">Tipo</span>
                  <span className="font-medium text-texto">{TIPOS[pqrs.tipo] || pqrs.tipo}</span>
                </div>
                <div>
                  <span className="text-xs text-texto-2 block font-semibold uppercase tracking-wide">Área</span>
                  <span className="font-medium text-texto">{pqrs.area_responsable || 'Por asignar'}</span>
                </div>
                <div>
                  <span className="text-xs text-texto-2 block font-semibold uppercase tracking-wide">Radicada</span>
                  <span className="font-medium text-texto">{formatFecha(pqrs.fecha_creacion)}</span>
                </div>
                {pqrs.fecha_cierre && (
                  <div>
                    <span className="text-xs text-texto-2 block font-semibold uppercase tracking-wide">Cerrada</span>
                    <span className="font-medium text-texto">{formatFecha(pqrs.fecha_cierre)}</span>
                  </div>
                )}
              </div>

              <SLAInfo fechaLimite={pqrs.fecha_limite_sla} cerrado={pqrs.estado === 'cerrado'} />
            </div>

            {/* Timeline de eventos */}
            {pqrs.historial?.length > 0 && (
              <div className="bg-white rounded-2xl shadow-sm border border-borde p-6">
                <h3 className="flex items-center gap-2 font-semibold text-texto mb-4 text-sm">
                  <IconoHistorial tam={17} className="text-texto-3" />
                  Historial de tu solicitud
                </h3>
                <div className="relative">
                  <div className="absolute left-3.5 top-0 bottom-0 w-px bg-borde" />
                  <div className="space-y-4">
                    {[...pqrs.historial].reverse().map((evento, idx) => (
                      <div key={idx} className="flex gap-4">
                        <div className="w-7 h-7 rounded-full bg-acento-fuerte border-2 border-white shadow flex items-center justify-center flex-shrink-0 z-10">
                          <div className="w-2 h-2 rounded-full bg-ambar" />
                        </div>
                        <div className="flex-1 pb-2">
                          {/* El texto lo redacta el servidor a partir del
                              estado. Aquí nunca llegan los comentarios
                              internos del área. */}
                          <div className="text-sm font-semibold text-texto">
                            {evento.movimiento}
                          </div>
                          <div className="text-xs text-texto-3 mt-0.5">
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
                className="block bg-alerta-bg border border-ambar/30 rounded-2xl p-5
                  text-center hover:border-ambar transition-colors duration-150 ease-suave"
              >
                <div className="flex justify-center mb-2 text-ambar-texto">
                  <IconoEstrella tam={22} />
                </div>
                <p className="text-sm font-semibold text-texto mb-1">
                  Tu solicitud fue cerrada
                </p>
                <p className="text-xs text-texto-2">
                  Cuéntanos cómo te fue — toma menos de un minuto
                </p>
              </a>
            )}

            {/* Radicar otra */}
            <div className="text-center">
              
                <a href="/formulario"
                className="text-sm text-acento font-semibold hover:underline"
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