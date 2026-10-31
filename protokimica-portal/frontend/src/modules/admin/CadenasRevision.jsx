/**
 * Las cadenas de revisión del Master Planner: qué firmas pide un documento y
 * en qué orden («Revisión contable»: Contador → Revisora Fiscal).
 *
 * Aquí se dice QUÉ pasos hay; QUIÉN firma cada uno se elige en cada tarea,
 * porque la misma cadena la recorre gente distinta según el documento. Al
 * activar el flujo en una tarea la cadena se copia, así que cambiarla aquí no
 * mueve los documentos que ya van en camino. No se borra: se desactiva.
 * Ver `backend/app/modules/master_planner/revision.py`.
 */
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api from '../../core/api.js'
import { mensajeDeError } from '../../core/errores.js'
import { IconoCerrar, IconoChevron, IconoEditar, IconoFicha } from '../../core/components/Iconos.jsx'
import { MAX_NOMBRE_PLANTILLA, MAX_PASOS_PLANTILLA } from '../masterPlanner/constants.js'
import { mover, quitar } from '../pqrs/flujo.js'

const campo = 'rounded-lg border border-borde px-3 py-1.5 text-sm bg-white'
const VACIA = { nombre: '', descripcion: '', pasos: [''] }

/** El formulario de una cadena, nueva o existente. */
function FormularioCadena({ inicial, ocupado, onGuardar, onCancelar }) {
  const [nombre, setNombre] = useState(inicial.nombre)
  const [descripcion, setDescripcion] = useState(inicial.descripcion || '')
  const [pasos, setPasos] = useState(inicial.pasos)
  const completos = nombre.trim() && pasos.length > 0 && pasos.every(p => p.trim())

  return (
    <form
      className="space-y-3"
      onSubmit={(e) => { e.preventDefault(); if (completos) onGuardar({ nombre, descripcion, pasos }) }}
    >
      <div className="grid gap-2 sm:grid-cols-2">
        <input value={nombre} onChange={(e) => setNombre(e.target.value)} maxLength={MAX_NOMBRE_PLANTILLA} autoFocus
               placeholder="Nombre, por ejemplo «Revisión contable»" aria-label="Nombre de la cadena" className={campo} />
        <input value={descripcion} onChange={(e) => setDescripcion(e.target.value)} maxLength={500}
               placeholder="Para qué documentos sirve (opcional)" aria-label="Descripción" className={campo} />
      </div>

      <div className="space-y-1.5">
        <p className="etiqueta">Quién firma, en orden</p>
        <p className="text-xs text-texto-3">
          Antes de la primera firma va siempre quien tiene la tarea: lo prepara y lo envía. Aquí van solo las firmas.
        </p>
        <ol className="space-y-1.5">
          {pasos.map((paso, i) => (
            <li key={i} className="flex items-center gap-2">
              <span className="w-6 text-right text-xs font-semibold text-texto-3 cifra">{i + 1}.</span>
              <input value={paso} maxLength={MAX_NOMBRE_PLANTILLA}
                     onChange={(e) => setPasos(pasos.map((p, k) => k === i ? e.target.value : p))}
                     placeholder="El papel de quien firma: «Contador», «Revisora Fiscal»"
                     aria-label={`Firma ${i + 1}`} className={`${campo} flex-1`} />
              <button type="button" disabled={i === 0} onClick={() => setPasos(mover(pasos, i, -1))}
                      aria-label={`Subir la firma ${i + 1}`}
                      className="p-1.5 rounded-lg text-texto-2 hover:bg-superficie-2 disabled:opacity-30">
                <IconoChevron tam={14} className="-rotate-90" />
              </button>
              <button type="button" disabled={i === pasos.length - 1} onClick={() => setPasos(mover(pasos, i, 1))}
                      aria-label={`Bajar la firma ${i + 1}`}
                      className="p-1.5 rounded-lg text-texto-2 hover:bg-superficie-2 disabled:opacity-30">
                <IconoChevron tam={14} className="rotate-90" />
              </button>
              <button type="button" disabled={pasos.length === 1} onClick={() => setPasos(quitar(pasos, i))}
                      aria-label={`Quitar la firma ${i + 1}`}
                      className="p-1.5 rounded-lg text-texto-3 hover:text-negativo hover:bg-negativo-bg disabled:opacity-30">
                <IconoCerrar tam={14} />
              </button>
            </li>
          ))}
        </ol>
        {pasos.length < MAX_PASOS_PLANTILLA ? (
          <button type="button" onClick={() => setPasos([...pasos, ''])}
                  className="ml-8 text-xs font-semibold text-acento hover:underline">
            + Agregar una firma
          </button>
        ) : (
          <p className="ml-8 text-xs text-texto-3">Máximo {MAX_PASOS_PLANTILLA} firmas por cadena.</p>
        )}
      </div>

      <div className="flex justify-end gap-2">
        <button type="button" onClick={onCancelar}
                className="px-3 py-1.5 rounded-lg text-xs text-texto-2 hover:bg-superficie-2">
          Cancelar
        </button>
        <button type="submit" disabled={!completos || ocupado}
                className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-acento-fuerte text-white disabled:opacity-40">
          Guardar
        </button>
      </div>
    </form>
  )
}

