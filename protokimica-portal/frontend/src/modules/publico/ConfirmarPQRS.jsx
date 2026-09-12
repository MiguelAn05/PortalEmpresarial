import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import api from '../../core/api.js'
import { LOGO, LOGO_ALT } from '../../core/marca.js'
import AvisoDatos from '../../core/components/AvisoDatos.jsx'
import {
  IconoAlDia, IconoAlerta, IconoClip, IconoReloj, IconoRechazo,
} from '../../core/components/Iconos.jsx'
import { mensajeDeError } from '../../core/errores.js'

function formatFecha(fecha) {
  if (!fecha) return null
  return new Date(fecha).toLocaleDateString('es-CO', {
    day: '2-digit', month: 'long', year: 'numeric',
  })
}

function esImagen(ruta) {
  return /\.(jpg|jpeg|png|webp)$/i.test(ruta)
}

/**
 * Lo que abre el cliente desde el correo de "resuelto": qué se le
 * solucionó, y dos botones — confirmar o decir que no quedó bien.
 *
 * Mismo patrón que `EncuestaPQRS.jsx`: el código de seguimiento ES la
 * autenticación, no hace falta cuenta en el portal — es SU caso.
 */
export default function ConfirmarPQRS() {
  const { codigo } = useParams()

  // cargando | disponible | ya_decidido | no_disponible | rechazando | listo | error
  const [estado, setEstado]     = useState('cargando')
  const [contexto, setContexto] = useState(null)
  const [comentario, setComentario] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [error, setError]       = useState('')
  const [mensajeFinal, setMensajeFinal] = useState('')

  useEffect(() => {
    const consultar = async () => {
      try {
        const { data } = await api.get(`/public/confirmar/${codigo.trim().toUpperCase()}`)
        if (!data.disponible) {
          setMensajeFinal(data.mensaje)
          setEstado(data.ya_decidido ? 'ya_decidido' : 'no_disponible')
        } else {
          setContexto(data)
          setEstado('disponible')
        }
      } catch {
        setEstado('error')
      }
    }
    consultar()
  }, [codigo])

  const enviar = async (conforme, comentarioEnvio) => {
    setEnviando(true)
    setError('')
    try {
      const { data } = await api.post(`/public/confirmar/${codigo.trim().toUpperCase()}`, {
        conforme, comentario: comentarioEnvio || null,
      })
      setMensajeFinal(data.mensaje)
      setEstado('listo')
    } catch (err) {
      setError(mensajeDeError(err, 'No pudimos registrar su respuesta. Intente de nuevo.'))
    } finally {
      setEnviando(false)
    }
  }

  const confirmarSolucion = () => enviar(true, null)

  const enviarRechazo = () => {
    if (!comentario.trim()) {
      setError('Cuéntenos qué falta antes de enviar.')
      return
    }
    enviar(false, comentario.trim())
  }

  return (
    <div className="min-h-screen bg-fondo p-4 pb-10">
      <div className="w-full max-w-lg mx-auto">

        <div className="text-center py-6">
          <div className="flex justify-center mb-3">
            <img src={LOGO} alt={LOGO_ALT} className="h-16 w-auto object-contain" />
          </div>
          <h1 className="text-xl font-bold text-acento-fuerte">Su solución</h1>
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

        {(estado === 'no_disponible' || estado === 'ya_decidido' || estado === 'listo') && (
          <div className="bg-superficie rounded-2xl shadow-sm border border-borde p-6 text-center">
            <div className="flex justify-center mb-2">
              <span className={`w-11 h-11 rounded-full flex items-center justify-center ${
                estado === 'listo' ? 'bg-positivo-bg text-positivo' : 'bg-superficie-2 text-texto-3'
              }`}>
                {estado === 'listo' ? <IconoAlDia tam={22} /> : <IconoReloj tam={22} />}
              </span>
            </div>
            <p className="text-sm font-semibold text-texto mb-1">{mensajeFinal}</p>
          </div>
        )}

        {estado === 'disponible' && (
          <div className="space-y-4">
            {contexto?.cliente_nombre && (
              <p className="text-center text-xs text-texto-2">
                Hola {contexto.cliente_nombre}, esto es lo que hicimos con su solicitud.
              </p>
            )}

            <div className="bg-white rounded-2xl shadow-sm border border-borde p-6">
              <p className="text-sm text-texto whitespace-pre-wrap">{contexto.solucion}</p>

              {contexto.adjuntos?.length > 0 && (
                <div className="mt-4 space-y-2">
                  {contexto.adjuntos.map((ruta) => (
                    esImagen(ruta) ? (
                      <a key={ruta} href={ruta} target="_blank" rel="noreferrer">
                        <img src={ruta} alt="Soporte de la solución"
                          className="rounded-xl border border-borde max-h-64 w-auto" />
                      </a>
                    ) : (
                      <a key={ruta} href={ruta} target="_blank" rel="noreferrer"
                        className="flex items-center gap-1.5 text-sm text-acento font-medium hover:underline">
                        <IconoClip tam={14} /> Ver documento
                      </a>
                    )
                  ))}
                </div>
              )}

              {contexto.plazo && (
                <p className="text-xs text-texto-3 mt-4">
                  Si no nos cuenta antes del {formatFecha(contexto.plazo)}, damos la
                  solicitud por resuelta y la cerramos.
                </p>
              )}
            </div>

            {error && (
              <p className="text-sm text-negativo text-center">{error}</p>
            )}

            <div className="grid grid-cols-2 gap-3">
              <button
                onClick={confirmarSolucion}
                disabled={enviando}
                className="flex flex-col items-center gap-1.5 bg-positivo-vivo text-white font-bold py-4 rounded-xl text-sm transition disabled:opacity-60"
              >
                <IconoAlDia tam={20} />
                Quedó resuelto
              </button>
              <button
                onClick={() => setEstado('rechazando')}
                disabled={enviando}
                className="flex flex-col items-center gap-1.5 bg-white border border-borde text-texto font-bold py-4 rounded-xl text-sm transition hover:border-negativo disabled:opacity-60"
              >
                <IconoRechazo tam={20} />
                Sigue el problema
              </button>
            </div>

            <AvisoDatos accion="responder" />
          </div>
        )}

        {estado === 'rechazando' && (
          <div className="space-y-4">
            <div className="bg-white rounded-2xl shadow-sm border border-borde p-6">
              <div className="flex items-start gap-2 mb-3">
                <IconoAlerta tam={16} className="text-alerta mt-0.5 flex-shrink-0" />
                <p className="text-sm font-semibold text-texto">
                  Cuéntenos qué falta
                </p>
              </div>
              <textarea
                value={comentario}
                onChange={(e) => { setComentario(e.target.value); setError('') }}
                rows={4}
                placeholder="Qué sigue mal, o qué esperaba que hiciéramos..."
                className="w-full px-4 py-3 rounded-xl border border-borde text-sm text-texto placeholder-texto-3 focus:outline-none focus:ring-2 focus:ring-acento resize-none"
              />
            </div>

            {error && (
              <p className="text-sm text-negativo text-center">{error}</p>
            )}

            <div className="flex gap-3">
              <button
                onClick={() => { setEstado('disponible'); setError('') }}
                disabled={enviando}
                className="flex-1 bg-white border border-borde text-texto-2 font-semibold py-3 rounded-xl text-sm transition"
              >
                Volver
              </button>
              <button
                onClick={enviarRechazo}
                disabled={enviando || !comentario.trim()}
                className="flex-1 bg-acento-fuerte hover:bg-acento text-white font-bold py-3 rounded-xl text-sm transition disabled:opacity-60"
              >
                {enviando ? 'Enviando…' : 'Enviar'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
