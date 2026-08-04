import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../../core/api.js'
import { AREAS } from '../../core/areas.js'

const TIPOS = {
  peticion: { label: 'Petición',   color: 'bg-purple-100 text-purple-700' },
  queja:    { label: 'Queja',      color: 'bg-red-100 text-red-700'       },
  reclamo:  { label: 'Reclamo',    color: 'bg-orange-100 text-orange-700' },
  sugerencia:{ label: 'Sugerencia',color: 'bg-blue-100 text-blue-700'   },
  felicitacion: {label: 'Felicitacion', color:'bg-green-100 text-green-700'}
}

const ESTADOS = {
  recibido:   { label: 'Recibido',    color: 'bg-gray-100 text-gray-600'   },
  asignado:   { label: 'Asignado',    color: 'bg-blue-100 text-blue-700'   },
  en_proceso: { label: 'En proceso',  color: 'bg-yellow-100 text-yellow-700'},
  resuelto:   { label: 'Resuelto',    color: 'bg-teal-100 text-teal-700'   },
  cerrado:    { label: 'Cerrado',     color: 'bg-green-100 text-green-700' },
}

const PRIORIDADES = {
  baja:    { label: 'Baja',    color: 'text-green-600'  },
  media:   { label: 'Media',   color: 'text-yellow-600' },
  alta:    { label: 'Alta',    color: 'text-orange-600' },
  critica: { label: 'Crítica', color: 'text-red-600'    },
}

// Mismo mapeo que PREFIJOS_POR_CANAL en el backend (service.py) — se usa
// para filtrar por punto de venta a partir del prefijo del radicado.
const PUNTOS_VENTA = [
  { prefijo: 'PVC',  label: 'Punto de venta Centro'     },
  { prefijo: 'PVB',  label: 'Punto de venta Belén'      },
  { prefijo: 'PVG',  label: 'Punto de venta Guayabal'   },
  { prefijo: 'PV65', label: 'Punto de venta La 65'      },
  { prefijo: 'PVCR', label: 'Punto de venta Cristo Rey' },
  { prefijo: 'PVI',  label: 'Punto de venta Itagüí'     },
  { prefijo: 'VI',   label: 'Venta institucional'       },
]

// AREAS_CAUSANTES y AREAS_PQRS eran la misma lista repetida: ahora las dos
// salen de src/core/areas.js
const AREAS_CAUSANTES = AREAS

// Compara el prefijo exacto del radicado (evita que "PVC" matchee "PVCR0010")
function coincidePuntoVenta(codigo, prefijo) {
  if (!codigo) return false
  return new RegExp(`^${prefijo}\\d+$`).test(codigo)
}

