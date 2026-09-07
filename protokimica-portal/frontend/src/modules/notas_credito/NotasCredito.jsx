/**
 * Solicitudes de nota crédito.
 *
 * Reemplaza el correo que hoy le manda el punto de venta a Contabilidad. Lo
 * que el correo no daba: un consecutivo, un estado, y el número de la nota
 * crédito que se emitió al final — que es lo que deja ver las que se
 * aprobaron y nunca se hicieron.
 *
 * Qué puede hacer cada quien lo decide el servidor y llega en `alcance`. La
 * pantalla solo esconde lo que no aplica.
 */
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../../core/api.js'
import { CANALES } from '../../core/canales.js'
import {
  IconoAlDia, IconoAlerta, IconoBuscar, IconoCerrar, IconoClip,
  IconoRecibo, IconoRechazo,
} from '../../core/components/Iconos.jsx'
import { mensajeDeError } from '../../core/errores.js'
import { useCierreSeguro } from '../../core/components/cierreSeguro.jsx'

// Atados a los mismos números del schema del backend (notas_credito/schemas.py).
// Si allá cambian, aquí también: el servidor manda, pero un input sin tope deja
// escribirlo todo para recibir un error al final.
const MAX_FACTURA = 60
const MAX_OBSERVACIONES = 2000
const MAX_NUMERO_NC = 60

const ESTADOS = {
  solicitada: { label: 'Esperando autorización', color: 'bg-alerta-bg text-alerta' },
  aprobada:   { label: 'Aprobada, falta emitir', color: 'bg-info-bg text-info' },
  rechazada:  { label: 'Rechazada',              color: 'bg-negativo-bg text-negativo' },
  aplicada:   { label: 'Nota crédito emitida',   color: 'bg-positivo-bg text-positivo' },
}

