import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../../core/api.js'

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

// ── Modal para crear PQRS ──────────────────────────────────────────
function ModalCrear({ onClose, onCreated }) {
  const [form, setForm] = useState({
    tipo: 'queja',
    cliente_nombre: '',
    cliente_email: '',
    cliente_telefono: '',
    descripcion: '',
    area_responsable: '',
  })
  const [error, setError] = useState('')

  const mutation = useMutation({
    mutationFn: (data) => api.post('/pqrs', data),
    onSuccess: () => { onCreated(); onClose() },
    onError: (err) => setError(err.response?.data?.detail || 'Error al crear la PQRS'),
  })

  const handleChange = (e) => setForm({ ...form, [e.target.name]: e.target.value })

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg">
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#D6E0F0]">
          <h2 className="font-bold text-[#0D2B5E] text-lg">Nueva PQRS</h2>
          <button onClick={onClose} className="text-[#6B7EA8] hover:text-[#0D2B5E] text-xl">✕</button>
        </div>

        <div className="p-6 space-y-4 max-h-[70vh] overflow-y-auto">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-[#6B7EA8] uppercase tracking-wide mb-1.5">
                Tipo
              </label>
              <select
                name="tipo"
                value={form.tipo}
                onChange={handleChange}
                className="w-full px-3 py-2.5 rounded-lg border border-[#D6E0F0] text-sm text-[#1A2B47] focus:outline-none focus:ring-2 focus:ring-[#1A4FA0]"
              >
                <option value="peticion">Petición</option>
                <option value="queja">Queja</option>
                <option value="reclamo">Reclamo</option>
                <option value="sugerencia">Sugerencia</option>
                <option value="felicitacon">Felicitacion</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-[#6B7EA8] uppercase tracking-wide mb-1.5">
                Área responsable
              </label>
              <select
                name="area_responsable"
                value={form.area_responsable}
                onChange={handleChange}
                className="w-full px-3 py-2.5 rounded-lg border border-[#D6E0F0] text-sm text-[#1A2B47] focus:outline-none focus:ring-2 focus:ring-[#1A4FA0]"
              >
                <option value="">Sin asignar</option>
                <option value="Comercial">Comercial</option>
                <option value="Logística">Logística</option>
                <option value="Calidad">Calidad</option>
                <option value="HSEQ">HSEQ</option>
                <option value="TI">TI</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-[#6B7EA8] uppercase tracking-wide mb-1.5">
              Nombre del cliente *
            </label>
            <input
              name="cliente_nombre"
              value={form.cliente_nombre}
              onChange={handleChange}
              placeholder="Ej: Industrias del Valle S.A.S"
              required
              className="w-full px-3 py-2.5 rounded-lg border border-[#D6E0F0] text-sm text-[#1A2B47] placeholder-[#9BACC8] focus:outline-none focus:ring-2 focus:ring-[#1A4FA0]"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-[#6B7EA8] uppercase tracking-wide mb-1.5">
                Correo cliente
              </label>
              <input
                name="cliente_email"
                type="email"
                value={form.cliente_email}
                onChange={handleChange}
                placeholder="cliente@empresa.com"
                className="w-full px-3 py-2.5 rounded-lg border border-[#D6E0F0] text-sm text-[#1A2B47] placeholder-[#9BACC8] focus:outline-none focus:ring-2 focus:ring-[#1A4FA0]"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-[#6B7EA8] uppercase tracking-wide mb-1.5">
                Teléfono
              </label>
              <input
                name="cliente_telefono"
                value={form.cliente_telefono}
                onChange={handleChange}
                placeholder="3001234567"
                className="w-full px-3 py-2.5 rounded-lg border border-[#D6E0F0] text-sm text-[#1A2B47] placeholder-[#9BACC8] focus:outline-none focus:ring-2 focus:ring-[#1A4FA0]"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-[#6B7EA8] uppercase tracking-wide mb-1.5">
              Descripción *
            </label>
            <textarea
              name="descripcion"
              value={form.descripcion}
              onChange={handleChange}
              placeholder="Describe detalladamente la situación..."
              rows={4}
              required
              className="w-full px-3 py-2.5 rounded-lg border border-[#D6E0F0] text-sm text-[#1A2B47] placeholder-[#9BACC8] focus:outline-none focus:ring-2 focus:ring-[#1A4FA0] resize-none"
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
            onClick={() => mutation.mutate(form)}
            disabled={mutation.isPending || !form.cliente_nombre || !form.descripcion}
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

  // Búsqueda local por radicado, cliente, NIT o empresa
  const pqrsFiltrada = pqrsList.filter((p) => {
    const q = busqueda.trim().toLowerCase()
    if (!q) return true
    return [p.codigo_seguimiento, p.radicado_calidad, p.cliente_nombre, p.empresa, p.nit_cedula]
      .filter(Boolean)
      .some(campo => campo.toLowerCase().includes(q))
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
      <div className="flex gap-2 mb-4 flex-wrap">
        <select
          value={filtroEstado}
          onChange={(e) => setFiltroEstado(e.target.value)}
          className="px-3 py-2 rounded-lg border border-[#D6E0F0] text-sm text-[#1A2B47] bg-white focus:outline-none focus:ring-2 focus:ring-[#1A4FA0]"
        >
          <option value="">Todos los estados</option>
          {Object.entries(ESTADOS).map(([key, { label }]) => (
            <option key={key} value={key}>{label}</option>
          ))}
        </select>

        <select
          value={filtroTipo}
          onChange={(e) => setFiltroTipo(e.target.value)}
          className="px-3 py-2 rounded-lg border border-[#D6E0F0] text-sm text-[#1A2B47] bg-white focus:outline-none focus:ring-2 focus:ring-[#1A4FA0]"
        >
          <option value="">Todos los tipos</option>
          {Object.entries(TIPOS).map(([key, { label }]) => (
            <option key={key} value={key}>{label}</option>
          ))}
        </select>

        {(filtroEstado || filtroTipo) && (
          <button
            onClick={() => { setFiltroEstado(''); setFiltroTipo('') }}
            className="px-3 py-2 rounded-lg border border-[#D6E0F0] text-sm text-[#6B7EA8] bg-white hover:bg-[#F0F4FA] transition"
          >
            ✕ Limpiar filtros
          </button>
        )}
      </div>

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