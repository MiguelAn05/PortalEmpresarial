/**
 * Quién tiene cada capacidad del portal.
 *
 * Antes esto era una constante en el código de cada módulo (quién autoriza
 * notas crédito, quién cierra una PQRS...). Mientras el área coincidiera con
 * quién hace el trabajo, funcionaba; el día que Aseguramiento también
 * tramita notas crédito y no solo Contabilidad, la única salida era
 * cambiarle el área a alguien — con lo que se le entregaba también todo lo
 * demás que esa área decide en otros módulos.
 *
 * Aquí una capacidad se otorga a un ÁREA (lo normal, se hereda sola cuando
 * entra gente nueva) o a una PERSONA (la excepción, con quién y cuándo la
 * dio). Ver `core/capacidades.py` en el backend para el diseño completo.
 */
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../../core/api.js'
import { AREAS } from '../../core/areas.js'
import { IconoCerrar, IconoLlave } from '../../core/components/Iconos.jsx'
import { mensajeDeError } from '../../core/errores.js'

function formatFecha(fecha) {
  if (!fecha) return '—'
  return new Date(fecha).toLocaleDateString('es-CO', {
    day: '2-digit', month: 'short', year: 'numeric',
  })
}

// Una fila de "otorgar", plegada por defecto: la mayoría de las veces no se
// está tocando esto, así que no necesita ocupar espacio permanente.
function FormOtorgar({ capacidad, usuarios, onCerrar, onOtorgado }) {
  const [modo, setModo] = useState('area')   // 'area' | 'persona'
  const [area, setArea] = useState('')
  const [usuarioId, setUsuarioId] = useState('')
  const [error, setError] = useState('')

  const mutacion = useMutation({
    mutationFn: () => api.post(`/capacidades/${capacidad}/otorgar`, {
      area: modo === 'area' ? area : undefined,
      usuario_id: modo === 'persona' ? Number(usuarioId) : undefined,
    }),
    onSuccess: () => { onOtorgado(); onCerrar() },
    onError: (err) => setError(mensajeDeError(err, 'No se pudo otorgar.')),
  })

  const listo = modo === 'area' ? Boolean(area) : Boolean(usuarioId)

  return (
    <div className="bg-superficie-2 rounded-lg p-3 mt-2">
      <div className="flex gap-4 mb-2">
        <label className="flex items-center gap-1.5 text-xs text-texto cursor-pointer">
          <input type="radio" checked={modo === 'area'} onChange={() => setModo('area')} />
          A toda un área
        </label>
        <label className="flex items-center gap-1.5 text-xs text-texto cursor-pointer">
          <input type="radio" checked={modo === 'persona'} onChange={() => setModo('persona')} />
          A una persona (excepción)
        </label>
      </div>

      {modo === 'area' ? (
        <select
          value={area}
          onChange={(e) => setArea(e.target.value)}
          className="w-full px-3 py-2 rounded-lg border border-borde text-sm text-texto focus:outline-none focus:ring-2 focus:ring-acento"
        >
          <option value="">Seleccionar área...</option>
          {AREAS.map(a => <option key={a} value={a}>{a}</option>)}
        </select>
      ) : (
        <select
          value={usuarioId}
          onChange={(e) => setUsuarioId(e.target.value)}
          className="w-full px-3 py-2 rounded-lg border border-borde text-sm text-texto focus:outline-none focus:ring-2 focus:ring-acento"
        >
          <option value="">Seleccionar persona...</option>
          {usuarios.map(u => (
            <option key={u.id} value={u.id}>{u.nombre} — {u.area || 'sin área'}</option>
          ))}
        </select>
      )}

      {error && <p role="alert" className="text-xs text-negativo mt-2">{error}</p>}

      <div className="flex gap-2 mt-3">
        <button
          onClick={() => mutacion.mutate()}
          disabled={!listo || mutacion.isPending}
          className="bg-ambar hover:bg-ambar-claro text-acento-fuerte font-bold px-3 py-1.5 rounded-lg text-xs transition disabled:opacity-50"
        >
          {mutacion.isPending ? 'Otorgando...' : 'Otorgar'}
        </button>
        <button
          onClick={onCerrar}
          className="text-texto-2 hover:text-texto text-xs font-semibold px-3 py-1.5 transition"
        >
          Cancelar
        </button>
      </div>
    </div>
  )
}

