import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useAuth } from '../../core/AuthContext.jsx'
import api from '../../core/api.js'
import { AREAS } from '../../core/areas.js'

const AREA_SERVICIO_CLIENTE = 'Servicio al Cliente'

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

// Las áreas viven en un solo sitio: src/core/areas.js

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

// ── Encuesta (solo lectura para el agente) ──────────────────────────
// El agente no debe poder auto-registrar la satisfacción del cliente.
// Esto solo debe verse si el cliente ya la respondió (vía el link de
// encuesta que le llega por correo al cerrarse la PQRS).
// Colapsada por defecto para no saturar el detalle: muestra un resumen
// de una línea y se expande con clic para ver las 6 respuestas completas.
const SOLUCIONADA_LABEL = { si: 'Sí', parcial: 'Parcialmente', no: 'No' }
const TIEMPO_LABEL = { excelente: 'Excelente', bueno: 'Bueno', regular: 'Regular', malo: 'Malo' }
const TIPO_ENCUESTA_LABEL = {
  peticion: 'Petición', queja: 'Queja', reclamo: 'Reclamo',
  sugerencia: 'Sugerencia', felicitacion: 'Felicitación',
}

function EncuestaSection({ encuesta }) {
  const [abierta, setAbierta] = useState(false)

  if (!encuesta?.respondida_en) {
    // La PQRS está cerrada pero el cliente aún no ha respondido —
    // igual vale la pena que el agente lo sepa de un vistazo.
    if (encuesta) {
      return (
        <div className="bg-[#F0F4FA] rounded-xl p-5">
          <h3 className="font-semibold text-[#0D2B5E] mb-1 text-sm">⭐ Encuesta de satisfacción</h3>
          <p className="text-xs text-[#6B7EA8]">Enviada al cliente, esperando respuesta.</p>
        </div>
      )
    }
    return null
  }

  return (
    <div className="bg-[#F0F4FA] rounded-xl overflow-hidden">
      <button
        onClick={() => setAbierta(!abierta)}
        className="w-full flex items-center justify-between p-5 text-left"
      >
        <div>
          <h3 className="font-semibold text-[#0D2B5E] text-sm mb-1">⭐ Encuesta de satisfacción</h3>
          <div className="flex items-center gap-1">
            {[1,2,3,4,5].map(n => (
              <span key={n} className={`text-lg ${n <= encuesta.calificacion ? 'text-yellow-400' : 'text-gray-300'}`}>★</span>
            ))}
            <span className="text-xs text-[#6B7EA8] ml-1">
              {encuesta.calificacion}/5 · respondida el {formatFecha(encuesta.respondida_en)}
            </span>
          </div>
        </div>
        <span className={`text-[#6B7EA8] transition-transform ${abierta ? 'rotate-180' : ''}`}>▾</span>
      </button>

      {abierta && (
        <div className="px-5 pb-5 space-y-3 border-t border-[#D6E0F0] pt-4">
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div>
              <span className="text-[#6B7EA8] font-semibold uppercase tracking-wide block mb-0.5">Tipo de solicitud</span>
              <span className="text-[#1A2B47] font-medium">{TIPO_ENCUESTA_LABEL[encuesta.tipo_solicitud] || encuesta.tipo_solicitud}</span>
            </div>
            <div>
              <span className="text-[#6B7EA8] font-semibold uppercase tracking-wide block mb-0.5">¿Solucionada?</span>
              <span className="text-[#1A2B47] font-medium">{SOLUCIONADA_LABEL[encuesta.solucionada] || '—'}</span>
            </div>
            <div>
              <span className="text-[#6B7EA8] font-semibold uppercase tracking-wide block mb-0.5">Tiempo de respuesta</span>
              <span className="text-[#1A2B47] font-medium">{TIEMPO_LABEL[encuesta.calificacion_tiempo_respuesta] || '—'}</span>
            </div>
            <div>
              <span className="text-[#6B7EA8] font-semibold uppercase tracking-wide block mb-0.5">¿Recomendaría?</span>
              <span className="text-[#1A2B47] font-medium">{encuesta.recomendaria ? 'Sí' : 'No'}</span>
            </div>
          </div>
          {encuesta.comentario && (
            <div>
              <span className="text-[#6B7EA8] font-semibold uppercase tracking-wide block mb-1 text-xs">Comentario</span>
              <p className="text-sm text-[#1A2B47] italic">"{encuesta.comentario}"</p>
            </div>
          )}
        </div>
      )}
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
  const [evidencia, setEvidencia]       = useState(null)
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
    mutationFn: () => {
      const formData = new FormData()
      formData.append('estado', nuevoEstado)
      if (comentario) formData.append('comentario', comentario)
      if (evidencia) formData.append('evidencia', evidencia)
      return api.patch(`/pqrs/${id}/estado`, formData)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pqrs', id] })
      queryClient.invalidateQueries({ queryKey: ['pqrs'] })
      setNuevoEstado(''); setComentario(''); setEvidencia(null)
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

  const mutAreaCausante = useMutation({
    mutationFn: (area_causante) => api.patch(`/pqrs/${id}/area-causante`, { area_causante }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pqrs', id] })
      queryClient.invalidateQueries({ queryKey: ['pqrs'] })
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
  // Cerrar y reclasificar son de Servicio al cliente: el tipo que elige el
  // cliente al radicar suele estar mal, y esa clasificacion alimenta los
  // indicadores. Admin siempre puede, para destrabar.
  const esServicioCliente = user?.rol === 'admin' || user?.area === AREA_SERVICIO_CLIENTE

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
              {pqrs.codigo_seguimiento || `PQRS #${pqrs.id}`}
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
            {/* Área causante — distinta del área que gestiona el caso.
                Solo de uso interno, para poder sacar reportes de "qué área
                fue la responsable del problema" más adelante en Indicadores. */}
            {puedeEditar ? (
              <select
                value={pqrs.area_causante || ''}
                onChange={(e) => mutAreaCausante.mutate(e.target.value)}
                className="mt-2 bg-white/10 hover:bg-white/20 text-white text-xs rounded-lg px-2 py-1 border border-white/20 focus:outline-none cursor-pointer transition"
                title="Área causante del problema (uso interno)"
              >
                <option value="" className="text-[#1A2B47]">Área causante: sin definir</option>
                {AREAS.map(a => <option key={a} value={a} className="text-[#1A2B47]">Causante: {a}</option>)}
              </select>
            ) : (
              pqrs.area_causante && (
                <div className="mt-2 text-xs text-white/60">Causante: {pqrs.area_causante}</div>
              )
            )}
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
                { label: 'Presentación',     value: pqrs.presentacion
                                                ? `${pqrs.presentacion}${pqrs.cantidad_presentacion ? ' - ' + pqrs.cantidad_presentacion : ''}`
                                                : null },
                { label: 'Canal de atención', value: pqrs.canal_atencion  },
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
          {(pqrs.adjunto_producto || pqrs.adjunto_factura || pqrs.adjunto_video) && (
            <div className="bg-white rounded-xl border border-[#D6E0F0] p-5">
              <h3 className="font-semibold text-[#0D2B5E] mb-4 text-sm">📎 Evidencias adjuntas</h3>
              <div className="space-y-3">
                {pqrs.adjunto_producto && (
                  <div>
                    <div className="text-xs text-[#6B7EA8] font-semibold uppercase tracking-wide mb-2">
                      Foto del producto
                    </div>
                    <a href={`${pqrs.adjunto_producto}`} target="_blank" rel="noreferrer">
                      <img
                        src={`${pqrs.adjunto_producto}`}
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
                      href={`${pqrs.adjunto_factura}`}
                      target="_blank"
                      rel="noreferrer"
                      className="flex items-center gap-2 p-3 bg-[#F0F4FA] rounded-lg hover:bg-[#D6E0F0] transition"
                    >
                      <span className="text-2xl">🧾</span>
                      <span className="text-sm font-medium text-[#1A4FA0] underline">Ver factura adjunta</span>
                    </a>
                  </div>
                )}
                {pqrs.adjunto_video && (
                  <div>
                    <div className="text-xs text-[#6B7EA8] font-semibold uppercase tracking-wide mb-2">
                      Video de evidencia
                    </div>
                    <video
                      src={`${pqrs.adjunto_video}`}
                      controls
                      className="w-full rounded-lg border border-[#D6E0F0] max-h-52"
                    />
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

          {/* Reclasificar el tipo — solo Servicio al cliente y antes de cerrar */}
          {esServicioCliente && pqrs.estado !== 'cerrado' && (
            <ReclasificarTipo pqrs={pqrs} />
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
                      // 'cerrado' solo aparece si la persona puede cerrar:
                      // mejor no ofrecerlo que dar un 403 al guardar.
                      .filter(([key]) => key !== 'cerrado' || esServicioCliente)
                      .map(([key, { label }]) => (
                        <option key={key} value={key}>{label}</option>
                      ))
                    }
                  </select>
                  {!esServicioCliente && (
                    <p className="text-xs text-[#6B7EA8] bg-[#F7F9FC] rounded-lg px-3 py-2 mb-3 -mt-1">
                      Marcala como <strong>Resuelto</strong> cuando termines. El cierre lo hace
                      Servicio al Cliente, que revisa y clasifica antes de cerrar.
                    </p>
                  )}
                  <textarea
                    value={comentario}
                    onChange={(e) => setComentario(e.target.value)}
                    placeholder="Comentario (opcional)..."
                    rows={3}
                    className="w-full px-3 py-2 rounded-lg border border-[#D6E0F0] text-sm text-[#1A2B47] placeholder-[#9BACC8] focus:outline-none focus:ring-2 focus:ring-[#1A4FA0] resize-none mb-3"
                  />
                  <label className="block text-xs text-[#6B7EA8] font-semibold uppercase tracking-wide mb-1">
                    Evidencia (opcional)
                  </label>
                  <input
                    type="file"
                    accept=".jpg,.jpeg,.png,.webp,.pdf"
                    onChange={(e) => setEvidencia(e.target.files?.[0] || null)}
                    className="w-full text-xs text-[#6B7EA8] mb-3 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-[#EAF0FB] file:text-[#1A4FA0] hover:file:bg-[#D6E0F0]"
                  />
                  {evidencia && (
                    <p className="text-xs text-[#6B7EA8] mb-3 -mt-2">📎 {evidencia.name}</p>
                  )}
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

          {/* Encuesta si está cerrada y el cliente ya respondió */}
          {pqrs.estado === 'cerrado' && (
            <EncuestaSection encuesta={pqrs.encuesta} />
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
                          <div className="text-xs text-[#6B7EA8] mb-1">
                            {seg.usuario_nombre
                              ? `${seg.usuario_nombre}${seg.usuario_area ? ` · ${seg.usuario_area}` : ''}`
                              : 'Cliente (formulario público)'}
                          </div>
                          {seg.comentario && (
                            <p className="text-sm text-[#1A2B47]">{seg.comentario}</p>
                          )}
                          {seg.adjunto_evidencia && (
                            /\.(jpg|jpeg|png|webp)$/i.test(seg.adjunto_evidencia) ? (
                              <a href={seg.adjunto_evidencia} target="_blank" rel="noreferrer" className="inline-block mt-2">
                                <img
                                  src={seg.adjunto_evidencia}
                                  alt="Evidencia"
                                  className="max-h-32 rounded-lg border border-[#D6E0F0] hover:opacity-90 transition cursor-pointer"
                                  onError={(e) => { e.target.style.display='none' }}
                                />
                              </a>
                            ) : (
                              <a
                                href={seg.adjunto_evidencia}
                                target="_blank"
                                rel="noreferrer"
                                className="inline-block mt-2 text-xs text-[#1A4FA0] font-semibold underline"
                              >
                                📎 Ver evidencia adjunta
                              </a>
                            )
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

/**
 * Corrige el tipo de una PQRS antes de cerrarla.
 *
 * El cliente casi nunca acierta al radicar: pone "petición" lo que en
 * realidad es un reclamo. Y esa clasificación es la que alimenta los
 * indicadores y los reportes de Calidad, así que Servicio al cliente la
 * ajusta como paso previo al cierre.
 *
 * El motivo es obligatorio y queda en la trazabilidad de la PQRS.
 */
function ReclasificarTipo({ pqrs }) {
  const queryClient = useQueryClient()
  const [abierto, setAbierto] = useState(false)
  const [tipo, setTipo] = useState(pqrs.tipo)
  const [motivo, setMotivo] = useState('')
  const [error, setError] = useState('')

  const mut = useMutation({
    mutationFn: () => {
      const fd = new FormData()
      fd.append('tipo', tipo)
      fd.append('motivo', motivo)
      return api.patch(`/pqrs/${pqrs.id}/tipo`, fd)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pqrs', String(pqrs.id)] })
      queryClient.invalidateQueries({ queryKey: ['pqrs'] })
      setAbierto(false); setMotivo(''); setError('')
    },
    onError: (e) => setError(e.response?.data?.detail || 'No se pudo reclasificar.'),
  })

  const cambio = tipo !== pqrs.tipo
  // El SLA y la prioridad se recalculan solos en el servidor; se avisa aquí
  // para que nadie se sorprenda al ver la fecha límite moverse.
  const avisoSLA = cambio
    ? 'Se recalculará la fecha límite con el plazo del tipo nuevo, contando desde que se radicó. Puede quedar vencida.'
    : null

  if (!abierto) {
    return (
      <div className="bg-white rounded-xl border border-[#D6E0F0] p-5">
        <h3 className="font-semibold text-[#0D2B5E] mb-1 text-sm">🏷️ Clasificación</h3>
        <p className="text-xs text-[#6B7EA8] mb-3">
          Está registrada como <strong>{TIPOS[pqrs.tipo]?.label || pqrs.tipo}</strong>.
          Si no corresponde, corrígela antes de cerrar.
        </p>
        <button
          onClick={() => setAbierto(true)}
          className="w-full border border-[#D6E0F0] hover:bg-[#F7F9FC] text-[#0D2B5E] font-semibold py-2.5 rounded-lg text-sm transition"
        >
          Cambiar tipo de solicitud
        </button>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-xl border border-[#1A4FA0] p-5">
      <h3 className="font-semibold text-[#0D2B5E] mb-3 text-sm">🏷️ Reclasificar</h3>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg px-3 py-2 text-sm text-red-700 mb-3">
          {error}
        </div>
      )}

      <label className="block text-xs text-[#6B7EA8] font-semibold uppercase tracking-wide mb-1">
        ¿Qué fue en realidad?
      </label>
      <select
        value={tipo}
        onChange={(e) => setTipo(e.target.value)}
        className="w-full px-3 py-2.5 rounded-lg border border-[#D6E0F0] text-sm text-[#1A2B47] focus:outline-none focus:ring-2 focus:ring-[#1A4FA0] mb-3"
      >
        {Object.entries(TIPOS).map(([key, { label }]) => (
          <option key={key} value={key}>
            {label}{key === pqrs.tipo ? ' — actual' : ''}
          </option>
        ))}
      </select>

      <label className="block text-xs text-[#6B7EA8] font-semibold uppercase tracking-wide mb-1">
        ¿Por qué? <span className="text-red-500">·  obligatorio</span>
      </label>
      <textarea
        value={motivo}
        onChange={(e) => setMotivo(e.target.value)}
        placeholder="Ej: el cliente pide devolución de dinero, es un reclamo"
        rows={2}
        className="w-full px-3 py-2 rounded-lg border border-[#D6E0F0] text-sm text-[#1A2B47] placeholder-[#9BACC8] focus:outline-none focus:ring-2 focus:ring-[#1A4FA0] resize-none mb-2"
      />

      {avisoSLA && (
        <p className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mb-3">
          {avisoSLA}
        </p>
      )}
      <p className="text-xs text-[#9BACC8] mb-3">
        Queda registrado en el seguimiento con tu nombre y la fecha.
      </p>

      <div className="flex gap-2">
        <button
          onClick={() => { setAbierto(false); setTipo(pqrs.tipo); setMotivo(''); setError('') }}
          className="flex-1 border border-[#D6E0F0] hover:bg-gray-50 text-[#0D2B5E] font-semibold py-2.5 rounded-lg text-sm transition"
        >
          Cancelar
        </button>
        <button
          onClick={() => { setError(''); mut.mutate() }}
          disabled={!cambio || !motivo.trim() || mut.isPending}
          className="flex-1 bg-[#0D2B5E] hover:bg-[#1A4FA0] disabled:opacity-40 text-white font-bold py-2.5 rounded-lg text-sm transition"
        >
          {mut.isPending ? 'Guardando...' : 'Reclasificar'}
        </button>
      </div>
    </div>
  )
}
