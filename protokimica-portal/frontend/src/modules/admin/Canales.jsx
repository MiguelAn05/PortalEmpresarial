/**
 * Los canales de atención de la empresa: por dónde entra una PQRS.
 *
 * Antes eran una lista en el código con los seis puntos de venta de
 * Protokimica escritos a mano. Ver `backend/app/models/canal.py`.
 *
 * - **El tipo dice qué es:** una *sede* es un mostrador (se le asigna a la
 *   gente como su punto de venta y acota qué PQRS ve), *institucional* sigue
 *   la cadena larga de las notas crédito, y *general* solo dice por dónde
 *   entró (WhatsApp, línea telefónica).
 * - **El prefijo no se cambia.** Es el código del QR impreso en la sede y el
 *   comienzo del consecutivo de sus PQRS. Se puede poner una vez a un canal
 *   que no tenía; editarlo, no.
 */
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api from '../../core/api.js'
import { mensajeDeError } from '../../core/errores.js'
import { IconoEditar, IconoSobre } from '../../core/components/Iconos.jsx'

// Atados a `MAX_NOMBRE_CANAL` y `MAX_PREFIJO` de backend/app/models/canal.py.
const MAX_NOMBRE = 100
const MAX_PREFIJO = 10

const TIPOS = {
  sede: { etiqueta: 'Sede', ayuda: 'Un mostrador: se asigna a la gente como su punto de venta.' },
  institucional: { etiqueta: 'Institucional', ayuda: 'Sus notas crédito pasan por Comercial y Contabilidad.' },
  general: { etiqueta: 'General', ayuda: 'Solo dice por dónde entró: WhatsApp, línea telefónica.' },
}

const campo = 'rounded-lg border border-borde px-3 py-1.5 text-sm'

function FilaCanal({ canal, ocupado, onCambiar }) {
  const [editando, setEditando] = useState(false)
  const [nombre, setNombre] = useState(canal.nombre)
  const [prefijo, setPrefijo] = useState('')

  const limpio = nombre.trim().replace(/\s+/g, ' ')

  if (editando) {
    return (
      <div className="px-5 py-3 space-y-2">
        <div className="flex flex-wrap gap-2">
          <input
            id={`canal-${canal.id}`} value={nombre} maxLength={MAX_NOMBRE} autoFocus
            onChange={e => setNombre(e.target.value)} className={`${campo} flex-1 min-w-48`}
          />
          {!canal.prefijo && (
            <input
              id={`canal-prefijo-${canal.id}`} value={prefijo} maxLength={MAX_PREFIJO}
              onChange={e => setPrefijo(e.target.value.toUpperCase())}
              placeholder="Prefijo (opcional)" className={`${campo} w-36`}
            />
          )}
          <button
            type="button"
            disabled={ocupado || limpio.length < 2 || (limpio === canal.nombre && !prefijo)}
            onClick={() => {
              const cambios = {}
              if (limpio !== canal.nombre) cambios.nombre = limpio
              if (prefijo) cambios.prefijo = prefijo
              onCambiar(cambios, () => setEditando(false))
            }}
            className="px-3 py-1.5 rounded-lg text-sm font-semibold bg-acento-fuerte text-white disabled:opacity-40"
          >
            Guardar
          </button>
          <button
            type="button"
            onClick={() => { setEditando(false); setNombre(canal.nombre); setPrefijo('') }}
            className="px-3 py-1.5 rounded-lg text-sm text-texto-2 hover:bg-superficie-2"
          >
            Cancelar
          </button>
        </div>
        <p className="text-xs text-texto-3">
          Cambiar el nombre lo cambia también en las PQRS y las notas crédito que lo llevan.
          {canal.prefijo
            ? ` El prefijo ${canal.prefijo} no se cambia: es el código de su QR.`
            : ' El prefijo se puede poner una sola vez y después no se cambia.'}
        </p>
      </div>
    )
  }

  return (
    <div className="px-5 py-2.5 flex flex-wrap items-center gap-3">
      <div className="flex-1 min-w-0">
        <div className={`text-sm font-medium truncate ${canal.activo ? 'text-texto' : 'text-texto-3 line-through'}`}>
          {canal.nombre}
          {canal.prefijo && (
            <span className="ml-2 font-mono text-xs px-1.5 py-0.5 rounded-md bg-superficie-2 text-texto-2">
              {canal.prefijo}
            </span>
          )}
        </div>
        <div className="text-xs text-texto-3 cifra">
          {TIPOS[canal.tipo]?.etiqueta ?? canal.tipo}
          {canal.tipo === 'sede' && ` · ${canal.personas} ${canal.personas === 1 ? 'persona' : 'personas'}`}
          {!canal.activo && ' · desactivado: no se ofrece y su QR no abre'}
        </div>
      </div>

      <select
        aria-label={`Tipo de ${canal.nombre}`} value={canal.tipo} disabled={ocupado || !canal.activo}
        onChange={e => onCambiar({ tipo: e.target.value })}
        title={TIPOS[canal.tipo]?.ayuda}
        className="rounded-lg border border-borde px-2 py-1 text-xs"
      >
        {Object.entries(TIPOS).map(([valor, { etiqueta }]) => (
          <option key={valor} value={valor} disabled={valor === 'sede' && !canal.prefijo}>{etiqueta}</option>
        ))}
      </select>
      {canal.activo && (
        <button
          type="button" onClick={() => setEditando(true)} aria-label={`Editar ${canal.nombre}`}
          className="p-1.5 rounded-lg text-texto-2 hover:bg-superficie-2"
        >
          <IconoEditar tam={15} />
        </button>
      )}
      <button
        type="button" disabled={ocupado} onClick={() => onCambiar({ activo: !canal.activo })}
        className="px-2.5 py-1 rounded-lg text-xs font-semibold text-texto-2 hover:bg-superficie-2"
      >
        {canal.activo ? 'Desactivar' : 'Reactivar'}
      </button>
    </div>
  )
}

