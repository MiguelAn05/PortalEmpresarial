/**
 * Flujos de PQRS: las plantillas de conceptos y las bodegas de despacho.
 *
 * Una plantilla dice qué conceptos se piden, en qué orden, para las PQRS de
 * un tipo de canal. Sus pasos son de tres clases: un concepto fijo, el de la
 * bodega de donde salió el producto, y el técnico de la causa («Asociado a»,
 * que se configura en su propia sección). Cambiar una plantilla afecta lo
 * que se inicie de aquí en adelante: las PQRS que ya van en camino conservan
 * su cadena. Ver `backend/app/modules/pqrs/flujo.py`.
 */
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api from '../../core/api.js'
import { mensajeDeError } from '../../core/errores.js'
import { IconoCerrar, IconoChevron, IconoRecargar } from '../../core/components/Iconos.jsx'
import { APLICA_A, CLASES_PASO, MAX_PASOS, mover, quitar } from '../pqrs/flujo.js'

const campo = 'rounded-lg border border-borde px-3 py-1.5 text-sm bg-white'

function EditorPlantilla({ plantilla, tipos, ocupado, onGuardar, onCancelar }) {
  const [nombre, setNombre] = useState(plantilla.nombre)
  const [aplicaA, setAplicaA] = useState(plantilla.aplica_a || '')
  const [activo, setActivo] = useState(plantilla.activo)
  const [pasos, setPasos] = useState(plantilla.pasos.map(p => ({ clase: p.clase, tipo_autorizacion_id: p.tipo_autorizacion_id || '' })))

  const cambiarPaso = (i, cambios) => setPasos(pasos.map((p, k) => (k === i ? { ...p, ...cambios } : p)))
  const listo = nombre.trim().length >= 2 && pasos.every(p => p.clase !== 'concepto' || p.tipo_autorizacion_id)

  return (
    <div className="px-5 py-4 space-y-3 bg-superficie-2/40">
      <div className="flex flex-wrap gap-2">
        <input value={nombre} onChange={(e) => setNombre(e.target.value)} maxLength={150} aria-label="Nombre del flujo"
               className={`${campo} flex-1 min-w-48`} />
        <select value={aplicaA} onChange={(e) => setAplicaA(e.target.value)} aria-label="Para qué canal" className={campo}>
          {Object.entries(APLICA_A).map(([v, etiqueta]) => <option key={v} value={v}>{etiqueta}</option>)}
        </select>
        <label className="inline-flex items-center gap-1.5 text-xs text-texto-2">
          <input type="checkbox" checked={activo} onChange={(e) => setActivo(e.target.checked)} /> Activo
        </label>
      </div>

      <ol className="space-y-1.5">
        {pasos.map((p, i) => (
          <li key={i} className="flex flex-wrap items-center gap-2 rounded-lg border border-borde bg-white px-3 py-2">
            <span className="cifra text-xs font-semibold text-texto-3 w-5">{i + 1}</span>
            <select value={p.clase} onChange={(e) => cambiarPaso(i, { clase: e.target.value, tipo_autorizacion_id: '' })}
                    aria-label={`Clase del paso ${i + 1}`} className={`${campo} w-64`}>
              {Object.entries(CLASES_PASO).map(([v, etiqueta]) => <option key={v} value={v}>{etiqueta}</option>)}
            </select>
            {p.clase === 'concepto' ? (
              <select value={p.tipo_autorizacion_id} onChange={(e) => cambiarPaso(i, { tipo_autorizacion_id: Number(e.target.value) || '' })}
                      aria-label={`Concepto del paso ${i + 1}`} className={`${campo} flex-1 min-w-48`}>
                <option value="">Elige el concepto…</option>
                {tipos.map(t => <option key={t.id} value={t.id}>{t.nombre} — {t.area_autorizadora}</option>)}
              </select>
            ) : (
              <span className="flex-1 text-xs text-texto-3">
                {p.clase === 'bodega'
                  ? 'Se resuelve con la bodega que se elija en la PQRS.'
                  : 'Se resuelve con el «Asociado a» de la PQRS.'}
              </span>
            )}
            <button type="button" onClick={() => setPasos(mover(pasos, i, -1))} disabled={i === 0}
                    aria-label="Subir" className="p-1 text-texto-3 hover:text-texto disabled:opacity-30">
              <IconoChevron tam={14} className="-rotate-90" />
            </button>
            <button type="button" onClick={() => setPasos(mover(pasos, i, 1))} disabled={i === pasos.length - 1}
                    aria-label="Bajar" className="p-1 text-texto-3 hover:text-texto disabled:opacity-30">
              <IconoChevron tam={14} className="rotate-90" />
            </button>
            <button type="button" onClick={() => setPasos(quitar(pasos, i))} aria-label="Quitar"
                    className="p-1 text-texto-3 hover:text-negativo">
              <IconoCerrar tam={14} />
            </button>
          </li>
        ))}
      </ol>

      <div className="flex flex-wrap justify-between gap-2">
        <button type="button" disabled={pasos.length >= MAX_PASOS}
                onClick={() => setPasos([...pasos, { clase: 'concepto', tipo_autorizacion_id: '' }])}
                className="px-3 py-1.5 rounded-lg text-sm font-semibold text-acento hover:bg-acento-suave disabled:opacity-40">
          + Agregar paso
        </button>
        <div className="flex gap-2">
          <button type="button" onClick={onCancelar} className="px-3 py-1.5 rounded-lg text-sm text-texto-2 hover:bg-superficie-2">
            Cancelar
          </button>
          <button type="button" disabled={!listo || ocupado}
                  onClick={() => onGuardar({
                    nombre, aplica_a: aplicaA || null, activo,
                    pasos: pasos.map(p => ({ clase: p.clase, tipo_autorizacion_id: p.clase === 'concepto' ? Number(p.tipo_autorizacion_id) : null })),
                  })}
                  className="px-3 py-1.5 rounded-lg text-sm font-semibold bg-acento-fuerte text-white disabled:opacity-40">
            Guardar
          </button>
        </div>
      </div>
      <p className="text-xs text-texto-3">Los cambios valen para los flujos que se inicien de aquí en adelante.</p>
    </div>
  )
}