function Badge({ map, value }) {
  const item = map[value] || { label: value, color: 'bg-gray-100 text-gray-600' }
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold ${item.color}`}>
      {item.label}
    </span>
  )
}

function SLALabel({ fechaLimite }) {
  if (!fechaLimite) return null
  const diff = new Date(fechaLimite) - new Date()
  const dias = Math.ceil(diff / (1000 * 60 * 60 * 24))

  if (dias < 0)  return <span className="text-xs font-semibold text-red-600">Vencida</span>
  if (dias === 0) return <span className="text-xs font-semibold text-red-500">Vence hoy</span>
  if (dias <= 2)  return <span className="text-xs font-semibold text-orange-500">Vence en {dias}d</span>
  return <span className="text-xs text-[#6B7EA8]">Vence en {dias}d</span>
}

const CANALES_ATENCION = [
  
  'Venta institucional',
  'WhatsApp',
  'Punto de venta Centro',
  'Punto de venta Belén',
  'Punto de venta Guayabal',
  'Punto de venta La 65',
  'Punto de venta Cristo Rey',
  'Punto de venta Itagüí',
  'Línea telefónica',
]

const CANALES_ATENCION_FELICITACION = [
  'Venta institucional',
  'Llamada telefónica',
  'WhatsApp',
  'Punto de venta Centro',
  'Punto de venta Belén',
  'Punto de venta Guayabal',
  'Punto de venta La 65',
  'Punto de venta Cristo Rey',
  'Punto de venta Itagüí',
]

const DEPARTAMENTOS = [
  'Amazonas','Antioquia','Arauca','Atlántico','Bolívar','Boyacá','Caldas',
  'Caquetá','Casanare','Cauca','Cesar','Chocó','Córdoba','Cundinamarca',
  'Guainía','Guaviare','Huila','La Guajira','Magdalena','Meta','Nariño',
  'Norte de Santander','Putumayo','Quindío','Risaralda','San Andrés',
  'Santander','Sucre','Tolima','Valle del Cauca','Vaupés','Vichada',
]

const AREAS_PQRS = AREAS
const PRESENTACIONES = ['Unidad', 'Kilo', 'Gramo', 'Litro', 'Mililitro']

// ── Modal para crear PQRS ──────────────────────────────────────────
// Mismos campos que el formulario público (/formulario), para que una
// PQRS registrada por un agente interno guarde exactamente la misma
// información que una radicada por el cliente.
function ModalCrear({ onClose, onCreated }) {
  const FORM_VACIO = {
    tipo: 'queja',
    empresa: '',
    nit_cedula: '',
    cliente_nombre: '',
    cliente_email: '',
    cliente_telefono: '',
    ciudad: '',
    departamento: '',
    producto_codigo: '',
    producto_nombre: '',
    presentacion: '',
    cantidad_presentacion: '',
    canal_atencion: '',
    lote: '',
    factura_numero: '',
    cantidad_factura: '',
    area_responsable: '',
    descripcion: '',
  }
  const [form, setForm] = useState(FORM_VACIO)
  const [adjuntoProducto, setAdjuntoProducto] = useState(null)
  const [adjuntoFactura, setAdjuntoFactura]   = useState(null)
  const [adjuntoVideo, setAdjuntoVideo]       = useState(null)
  const [error, setError] = useState('')

  const mutation = useMutation({
    mutationFn: () => {
      const formData = new FormData()
      Object.entries(form).forEach(([key, value]) => formData.append(key, value ?? ''))
      if (adjuntoProducto) formData.append('adjunto_producto', adjuntoProducto)
      if (adjuntoFactura)  formData.append('adjunto_factura', adjuntoFactura)
      if (adjuntoVideo)    formData.append('adjunto_video', adjuntoVideo)
      return api.post('/pqrs', formData, { headers: { 'Content-Type': 'multipart/form-data' } })
    },
    onSuccess: () => { onCreated(); onClose() },
    onError: (err) => setError(err.response?.data?.detail || 'Error al crear la PQRS'),
  })

  const handleChange = (e) => { setForm({ ...form, [e.target.name]: e.target.value }); setError('') }

  // Una felicitación no necesita producto/factura/lote — solo el canal
  // por el que llegó y un comentario opcional. Una queja tampoco, porque
  // es sobre el servicio (ej: "me atendieron mal"), no sobre un producto.
  // Mismo criterio que el formulario público.
  const esFelicitacion = form.tipo === 'felicitacion'
  const esQueja = form.tipo === 'queja'
  const mostrarProducto = !esFelicitacion && !esQueja

  const inputCls = "w-full px-3 py-2.5 rounded-lg border border-[#D6E0F0] text-sm text-[#1A2B47] placeholder-[#9BACC8] focus:outline-none focus:ring-2 focus:ring-[#1A4FA0]"
  const labelCls = "block text-xs font-semibold text-[#6B7EA8] uppercase tracking-wide mb-1.5"

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-2xl">
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#D6E0F0]">
          <div>
            <h2 className="font-bold text-[#0D2B5E] text-lg">Registrar PQRS</h2>
            <p className="text-xs text-[#6B7EA8] mt-0.5">Mismos datos que el formulario público del cliente.</p>
          </div>
          <button onClick={onClose} className="text-[#6B7EA8] hover:text-[#0D2B5E] text-xl">✕</button>
        </div>

        <div className="p-6 space-y-5 max-h-[70vh] overflow-y-auto">

          {/* Tipo y área */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={labelCls}>Tipo *</label>
              <select name="tipo" value={form.tipo} onChange={handleChange} className={inputCls}>
                <option value="peticion">Petición</option>
                <option value="queja">Queja</option>
                <option value="reclamo">Reclamo</option>
                <option value="sugerencia">Sugerencia</option>
                <option value="felicitacion">Felicitación</option>
              </select>
            </div>
            <div>
              <label className={labelCls}>Área responsable</label>
              <select name="area_responsable" value={form.area_responsable} onChange={handleChange} className={inputCls}>
                <option value="">Sin asignar</option>
                {AREAS_PQRS.map(a => <option key={a} value={a}>{a}</option>)}
              </select>
            </div>
          </div>

          {/* Cliente */}
          <div>
            <p className="text-xs font-bold text-[#0D2B5E] uppercase tracking-wide mb-2">Datos del cliente</p>
            <div className="grid grid-cols-2 gap-4 mb-3">
              <div>
                <label className={labelCls}>Empresa</label>
                <input name="empresa" value={form.empresa} onChange={handleChange} placeholder="Ej: Industrias del Valle S.A.S" className={inputCls} />
              </div>
              <div>
                <label className={labelCls}>NIT / Cédula</label>
                <input name="nit_cedula" value={form.nit_cedula} onChange={handleChange} placeholder="Ej: 900123456-7" className={inputCls} />
              </div>
            </div>
            <div className="mb-3">
              <label className={labelCls}>Nombre del contacto *</label>
              <input name="cliente_nombre" value={form.cliente_nombre} onChange={handleChange} placeholder="Nombre de quien contacta" required className={inputCls} />
            </div>
            <div className="grid grid-cols-2 gap-4 mb-3">
              <div>
                <label className={labelCls}>Correo</label>
                <input name="cliente_email" type="email" value={form.cliente_email} onChange={handleChange} placeholder="cliente@empresa.com" className={inputCls} />
              </div>
              <div>
                <label className={labelCls}>Teléfono</label>
                <input name="cliente_telefono" value={form.cliente_telefono} onChange={handleChange} placeholder="3001234567" className={inputCls} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className={labelCls}>Ciudad</label>
                <input name="ciudad" value={form.ciudad} onChange={handleChange} placeholder="Ej: Medellín" className={inputCls} />
              </div>
              <div>
                <label className={labelCls}>Departamento</label>
                <select name="departamento" value={form.departamento} onChange={handleChange} className={inputCls}>
                  <option value="">Selecciona...</option>
                  {DEPARTAMENTOS.map(d => <option key={d} value={d}>{d}</option>)}
                </select>
              </div>
            </div>
          </div>

          {/* Canal de atención — siempre visible, cambia de opciones según el tipo */}
          <div>
            <label className={labelCls}>Canal de atención</label>
            <select name="canal_atencion" value={form.canal_atencion} onChange={handleChange} className={inputCls}>
              <option value="">Selecciona...</option>
              {(esFelicitacion ? CANALES_ATENCION_FELICITACION : CANALES_ATENCION).map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>

          {/* Producto — no aplica a felicitaciones ni quejas */}
          {mostrarProducto && (
            <div>
              <p className="text-xs font-bold text-[#0D2B5E] uppercase tracking-wide mb-2">Producto y factura</p>
              <div className="grid grid-cols-2 gap-4 mb-3">
                <div>
                  <label className={labelCls}>Código de producto</label>
                  <input name="producto_codigo" value={form.producto_codigo} onChange={handleChange} placeholder="Ej: PK-001" className={inputCls} />
                </div>
                <div>
                  <label className={labelCls}>Nombre del producto</label>
                  <input name="producto_nombre" value={form.producto_nombre} onChange={handleChange} placeholder="Ej: Hipoclorito de Sodio 13%" className={inputCls} />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4 mb-3">
                <div>
                  <label className={labelCls}>Presentación</label>
                  <div className="flex gap-2">
                    <select name="presentacion" value={form.presentacion} onChange={handleChange} className={inputCls}>
                      <option value="">Selecciona...</option>
                      {PRESENTACIONES.map(p => <option key={p} value={p}>{p}</option>)}
                    </select>
                    <input
                      type="text"
                      name="cantidad_presentacion"
                      value={form.cantidad_presentacion}
                      onChange={handleChange}
                      disabled={!form.presentacion}
                      placeholder="Cant."
                      className={`${inputCls} w-20 disabled:bg-[#F5F7FB] disabled:cursor-not-allowed`}
                    />
                  </div>
                </div>
                <div>
                  <label className={labelCls}>Lote</label>
                  <input name="lote" value={form.lote} onChange={handleChange} placeholder="Ej: L240815" className={inputCls} />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4 mb-3">
                <div>
                  <label className={labelCls}>N° Factura</label>
                  <input name="factura_numero" value={form.factura_numero} onChange={handleChange} placeholder="Ej: FV-2026-1234" className={inputCls} />
                </div>
                <div>
                  <label className={labelCls}>Cant. en factura</label>
                  <input name="cantidad_factura" value={form.cantidad_factura} onChange={handleChange} placeholder="Ej: 10" className={inputCls} />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className={labelCls}>Foto del producto</label>
                  <input type="file" accept="image/*,.pdf" onChange={(e) => setAdjuntoProducto(e.target.files[0] || null)} className="text-xs text-[#6B7EA8]" />
                </div>
                <div>
                  <label className={labelCls}>Foto de la factura</label>
                  <input type="file" accept="image/*,.pdf" onChange={(e) => setAdjuntoFactura(e.target.files[0] || null)} className="text-xs text-[#6B7EA8]" />
                </div>
              </div>
            </div>
          )}

          {/* Video de evidencia — opcional, aplica a todo menos felicitaciones */}
          {!esFelicitacion && (
            <div>
              <label className={labelCls}>Video de evidencia (opcional)</label>
              <input
                type="file"
                accept="video/mp4,video/quicktime,video/webm"
                onChange={(e) => setAdjuntoVideo(e.target.files[0] || null)}
                className="text-xs text-[#6B7EA8]"
              />
              <p className="text-xs text-[#9BACC8] mt-1">MP4, MOV o WEBM — máx. 20MB (~20-30 seg)</p>
            </div>
          )}

          {/* Descripción / comentario */}
          <div>
            <label className={labelCls}>
              {esFelicitacion ? 'Comentario (opcional)' : 'Descripción *'}
            </label>
            <textarea
              name="descripcion"
              value={form.descripcion}
              onChange={handleChange}
              placeholder={esFelicitacion ? 'Cuéntanos qué le gustó al cliente...' : 'Describe detalladamente la situación...'}
              rows={4}
              required={!esFelicitacion}
              className={`${inputCls} resize-none`}
            />
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}
        </div>

        <div className="px-6 py-4 border-t border-[#D6E0F0] flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg border border-[#D6E0F0] text-sm font-semibold text-[#6B7EA8] hover:bg-[#F0F4FA] transition"
          >
            Cancelar
          </button>
          <button
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending || !form.cliente_nombre || (!esFelicitacion && !form.descripcion)}
            className="px-4 py-2 rounded-lg bg-[#F5A800] hover:bg-[#FFC840] text-[#0D2B5E] text-sm font-bold transition disabled:opacity-50"
          >
            {mutation.isPending ? 'Creando...' : 'Crear PQRS'}
          </button>
        </div>
      </div>
    </div>
  )
}


