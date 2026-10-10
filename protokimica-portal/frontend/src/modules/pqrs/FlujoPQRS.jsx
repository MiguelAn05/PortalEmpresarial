/**
 * «Flujo de conceptos»: la cadena de autorizaciones de la PQRS, que avanza
 * sola. Quien reparte la inicia (con la propuesta ya resuelta por bodega y
 * por causa), y el portal pide el siguiente concepto cada vez que se aprueba
 * uno. Si alguien rechaza o devuelve, se detiene y quien reparte decide.
 *
 * Todo lo que es regla vive en el servidor (`pqrs/flujo.py`); aquí se
 * muestra y se edita la lista antes de mandarla (`flujo.js`).
 *
 * Vive dentro del modo «Conceptos» del panel Gestionar (`GestionarPQRS.jsx`),
 * sin tarjeta propia: pedir un concepto suelto y mover el flujo son la misma
 * decisión —quién tiene que opinar— y estaban en dos tarjetas separadas.
 */
import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useFlujo } from './useFlujo.js'
import api from '../../core/api.js'
import { mensajeDeError } from '../../core/errores.js'
import Boton from '../../core/components/Boton.jsx'
import { Esqueleto } from '../../core/components/Cargando.jsx'
import { IconoAlerta, IconoCerrar, IconoCheck, IconoChevron } from '../../core/components/Iconos.jsx'
import {
  ESTADOS_FLUJO, ESTADOS_PASO, ORIGENES, agregar, mover, paraEnviar, quitar, ultimoDetenido,
} from './flujo.js'
import { Insignia } from './piezas.jsx'

const claseCampo = 'w-full px-3 py-2 rounded-lg border border-borde text-sm text-texto bg-white focus:outline-none focus:ring-2 focus:ring-acento'

/** La cadena tal como va: un renglón por concepto, con su estado. */
function Cadena({ pasos }) {
  return (
    <ol className="space-y-1.5">
      {pasos.map((p, i) => {
        const estado = ESTADOS_PASO[p.estado] || { label: p.estado, tono: 'neutro' }
        return (
          <li key={p.id ?? `${p.tipo_autorizacion_id}-${i}`}
              className={`flex items-center gap-3 rounded-lg px-3 py-2 ${p.estado === 'en_curso' ? 'bg-acento-suave' : 'bg-superficie-2/60'}`}>
            <span className={`w-6 h-6 rounded-full grid place-items-center text-[11px] font-semibold flex-shrink-0 ${
              p.estado === 'aprobado' ? 'bg-positivo-vivo text-white'
                : p.estado === 'en_curso' ? 'bg-acento-fuerte text-white'
                  : 'bg-superficie border border-borde text-texto-3'
            }`}>
              {p.estado === 'aprobado' ? <IconoCheck tam={12} /> : i + 1}
            </span>
            <div className="min-w-0 flex-1">
              <div className="text-sm font-medium text-texto truncate">{p.concepto}</div>
              <div className="text-xs text-texto-3 truncate">
                {p.area}{p.origen && ORIGENES[p.origen] ? ` · ${ORIGENES[p.origen]}` : ''}
                {p.respondida_por ? ` · respondió ${p.respondida_por}` : ''}
              </div>
            </div>
            <Insignia tono={estado.tono}>{p.estado === 'en_curso' ? `Esperando a ${p.area}` : estado.label}</Insignia>
          </li>
        )
      })}
    </ol>
  )
}