function Badge({ estado }) {
  const item = ESTADOS[estado] || { label: estado, color: 'bg-superficie-2 text-texto-2' }
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

function formatValor(valor) {
  if (valor === null || valor === undefined || valor === '') return null
  const numero = Number(valor)
  if (Number.isNaN(numero)) return null
  return numero.toLocaleString('es-CO', {
    style: 'currency', currency: 'COP', maximumFractionDigits: 0,
  })
}

// ── Formulario de solicitud ────────────────────────────────────────
function ModalSolicitar({ motivos, onClose, onCreada }) {
  const VACIO = {
    punto_venta: '',
    factura_afectada: '',
    factura_reemplaza: '',
    valor: '',
    motivo_id: '',
    observaciones: '',
  }
  const [form, setForm] = useState(VACIO)
  const [adjunto, setAdjunto] = useState(null)
  const [error, setError] = useState('')

  // Un clic fuera o un Escape no pueden borrar lo que se acabó de escribir.
  const hayAlgoEscrito = Object.values(form).some(Boolean) || Boolean(adjunto)
  const { intentarCerrar, dialogoDescarte } = useCierreSeguro({
    hayCambios: hayAlgoEscrito, onCerrar: onClose,
  })

  const mutacion = useMutation({
    mutationFn: () => {
      const datos = new FormData()
      Object.entries(form).forEach(([clave, valor]) => {
        if (valor !== '') datos.append(clave, valor)
      })
      if (adjunto) datos.append('adjunto', adjunto)
      return api.post('/notas-credito', datos)
    },
    onSuccess: () => { onCreada(); onClose() },
    onError: (err) => setError(mensajeDeError(err, 'No se pudo radicar la solicitud.')),
  })

  const cambiar = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value })
    setError('')
  }

  const listo = form.punto_venta && form.factura_afectada.trim() && form.observaciones.trim()

  const campo = "w-full px-3 py-2.5 rounded-lg border border-borde text-sm text-texto placeholder-texto-3 focus:outline-none focus:ring-2 focus:ring-acento"
  const etiqueta = "block text-xs text-texto-2 font-semibold uppercase tracking-wide mb-1"

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4"
         onClick={intentarCerrar}>
      <div className="bg-white rounded-2xl shadow-lg w-full max-w-2xl max-h-[90vh] flex flex-col"
           onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-6 py-4 border-b border-borde">
          <div>
            <h2 className="font-bold text-acento-fuerte text-lg">Solicitar nota crédito</h2>
            <p className="text-xs text-texto-2">La autoriza Contabilidad</p>
          </div>
          <button onClick={intentarCerrar} aria-label="Cerrar"
                  className="w-8 h-8 flex items-center justify-center rounded-lg text-texto-3 hover:bg-superficie-2 hover:text-texto transition-colors duration-150">
            <IconoCerrar tam={16} />
          </button>
        </div>

        <div className="px-6 py-5 overflow-y-auto space-y-4">
          <div className="grid sm:grid-cols-2 gap-4">
            <div>
              <label htmlFor="nc-punto" className={etiqueta}>Punto de venta *</label>
              <select id="nc-punto" name="punto_venta" value={form.punto_venta}
                      onChange={cambiar} className={campo}>
                <option value="">Seleccionar...</option>
                {CANALES.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div>
              <label htmlFor="nc-motivo" className={etiqueta}>Motivo</label>
              <select id="nc-motivo" name="motivo_id" value={form.motivo_id}
                      onChange={cambiar} className={campo}>
                <option value="">Sin especificar</option>
                {motivos.map(m => <option key={m.id} value={m.id}>{m.nombre}</option>)}
              </select>
            </div>
          </div>

          <div className="grid sm:grid-cols-2 gap-4">
            <div>
              <label htmlFor="nc-factura" className={etiqueta}>Factura afectada *</label>
              <input id="nc-factura" name="factura_afectada" value={form.factura_afectada}
                     onChange={cambiar} maxLength={MAX_FACTURA}
                     placeholder="POS#141824" className={campo} />
            </div>
            <div>
              <label htmlFor="nc-reemplaza" className={etiqueta}>Factura que la reemplaza</label>
              <input id="nc-reemplaza" name="factura_reemplaza" value={form.factura_reemplaza}
                     onChange={cambiar} maxLength={MAX_FACTURA}
                     placeholder="Si el cliente volvió a comprar" className={campo} />
            </div>
          </div>

          {/* Sin campo de producto a propósito: una factura trae varios
              renglones, así que uno solo obliga a elegir cuál —y el informe
              queda contando mal. Ver models/nota_credito.py. */}
          <div className="grid sm:grid-cols-2 gap-4">
            <div>
              <label htmlFor="nc-valor" className={etiqueta}>Valor de la factura</label>
              <input id="nc-valor" name="valor" value={form.valor} onChange={cambiar}
                     type="number" min="0" step="0.01" placeholder="0" className={`${campo} cifra`} />
            </div>
          </div>

          <div>
            <label htmlFor="nc-obs" className={etiqueta}>Qué pasó *</label>
            <textarea id="nc-obs" name="observaciones" value={form.observaciones}
                      onChange={cambiar} rows={4} maxLength={MAX_OBSERVACIONES}
                      placeholder="El cliente compró en la mañana y al recoger se dieron cuenta del error..."
                      className={`${campo} resize-none`} />
            <p className="text-xs text-texto-3 mt-1">
              Es lo que lee Contabilidad para decidir. Entre más claro, menos idas y vueltas.
            </p>
          </div>

          <div>
            <label htmlFor="nc-adjunto" className={etiqueta}>Soporte (opcional)</label>
            <input id="nc-adjunto" type="file" accept=".jpg,.jpeg,.png,.webp,.pdf"
                   onChange={(e) => setAdjunto(e.target.files?.[0] || null)}
                   className="w-full text-xs text-texto-2 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-acento-suave file:text-acento hover:file:bg-borde" />
            {adjunto && <p className="text-xs text-texto-2 mt-1">{adjunto.name}</p>}
          </div>

          {error && <p role="alert" className="text-sm text-negativo">{error}</p>}
        </div>

        <div className="px-6 py-4 border-t border-borde flex justify-end gap-3">
          <button onClick={intentarCerrar}
                  className="px-4 py-2 rounded-lg border border-borde text-sm font-semibold text-texto-2 hover:bg-fondo transition">
            Cancelar
          </button>
          <button onClick={() => mutacion.mutate()} disabled={!listo || mutacion.isPending}
                  className="px-4 py-2 rounded-lg bg-acento-fuerte hover:bg-acento text-white text-sm font-bold transition disabled:opacity-50">
            {mutacion.isPending ? 'Enviando...' : 'Enviar solicitud'}
          </button>
        </div>
      </div>
      {dialogoDescarte}
    </div>
  )
}