function Pill({ otorgamiento, onRevocar }) {
  const esArea = Boolean(otorgamiento.area)
  // Quién lo otorgó y cuándo, en el tooltip nativo: es lo que hace
  // explicable la excepción cuando alguien pregunte por qué puede hacer
  // esto, sin ocupar espacio permanente en pantalla.
  const rastro = `Otorgada por ${otorgamiento.otorgante_nombre || '—'} · ${formatFecha(otorgamiento.otorgada_en)}`
  return (
    <span
      title={rastro}
      className={`inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full ${
        esArea ? 'bg-acento-suave text-acento' : 'bg-alerta-bg text-alerta'
      }`}
    >
      {esArea ? otorgamiento.area : `${otorgamiento.usuario_nombre} (persona)`}
      <button
        onClick={onRevocar}
        aria-label={`Revocar ${esArea ? otorgamiento.area : otorgamiento.usuario_nombre}`}
        className="hover:opacity-60 transition"
      >
        <IconoCerrar tam={11} />
      </button>
    </span>
  )
}

function FilaCapacidad({ capacidad, usuarios, invalidar }) {
  const [agregando, setAgregando] = useState(false)

  const mutRevocar = useMutation({
    mutationFn: (id) => api.delete(`/capacidades/otorgamientos/${id}`),
    onSuccess: invalidar,
  })

  return (
    <div className="px-5 py-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-texto">{capacidad.descripcion}</div>
          <div className="text-xs text-texto-3 cifra mt-0.5">{capacidad.clave}</div>
        </div>
        <button
          onClick={() => setAgregando(!agregando)}
          className="text-xs font-semibold text-acento hover:text-acento-fuerte transition flex-shrink-0"
        >
          {agregando ? 'Cerrar' : '+ Otorgar'}
        </button>
      </div>

      <div className="flex flex-wrap gap-2 mt-3">
        {capacidad.otorgamientos.length === 0 ? (
          <span className="text-xs text-texto-3">Nadie la tiene todavía.</span>
        ) : (
          capacidad.otorgamientos.map(o => (
            <Pill key={o.id} otorgamiento={o} onRevocar={() => mutRevocar.mutate(o.id)} />
          ))
        )}
      </div>

      {agregando && (
        <FormOtorgar
          capacidad={capacidad.clave}
          usuarios={usuarios}
          onCerrar={() => setAgregando(false)}
          onOtorgado={invalidar}
        />
      )}
    </div>
  )
}

export default function Capacidades() {
  const queryClient = useQueryClient()

  const { data: capacidades = [], isLoading } = useQuery({
    queryKey: ['capacidades'],
    queryFn: async () => { const { data } = await api.get('/capacidades'); return data },
  })

  const { data: usuarios = [] } = useQuery({
    queryKey: ['usuarios-para-capacidades'],
    queryFn: async () => { const { data } = await api.get('/auth/usuarios'); return data },
  })

  const invalidar = () => queryClient.invalidateQueries({ queryKey: ['capacidades'] })

  return (
    <div className="bg-white rounded-xl border border-borde overflow-hidden">
      <div className="px-5 py-4 border-b border-borde">
        <h3 className="font-bold text-acento-fuerte flex items-center gap-2">
          <IconoLlave tam={18} /> Capacidades
        </h3>
        <p className="text-xs text-texto-2 mt-0.5">
          Quién puede autorizar, aprobar o cerrar cada cosa. Se otorga por área
          —lo normal, se hereda sola— o a una persona puntual cuando el área no alcanza.
        </p>
      </div>

      <div className="divide-y divide-borde">
        {isLoading ? (
          <div className="px-5 py-8 text-center text-sm text-texto-2">Cargando...</div>
        ) : (
          capacidades.map(c => (
            <FilaCapacidad key={c.clave} capacidad={c} usuarios={usuarios} invalidar={invalidar} />
          ))
        )}
      </div>
    </div>
  )
}