/** Editar una lista de pasos: mover, quitar y agregar conceptos. */
function EditorPasos({ pasos, onCambio, tipos }) {
  const [nuevo, setNuevo] = useState('')
  return (
    <div className="space-y-2">
      {pasos.length === 0 && <p className="text-xs text-texto-2">Sin pasos. Agrega al menos un concepto.</p>}
      <ol className="space-y-1.5">
        {pasos.map((p, i) => (
          <li key={`${p.id ?? 'n'}-${p.tipo_autorizacion_id}`} className="flex items-center gap-2 rounded-lg border border-borde bg-white px-3 py-2">
            <span className="cifra text-xs font-semibold text-texto-3 w-5">{i + 1}</span>
            <div className="min-w-0 flex-1">
              <div className="text-sm text-texto truncate">{p.concepto}</div>
              <div className="text-xs text-texto-3 truncate">{p.area}{ORIGENES[p.origen] ? ` · ${ORIGENES[p.origen]}` : ''}</div>
            </div>
            <button type="button" onClick={() => onCambio(mover(pasos, i, -1))} disabled={i === 0}
                    aria-label={`Subir ${p.concepto}`} className="p-1 rounded text-texto-3 hover:text-texto disabled:opacity-30">
              <IconoChevron tam={14} className="-rotate-90" />
            </button>
            <button type="button" onClick={() => onCambio(mover(pasos, i, 1))} disabled={i === pasos.length - 1}
                    aria-label={`Bajar ${p.concepto}`} className="p-1 rounded text-texto-3 hover:text-texto disabled:opacity-30">
              <IconoChevron tam={14} className="rotate-90" />
            </button>
            <button type="button" onClick={() => onCambio(quitar(pasos, i))}
                    aria-label={`Quitar ${p.concepto}`} className="p-1 rounded text-texto-3 hover:text-negativo">
              <IconoCerrar tam={14} />
            </button>
          </li>
        ))}
      </ol>
      <div className="flex gap-2">
        <select value={nuevo} onChange={(e) => setNuevo(e.target.value)} aria-label="Agregar un concepto" className={claseCampo}>
          <option value="">Agregar un concepto…</option>
          {tipos.filter(t => !pasos.some(p => p.tipo_autorizacion_id === t.id)).map(t => (
            <option key={t.id} value={t.id}>{t.nombre} — {t.area_autorizadora}</option>
          ))}
        </select>
        <Boton disabled={!nuevo} onClick={() => {
          onCambio(agregar(pasos, tipos.find(t => String(t.id) === nuevo)))
          setNuevo('')
        }}>
          Agregar
        </Boton>
      </div>
    </div>
  )
}

