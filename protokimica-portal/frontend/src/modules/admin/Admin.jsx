import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useAuth } from '../../core/AuthContext.jsx'
import api from '../../core/api.js'

const AREAS = [
  'Comercial', 'Logística', 'Calidad', 'HSEQ',
  'TI', 'Facturación', 'Servicio al cliente', 'Contabilidad',
]

function TiposAutorizacion() {
  const queryClient = useQueryClient()
  const [form, setForm] = useState({ nombre: '', descripcion: '', area_autorizadora: '' })
  const [error, setError] = useState('')

  const { data: tipos = [], isLoading } = useQuery({
    queryKey: ['tipos-autorizacion'],
    queryFn: async () => { const { data } = await api.get('/autorizaciones/tipos'); return data },
  })

  const mutCrear = useMutation({
    mutationFn: () => api.post('/autorizaciones/tipos', form),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tipos-autorizacion'] })
      setForm({ nombre: '', descripcion: '', area_autorizadora: '' })
      setError('')
    },
    onError: (err) => setError(err.response?.data?.detail || 'Error al crear.'),
  })

  const mutEliminar = useMutation({
    mutationFn: (id) => api.delete(`/autorizaciones/tipos/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['tipos-autorizacion'] }),
  })

  const handleChange = (e) => setForm({ ...form, [e.target.name]: e.target.value })

  return (
    <div className="bg-white rounded-xl border border-[#D6E0F0] overflow-hidden">
      <div className="px-5 py-4 border-b border-[#D6E0F0] flex items-center justify-between">
        <div>
          <h3 className="font-bold text-[#0D2B5E]">Tipos de Autorización</h3>
          <p className="text-xs text-[#6B7EA8] mt-0.5">
            Define qué tipos de autorización pueden solicitar los agentes para gestionar una PQRS.
          </p>
        </div>
        <span className="bg-[#F0F4FA] text-[#6B7EA8] text-xs font-bold px-2.5 py-1 rounded-full">
          {tipos.length} configurados
        </span>
      </div>

      {/* Formulario para crear */}
      <div className="p-5 border-b border-[#D6E0F0] bg-[#F8FAFD]">
        <p className="text-xs font-semibold text-[#6B7EA8] uppercase tracking-wide mb-3">
          Agregar nuevo tipo
        </p>
        <div className="grid grid-cols-3 gap-3 mb-3">
          <div>
            <label className="block text-xs font-semibold text-[#6B7EA8] uppercase tracking-wide mb-1.5">
              Nombre *
            </label>
            <input
              name="nombre"
              value={form.nombre}
              onChange={handleChange}
              placeholder="Ej: Devolución de dinero"
              className="w-full px-3 py-2.5 rounded-lg border border-[#D6E0F0] text-sm text-[#1A2B47] placeholder-[#9BACC8] focus:outline-none focus:ring-2 focus:ring-[#1A4FA0]"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-[#6B7EA8] uppercase tracking-wide mb-1.5">
              Área autorizadora *
            </label>
            <select
              name="area_autorizadora"
              value={form.area_autorizadora}
              onChange={handleChange}
              className="w-full px-3 py-2.5 rounded-lg border border-[#D6E0F0] text-sm text-[#1A2B47] focus:outline-none focus:ring-2 focus:ring-[#1A4FA0]"
            >
              <option value="">Seleccionar área...</option>
              {AREAS.map(a => <option key={a} value={a}>{a}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold text-[#6B7EA8] uppercase tracking-wide mb-1.5">
              Descripción
            </label>
            <input
              name="descripcion"
              value={form.descripcion}
              onChange={handleChange}
              placeholder="Descripción opcional"
              className="w-full px-3 py-2.5 rounded-lg border border-[#D6E0F0] text-sm text-[#1A2B47] placeholder-[#9BACC8] focus:outline-none focus:ring-2 focus:ring-[#1A4FA0]"
            />
          </div>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg px-3 py-2 text-sm text-red-700 mb-3">
            {error}
          </div>
        )}

        <button
          onClick={() => mutCrear.mutate()}
          disabled={!form.nombre || !form.area_autorizadora || mutCrear.isPending}
          className="bg-[#F5A800] hover:bg-[#FFC840] text-[#0D2B5E] font-bold px-4 py-2.5 rounded-lg text-sm transition disabled:opacity-50"
        >
          {mutCrear.isPending ? 'Guardando...' : '+ Agregar tipo'}
        </button>
      </div>

      {/* Lista de tipos */}
      <div className="divide-y divide-[#F0F4FA]">
        {isLoading ? (
          <div className="px-5 py-8 text-center text-sm text-[#6B7EA8]">Cargando...</div>
        ) : tipos.length === 0 ? (
          <div className="px-5 py-8 text-center">
            <div className="text-3xl mb-2">🔐</div>
            <p className="text-sm text-[#6B7EA8]">No hay tipos configurados aún.</p>
            <p className="text-xs text-[#9BACC8] mt-1">Crea el primero con el formulario de arriba.</p>
          </div>
        ) : (
          tipos.map((tipo) => (
            <div key={tipo.id} className="flex items-center gap-4 px-5 py-3.5">
              <div className="flex-1">
                <div className="text-sm font-semibold text-[#1A2B47]">{tipo.nombre}</div>
                {tipo.descripcion && (
                  <div className="text-xs text-[#9BACC8] mt-0.5">{tipo.descripcion}</div>
                )}
              </div>
              <span className="text-xs font-semibold bg-[#E8EDF8] text-[#1A4FA0] px-2.5 py-1 rounded-full flex-shrink-0">
                {tipo.area_autorizadora}
              </span>
              <button
                onClick={() => {
                  if (confirm(`¿Desactivar "${tipo.nombre}"?`)) mutEliminar.mutate(tipo.id)
                }}
                className="text-xs text-red-400 hover:text-red-600 font-semibold transition flex-shrink-0"
              >
                Desactivar
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

export default function Admin() {
  const { user } = useAuth()

  if (user?.rol !== 'admin') {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-[#6B7EA8]">
        <span className="text-4xl mb-3">🔒</span>
        <span className="text-sm font-semibold">Acceso restringido</span>
        <span className="text-xs mt-1">Solo administradores pueden acceder a esta sección.</span>
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-6">
        <h1 className="text-xl font-bold text-[#0D2B5E]">Administración</h1>
        <p className="text-sm text-[#6B7EA8] mt-1">Configuración del sistema · Solo administradores</p>
      </div>

      <div className="space-y-5">
        <TiposAutorizacion />
      </div>
    </div>
  )
}