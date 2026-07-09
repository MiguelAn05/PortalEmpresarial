import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useAuth } from '../../core/AuthContext.jsx'
import api from '../../core/api.js'

const TIPOS = {
  peticion:   { label: 'Petición',   color: 'bg-purple-100 text-purple-700' },
  queja:      { label: 'Queja',      color: 'bg-red-100 text-red-700'       },
  reclamo:    { label: 'Reclamo',    color: 'bg-orange-100 text-orange-700' },
  sugerencia: { label: 'Sugerencia', color: 'bg-blue-100 text-blue-700'   },
  felicitacion: {label: 'Felicitacion', color: 'bg-green-100 text-green-700' }
}

const ESTADOS = {
  recibido:   { label: 'Recibido',   color: 'bg-gray-100 text-gray-600'    },
  asignado:   { label: 'Asignado',   color: 'bg-blue-100 text-blue-700'    },
  en_proceso: { label: 'En proceso', color: 'bg-yellow-100 text-yellow-700' },
  resuelto:   { label: 'Resuelto',   color: 'bg-teal-100 text-teal-700'    },
  cerrado:    { label: 'Cerrado',    color: 'bg-green-100 text-green-700'  },
}

const PRIORIDADES = {
  baja:    { label: 'Baja',    color: 'text-green-600'  },
  media:   { label: 'Media',   color: 'text-yellow-600' },
  alta:    { label: 'Alta',    color: 'text-orange-600' },
  critica: { label: 'Crítica', color: 'text-red-600'    },
}

const EVENTOS = {
  cambio_estado:           { icon: '🔄', label: 'Cambio de estado'      },
  asignacion:              { icon: '👤', label: 'Asignación'            },
  asignacion_area:         { icon: '🏢', label: 'Área asignada'         },
  comentario:              { icon: '💬', label: 'Comentario'            },
  escalamiento:            { icon: '🚨', label: 'Escalamiento'          },
  autorizacion_solicitada: { icon: '🔐', label: 'Autorización solicitada'},
  autorizacion_respondida: { icon: '✅', label: 'Autorización respondida'},
}

const AREAS = ['Comercial','Logística','Calidad','HSEQ','TI','Facturación','Servicio al cliente']