export default function FlujoPQRS({ pqrs, tipos }) {
  const queryClient = useQueryClient()
  const [editando, setEditando] = useState(null)   // la lista que se está armando, o null
  const [error, setError] = useState('')

  const { data: flujo, isLoading } = useFlujo(pqrs.id)

  const refrescar = () => {
    queryClient.invalidateQueries({ queryKey: ['pqrs', String(pqrs.id)] })
    queryClient.invalidateQueries({ queryKey: ['autorizaciones', String(pqrs.id)] })
    queryClient.invalidateQueries({ queryKey: ['pqrs'] })
  }
  const accion = useMutation({
    mutationFn: ({ metodo, ruta, cuerpo }) => api[metodo](`/pqrs/${pqrs.id}${ruta}`, cuerpo),
    onSuccess: () => { setError(''); setEditando(null); refrescar() },
    onError: (err) => setError(mensajeDeError(err, 'No se pudo mover el flujo.')),
  })

  if (isLoading) return <Esqueleto alto="h-24" className="rounded-lg" />
  if (!flujo) return null

  const { estado, pasos, propuesta, bodegas, puede_gestionar: puede } = flujo
  const estadoFlujo = ESTADOS_FLUJO[estado] || ESTADOS_FLUJO.sin_flujo
  const pendientes = pasos.filter(p => p.estado === 'pendiente')
  const detenido = ultimoDetenido(pasos)
  const sinNada = estado === 'sin_flujo' || estado === 'completa'
  // Ninguna plantilla sirve para su tipo y su canal (una felicitación, una
  // queja sin plantilla): se dice por qué y los pasos se arman a mano si
  // hacen falta. Un editor vacío ahí se leía como un flujo roto.
  const sinPlantilla = sinNada && propuesta && !propuesta.flujo

  // Nadie puede moverlo y no hay nada que ver: no dice nada.
  if (!puede && !pasos.length) return null

  const iniciar = (lista) => accion.mutate({ metodo: 'post', ruta: '/flujo/iniciar', cuerpo: { pasos: paraEnviar(lista) } })
  const guardarPendientes = (lista) => accion.mutate({ metodo: 'put', ruta: '/flujo/pasos', cuerpo: { pasos: paraEnviar(lista) } })

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2 mb-3">
        <span className="etiqueta">Flujo de conceptos</span>
        <Insignia tono={estadoFlujo.tono}>{estadoFlujo.label}</Insignia>
        <span className="text-xs text-texto-3 flex-1 min-w-48">
          Al aprobarse uno, el portal pide el siguiente solo. Si alguien rechaza o devuelve, se detiene y vuelve a Servicio al Cliente.
        </span>
      </div>

      {pasos.length > 0 && <div className="mb-4"><Cadena pasos={pasos} /></div>}

      {puede && (
        <div className="space-y-3">
          {/* Antes de iniciar: la bodega y la propuesta, que se puede ajustar. */}
          {sinPlantilla && editando === null && (
            <div className="border-t border-borde pt-4 space-y-3">
              <p className="text-sm text-texto-2">{propuesta.sin_plantilla}</p>
              <div className="flex justify-end">
                <Boton onClick={() => setEditando([])}>Armar los pasos a mano</Boton>
              </div>
            </div>
          )}

          {sinNada && propuesta && !(sinPlantilla && editando === null) && (
            <div className="space-y-3 border-t border-borde pt-4">
              {!sinPlantilla && <div className="grid sm:grid-cols-[1fr_auto] gap-3 items-end">
                <div>
                  <label htmlFor="flujo-bodega" className="etiqueta block mb-1.5">Bodega de despacho</label>
                  <select id="flujo-bodega" value={flujo.bodega_despacho_id ?? ''} className={claseCampo}
                          onChange={(e) => accion.mutate({
                            metodo: 'patch', ruta: '/bodega-despacho',
                            cuerpo: { bodega_despacho_id: e.target.value ? Number(e.target.value) : null },
                          })}>
                    <option value="">¿De dónde salió el producto?</option>
                    {bodegas.map(b => <option key={b.id} value={b.id}>{b.nombre}</option>)}
                  </select>
                </div>
                <span className="text-xs text-texto-3 pb-2">Plantilla: {propuesta.flujo.nombre}</span>
              </div>}

              {propuesta.faltan.map(f => (
                <p key={f.clase} className="flex items-start gap-1.5 text-xs text-alerta bg-alerta-bg rounded-lg px-3 py-2">
                  <IconoAlerta tam={13} className="mt-0.5" /> {f.mensaje}
                </p>
              ))}

              <EditorPasos pasos={editando ?? propuesta.pasos} onCambio={setEditando} tipos={tipos} />

              <div className="flex justify-end gap-2">
                {sinPlantilla && <Boton onClick={() => setEditando(null)}>Cancelar</Boton>}
                <Boton tono="primario" cargando={accion.isPending} textoCargando="Iniciando…"
                       disabled={!(editando ?? propuesta.pasos).length}
                       onClick={() => iniciar(editando ?? propuesta.pasos)}>
                  {estado === 'completa' ? 'Iniciar otro flujo' : 'Iniciar flujo'}
                </Boton>
              </div>
            </div>
          )}

          {/* Detenido: quien reparte decide qué sigue. */}
          {estado === 'detenida' && !editando && (
            <div className="border-t border-borde pt-4 space-y-2">
              <p className="text-sm text-texto">
                <strong>{detenido?.concepto}</strong> salió {detenido?.estado === 'devuelto' ? 'devuelto' : 'rechazado'}.
                ¿Qué sigue?
              </p>
              <div className="flex flex-wrap gap-2">
                <Boton tono="primario" cargando={accion.isPending}
                       onClick={() => accion.mutate({ metodo: 'post', ruta: '/flujo/reanudar', cuerpo: { repetir: true } })}>
                  Volver a pedir {detenido?.concepto}
                </Boton>
                {pendientes.length > 0 && (
                  <Boton onClick={() => accion.mutate({ metodo: 'post', ruta: '/flujo/reanudar', cuerpo: { repetir: false } })}>
                    Seguir con {pendientes[0].concepto}
                  </Boton>
                )}
                <Boton onClick={() => setEditando(pendientes)}>Cambiar lo que falta</Boton>
                {pendientes.length > 0 && (
                  <Boton onClick={() => accion.mutate({ metodo: 'post', ruta: '/flujo/terminar' })}>Terminar el flujo</Boton>
                )}
              </div>
            </div>
          )}

          {/* En curso o esperando: se puede cambiar lo que falta. */}
          {(estado === 'en_curso' || estado === 'lista') && !editando && (
            <div className="flex flex-wrap justify-end gap-2 border-t border-borde pt-4">
              {estado === 'lista' && pendientes.length > 0 && (
                <Boton tono="primario" cargando={accion.isPending}
                       onClick={() => accion.mutate({ metodo: 'post', ruta: '/flujo/reanudar', cuerpo: { repetir: false } })}>
                  Pedir {pendientes[0].concepto}
                </Boton>
              )}
              <Boton onClick={() => setEditando(pendientes)}>Cambiar lo que falta</Boton>
            </div>
          )}

          {/* Editando lo que falta de un flujo andando. */}
          {editando && !sinNada && (
            <div className="border-t border-borde pt-4 space-y-3">
              <p className="etiqueta">Lo que falta</p>
              <EditorPasos pasos={editando} onCambio={setEditando} tipos={tipos} />
              <div className="flex justify-end gap-2">
                <Boton onClick={() => setEditando(null)}>Cancelar</Boton>
                <Boton tono="primario" cargando={accion.isPending} onClick={() => guardarPendientes(editando)}>
                  Guardar pasos
                </Boton>
              </div>
            </div>
          )}

          {error && <p role="alert" className="text-sm text-negativo">{error}</p>}
        </div>
      )}
    </div>
  )
}