export default function Canales() {
  const queryClient = useQueryClient()
  const [nuevo, setNuevo] = useState({ nombre: '', prefijo: '', tipo: 'general' })
  const [aviso, setAviso] = useState(null)

  const { data: canales = [], isLoading } = useQuery({
    queryKey: ['canales', 'admin'],
    queryFn: () => api.get('/canales/todos').then(r => r.data),
  })

  // Los canales salen en los formularios de PQRS, de notas crédito y en los
  // QR: cualquier cambio los refresca todos.
  const refrescar = () => {
    queryClient.invalidateQueries({ queryKey: ['canales'] })
    queryClient.invalidateQueries({ queryKey: ['qr-puntos'] })
  }

  const crear = useMutation({
    mutationFn: () => api.post('/canales', {
      nombre: nuevo.nombre, tipo: nuevo.tipo, prefijo: nuevo.prefijo || null,
    }),
    onSuccess: ({ data }) => {
      setNuevo({ nombre: '', prefijo: '', tipo: 'general' })
      setAviso({ tono: 'positivo', texto: `Se creó «${data.nombre}».${data.prefijo ? ` Su QR es /q/${data.prefijo}.` : ''}` })
      refrescar()
    },
    onError: err => setAviso({ tono: 'negativo', texto: mensajeDeError(err, 'No se pudo crear el canal.') }),
  })

  const cambiar = useMutation({
    mutationFn: ({ id, cambios }) => api.patch(`/canales/${id}`, cambios),
    onError: err => setAviso({ tono: 'negativo', texto: mensajeDeError(err, 'No se pudo guardar el cambio.') }),
  })

  const onCambiar = canal => (cambios, alTerminar) => {
    cambiar.mutate({ id: canal.id, cambios }, {
      onSuccess: ({ data }) => {
        const total = Object.values(data.cambios || {}).reduce((a, n) => a + n, 0)
        setAviso(cambios.nombre
          ? { tono: 'positivo', texto: `Renombrado a «${data.canal.nombre}». ${total ? `Se actualizó en ${total} ${total === 1 ? 'registro' : 'registros'}.` : ''}` }
          : null)
        alTerminar?.()
        refrescar()
      },
    })
  }

  const ocupado = crear.isPending || cambiar.isPending
  const sinPrefijo = nuevo.tipo === 'sede' && !nuevo.prefijo.trim()

  return (
    <div className="bg-white rounded-xl border border-borde overflow-hidden">
      <div className="px-5 py-4 border-b border-borde">
        <h3 className="font-bold text-acento-fuerte flex items-center gap-2">
          <IconoSobre tam={18} /> Canales de atención
        </h3>
        <p className="text-xs text-texto-2 mt-0.5">
          Por dónde entra una PQRS. Los que tienen prefijo numeran sus casos aparte y tienen
          su QR; el prefijo no se cambia después, porque ya está impreso.
        </p>
      </div>

      <form
        className="px-5 py-3 border-b border-borde flex flex-wrap gap-2"
        onSubmit={e => { e.preventDefault(); if (nuevo.nombre.trim().length >= 2 && !sinPrefijo) crear.mutate() }}
      >
        <input
          id="canal-nuevo" value={nuevo.nombre} maxLength={MAX_NOMBRE} placeholder="Nombre del canal nuevo"
          onChange={e => setNuevo(n => ({ ...n, nombre: e.target.value }))} className={`${campo} flex-1 min-w-48`}
        />
        <input
          id="canal-nuevo-prefijo" value={nuevo.prefijo} maxLength={MAX_PREFIJO}
          placeholder={nuevo.tipo === 'sede' ? 'Prefijo (obligatorio)' : 'Prefijo (opcional)'}
          onChange={e => setNuevo(n => ({ ...n, prefijo: e.target.value.toUpperCase() }))} className={`${campo} w-40`}
        />
        <select
          id="canal-nuevo-tipo" value={nuevo.tipo} title={TIPOS[nuevo.tipo].ayuda}
          onChange={e => setNuevo(n => ({ ...n, tipo: e.target.value }))} className={campo}
        >
          {Object.entries(TIPOS).map(([valor, { etiqueta }]) => <option key={valor} value={valor}>{etiqueta}</option>)}
        </select>
        <button
          type="submit" disabled={nuevo.nombre.trim().length < 2 || sinPrefijo || ocupado}
          className="px-3 py-1.5 rounded-lg text-sm font-semibold bg-acento-fuerte text-white disabled:opacity-40"
        >
          Crear
        </button>
        <p className="w-full text-xs text-texto-3">{TIPOS[nuevo.tipo].ayuda}</p>
      </form>

      {aviso && (
        <div className={`px-5 py-2 text-sm border-b border-borde ${
          aviso.tono === 'negativo' ? 'bg-negativo-bg text-negativo' : 'bg-positivo-bg text-positivo'
        }`}>
          {aviso.texto}
        </div>
      )}

      <div className="divide-y divide-borde">
        {isLoading ? (
          <div className="px-5 py-8 text-center text-sm text-texto-2">Cargando...</div>
        ) : (
          canales.map(c => (
            <FilaCanal key={`${c.id}-${c.nombre}-${c.prefijo}`} canal={c} ocupado={ocupado} onCambiar={onCambiar(c)} />
          ))
        )}
      </div>
    </div>
  )
}
