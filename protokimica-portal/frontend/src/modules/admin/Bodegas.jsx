/**
 * Las bodegas de la empresa: una sola lista para todo el portal.
 *
 * Aquí se crean, se renombran, se desactivan, se borra la creada por error y
 * se eligen sus RESPONSABLES: en una nota crédito institucional son a quienes
 * se les avisa primero y quienes confirman que el producto está bien. Antes
 * se marcaba la bodega en cada usuario; ahora se elige aquí, que es donde se
 * piensa la pregunta «¿quién responde por esta bodega?».
 *
 * El concepto que pide cada una en el flujo de PQRS (Logística o Producción)
 * se elige en «Flujos de PQRS». Ver `backend/app/models/bodega.py`.
 */
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api from '../../core/api.js'
import { mensajeDeError } from '../../core/errores.js'
import { IconoCerrar, IconoEditar, IconoPapelera, IconoPaquete } from '../../core/components/Iconos.jsx'

// Atado a `MAX_NOMBRE_BODEGA` de backend/app/models/bodega.py.
const MAX_NOMBRE = 40
const campo = 'rounded-lg border border-borde px-3 py-1.5 text-sm bg-white'

/** Una bodega: nombre editable, responsables, desactivar y borrar. */
function FilaBodega({ bodega, usuarios, ocupado, onGuardar, onBorrar }) {
  const [editando, setEditando] = useState(false)
  const [nombre, setNombre] = useState(bodega.nombre)
  const [agregar, setAgregar] = useState('')
  const limpio = nombre.trim().replace(/\s+/g, ' ')
  const ids = bodega.responsables.map(r => r.id)
  const disponibles = usuarios.filter(u => u.activo !== false && !ids.includes(u.id))

  return (
    <div className="px-5 py-3 space-y-2">
      <div className="flex flex-wrap items-center gap-3">
        {editando ? (
          <form className="flex gap-2"
                onSubmit={(e) => {
                  e.preventDefault()
                  if (limpio && limpio !== bodega.nombre) onGuardar({ nombre: limpio }, () => setEditando(false))
                }}>
            <input value={nombre} onChange={(e) => setNombre(e.target.value)} maxLength={MAX_NOMBRE} autoFocus
                   aria-label={`Nuevo nombre de ${bodega.nombre}`} className={`${campo} w-44`} />
            <button type="submit" disabled={!limpio || limpio === bodega.nombre || ocupado}
                    className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-acento-fuerte text-white disabled:opacity-40">
              Guardar
            </button>
            <button type="button" onClick={() => { setEditando(false); setNombre(bodega.nombre) }}
                    className="px-2.5 py-1.5 rounded-lg text-xs text-texto-2 hover:bg-superficie-2">
              Cancelar
            </button>
          </form>
        ) : (
          <div className="flex-1 min-w-0">
            <div className={`text-sm font-medium truncate ${bodega.activo ? 'text-texto' : 'text-texto-3 line-through'}`}>
              {bodega.nombre}
            </div>
            <div className="cifra text-xs text-texto-3">
              {bodega.usos ? `Aparece en ${bodega.usos} ${bodega.usos === 1 ? 'registro' : 'registros'}` : 'Sin usar'}
              {!bodega.activo && ' · desactivada: no se ofrece'}
            </div>
          </div>
        )}
        {!editando && (
          <button type="button" onClick={() => setEditando(true)} aria-label={`Editar ${bodega.nombre}`}
                  className="p-1.5 rounded-lg text-texto-2 hover:bg-superficie-2">
            <IconoEditar tam={15} />
          </button>
        )}
        <button type="button" disabled={ocupado} onClick={() => onGuardar({ activo: !bodega.activo })}
                className="px-2.5 py-1 rounded-lg text-xs font-semibold text-texto-2 hover:bg-superficie-2">
          {bodega.activo ? 'Desactivar' : 'Reactivar'}
        </button>
        <button type="button" disabled={ocupado} onClick={onBorrar} aria-label={`Borrar ${bodega.nombre}`}
                className="p-1.5 rounded-lg text-texto-3 hover:text-negativo hover:bg-negativo-bg">
          <IconoPapelera tam={15} />
        </button>
      </div>

      {/* Responsables: a quienes se les avisa primero y quienes confirman. */}
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="etiqueta mr-1">Responsables</span>
        {bodega.responsables.length === 0 && (
          <span className="text-xs text-texto-3">Ninguno: confirma quien tenga el permiso de confirmar producto.</span>
        )}
        {bodega.responsables.map(r => (
          <span key={r.id} className="inline-flex items-center gap-1 rounded-md bg-acento-suave text-acento-fuerte text-xs font-medium pl-2 pr-1 py-0.5">
            {r.nombre}
            <button type="button" disabled={ocupado} aria-label={`Quitar a ${r.nombre}`}
                    onClick={() => onGuardar({ responsables: ids.filter(i => i !== r.id) })}
                    className="p-0.5 rounded hover:bg-white/60">
              <IconoCerrar tam={11} />
            </button>
          </span>
        ))}
        <select value={agregar} disabled={ocupado} aria-label={`Agregar responsable a ${bodega.nombre}`}
                onChange={(e) => {
                  const id = Number(e.target.value)
                  if (id) onGuardar({ responsables: [...ids, id] })
                  setAgregar('')
                }}
                className="rounded-lg border border-borde px-2 py-1 text-xs bg-white">
          <option value="">+ Agregar responsable…</option>
          {disponibles.map(u => <option key={u.id} value={u.id}>{u.nombre}{u.area ? ` — ${u.area}` : ''}</option>)}
        </select>
      </div>
    </div>
  )
}