function Badge({ map, value }) {
  const item = map[value] || { label: value, color: 'bg-gray-100 text-gray-600' }
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold ${item.color}`}>
      {item.label}
    </span>
  )
}

function formatFecha(fecha) {
  if (!fecha) return '—'
  return new Date(fecha).toLocaleString('es-CO', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

function SLALabel({ fechaLimite, cerrado }) {
  if (!fechaLimite || cerrado) return null
  const diff = new Date(fechaLimite) - new Date()
  const dias = Math.ceil(diff / (1000 * 60 * 60 * 24))
  if (dias < 0)   return <span className="text-sm font-semibold text-red-600">⚠️ Vencida hace {Math.abs(dias)} día(s)</span>
  if (dias === 0) return <span className="text-sm font-semibold text-red-500">⚠️ Vence hoy</span>
  if (dias <= 2)  return <span className="text-sm font-semibold text-orange-500">⏰ Vence en {dias} día(s)</span>
  return <span className="text-sm text-green-600">✅ Vence en {dias} días</span>
}

// ── Panel de autorizaciones ────────────────────────────────────────
function PanelAutorizaciones({ pqrsId, pqrsEstado, user, tipos, autorizaciones, hayPendiente, invalidar }) {
  const [tipoId, setTipoId]         = useState('')
  const [comentario, setComentario] = useState('')
  const [respuesta, setRespuesta]   = useState({ id: null, decision: '', comentario: '' })

  const mutSolicitar = useMutation({
    mutationFn: () => api.post(`/autorizaciones/pqrs/${pqrsId}/solicitar`, {
      tipo_id: parseInt(tipoId),
      comentario_solicitud: comentario,
    }),
    onSuccess: () => {
      invalidar()
      setTipoId(''); setComentario('')
    },
  })

  const mutResponder = useMutation({
    mutationFn: ({ autId, decision, comentario }) =>
      api.post(`/autorizaciones/pqrs/${pqrsId}/${autId}/responder`, {
        decision, comentario_respuesta: comentario,
      }),
    onSuccess: () => {
      invalidar()
      setRespuesta({ id: null, decision: '', comentario: '' })
    },
  })

  const puedeAutorizar = user?.rol === 'admin' || user?.rol === 'lider'
  const puedeSolicitar = user?.rol !== 'lectura'

  return (
    <div className="bg-white rounded-xl border border-[#D6E0F0] p-5">
      <h3 className="font-semibold text-[#0D2B5E] mb-4 text-sm flex items-center gap-2">
        🔐 Autorizaciones
        {hayPendiente && (
          <span className="bg-orange-100 text-orange-700 text-xs font-bold px-2 py-0.5 rounded-full">
            Pendiente — PQRS bloqueada
          </span>
        )}
      </h3>

      {/* Lista de autorizaciones existentes */}
      {autorizaciones.length > 0 && (
        <div className="space-y-3 mb-4">
          {autorizaciones.map((aut) => (
            <div key={aut.id} className={`rounded-xl p-4 border ${
              aut.estado === 'pendiente'  ? 'bg-orange-50 border-orange-200' :
              aut.estado === 'aprobada'   ? 'bg-green-50 border-green-200'  :
                                            'bg-red-50 border-red-200'
            }`}>
              <div className="flex items-start justify-between gap-2 mb-2">
                <div>
                  <div className="text-sm font-bold text-[#1A2B47]">{aut.tipo.nombre}</div>
                  <div className="text-xs text-[#6B7EA8]">Área: {aut.tipo.area_autorizadora}</div>
                </div>
                <span className={`text-xs font-bold px-2 py-0.5 rounded-full flex-shrink-0 ${
                  aut.estado === 'pendiente'  ? 'bg-orange-200 text-orange-800' :
                  aut.estado === 'aprobada'   ? 'bg-green-200 text-green-800'  :
                                                'bg-red-200 text-red-800'
                }`}>
                  {aut.estado === 'pendiente' ? '⏳ Pendiente' :
                   aut.estado === 'aprobada'  ? '✅ Aprobada'  : '❌ Rechazada'}
                </span>
              </div>

              {aut.comentario_solicitud && (
                <p className="text-xs text-[#6B7EA8] mb-2">
                  Solicitud: {aut.comentario_solicitud}
                </p>
              )}

              {aut.comentario_respuesta && (
                <p className="text-xs text-[#6B7EA8]">
                  Respuesta: {aut.comentario_respuesta}
                </p>
              )}

              {/* Botones de respuesta para líderes */}
              {aut.estado === 'pendiente' && puedeAutorizar && (
                <div className="mt-3 space-y-2">
                  <textarea
                    value={respuesta.id === aut.id ? respuesta.comentario : ''}
                    onChange={(e) => setRespuesta({ id: aut.id, decision: respuesta.decision, comentario: e.target.value })}
                    placeholder="Comentario de la decisión (opcional)..."
                    rows={2}
                    className="w-full px-3 py-2 rounded-lg border border-[#D6E0F0] text-xs text-[#1A2B47] placeholder-[#9BACC8] focus:outline-none focus:ring-2 focus:ring-[#1A4FA0] resize-none"
                  />
                  <div className="flex gap-2">
                    <button
                      onClick={() => mutResponder.mutate({
                        autId: aut.id,
                        decision: 'aprobada',
                        comentario: respuesta.id === aut.id ? respuesta.comentario : '',
                      })}
                      disabled={mutResponder.isPending}
                      className="flex-1 bg-green-600 hover:bg-green-700 text-white font-bold py-2 rounded-lg text-xs transition disabled:opacity-50"
                    >
                      ✅ Aprobar
                    </button>
                    <button
                      onClick={() => mutResponder.mutate({
                        autId: aut.id,
                        decision: 'rechazada',
                        comentario: respuesta.id === aut.id ? respuesta.comentario : '',
                      })}
                      disabled={mutResponder.isPending}
                      className="flex-1 bg-red-600 hover:bg-red-700 text-white font-bold py-2 rounded-lg text-xs transition disabled:opacity-50"
                    >
                      ❌ Rechazar
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Solicitar nueva autorización */}
      {puedeSolicitar && pqrsEstado !== 'cerrado' && !hayPendiente && (
        <div className="border-t border-[#D6E0F0] pt-4">
          <p className="text-xs font-semibold text-[#6B7EA8] uppercase tracking-wide mb-3">
            Solicitar autorización
          </p>
          <select
            value={tipoId}
            onChange={(e) => setTipoId(e.target.value)}
            className="w-full px-3 py-2.5 rounded-lg border border-[#D6E0F0] text-sm text-[#1A2B47] focus:outline-none focus:ring-2 focus:ring-[#1A4FA0] mb-3"
          >
            <option value="">Seleccionar tipo...</option>
            {tipos.map(t => (
              <option key={t.id} value={t.id}>
                {t.nombre} — {t.area_autorizadora}
              </option>
            ))}
          </select>
          <textarea
            value={comentario}
            onChange={(e) => setComentario(e.target.value)}
            placeholder="Motivo de la solicitud (opcional)..."
            rows={2}
            className="w-full px-3 py-2 rounded-lg border border-[#D6E0F0] text-sm text-[#1A2B47] placeholder-[#9BACC8] focus:outline-none focus:ring-2 focus:ring-[#1A4FA0] resize-none mb-3"
          />
          <button
            onClick={() => mutSolicitar.mutate()}
            disabled={!tipoId || mutSolicitar.isPending}
            className="w-full bg-[#0D2B5E] hover:bg-[#1A4FA0] text-white font-bold py-2.5 rounded-lg text-sm transition disabled:opacity-50"
          >
            {mutSolicitar.isPending ? 'Solicitando...' : '🔐 Solicitar autorización'}
          </button>
        </div>
      )}

      {tipos.length === 0 && (
        <p className="text-xs text-[#9BACC8] text-center py-2">
          No hay tipos de autorización configurados. Ve a Administración para crearlos.
        </p>
      )}
    </div>
  )
}

// ── Encuesta ───────────────────────────────────────────────────────
function EncuestaSection({ pqrsId, encuesta }) {
  const queryClient = useQueryClient()
  const [calificacion, setCalificacion] = useState(0)
  const [comentario, setComentario]     = useState('')
  const [enviada, setEnviada]           = useState(false)

  const mutation = useMutation({
    mutationFn: () => api.post(`/pqrs/${pqrsId}/encuesta`, { calificacion, comentario }),
    onSuccess: () => { setEnviada(true); queryClient.invalidateQueries({ queryKey: ['pqrs', pqrsId] }) },
  })

  if (encuesta?.calificacion) {
    return (
      <div className="bg-[#F0F4FA] rounded-xl p-5">
        <h3 className="font-semibold text-[#0D2B5E] mb-3 text-sm">⭐ Encuesta de satisfacción</h3>
        <div className="flex items-center gap-2 mb-2">
          {[1,2,3,4,5].map(n => (
            <span key={n} className={`text-2xl ${n <= encuesta.calificacion ? 'text-yellow-400' : 'text-gray-200'}`}>★</span>
          ))}
          <span className="text-sm font-semibold text-[#1A2B47] ml-2">{encuesta.calificacion}/5</span>
        </div>
        {encuesta.comentario && <p className="text-sm text-[#6B7EA8] italic">"{encuesta.comentario}"</p>}
      </div>
    )
  }

  if (enviada) {
    return (
      <div className="bg-green-50 border border-green-200 rounded-xl p-5 text-center">
        <div className="text-2xl mb-1">✅</div>
        <p className="text-sm font-semibold text-green-700">Encuesta registrada</p>
      </div>
    )
  }

  return (
    <div className="bg-[#FFF4E0] border border-[#F5A800]/30 rounded-xl p-5">
      <h3 className="font-semibold text-[#0D2B5E] mb-1 text-sm">⭐ Registrar satisfacción del cliente</h3>
      <p className="text-xs text-[#6B7EA8] mb-4">PQRS cerrada — registra la calificación del cliente.</p>
      <div className="flex gap-2 mb-4">
        {[1,2,3,4,5].map(n => (
          <button key={n} onClick={() => setCalificacion(n)}
            className={`text-3xl transition-transform hover:scale-110 ${n <= calificacion ? 'text-yellow-400' : 'text-gray-300'}`}>
            ★
          </button>
        ))}
      </div>
      <textarea
        value={comentario}
        onChange={(e) => setComentario(e.target.value)}
        placeholder="Comentario del cliente (opcional)..."
        rows={2}
        className="w-full px-3 py-2 rounded-lg border border-[#D6E0F0] text-sm text-[#1A2B47] placeholder-[#9BACC8] focus:outline-none focus:ring-2 focus:ring-[#F5A800] resize-none mb-3"
      />
      <button
        onClick={() => mutation.mutate()}
        disabled={calificacion === 0 || mutation.isPending}
        className="w-full bg-[#F5A800] hover:bg-[#FFC840] text-[#0D2B5E] font-bold py-2 rounded-lg text-sm transition disabled:opacity-50"
      >
        {mutation.isPending ? 'Guardando...' : 'Guardar calificación'}
      </button>
    </div>
  )
}

// ── Pantalla principal ─────────────────────────────────────────────
export default function PQRSDetail() {
  const { id }      = useParams()
  const navigate    = useNavigate()
  const queryClient = useQueryClient()
  const { user }    = useAuth()

  const [nuevoEstado, setNuevoEstado]   = useState('')
  const [comentario, setComentario]     = useState('')
  const [nuevaArea, setNuevaArea]       = useState('')

  const { data: pqrs, isLoading, isError } = useQuery({
    queryKey: ['pqrs', id],
    queryFn: async () => { const { data } = await api.get(`/pqrs/${id}`); return data },
  })

  const { data: tipos = [] } = useQuery({
    queryKey: ['tipos-autorizacion'],
    queryFn: async () => { const { data } = await api.get('/autorizaciones/tipos'); return data },
  })

  const { data: autorizaciones = [] } = useQuery({
    queryKey: ['autorizaciones', id],
    queryFn: async () => { const { data } = await api.get(`/autorizaciones/pqrs/${id}`); return data },
  })

  const hayPendiente = autorizaciones.some(a => a.estado === 'pendiente')

  // Única fuente de invalidación: la usan tanto el panel de autorizaciones
  // como el resto de la pantalla, así todo se refresca al instante.
  const invalidarAutorizaciones = () => {
    queryClient.invalidateQueries({ queryKey: ['autorizaciones', id] })
    queryClient.invalidateQueries({ queryKey: ['pqrs', id] })
    queryClient.invalidateQueries({ queryKey: ['pqrs'] })
  }

  const mutEstado = useMutation({
    mutationFn: () => api.patch(`/pqrs/${id}/estado`, { estado: nuevoEstado, comentario }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pqrs', id] })
      queryClient.invalidateQueries({ queryKey: ['pqrs'] })
      setNuevoEstado(''); setComentario('')
    },
  })

  const mutArea = useMutation({
    mutationFn: () => api.patch(`/pqrs/${id}/area`, { area: nuevaArea }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pqrs', id] })
      queryClient.invalidateQueries({ queryKey: ['pqrs'] })
      setNuevaArea('')
    },
  })

  if (isLoading) return (
    <div className="flex items-center justify-center py-20 text-[#6B7EA8] text-sm">Cargando...</div>
  )
  if (isError || !pqrs) return (
    <div className="flex flex-col items-center justify-center py-20 text-[#6B7EA8]">
      <span className="text-4xl mb-3">😕</span>
      <span className="text-sm">No se encontró la PQRS.</span>
      <button onClick={() => navigate('/pqrs')} className="mt-4 text-[#1A4FA0] text-sm underline">Volver</button>
    </div>
  )

  const puedeEditar = user?.rol !== 'lectura'

  return (
    <div className="max-w-5xl mx-auto">
      <button onClick={() => navigate('/pqrs')} className="flex items-center gap-2 text-sm text-[#6B7EA8] hover:text-[#0D2B5E] mb-5 transition">
        ← Volver a PQRS
      </button>

      {/* Header */}
      <div className="bg-gradient-to-r from-[#0D2B5E] to-[#1A4FA0] rounded-2xl p-6 mb-5 text-white">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="text-white/60 text-xs font-semibold uppercase tracking-wide mb-1">
              PQRS #{pqrs.id} · {pqrs.codigo_seguimiento || 'Sin código'}
              {pqrs.radicado_calidad && ` · Calidad: ${pqrs.radicado_calidad}`}
            </div>
            <h1 className="text-xl font-bold mb-1">{pqrs.empresa || pqrs.cliente_nombre}</h1>
            {pqrs.empresa && (
              <p className="text-white/70 text-sm mb-2">{pqrs.cliente_nombre}</p>
            )}
            <div className="flex gap-2 flex-wrap">
              <Badge map={TIPOS} value={pqrs.tipo} />
              <Badge map={ESTADOS} value={pqrs.estado} />
              <span className={`text-xs font-semibold ${PRIORIDADES[pqrs.prioridad]?.color}`}>
                ● {PRIORIDADES[pqrs.prioridad]?.label}
              </span>
              {hayPendiente && (
                <span className="bg-orange-400/30 text-orange-200 text-xs font-bold px-2 py-0.5 rounded-full">
                  🔐 Autorización pendiente
                </span>
              )}
              <span className="bg-white/10 text-white/70 text-xs px-2 py-0.5 rounded-full">
                {pqrs.origen_publico === 'publico' ? '🌐 Formulario web' : '🏢 Interno'}
              </span>
            </div>
          </div>
          <div className="text-right text-sm text-white/70 flex-shrink-0">
            <div>{formatFecha(pqrs.fecha_creacion)}</div>
            <div className="mt-1">
              <SLALabel fechaLimite={pqrs.fecha_limite_sla} cerrado={pqrs.estado === 'cerrado'} />
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-5">

        {/* Columna izquierda */}
        <div className="col-span-1 space-y-5">

          {/* Datos del cliente */}
          <div className="bg-white rounded-xl border border-[#D6E0F0] p-5">
            <h3 className="font-semibold text-[#0D2B5E] mb-4 text-sm">📋 Datos del cliente</h3>
            <div className="space-y-3">
              {[
                { label: 'Empresa',        value: pqrs.empresa          },
                { label: 'NIT / Cédula',   value: pqrs.nit_cedula       },
                { label: 'Contacto',       value: pqrs.cliente_nombre   },
                { label: 'Teléfono',       value: pqrs.cliente_telefono },
                { label: 'Email',          value: pqrs.cliente_email    },
                { label: 'Ciudad',         value: pqrs.ciudad           },
                { label: 'Departamento',   value: pqrs.departamento     },
              ].map(({ label, value }) => value && (
                <div key={label}>
                  <div className="text-xs text-[#6B7EA8] font-semibold uppercase tracking-wide">{label}</div>
                  <div className="text-sm text-[#1A2B47] font-medium mt-0.5">{value}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Datos del producto */}
          <div className="bg-white rounded-xl border border-[#D6E0F0] p-5">
            <h3 className="font-semibold text-[#0D2B5E] mb-4 text-sm">📦 Producto y factura</h3>
            <div className="space-y-3">
              {[
                { label: 'Producto',         value: pqrs.producto_nombre  },
                { label: 'Código',           value: pqrs.producto_codigo  },
                { label: 'Lote',             value: pqrs.lote             },
                { label: 'Factura',          value: pqrs.factura_numero   },
                { label: 'Cant. factura',    value: pqrs.cantidad_factura },
                { label: 'Cant. reclamo',    value: pqrs.cantidad_reclamo },
              ].map(({ label, value }) => value && (
                <div key={label}>
                  <div className="text-xs text-[#6B7EA8] font-semibold uppercase tracking-wide">{label}</div>
                  <div className="text-sm text-[#1A2B47] font-medium mt-0.5">{value}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Adjuntos */}
          {(pqrs.adjunto_producto || pqrs.adjunto_factura) && (
            <div className="bg-white rounded-xl border border-[#D6E0F0] p-5">
              <h3 className="font-semibold text-[#0D2B5E] mb-4 text-sm">📎 Evidencias adjuntas</h3>
              <div className="space-y-3">
                {pqrs.adjunto_producto && (
                  <div>
                    <div className="text-xs text-[#6B7EA8] font-semibold uppercase tracking-wide mb-2">
                      Foto del producto
                    </div>
                    <a href={`http://localhost:8000${pqrs.adjunto_producto}`} target="_blank" rel="noreferrer">
                      <img
                        src={`http://localhost:8000${pqrs.adjunto_producto}`}
                        alt="Producto"
                        className="w-full rounded-lg border border-[#D6E0F0] object-cover max-h-40 hover:opacity-90 transition cursor-pointer"
                        onError={(e) => { e.target.style.display='none' }}
                      />
                    </a>
                  </div>
                )}
                {pqrs.adjunto_factura && (
                  <div>
                    <div className="text-xs text-[#6B7EA8] font-semibold uppercase tracking-wide mb-2">
                      Factura
                    </div>
                    
                      <a
                      href={`http://localhost:8000${pqrs.adjunto_factura}`}
                      target="_blank"
                      rel="noreferrer"
                      className="flex items-center gap-2 p-3 bg-[#F0F4FA] rounded-lg hover:bg-[#D6E0F0] transition"
                    >
                      <span className="text-2xl">🧾</span>
                      <span className="text-sm font-medium text-[#1A4FA0] underline">Ver factura adjunta</span>
                    </a>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Asignar área */}
          {puedeEditar && pqrs.estado !== 'cerrado' && (user?.rol === 'admin' || user?.rol === 'lider') && (
            <div className="bg-white rounded-xl border border-[#D6E0F0] p-5">
              <h3 className="font-semibold text-[#0D2B5E] mb-3 text-sm">🏢 Asignar área</h3>
              <div className="text-xs text-[#6B7EA8] mb-2">
                Área actual: <strong>{pqrs.area_responsable || 'Sin asignar'}</strong>
              </div>
              {pqrs.radicado_calidad && (
                <div className="text-xs text-[#6B7EA8] mb-2">
                  Radicado de Calidad: <strong>{pqrs.radicado_calidad}</strong>
                </div>
              )}
              <select
                value={nuevaArea}
                onChange={(e) => setNuevaArea(e.target.value)}
                className="w-full px-3 py-2.5 rounded-lg border border-[#D6E0F0] text-sm text-[#1A2B47] focus:outline-none focus:ring-2 focus:ring-[#1A4FA0] mb-3"
              >
                <option value="">Seleccionar área...</option>
                {AREAS.map(a => <option key={a} value={a}>{a}</option>)}
              </select>
              <button
                onClick={() => mutArea.mutate()}
                disabled={!nuevaArea || mutArea.isPending}
                className="w-full bg-[#F5A800] hover:bg-[#FFC840] text-[#0D2B5E] font-bold py-2.5 rounded-lg text-sm transition disabled:opacity-50"
              >
                {mutArea.isPending ? 'Asignando...' : 'Asignar área'}
              </button>
            </div>
          )}

          {/* Cambiar estado */}
          {puedeEditar && pqrs.estado !== 'cerrado' && (
            <div className="bg-white rounded-xl border border-[#D6E0F0] p-5">
              <h3 className="font-semibold text-[#0D2B5E] mb-3 text-sm">🔄 Cambiar estado</h3>

              {hayPendiente ? (
                <div className="bg-orange-50 border border-orange-200 rounded-lg p-3 text-sm text-orange-700">
                  🔐 Hay una autorización pendiente. No puedes cambiar el estado hasta que sea aprobada o rechazada.
                </div>
              ) : (
                <>
                  <select
                    value={nuevoEstado}
                    onChange={(e) => setNuevoEstado(e.target.value)}
                    className="w-full px-3 py-2.5 rounded-lg border border-[#D6E0F0] text-sm text-[#1A2B47] focus:outline-none focus:ring-2 focus:ring-[#1A4FA0] mb-3"
                  >
                    <option value="">Seleccionar estado...</option>
                    {Object.entries(ESTADOS)
                      .filter(([key]) => key !== pqrs.estado)
                      .map(([key, { label }]) => (
                        <option key={key} value={key}>{label}</option>
                      ))
                    }
                  </select>
                  <textarea
                    value={comentario}
                    onChange={(e) => setComentario(e.target.value)}
                    placeholder="Comentario (opcional)..."
                    rows={3}
                    className="w-full px-3 py-2 rounded-lg border border-[#D6E0F0] text-sm text-[#1A2B47] placeholder-[#9BACC8] focus:outline-none focus:ring-2 focus:ring-[#1A4FA0] resize-none mb-3"
                  />
                  <button
                    onClick={() => mutEstado.mutate()}
                    disabled={!nuevoEstado || mutEstado.isPending}
                    className="w-full bg-[#0D2B5E] hover:bg-[#1A4FA0] text-white font-bold py-2.5 rounded-lg text-sm transition disabled:opacity-50"
                  >
                    {mutEstado.isPending ? 'Guardando...' : 'Guardar cambio'}
                  </button>
                </>
              )}
            </div>
          )}

          {/* Encuesta si está cerrada */}
          {pqrs.estado === 'cerrado' && (
            <EncuestaSection pqrsId={pqrs.id} encuesta={pqrs.encuesta} />
          )}
        </div>

        {/* Columna derecha */}
        <div className="col-span-2 space-y-5">

          {/* Descripción */}
          <div className="bg-white rounded-xl border border-[#D6E0F0] p-5">
            <h3 className="font-semibold text-[#0D2B5E] mb-3 text-sm">📝 Descripción del caso</h3>
            <p className="text-sm text-[#1A2B47] leading-relaxed whitespace-pre-wrap">{pqrs.descripcion}</p>
          </div>

          {/* Autorizaciones */}
          <PanelAutorizaciones
            pqrsId={pqrs.id}
            pqrsEstado={pqrs.estado}
            user={user}
            tipos={tipos}
            autorizaciones={autorizaciones}
            hayPendiente={hayPendiente}
            invalidar={invalidarAutorizaciones}
          />

          {/* Historial */}
          <div className="bg-white rounded-xl border border-[#D6E0F0] p-5">
            <h3 className="font-semibold text-[#0D2B5E] mb-4 text-sm">
              📡 Historial interno
              <span className="ml-2 bg-[#F0F4FA] text-[#6B7EA8] text-xs font-semibold px-2 py-0.5 rounded-full">
                {pqrs.seguimientos?.length || 0} eventos
              </span>
            </h3>

            {pqrs.seguimientos?.length === 0 ? (
              <p className="text-sm text-[#6B7EA8] text-center py-4">Sin eventos registrados.</p>
            ) : (
              <div className="relative">
                <div className="absolute left-4 top-0 bottom-0 w-px bg-[#D6E0F0]" />
                <div className="space-y-4">
                  {[...pqrs.seguimientos].reverse().map((seg) => {
                    const evento = EVENTOS[seg.tipo_evento] || { icon: '📌', label: seg.tipo_evento }
                    return (
                      <div key={seg.id} className="flex gap-4 relative">
                        <div className="w-8 h-8 rounded-full bg-white border-2 border-[#D6E0F0] flex items-center justify-center flex-shrink-0 z-10 text-sm">
                          {evento.icon}
                        </div>
                        <div className="flex-1 bg-[#F8FAFD] rounded-lg p-3 min-w-0">
                          <div className="flex items-center justify-between gap-2 mb-1">
                            <span className="text-xs font-semibold text-[#0D2B5E]">{evento.label}</span>
                            <span className="text-xs text-[#9BACC8] flex-shrink-0">{formatFecha(seg.fecha)}</span>
                          </div>
                          {seg.comentario && (
                            <p className="text-sm text-[#1A2B47]">{seg.comentario}</p>
                          )}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}