// ── Modal detalle / cambiar estado ─────────────────────────────────
function ModalDetalle({ pqrs, onClose, onUpdated }) {
  const [nuevoEstado, setNuevoEstado] = useState(pqrs.estado)
  const [comentario, setComentario] = useState('')

  const mutation = useMutation({
    mutationFn: () => api.patch(`/pqrs/${pqrs.id}/estado`, {
      estado: nuevoEstado,
      comentario,
    }),
    onSuccess: () => { onUpdated(); onClose() },
  })

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg">
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#D6E0F0]">
          <div>
            <h2 className="font-bold text-[#0D2B5E] text-lg">
              {pqrs.codigo_seguimiento || `PQRS #${pqrs.id}`}
            </h2>
            <p className="text-xs text-[#6B7EA8]">{pqrs.cliente_nombre}</p>
          </div>
          <button onClick={onClose} className="text-[#6B7EA8] hover:text-[#0D2B5E] text-xl">✕</button>
        </div>

        <div className="p-6 space-y-4">
          <div className="flex gap-2 flex-wrap">
            <Badge map={TIPOS} value={pqrs.tipo} />
            <Badge map={ESTADOS} value={pqrs.estado} />
            <span className={`text-xs font-semibold ${PRIORIDADES[pqrs.prioridad]?.color}`}>
              ● {PRIORIDADES[pqrs.prioridad]?.label}
            </span>
          </div>

          <div className="bg-[#F0F4FA] rounded-lg p-4 text-sm text-[#1A2B47]">
            {pqrs.descripcion}
          </div>

          <div className="grid grid-cols-2 gap-3 text-sm">
            <div>
              <span className="text-xs text-[#6B7EA8] block">Área</span>
              <span className="font-medium">{pqrs.area_responsable || '—'}</span>
            </div>
            <div>
              <span className="text-xs text-[#6B7EA8] block">SLA</span>
              <SLALabel fechaLimite={pqrs.fecha_limite_sla} />
            </div>
            {pqrs.cliente_email && (
              <div>
                <span className="text-xs text-[#6B7EA8] block">Email cliente</span>
                <span className="font-medium">{pqrs.cliente_email}</span>
              </div>
            )}
            {pqrs.cliente_telefono && (
              <div>
                <span className="text-xs text-[#6B7EA8] block">Teléfono</span>
                <span className="font-medium">{pqrs.cliente_telefono}</span>
              </div>
            )}
          </div>

          <div className="border-t border-[#D6E0F0] pt-4">
            <label className="block text-xs font-semibold text-[#6B7EA8] uppercase tracking-wide mb-2">
              Cambiar estado
            </label>
            <select
              value={nuevoEstado}
              onChange={(e) => setNuevoEstado(e.target.value)}
              className="w-full px-3 py-2.5 rounded-lg border border-[#D6E0F0] text-sm text-[#1A2B47] focus:outline-none focus:ring-2 focus:ring-[#1A4FA0] mb-3"
            >
              {Object.entries(ESTADOS).map(([key, { label }]) => (
                <option key={key} value={key}>{label}</option>
              ))}
            </select>
            <textarea
              value={comentario}
              onChange={(e) => setComentario(e.target.value)}
              placeholder="Comentario del cambio de estado (opcional)..."
              rows={3}
              className="w-full px-3 py-2.5 rounded-lg border border-[#D6E0F0] text-sm text-[#1A2B47] placeholder-[#9BACC8] focus:outline-none focus:ring-2 focus:ring-[#1A4FA0] resize-none"
            />
          </div>
        </div>

        <div className="px-6 py-4 border-t border-[#D6E0F0] flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg border border-[#D6E0F0] text-sm font-semibold text-[#6B7EA8] hover:bg-[#F0F4FA] transition"
          >
            Cerrar
          </button>
          <button
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending || nuevoEstado === pqrs.estado}
            className="px-4 py-2 rounded-lg bg-[#0D2B5E] hover:bg-[#1A4FA0] text-white text-sm font-bold transition disabled:opacity-50"
          >
            {mutation.isPending ? 'Guardando...' : 'Guardar cambio'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Pantalla principal ─────────────────────────────────────────────
export default function PQRSList() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [filtroEstado, setFiltroEstado] = useState('')
  const [filtroTipo, setFiltroTipo]     = useState('')
  const [busqueda, setBusqueda]         = useState('')
  const [modalCrear, setModalCrear]     = useState(false)
  const [seleccionada, setSeleccionada] = useState(null)

  // Filtros adicionales (client-side, sobre lo ya traído del servidor)
  const [panelFiltrosAbierto, setPanelFiltrosAbierto] = useState(false)
  const [filtroFechaDesde, setFiltroFechaDesde]       = useState('')
  const [filtroFechaHasta, setFiltroFechaHasta]       = useState('')
  const [filtroPuntoVenta, setFiltroPuntoVenta]       = useState('')
  const [filtroAreaCausante, setFiltroAreaCausante]   = useState('')

  const { data: pqrsList = [], isLoading, isError } = useQuery({
    queryKey: ['pqrs', filtroEstado, filtroTipo],
    queryFn: async () => {
      const params = {}
      if (filtroEstado) params.estado = filtroEstado
      if (filtroTipo)   params.tipo   = filtroTipo
      const { data } = await api.get('/pqrs', { params })
      return data
    },
  })

  const refetch = () => queryClient.invalidateQueries({ queryKey: ['pqrs'] })

  // Búsqueda + filtros adicionales, todo en client-side sobre lo ya traído
  const pqrsFiltrada = pqrsList.filter((p) => {
    const q = busqueda.trim().toLowerCase()
    if (q) {
      const coincideBusqueda = [p.codigo_seguimiento, p.radicado_calidad, p.cliente_nombre, p.empresa, p.nit_cedula]
        .filter(Boolean)
        .some(campo => campo.toLowerCase().includes(q))
      if (!coincideBusqueda) return false
    }

    if (filtroFechaDesde && new Date(p.fecha_creacion) < new Date(filtroFechaDesde)) return false
    if (filtroFechaHasta) {
      const hasta = new Date(filtroFechaHasta)
      hasta.setHours(23, 59, 59, 999) // incluir todo el día seleccionado
      if (new Date(p.fecha_creacion) > hasta) return false
    }

    if (filtroPuntoVenta && !coincidePuntoVenta(p.codigo_seguimiento, filtroPuntoVenta)) return false

    if (filtroAreaCausante && p.area_causante !== filtroAreaCausante) return false

    return true
  })

  // Contadores para las tarjetas de resumen
  const total    = pqrsList.length
  const abiertas = pqrsList.filter(p => p.estado !== 'cerrado').length
  const criticas = pqrsList.filter(p => p.prioridad === 'alta' || p.prioridad === 'critica').length
  const vencidas = pqrsList.filter(p => p.fecha_limite_sla && new Date(p.fecha_limite_sla) < new Date() && p.estado !== 'cerrado').length

  return (
    <div>
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-[#0D2B5E]">
            PQRS — Peticiones, Quejas, Reclamos, Sugerencias y Felicitaciones
          </h1>
          <p className="text-sm text-[#6B7EA8] mt-1">
            Gestión de solicitudes 
          </p>
        </div>
        <button
          onClick={() => setModalCrear(true)}
          className="flex items-center gap-2 bg-[#F5A800] hover:bg-[#FFC840] text-[#0D2B5E] font-bold px-4 py-2.5 rounded-lg text-sm transition"
        >
          + Registrar PQRS
        </button>
      </div>

      {/* Tarjetas de resumen */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        {[
          { label: 'Total',         value: total,    color: 'border-t-[#0D2B5E]' },
          { label: 'Abiertas',      value: abiertas, color: 'border-t-[#1A4FA0]' },
          { label: 'Alta prioridad',value: criticas, color: 'border-t-[#F5A800]' },
          { label: 'Vencidas SLA',  value: vencidas, color: 'border-t-[#D93B3B]' },
        ].map(({ label, value, color }) => (
          <div key={label} className={`bg-white rounded-xl border border-[#D6E0F0] border-t-4 ${color} p-4`}>
            <div className="text-xs font-semibold text-[#6B7EA8] uppercase tracking-wide">{label}</div>
            <div className="text-3xl font-bold text-[#0D2B5E] mt-1">{value}</div>
          </div>
        ))}
      </div>

      {/* Buscador por radicado */}
      <div className="relative mb-4">
        <span className="absolute left-3 top-1/2 -translate-y-1/2 text-[#9BACC8] text-sm">🔍</span>
        <input
          value={busqueda}
          onChange={(e) => setBusqueda(e.target.value)}
          placeholder="Buscar por radicado (PK-2026-0001), cliente, NIT o empresa..."
          className="w-full pl-9 pr-4 py-2.5 rounded-lg border border-[#D6E0F0] text-sm text-[#1A2B47] placeholder-[#9BACC8] bg-white focus:outline-none focus:ring-2 focus:ring-[#1A4FA0] transition"
        />
        {busqueda && (
          <button
            onClick={() => setBusqueda('')}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-[#9BACC8] hover:text-[#6B7EA8] text-sm"
          >
            ✕
          </button>
        )}
      </div>

      {/* Filtros */}
      {(() => {
        const hayFiltrosActivos = filtroEstado || filtroTipo || filtroFechaDesde || filtroFechaHasta || filtroPuntoVenta || filtroAreaCausante
        const limpiarTodo = () => {
          setFiltroEstado(''); setFiltroTipo('')
          setFiltroFechaDesde(''); setFiltroFechaHasta('')
          setFiltroPuntoVenta(''); setFiltroAreaCausante('')
        }
        return (
          <div className="mb-4">
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPanelFiltrosAbierto(v => !v)}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-sm font-semibold transition ${
                  panelFiltrosAbierto || hayFiltrosActivos
                    ? 'border-[#1A4FA0] text-[#1A4FA0] bg-[#F0F4FA]'
                    : 'border-[#D6E0F0] text-[#6B7EA8] bg-white hover:bg-[#F0F4FA]'
                }`}
              >
                🔧 Filtros {hayFiltrosActivos && <span className="w-1.5 h-1.5 rounded-full bg-[#1A4FA0]" />}
                <span className="text-xs">{panelFiltrosAbierto ? '▲' : '▼'}</span>
              </button>

              {hayFiltrosActivos && (
                <button
                  onClick={limpiarTodo}
                  className="px-3 py-2 rounded-lg border border-[#D6E0F0] text-sm text-[#6B7EA8] bg-white hover:bg-[#F0F4FA] transition"
                >
                  ✕ Limpiar filtros
                </button>
              )}
            </div>

            {panelFiltrosAbierto && (
              <div className="mt-3 p-4 bg-white rounded-xl border border-[#D6E0F0] grid grid-cols-3 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-[#6B7EA8] uppercase tracking-wide mb-1.5">Estado</label>
                  <select
                    value={filtroEstado}
                    onChange={(e) => setFiltroEstado(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-[#D6E0F0] text-sm text-[#1A2B47] bg-white focus:outline-none focus:ring-2 focus:ring-[#1A4FA0]"
                  >
                    <option value="">Todos los estados</option>
                    {Object.entries(ESTADOS).map(([key, { label }]) => (
                      <option key={key} value={key}>{label}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-[#6B7EA8] uppercase tracking-wide mb-1.5">Tipo</label>
                  <select
                    value={filtroTipo}
                    onChange={(e) => setFiltroTipo(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-[#D6E0F0] text-sm text-[#1A2B47] bg-white focus:outline-none focus:ring-2 focus:ring-[#1A4FA0]"
                  >
                    <option value="">Todos los tipos</option>
                    {Object.entries(TIPOS).map(([key, { label }]) => (
                      <option key={key} value={key}>{label}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-[#6B7EA8] uppercase tracking-wide mb-1.5">Punto de venta</label>
                  <select
                    value={filtroPuntoVenta}
                    onChange={(e) => setFiltroPuntoVenta(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-[#D6E0F0] text-sm text-[#1A2B47] bg-white focus:outline-none focus:ring-2 focus:ring-[#1A4FA0]"
                  >
                    <option value="">Todos</option>
                    {PUNTOS_VENTA.map(({ prefijo, label }) => (
                      <option key={prefijo} value={prefijo}>{label}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-[#6B7EA8] uppercase tracking-wide mb-1.5">Área causante</label>
                  <select
                    value={filtroAreaCausante}
                    onChange={(e) => setFiltroAreaCausante(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-[#D6E0F0] text-sm text-[#1A2B47] bg-white focus:outline-none focus:ring-2 focus:ring-[#1A4FA0]"
                  >
                    <option value="">Todas</option>
                    {AREAS_CAUSANTES.map(a => (
                      <option key={a} value={a}>{a}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-[#6B7EA8] uppercase tracking-wide mb-1.5">Fecha desde</label>
                  <input
                    type="date"
                    value={filtroFechaDesde}
                    onChange={(e) => setFiltroFechaDesde(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-[#D6E0F0] text-sm text-[#1A2B47] bg-white focus:outline-none focus:ring-2 focus:ring-[#1A4FA0]"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-[#6B7EA8] uppercase tracking-wide mb-1.5">Fecha hasta</label>
                  <input
                    type="date"
                    value={filtroFechaHasta}
                    onChange={(e) => setFiltroFechaHasta(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-[#D6E0F0] text-sm text-[#1A2B47] bg-white focus:outline-none focus:ring-2 focus:ring-[#1A4FA0]"
                  />
                </div>
              </div>
            )}
          </div>
        )
      })()}

      {/* Tabla */}
      <div className="bg-white rounded-xl border border-[#D6E0F0] overflow-hidden">
        {isLoading ? (
          <div className="flex items-center justify-center py-16 text-[#6B7EA8] text-sm">
            Cargando solicitudes...
          </div>
        ) : isError ? (
          <div className="flex items-center justify-center py-16 text-red-500 text-sm">
            Error al cargar las PQRS. Verifica tu conexión.
          </div>
        ) : pqrsList.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-[#6B7EA8]">
            <span className="text-4xl mb-3">📭</span>
            <span className="text-sm font-medium">No hay PQRS registradas</span>
            <span className="text-xs mt-1">Crea la primera con el botón "Registrar PQRS"</span>
          </div>
        ) : pqrsFiltrada.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-[#6B7EA8]">
            <span className="text-4xl mb-3">🔍</span>
            <span className="text-sm font-medium">Sin resultados para "{busqueda}"</span>
            <span className="text-xs mt-1">Verifica el radicado o intenta con otro término</span>
          </div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="bg-[#F0F4FA] border-b border-[#D6E0F0]">
                {['Radicado', 'Tipo', 'Cliente', 'Área', 'Prioridad', 'SLA', 'Estado', ''].map(h => (
                  <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-[#6B7EA8] uppercase tracking-wide">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {pqrsFiltrada.map((pqrs) => (
                <tr
                  key={pqrs.id}
                  className="border-b border-[#F0F4FA] hover:bg-[#F8FAFD] transition cursor-pointer"
                  onClick={() => navigate(`/pqrs/${pqrs.id}`)}
                >
                  <td className="px-4 py-3 text-xs text-[#1A4FA0] font-mono font-semibold">
                    {pqrs.codigo_seguimiento || `#${pqrs.id}`}
                  </td>
                  <td className="px-4 py-3"><Badge map={TIPOS} value={pqrs.tipo} /></td>
                  <td className="px-4 py-3">
                    <div className="text-sm font-semibold text-[#1A2B47]">{pqrs.cliente_nombre}</div>
                    {pqrs.cliente_email && (
                      <div className="text-xs text-[#6B7EA8]">{pqrs.cliente_email}</div>
                    )}
                  </td>
                  <td className="px-4 py-3 text-sm text-[#6B7EA8]">{pqrs.area_responsable || '—'}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs font-semibold ${PRIORIDADES[pqrs.prioridad]?.color}`}>
                      ● {PRIORIDADES[pqrs.prioridad]?.label}
                    </span>
                  </td>
                  <td className="px-4 py-3"><SLALabel fechaLimite={pqrs.fecha_limite_sla} /></td>
                  <td className="px-4 py-3"><Badge map={ESTADOS} value={pqrs.estado} /></td>
                  <td className="px-4 py-3">
                    <button className="text-xs text-[#1A4FA0] font-semibold hover:underline">
                      Ver
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Modales */}
      {modalCrear && (
        <ModalCrear
          onClose={() => setModalCrear(false)}
          onCreated={refetch}
        />
      )}
      {seleccionada && (
        <ModalDetalle
          pqrs={seleccionada}
          onClose={() => setSeleccionada(null)}
          onUpdated={refetch}
        />
      )}
    </div>
  )
}