// ── Una solicitud, con lo que se puede hacer sobre ella ────────────
function Tarjeta({ solicitud, invalidar }) {
  const [abierta, setAbierta] = useState(false)
  const [comentario, setComentario] = useState('')
  const [numeroNc, setNumeroNc] = useState('')
  const [error, setError] = useState('')

  const { data: detalle } = useQuery({
    queryKey: ['nota-credito', solicitud.id],
    queryFn: async () => {
      const { data } = await api.get(`/notas-credito/${solicitud.id}`)
      return data
    },
    enabled: abierta,
  })

  const responder = useMutation({
    mutationFn: (decision) => api.post(`/notas-credito/${solicitud.id}/responder`,
                                       { decision, comentario }),
    onSuccess: () => { invalidar(); setComentario(''); setError('') },
    onError: (err) => setError(mensajeDeError(err, 'No se pudo registrar la decisión.')),
  })

  const aplicar = useMutation({
    mutationFn: () => api.post(`/notas-credito/${solicitud.id}/aplicar`,
                               { numero_nc: numeroNc, comentario }),
    onSuccess: () => { invalidar(); setNumeroNc(''); setComentario(''); setError('') },
    onError: (err) => setError(mensajeDeError(err, 'No se pudo registrar el número.')),
  })

  const alcance = detalle?.alcance
  const valor = formatValor(solicitud.valor)

  return (
    <div className="bg-white rounded-xl border border-borde shadow-sm overflow-hidden">
      <button onClick={() => setAbierta(!abierta)}
              className="w-full text-left px-5 py-4 hover:bg-fondo transition">
        <div className="flex items-start justify-between gap-3 flex-wrap">
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-sm font-bold text-acento-fuerte cifra">
                {solicitud.codigo || `#${solicitud.id}`}
              </span>
              <Badge estado={solicitud.estado} />
            </div>
            <div className="text-sm text-texto mt-1">
              Factura <strong className="cifra">{solicitud.factura_afectada}</strong>
              {' · '}{solicitud.punto_venta}
            </div>
            <div className="text-xs text-texto-2 mt-0.5">
              {solicitud.solicitante_nombre} · {formatFecha(solicitud.creado_en)}
              {solicitud.motivo_nombre && ` · ${solicitud.motivo_nombre}`}
            </div>
          </div>
          {valor && <div className="text-sm font-semibold text-texto cifra">{valor}</div>}
        </div>
      </button>

      {abierta && (
        <div className="px-5 pb-5 border-t border-borde pt-4 space-y-3">
          <p className="text-sm text-texto leading-relaxed whitespace-pre-wrap">
            {solicitud.observaciones}
          </p>

          <div className="grid sm:grid-cols-2 gap-3 text-sm">
            {solicitud.factura_reemplaza && (
              <div>
                <span className="text-xs text-texto-2 block">La reemplaza</span>
                <span className="font-medium cifra">{solicitud.factura_reemplaza}</span>
              </div>
            )}
            {solicitud.numero_nc && (
              <div>
                <span className="text-xs text-texto-2 block">Nota crédito emitida</span>
                <span className="font-medium cifra">{solicitud.numero_nc}</span>
              </div>
            )}
            {solicitud.autorizador_nombre && (
              <div>
                <span className="text-xs text-texto-2 block">Respondió</span>
                <span className="font-medium">
                  {solicitud.autorizador_nombre} · {formatFecha(solicitud.fecha_respuesta)}
                </span>
              </div>
            )}
          </div>

          {solicitud.adjunto && (
            <a href={solicitud.adjunto} target="_blank" rel="noreferrer"
               className="inline-flex items-center gap-1.5 text-sm text-acento font-medium hover:underline">
              <IconoClip tam={15} /> Ver soporte
            </a>
          )}

          {solicitud.comentario_respuesta && (
            <p className="text-sm text-texto-2 bg-superficie-2 rounded-lg px-3 py-2">
              {solicitud.comentario_respuesta}
            </p>
          )}

          {(alcance?.puede_autorizar || alcance?.puede_aplicar) && (
            <div className="border-t border-borde pt-3 space-y-2">
              {alcance.puede_aplicar && (
                <div>
                  <label htmlFor={`nc-num-${solicitud.id}`}
                         className="block text-xs text-texto-2 font-semibold uppercase tracking-wide mb-1">
                    Número de la nota crédito emitida
                  </label>
                  <input id={`nc-num-${solicitud.id}`} value={numeroNc}
                         onChange={(e) => setNumeroNc(e.target.value)}
                         maxLength={MAX_NUMERO_NC} placeholder="NC-9911"
                         className="w-full px-3 py-2 rounded-lg border border-borde text-sm text-texto cifra focus:outline-none focus:ring-2 focus:ring-acento" />
                </div>
              )}

              <textarea value={comentario} onChange={(e) => setComentario(e.target.value)}
                        rows={2} placeholder="Comentario (opcional)..."
                        className="w-full px-3 py-2 rounded-lg border border-borde text-sm text-texto placeholder-texto-3 focus:outline-none focus:ring-2 focus:ring-acento resize-none" />

              {error && <p role="alert" className="text-sm text-negativo">{error}</p>}

              {alcance.puede_autorizar && (
                <div className="flex gap-2">
                  <button onClick={() => responder.mutate('aprobada')} disabled={responder.isPending}
                          className="flex-1 inline-flex items-center justify-center gap-1.5 bg-positivo-vivo text-white font-bold py-2 rounded-lg text-sm transition disabled:opacity-50">
                    <IconoAlDia tam={15} /> Aprobar
                  </button>
                  <button onClick={() => responder.mutate('rechazada')} disabled={responder.isPending}
                          className="flex-1 inline-flex items-center justify-center gap-1.5 bg-negativo-vivo text-white font-bold py-2 rounded-lg text-sm transition disabled:opacity-50">
                    <IconoRechazo tam={15} /> Rechazar
                  </button>
                </div>
              )}

              {alcance.puede_aplicar && (
                <button onClick={() => aplicar.mutate()}
                        disabled={!numeroNc.trim() || aplicar.isPending}
                        className="w-full bg-acento-fuerte hover:bg-acento text-white font-bold py-2.5 rounded-lg text-sm transition disabled:opacity-50">
                  {aplicar.isPending ? 'Guardando...' : 'Registrar la nota crédito'}
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Pantalla ───────────────────────────────────────────────────────
export default function NotasCredito() {
  const queryClient = useQueryClient()
  const [modal, setModal] = useState(false)
  const [filtro, setFiltro] = useState('')

  const { data: solicitudes = [], isLoading } = useQuery({
    queryKey: ['notas-credito', filtro],
    queryFn: async () => {
      const { data } = await api.get('/notas-credito', {
        params: filtro ? { estado: filtro } : {},
      })
      return data
    },
  })

  const { data: motivos = [] } = useQuery({
    queryKey: ['nc-motivos'],
    queryFn: async () => {
      const { data } = await api.get('/notas-credito/motivos')
      return data
    },
  })

  const invalidar = () => {
    queryClient.invalidateQueries({ queryKey: ['notas-credito'] })
    queryClient.invalidateQueries({ queryKey: ['nota-credito'] })
  }

  // Cuántas esperan a alguien. Una cifra sin contexto obliga a preguntar
  // «¿eso es bueno?», así que va con su etiqueta.
  const esperando = solicitudes.filter(s => s.estado === 'solicitada').length
  const porEmitir = solicitudes.filter(s => s.estado === 'aprobada').length

  return (
    <div className="max-w-5xl mx-auto">
      <div className="flex items-center gap-2 mb-5">
        <Link to="/pqrs"
              className="px-3 py-1.5 rounded-lg text-sm font-semibold text-texto-2 hover:bg-superficie-2 transition">
          PQRS
        </Link>
        <span className="px-3 py-1.5 rounded-lg text-sm font-semibold bg-acento-suave text-acento">
          Notas crédito
        </span>
      </div>

      <div className="flex items-start justify-between gap-4 mb-5 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold text-acento-fuerte flex items-center gap-2">
            <IconoRecibo tam={22} /> Notas crédito
          </h1>
          <p className="text-sm text-texto-2 mt-1">
            Lo que antes se pedía por correo a Contabilidad
          </p>
        </div>
        <button onClick={() => setModal(true)}
                className="flex items-center gap-2 bg-ambar hover:bg-ambar-claro text-acento-fuerte font-bold px-4 py-2.5 rounded-lg text-sm transition">
          + Solicitar nota crédito
        </button>
      </div>

      <div className="grid sm:grid-cols-2 gap-3 mb-5">
        <div className="bg-white rounded-xl border border-borde p-4">
          <div className="text-xs text-texto-2 font-semibold uppercase tracking-wide">
            Esperando autorización
          </div>
          <div className={`text-2xl font-bold cifra mt-1 ${esperando ? 'text-alerta' : 'text-positivo'}`}>
            {esperando}
          </div>
          <div className="text-xs text-texto-2">
            {esperando === 0 ? 'Ninguna pendiente' : 'A la espera de Contabilidad'}
          </div>
        </div>
        <div className="bg-white rounded-xl border border-borde p-4">
          <div className="text-xs text-texto-2 font-semibold uppercase tracking-wide">
            Aprobadas sin emitir
          </div>
          <div className={`text-2xl font-bold cifra mt-1 ${porEmitir ? 'text-alerta' : 'text-positivo'}`}>
            {porEmitir}
          </div>
          <div className="text-xs text-texto-2">
            {porEmitir === 0 ? 'Todo al día' : 'Falta registrar su número'}
          </div>
        </div>
      </div>

      <div className="flex gap-2 mb-4 flex-wrap">
        {[['', 'Todas'], ...Object.entries(ESTADOS).map(([k, e]) => [k, e.label])].map(([clave, texto]) => (
          <button key={clave} onClick={() => setFiltro(clave)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                    filtro === clave
                      ? 'bg-acento-fuerte text-white'
                      : 'bg-white border border-borde text-texto-2 hover:bg-fondo'
                  }`}>
            {texto}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-20 text-texto-2 text-sm">Cargando...</div>
      ) : solicitudes.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-texto-2 bg-white rounded-xl border border-borde">
          <IconoBuscar tam={26} className="mb-3 text-texto-3" />
          <span className="text-sm">
            {filtro ? 'Ninguna en ese estado.' : 'Todavía no hay solicitudes de nota crédito.'}
          </span>
        </div>
      ) : (
        <div className="space-y-3">
          {solicitudes.map(s => (
            <Tarjeta key={s.id} solicitud={s} invalidar={invalidar} />
          ))}
        </div>
      )}

      {motivos.length === 0 && (
        <p className="text-xs text-texto-3 text-center mt-4 flex items-center justify-center gap-1.5">
          <IconoAlerta tam={14} />
          No hay motivos configurados. Se agregan desde Administración.
        </p>
      )}

      {modal && (
        <ModalSolicitar motivos={motivos} onClose={() => setModal(false)} onCreada={invalidar} />
      )}
    </div>
  )
}
