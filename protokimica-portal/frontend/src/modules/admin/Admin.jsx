import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useAuth } from '../../core/AuthContext.jsx'
import api from '../../core/api.js'
import { AREAS, areasParaSelect } from '../../core/areas.js'
import {
  IconoCandado, IconoLlave, IconoPersonas,
} from '../../core/components/Iconos.jsx'

// Las áreas viven en un solo sitio: src/core/areas.js

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
    <div className="bg-white rounded-xl border border-borde overflow-hidden">
      <div className="px-5 py-4 border-b border-borde flex items-center justify-between">
        <div>
          <h3 className="font-bold text-acento-fuerte">Tipos de Autorización</h3>
          <p className="text-xs text-texto-2 mt-0.5">
            Define qué tipos de autorización pueden solicitar los agentes para gestionar una PQRS.
          </p>
        </div>
        <span className="bg-fondo text-texto-2 text-xs font-bold px-2.5 py-1 rounded-full">
          {tipos.length} configurados
        </span>
      </div>

      {/* Formulario para crear */}
      <div className="p-5 border-b border-borde bg-superficie-2">
        <p className="text-xs font-semibold text-texto-2 uppercase tracking-wide mb-3">
          Agregar nuevo tipo
        </p>
        <div className="grid grid-cols-3 gap-3 mb-3">
          <div>
            <label className="block text-xs font-semibold text-texto-2 uppercase tracking-wide mb-1.5">
              Nombre *
            </label>
            <input
              name="nombre"
              value={form.nombre}
              onChange={handleChange}
              placeholder="Ej: Devolución de dinero"
              className="w-full px-3 py-2.5 rounded-lg border border-borde text-sm text-texto placeholder-texto-3 focus:outline-none focus:ring-2 focus:ring-acento"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-texto-2 uppercase tracking-wide mb-1.5">
              Área autorizadora *
            </label>
            <select
              name="area_autorizadora"
              value={form.area_autorizadora}
              onChange={handleChange}
              className="w-full px-3 py-2.5 rounded-lg border border-borde text-sm text-texto focus:outline-none focus:ring-2 focus:ring-acento"
            >
              <option value="">Seleccionar área...</option>
              {AREAS.map(a => <option key={a} value={a}>{a}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold text-texto-2 uppercase tracking-wide mb-1.5">
              Descripción
            </label>
            <input
              name="descripcion"
              value={form.descripcion}
              onChange={handleChange}
              placeholder="Descripción opcional"
              className="w-full px-3 py-2.5 rounded-lg border border-borde text-sm text-texto placeholder-texto-3 focus:outline-none focus:ring-2 focus:ring-acento"
            />
          </div>
        </div>

        {error && (
          <div className="bg-negativo-bg border border-negativo/25 rounded-lg px-3 py-2 text-sm text-negativo mb-3">
            {error}
          </div>
        )}

        <button
          onClick={() => mutCrear.mutate()}
          disabled={!form.nombre || !form.area_autorizadora || mutCrear.isPending}
          className="bg-ambar hover:bg-ambar-claro text-acento-fuerte font-bold px-4 py-2.5 rounded-lg text-sm transition disabled:opacity-50"
        >
          {mutCrear.isPending ? 'Guardando...' : '+ Agregar tipo'}
        </button>
      </div>

      {/* Lista de tipos */}
      <div className="divide-y divide-borde">
        {isLoading ? (
          <div className="px-5 py-8 text-center text-sm text-texto-2">Cargando...</div>
        ) : tipos.length === 0 ? (
          <div className="px-5 py-8 text-center">
            <div className="flex justify-center mb-3 text-texto-3"><IconoCandado tam={24} /></div>
            <p className="text-sm text-texto-2">No hay tipos configurados aún.</p>
            <p className="text-xs text-texto-3 mt-1">Crea el primero con el formulario de arriba.</p>
          </div>
        ) : (
          tipos.map((tipo) => (
            <div key={tipo.id} className="flex items-center gap-4 px-5 py-3.5">
              <div className="flex-1">
                <div className="text-sm font-semibold text-texto">{tipo.nombre}</div>
                {tipo.descripcion && (
                  <div className="text-xs text-texto-3 mt-0.5">{tipo.descripcion}</div>
                )}
              </div>
              <span className="text-xs font-semibold bg-acento-suave text-acento px-2.5 py-1 rounded-full flex-shrink-0">
                {tipo.area_autorizadora}
              </span>
              <button
                onClick={() => {
                  if (confirm(`¿Desactivar "${tipo.nombre}"?`)) mutEliminar.mutate(tipo.id)
                }}
                className="text-xs text-negativo-vivo hover:text-negativo font-semibold transition flex-shrink-0"
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

const ROLES = [
  { value: 'admin',    label: 'Administrador',       desc: 'Acceso total, incluida esta sección' },
  { value: 'gerencia', label: 'Gerencia / Dirección', desc: 'Ve TODAS las áreas sin límite, pero no modifica nada; solo puede comentar' },
  { value: 'lider',    label: 'Líder de área',        desc: 'Gestiona y autoriza PQRS de su área' },
  { value: 'agente',   label: 'Agente',               desc: 'Gestiona PQRS asignadas' },
  { value: 'lectura',  label: 'Solo lectura',         desc: 'Solo puede consultar, no editar' },
]

// Aviso para el admin: en Master Planner el área del usuario ya no es
// informativa, decide qué proyectos ve.
const NOTA_AREA = 'En Master Planner el área determina qué proyectos ve la persona. Sin área, solo verá lo asignado a ella y los proyectos sin clasificar.'

function GestionUsuarios() {
  const queryClient = useQueryClient()
  const { user: usuarioActual } = useAuth()
  const [form, setForm] = useState({ nombre: '', email: '', password: '', rol: 'agente', area: '' })
  const [error, setError] = useState('')
  const [mostrarForm, setMostrarForm] = useState(false)

  const { data: usuarios = [], isLoading } = useQuery({
    queryKey: ['usuarios'],
    queryFn: async () => { const { data } = await api.get('/auth/usuarios'); return data },
  })

  const mutCrear = useMutation({
    mutationFn: () => api.post('/auth/usuarios', form),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['usuarios'] })
      setForm({ nombre: '', email: '', password: '', rol: 'agente', area: '' })
      setError('')
      setMostrarForm(false)
    },
    onError: (err) => setError(err.response?.data?.detail || 'Error al crear el usuario.'),
  })

  const mutActualizar = useMutation({
    mutationFn: ({ id, cambios }) => api.patch(`/auth/usuarios/${id}`, cambios),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['usuarios'] }),
    onError: (err) => alert(err.response?.data?.detail || 'Error al actualizar el usuario.'),
  })

  const handleChange = (e) => setForm({ ...form, [e.target.name]: e.target.value })

  return (
    <div className="bg-white rounded-xl border border-borde overflow-hidden">
      <div className="px-5 py-4 border-b border-borde flex items-center justify-between">
        <div>
          <h3 className="font-bold text-acento-fuerte">Usuarios y roles</h3>
          <p className="text-xs text-texto-2 mt-0.5">
            Crea usuarios internos y asígnales rol y área para probar permisos.
          </p>
        </div>
        <button
          onClick={() => setMostrarForm(v => !v)}
          className="bg-ambar hover:bg-ambar-claro text-acento-fuerte font-bold px-4 py-2 rounded-lg text-sm transition"
        >
          {mostrarForm ? 'Cancelar' : '+ Nuevo usuario'}
        </button>
      </div>

      {mostrarForm && (
        <div className="p-5 border-b border-borde bg-superficie-2 space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-texto-2 uppercase tracking-wide mb-1.5">Nombre *</label>
              <input name="nombre" value={form.nombre} onChange={handleChange} placeholder="Ej: Laura Gómez"
                className="w-full px-3 py-2.5 rounded-lg border border-borde text-sm focus:outline-none focus:ring-2 focus:ring-acento" />
            </div>
            <div>
              <label className="block text-xs font-semibold text-texto-2 uppercase tracking-wide mb-1.5">Correo *</label>
              <input name="email" type="email" value={form.email} onChange={handleChange} placeholder="laura@protokimica.com"
                className="w-full px-3 py-2.5 rounded-lg border border-borde text-sm focus:outline-none focus:ring-2 focus:ring-acento" />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-texto-2 uppercase tracking-wide mb-1.5">Contraseña temporal *</label>
            <input name="password" type="text" value={form.password} onChange={handleChange} placeholder="Mínimo 6 caracteres"
              className="w-full px-3 py-2.5 rounded-lg border border-borde text-sm focus:outline-none focus:ring-2 focus:ring-acento" />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-texto-2 uppercase tracking-wide mb-1.5">Rol</label>
              <select name="rol" value={form.rol} onChange={handleChange}
                className="w-full px-3 py-2.5 rounded-lg border border-borde text-sm focus:outline-none focus:ring-2 focus:ring-acento">
                {ROLES.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
              </select>
            </div>
            <div>
              <label
                className="block text-xs font-semibold text-texto-2 uppercase tracking-wide mb-1.5"
                title={NOTA_AREA}
              >
                Área <span className="normal-case font-normal text-texto-3">(define qué ve)</span>
              </label>
              <select name="area" value={form.area} onChange={handleChange}
                className="w-full px-3 py-2.5 rounded-lg border border-borde text-sm focus:outline-none focus:ring-2 focus:ring-acento">
                <option value="">Sin área</option>
                {AREAS.map(a => <option key={a} value={a}>{a}</option>)}
              </select>
            </div>
          </div>

          {error && (
            <div className="bg-negativo-bg border border-negativo/25 rounded-lg px-3 py-2 text-sm text-negativo">{error}</div>
          )}

          <button
            onClick={() => mutCrear.mutate()}
            disabled={!form.nombre || !form.email || form.password.length < 6 || mutCrear.isPending}
            className="bg-acento-fuerte hover:bg-acento text-white font-bold px-4 py-2.5 rounded-lg text-sm transition disabled:opacity-50"
          >
            {mutCrear.isPending ? 'Creando...' : 'Crear usuario'}
          </button>
        </div>
      )}

      <div className="divide-y divide-borde">
        {isLoading ? (
          <div className="px-5 py-8 text-center text-sm text-texto-2">Cargando...</div>
        ) : usuarios.length === 0 ? (
          <div className="px-5 py-8 text-center">
            <div className="flex justify-center mb-3 text-texto-3"><IconoPersonas tam={24} /></div>
            <p className="text-sm text-texto-2">Aún no hay usuarios creados desde este panel.</p>
          </div>
        ) : (
          usuarios.map((u) => (
            <div key={u.id} className="flex items-center gap-3 px-5 py-3.5">
              <div className="flex-1 min-w-0">
                <div className="text-sm font-semibold text-texto truncate">
                  {u.nombre} {u.id === usuarioActual?.id && <span className="text-xs text-texto-3">(tú)</span>}
                </div>
                <div className="text-xs text-texto-3 truncate">{u.email}</div>
              </div>

              <select
                value={u.rol}
                onChange={(e) => mutActualizar.mutate({ id: u.id, cambios: { rol: e.target.value } })}
                className="text-xs font-semibold border border-borde rounded-lg px-2 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-acento"
              >
                {ROLES.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
              </select>

              <select
                value={u.area || ''}
                onChange={(e) => mutActualizar.mutate({ id: u.id, cambios: { area: e.target.value || null } })}
                className="text-xs border border-borde rounded-lg px-2 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-acento"
              >
                <option value="">Sin área</option>
                {areasParaSelect(u.area).map(a => <option key={a} value={a}>{a}</option>)}
              </select>

              <button
                onClick={() => {
                  const nueva = prompt(`Nueva contraseña para ${u.nombre} (mínimo 6 caracteres):`)
                  if (nueva) mutActualizar.mutate({ id: u.id, cambios: { password: nueva } })
                }}
                title="Restablecer contraseña"
                className="text-xs font-semibold px-2.5 py-1 rounded-full flex-shrink-0 bg-fondo text-texto-2 hover:bg-borde transition"
              >
                <IconoLlave tam={15} />
              </button>

              <button
                onClick={() => mutActualizar.mutate({ id: u.id, cambios: { activo: !u.activo } })}
                className={`text-xs font-semibold px-2.5 py-1 rounded-full flex-shrink-0 transition ${
                  u.activo ? 'bg-positivo-bg text-positivo hover:bg-positivo-bg' : 'bg-superficie-2 text-texto-2 hover:bg-borde-fuerte'
                }`}
              >
                {u.activo ? 'Activo' : 'Inactivo'}
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
      <div className="flex flex-col items-center justify-center py-20 text-texto-2">
        <IconoCandado tam={26} className="mb-3 text-texto-3" />
        <span className="text-sm font-semibold">Acceso restringido</span>
        <span className="text-xs mt-1">Solo administradores pueden acceder a esta sección.</span>
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-6">
        <h1 className="text-xl font-bold text-acento-fuerte">Administración</h1>
        <p className="text-sm text-texto-2 mt-1">Configuración del sistema · Solo administradores</p>
      </div>

      <div className="space-y-5">
        <GestionUsuarios />
        <TiposAutorizacion />
      </div>
    </div>
  )
}