export default function CadenasRevision() {
  const queryClient = useQueryClient()
  const [editando, setEditando] = useState(null)      // id | 'nueva' | null
  const [aviso, setAviso] = useState(null)

  const { data: lista = [], isLoading } = useQuery({
    queryKey: ['mp-plantillas-revision', 'todas'],
    queryFn: () => api.get('/master-planner/plantillas-revision', { params: { todas: true } }).then(r => r.data),
  })
  // El formulario de las tareas pide las activas con otra clave: se refrescan las dos.
  const refrescar = () => queryClient.invalidateQueries({ queryKey: ['mp-plantillas-revision'] })
  const fallo = (texto) => (err) => setAviso({ tono: 'negativo', texto: mensajeDeError(err, texto) })

  const guardar = useMutation({
    mutationFn: ({ id, datos }) => id
      ? api.put(`/master-planner/plantillas-revision/${id}`, datos)
      : api.post('/master-planner/plantillas-revision', datos),
    onSuccess: ({ data }, { mensaje }) => {
      setEditando(null)
      setAviso({ tono: 'positivo', texto: mensaje || `Se guardó «${data.nombre}».` })
      refrescar()
    },
    onError: fallo('No se pudo guardar la cadena.'),
  })
  const datosDe = (p) => ({ nombre: p.nombre, descripcion: p.descripcion, activa: p.activa, pasos: p.pasos.map(s => s.nombre) })

  return (
    <div className="bg-white rounded-xl border border-borde overflow-hidden">
      <div className="px-5 py-4 border-b border-borde flex items-start justify-between gap-4">
        <div>
          <h3 className="font-bold text-acento-fuerte flex items-center gap-2">
            <IconoFicha tam={18} /> Cadenas de revisión de documentos
          </h3>
          <p className="text-xs text-texto-2 mt-0.5">
            Qué firmas pide un documento del Master Planner y en qué orden. Quién firma cada paso se elige en cada
            tarea. Cambiar una cadena no mueve los documentos que ya van en camino: cada tarea copió la suya.
          </p>
        </div>
        {editando !== 'nueva' && (
          <button type="button" onClick={() => { setEditando('nueva'); setAviso(null) }}
                  className="shrink-0 px-3 py-1.5 rounded-lg text-xs font-semibold bg-acento-fuerte text-white">
            + Nueva cadena
          </button>
        )}
      </div>

      {aviso && (
        <div className={`px-5 py-2 text-sm border-b border-borde ${aviso.tono === 'negativo' ? 'bg-negativo-bg text-negativo' : 'bg-positivo-bg text-positivo'}`}>
          {aviso.texto}
        </div>
      )}

      {editando === 'nueva' && (
        <div className="px-5 py-4 border-b border-borde bg-superficie-2">
          <FormularioCadena inicial={VACIA} ocupado={guardar.isPending}
                            onGuardar={(datos) => guardar.mutate({ datos })}
                            onCancelar={() => setEditando(null)} />
        </div>
      )}

      <div className="divide-y divide-borde">
        {isLoading ? (
          <div className="px-5 py-8 text-center text-sm text-texto-2">Cargando...</div>
        ) : lista.map(p => (
          <div key={p.id} className="px-5 py-3">
            {editando === p.id ? (
              <FormularioCadena inicial={datosDe(p)} ocupado={guardar.isPending}
                                onGuardar={(datos) => guardar.mutate({ id: p.id, datos: { ...datos, activa: p.activa } })}
                                onCancelar={() => setEditando(null)} />
            ) : (
              <div className="flex flex-wrap items-center gap-3">
                <div className="flex-1 min-w-0">
                  <div className={`text-sm font-medium ${p.activa ? 'text-texto' : 'text-texto-3 line-through'}`}>{p.nombre}</div>
                  <div className="text-xs text-texto-2">
                    Quien tiene la tarea → {p.pasos.map(s => s.nombre).join(' → ')}
                    {!p.activa && <span className="text-texto-3"> · desactivada: no se ofrece en las tareas nuevas</span>}
                  </div>
                  {p.descripcion && <div className="text-xs text-texto-3 mt-0.5">{p.descripcion}</div>}
                </div>
                <button type="button" onClick={() => { setEditando(p.id); setAviso(null) }} aria-label={`Editar ${p.nombre}`}
                        className="p-1.5 rounded-lg text-texto-2 hover:bg-superficie-2">
                  <IconoEditar tam={15} />
                </button>
                <button type="button" disabled={guardar.isPending}
                        onClick={() => guardar.mutate({
                          id: p.id, datos: { ...datosDe(p), activa: !p.activa },
                          mensaje: p.activa ? `«${p.nombre}» ya no se ofrece en las tareas nuevas.` : `«${p.nombre}» se ofrece otra vez.`,
                        })}
                        className="px-2.5 py-1 rounded-lg text-xs font-semibold text-texto-2 hover:bg-superficie-2">
                  {p.activa ? 'Desactivar' : 'Reactivar'}
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