function resumenPasos(plantilla) {
  return plantilla.pasos.map(p => (
    p.clase === 'bodega' ? 'Bodega' : p.clase === 'tecnico' ? 'Técnico (causa)' : p.concepto || '¿?'
  )).join(' → ')
}

export default function FlujosPQRS() {
  const queryClient = useQueryClient()
  const [editando, setEditando] = useState(null)   // id de plantilla, 'nueva', o null
  const [aviso, setAviso] = useState(null)

  const { data: tipos = [] } = useQuery({
    queryKey: ['tipos-autorizacion'],
    queryFn: () => api.get('/autorizaciones/tipos').then(r => r.data),
  })
  const { data: plantillas = [], isLoading } = useQuery({
    queryKey: ['pqrs', 'flujos', 'admin'],
    queryFn: () => api.get('/pqrs/flujos').then(r => r.data),
  })
  const { data: bodegas = [] } = useQuery({
    queryKey: ['pqrs', 'bodegas-despacho', 'admin'],
    queryFn: () => api.get('/pqrs/bodegas-despacho').then(r => r.data),
  })
  const refrescar = () => queryClient.invalidateQueries({ queryKey: ['pqrs'] })
  const fallo = (texto) => (err) => setAviso({ tono: 'negativo', texto: mensajeDeError(err, texto) })

  const guardarPlantilla = useMutation({
    mutationFn: ({ id, datos }) => (id === 'nueva' ? api.post('/pqrs/flujos', datos) : api.put(`/pqrs/flujos/${id}`, datos)),
    onSuccess: () => { setEditando(null); setAviso({ tono: 'positivo', texto: 'Flujo guardado.' }); refrescar() },
    onError: fallo('No se pudo guardar el flujo.'),
  })
  const guardarBodega = useMutation({
    mutationFn: ({ id, datos }) => (id ? api.put(`/pqrs/bodegas-despacho/${id}`, datos) : api.post('/pqrs/bodegas-despacho', datos)),
    onSuccess: () => { setAviso(null); refrescar() },
    onError: fallo('No se pudo guardar la bodega.'),
  })
  const [bodegaNueva, setBodegaNueva] = useState('')
  const ocupado = guardarPlantilla.isPending || guardarBodega.isPending

  return (
    <div className="bg-white rounded-xl border border-borde overflow-hidden">
      <div className="px-5 py-4 border-b border-borde">
        <h3 className="font-bold text-acento-fuerte flex items-center gap-2">
          <IconoRecargar tam={18} /> Flujos de PQRS
        </h3>
        <p className="text-xs text-texto-2 mt-0.5">
          Qué conceptos se piden, en qué orden, según el canal. Al aprobarse uno, el portal pide el siguiente solo.
          El concepto técnico de cada causa se elige en «Asociado a».
        </p>
      </div>

      {aviso && (
        <div className={`px-5 py-2 text-sm border-b border-borde ${aviso.tono === 'negativo' ? 'bg-negativo-bg text-negativo' : 'bg-positivo-bg text-positivo'}`}>
          {aviso.texto}
        </div>
      )}

      <div className="divide-y divide-borde">
        {isLoading ? (
          <div className="px-5 py-8 text-center text-sm text-texto-2">Cargando...</div>
        ) : plantillas.map(f => (
          editando === f.id ? (
            <EditorPlantilla key={f.id} plantilla={f} tipos={tipos} ocupado={ocupado}
                             onCancelar={() => setEditando(null)}
                             onGuardar={(datos) => guardarPlantilla.mutate({ id: f.id, datos })} />
          ) : (
            <div key={f.id} className="px-5 py-3 flex flex-wrap items-center gap-3">
              <div className="flex-1 min-w-0">
                <div className={`text-sm font-medium ${f.activo ? 'text-texto' : 'text-texto-3 line-through'}`}>
                  {f.nombre} <span className="text-xs text-texto-3 font-normal">· {APLICA_A[f.aplica_a || '']}</span>
                </div>
                <div className="text-xs text-texto-3 truncate">{resumenPasos(f) || 'Sin pasos'}</div>
              </div>
              <button type="button" onClick={() => setEditando(f.id)}
                      className="px-2.5 py-1 rounded-lg text-xs font-semibold text-acento hover:bg-acento-suave">
                Editar
              </button>
            </div>
          )
        ))}
        {editando === 'nueva' ? (
          <EditorPlantilla plantilla={{ nombre: '', aplica_a: '', activo: true, pasos: [] }} tipos={tipos} ocupado={ocupado}
                           onCancelar={() => setEditando(null)}
                           onGuardar={(datos) => guardarPlantilla.mutate({ id: 'nueva', datos })} />
        ) : (
          <div className="px-5 py-3">
            <button type="button" onClick={() => setEditando('nueva')}
                    className="px-3 py-1.5 rounded-lg text-sm font-semibold text-acento hover:bg-acento-suave">
              + Nuevo flujo
            </button>
          </div>
        )}
      </div>

      {/* Las bodegas de despacho: de dónde salió el producto, y qué concepto pide. */}
      <div className="border-t border-borde">
        <div className="px-5 pt-4 pb-2">
          <p className="etiqueta">Bodegas de despacho</p>
          <p className="text-xs text-texto-3 mt-0.5">
            De dónde salió el producto. No son las bodegas de Notas crédito, que es a donde vuelve.
          </p>
        </div>
        <div className="divide-y divide-borde">
          {bodegas.map(b => (
            <div key={`${b.id}-${b.tipo_autorizacion_id}-${b.activo}`} className="px-5 py-2.5 flex flex-wrap items-center gap-3">
              <span className={`text-sm font-medium w-32 ${b.activo ? 'text-texto' : 'text-texto-3 line-through'}`}>{b.nombre}</span>
              <select value={b.tipo_autorizacion_id || ''} disabled={ocupado} aria-label={`Concepto de ${b.nombre}`}
                      onChange={(e) => guardarBodega.mutate({ id: b.id, datos: { nombre: b.nombre, activo: b.activo, tipo_autorizacion_id: Number(e.target.value) || null } })}
                      className={`${campo} flex-1 min-w-48`}>
                <option value="">Sin concepto</option>
                {tipos.map(t => <option key={t.id} value={t.id}>{t.nombre} — {t.area_autorizadora}</option>)}
              </select>
              <button type="button" disabled={ocupado}
                      onClick={() => guardarBodega.mutate({ id: b.id, datos: { nombre: b.nombre, tipo_autorizacion_id: b.tipo_autorizacion_id, activo: !b.activo } })}
                      className="px-2.5 py-1 rounded-lg text-xs font-semibold text-texto-2 hover:bg-superficie-2">
                {b.activo ? 'Desactivar' : 'Reactivar'}
              </button>
            </div>
          ))}
          <form className="px-5 py-3 flex gap-2"
                onSubmit={(e) => {
                  e.preventDefault()
                  if (bodegaNueva.trim()) {
                    guardarBodega.mutate({ id: null, datos: { nombre: bodegaNueva.trim(), tipo_autorizacion_id: null, activo: true } })
                    setBodegaNueva('')
                  }
                }}>
            <input value={bodegaNueva} onChange={(e) => setBodegaNueva(e.target.value)} maxLength={150}
                   placeholder="Bodega nueva" aria-label="Bodega nueva" className={`${campo} flex-1`} />
            <button type="submit" disabled={!bodegaNueva.trim() || ocupado}
                    className="px-3 py-1.5 rounded-lg text-sm font-semibold bg-acento-fuerte text-white disabled:opacity-40">
              Agregar
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