/**
 * La pregunta antes de borrar. Una bodega que ya aparece en una PQRS o una
 * nota crédito no se borra —perderían de dónde salió su producto—: aquí se
 * dice y se ofrece desactivarla, en vez de dejar que el servidor lo rechace.
 */
function ConfirmarBorrado({ bodega, borrando, onBorrar, onDesactivar, onCancelar }) {
  const usada = bodega.usos > 0
  return (
    <div className="fixed inset-0 bg-texto/50 flex items-center justify-center z-[70] p-4" onClick={onCancelar}>
      <div role="alertdialog" aria-modal="true" aria-labelledby="borrar-bodega-titulo"
           onClick={(e) => e.stopPropagation()} className="bg-white rounded-2xl shadow-lg w-full max-w-md">
        <div className="px-6 py-4 border-b border-borde">
          <h3 id="borrar-bodega-titulo" className="text-base font-bold text-acento-fuerte">
            {usada ? `«${bodega.nombre}» no se puede borrar` : `¿Borrar la bodega «${bodega.nombre}»?`}
          </h3>
        </div>
        <div className="px-6 py-5 text-sm text-texto-2 space-y-2">
          {usada ? (
            <>
              <p>
                Ya aparece en <strong className="text-texto cifra">{bodega.usos} {bodega.usos === 1 ? 'registro' : 'registros'}</strong> entre
                PQRS y notas crédito. Si se borrara, perderían de dónde salió su producto.
              </p>
              <p>Desactívala: deja de ofrecerse en lo nuevo y lo que ya la tiene la conserva.</p>
            </>
          ) : (
            <p>Nada la usa todavía. Se borra del todo y no se puede deshacer.</p>
          )}
        </div>
        <div className="flex justify-end gap-3 px-6 py-4 bg-superficie-2 border-t border-borde rounded-b-2xl">
          <button onClick={onCancelar} autoFocus
                  className="px-4 py-2 rounded-lg border border-borde text-sm font-semibold text-texto-2 hover:bg-white transition">
            Cancelar
          </button>
          {usada ? (
            bodega.activo && (
              <button onClick={onDesactivar}
                      className="px-4 py-2 rounded-lg bg-acento-fuerte hover:bg-acento text-white text-sm font-bold transition">
                Desactivarla
              </button>
            )
          ) : (
            <button onClick={onBorrar} disabled={borrando}
                    className="px-4 py-2 rounded-lg bg-negativo-vivo hover:bg-negativo text-white text-sm font-bold transition disabled:opacity-50">
              {borrando ? 'Borrando…' : 'Sí, borrar'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

export default function Bodegas() {
  const queryClient = useQueryClient()
  const [nueva, setNueva] = useState('')
  const [aviso, setAviso] = useState(null)
  const [borrando, setBorrando] = useState(null)

  const { data: lista = [], isLoading } = useQuery({
    queryKey: ['bodegas', 'admin'],
    queryFn: () => api.get('/bodegas/todas').then(r => r.data),
  })
  const { data: usuarios = [] } = useQuery({
    queryKey: ['usuarios'],
    queryFn: () => api.get('/auth/usuarios').then(r => r.data),
  })
  // Las bodegas salen en notas crédito y en el flujo de PQRS: cualquier
  // cambio las refresca en todas partes.
  const refrescar = () => {
    queryClient.invalidateQueries({ queryKey: ['bodegas'] })
    queryClient.invalidateQueries({ queryKey: ['pqrs'] })
  }
  const fallo = (texto) => (err) => setAviso({ tono: 'negativo', texto: mensajeDeError(err, texto) })

  const crear = useMutation({
    mutationFn: () => api.post('/bodegas', { nombre: nueva.trim() }),
    onSuccess: ({ data }) => { setNueva(''); setAviso({ tono: 'positivo', texto: `Se creó «${data.nombre}».` }); refrescar() },
    onError: fallo('No se pudo crear la bodega.'),
  })
  const cambiar = useMutation({
    mutationFn: ({ id, cambios }) => api.patch(`/bodegas/${id}`, cambios),
    onError: fallo('No se pudo guardar el cambio.'),
  })
  const borrar = useMutation({
    mutationFn: (id) => api.delete(`/bodegas/${id}`),
    onSuccess: () => { setBorrando(null); setAviso({ tono: 'positivo', texto: 'Bodega borrada.' }); refrescar() },
    onError: (err) => { setBorrando(null); fallo('No se pudo borrar la bodega.')(err) },
  })
  const ocupado = crear.isPending || cambiar.isPending || borrar.isPending
  const guardar = (bodega) => (cambios, alTerminar) => cambiar.mutate({ id: bodega.id, cambios }, {
    onSuccess: () => { setAviso(null); alTerminar?.(); refrescar() },
  })

  return (
    <div className="bg-white rounded-xl border border-borde overflow-hidden">
      <div className="px-5 py-4 border-b border-borde">
        <h3 className="font-bold text-acento-fuerte flex items-center gap-2">
          <IconoPaquete tam={18} /> Bodegas
        </h3>
        <p className="text-xs text-texto-2 mt-0.5">
          De dónde sale el producto. Sus responsables son a quienes se les avisa primero en una nota crédito
          institucional y quienes confirman que el producto está bien. Las usan Notas crédito y el flujo de PQRS.
        </p>
      </div>

      <form className="px-5 py-3 border-b border-borde flex gap-2"
            onSubmit={(e) => { e.preventDefault(); if (nueva.trim()) crear.mutate() }}>
        <input value={nueva} onChange={(e) => setNueva(e.target.value)} maxLength={MAX_NOMBRE}
               placeholder="Nombre de la bodega nueva" aria-label="Bodega nueva" className={`${campo} flex-1`} />
        <button type="submit" disabled={!nueva.trim() || ocupado}
                className="px-3 py-1.5 rounded-lg text-sm font-semibold bg-acento-fuerte text-white disabled:opacity-40">
          Crear
        </button>
      </form>

      {aviso && (
        <div className={`px-5 py-2 text-sm border-b border-borde ${aviso.tono === 'negativo' ? 'bg-negativo-bg text-negativo' : 'bg-positivo-bg text-positivo'}`}>
          {aviso.texto}
        </div>
      )}

      <div className="divide-y divide-borde">
        {isLoading ? (
          <div className="px-5 py-8 text-center text-sm text-texto-2">Cargando...</div>
        ) : lista.map(b => (
          <FilaBodega key={`${b.id}-${b.nombre}-${b.activo}`} bodega={b} usuarios={usuarios} ocupado={ocupado}
                      onGuardar={guardar(b)} onBorrar={() => setBorrando(b)} />
        ))}
      </div>

      {borrando && (
        <ConfirmarBorrado
          bodega={borrando}
          borrando={borrar.isPending}
          onBorrar={() => borrar.mutate(borrando.id)}
          onDesactivar={() => { guardar(borrando)({ activo: false }); setBorrando(null) }}
          onCancelar={() => setBorrando(null)}
        />
      )}
    </div>
  )
}
