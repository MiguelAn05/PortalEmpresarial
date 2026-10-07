/**
 * «Asociado a»: el catálogo de causas de las PQRS.
 *
 * Es la lista con la que Calidad clasificaba en Excel (Mala entrega, Calidad
 * del producto…). Aquí se agregan, se corrigen y se desactivan sin
 * desplegar, y sobre todo se completa el ÁREA SUGERIDA de cada uno: es la
 * que se propone como área causante al elegirlo. Ver
 * `backend/app/modules/pqrs/asociados.py`.
 *
 * Las PQRS guardan el asociado por su id: renombrarlo no rompe los informes.
 * No se borra, se desactiva — las PQRS que ya lo tenían lo conservan.
 */
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api from '../../core/api.js'
import { areasParaSelect, useAreas } from '../../core/areas.js'
import { mensajeDeError } from '../../core/errores.js'
import { IconoEditar, IconoEtiqueta } from '../../core/components/Iconos.jsx'
import { LIMITES_ASOCIADO } from '../pqrs/asociados.js'

const APLICA_A = {
  '': 'Cualquier canal',
  sede: 'Punto de venta',
  institucional: 'Venta institucional',
}

const campo = 'rounded-lg border border-borde px-3 py-1.5 text-sm'
const VACIO = { codigo: '', nombre: '', grupo: '', area_sugerida: '', aplica_a: '', sugiere_omp: false }

function Formulario({ valores, onCambio, areas, grupos, idBase }) {
  const poner = (clave) => (e) => onCambio({ ...valores, [clave]: e.target.type === 'checkbox' ? e.target.checked : e.target.value })
  return (
    <div className="flex flex-wrap gap-2">
      <input id={`${idBase}-codigo`} value={valores.codigo} onChange={poner('codigo')}
             maxLength={LIMITES_ASOCIADO.codigo} placeholder="Sigla (ME)" aria-label="Sigla"
             className={`${campo} w-28 uppercase`} />
      <input id={`${idBase}-nombre`} value={valores.nombre} onChange={poner('nombre')}
             maxLength={LIMITES_ASOCIADO.nombre} placeholder="Nombre" aria-label="Nombre"
             className={`${campo} flex-1 min-w-48`} />
      <input id={`${idBase}-grupo`} value={valores.grupo} onChange={poner('grupo')}
             maxLength={LIMITES_ASOCIADO.grupo} placeholder="Grupo" aria-label="Grupo"
             list={`${idBase}-grupos`} className={`${campo} w-44`} />
      <datalist id={`${idBase}-grupos`}>
        {grupos.map(g => <option key={g} value={g} />)}
      </datalist>
      <select value={valores.area_sugerida} onChange={poner('area_sugerida')} aria-label="Área sugerida"
              className={`${campo} w-48`}>
        <option value="">Sin área sugerida</option>
        {areasParaSelect(areas, valores.area_sugerida).map(a => <option key={a} value={a}>{a}</option>)}
      </select>
      <select value={valores.aplica_a} onChange={poner('aplica_a')} aria-label="Aplica a"
              title="Se ofrece primero cuando la PQRS entró por ese tipo de canal"
              className={`${campo} w-44`}>
        {Object.entries(APLICA_A).map(([v, etiqueta]) => <option key={v} value={v}>{etiqueta}</option>)}
      </select>
      <label className="inline-flex items-center gap-1.5 text-xs text-texto-2">
        <input type="checkbox" checked={valores.sugiere_omp} onChange={poner('sugiere_omp')} />
        Puede volverse OMP
      </label>
    </div>
  )
}

const completo = (v) => v.codigo.trim() && v.nombre.trim().length >= 2 && v.grupo.trim().length >= 2

function Fila({ asociado, areas, grupos, ocupado, onCambiar }) {
  const [editando, setEditando] = useState(false)
  const inicial = {
    codigo: asociado.codigo, nombre: asociado.nombre, grupo: asociado.grupo,
    area_sugerida: asociado.area_sugerida || '', aplica_a: asociado.aplica_a || '',
    sugiere_omp: asociado.sugiere_omp,
  }
  const [valores, setValores] = useState(inicial)

  if (editando) {
    return (
      <div className="px-5 py-3 space-y-2">
        <Formulario valores={valores} onCambio={setValores} areas={areas} grupos={grupos} idBase={`asociado-${asociado.id}`} />
        <div className="flex gap-2">
          <button type="button" disabled={ocupado || !completo(valores)}
                  onClick={() => onCambiar(valores, () => setEditando(false))}
                  className="px-3 py-1.5 rounded-lg text-sm font-semibold bg-acento-fuerte text-white disabled:opacity-40">
            Guardar
          </button>
          <button type="button" onClick={() => { setEditando(false); setValores(inicial) }}
                  className="px-3 py-1.5 rounded-lg text-sm text-texto-2 hover:bg-superficie-2">
            Cancelar
          </button>
        </div>
        <p className="text-xs text-texto-3">
          Las PQRS guardan el asociado, no su nombre: cambiarlo no mueve ningún informe.
        </p>
      </div>
    )
  }

  return (
    <div className="px-5 py-2.5 flex flex-wrap items-center gap-3">
      <span className="cifra font-mono text-xs px-1.5 py-0.5 rounded-md bg-superficie-2 text-texto-2 w-16 text-center flex-shrink-0">
        {asociado.codigo}
      </span>
      <div className="flex-1 min-w-0">
        <div className={`text-sm font-medium ${asociado.activo ? 'text-texto' : 'text-texto-3 line-through'}`}>
          {asociado.nombre}
        </div>
        <div className="text-xs text-texto-3 cifra">
          {asociado.area_sugerida ? `Propone ${asociado.area_sugerida}` : 'Sin área sugerida'}
          {asociado.aplica_a && ` · ${APLICA_A[asociado.aplica_a]}`}
          {asociado.sugiere_omp && ' · puede volverse OMP'}
          {` · ${asociado.pqrs} PQRS`}
          {!asociado.activo && ' · desactivado: no se ofrece'}
        </div>
      </div>
      {asociado.activo && (
        <button type="button" onClick={() => setEditando(true)} aria-label={`Editar ${asociado.nombre}`}
                className="p-1.5 rounded-lg text-texto-2 hover:bg-superficie-2">
          <IconoEditar tam={15} />
        </button>
      )}
      <button type="button" disabled={ocupado} onClick={() => onCambiar({ activo: !asociado.activo })}
              className="px-2.5 py-1 rounded-lg text-xs font-semibold text-texto-2 hover:bg-superficie-2">
        {asociado.activo ? 'Desactivar' : 'Reactivar'}
      </button>
    </div>
  )
}

export default function Asociados() {
  const queryClient = useQueryClient()
  const areas = useAreas()
  const [nuevo, setNuevo] = useState(VACIO)
  const [aviso, setAviso] = useState(null)

  const { data: lista = [], isLoading } = useQuery({
    queryKey: ['pqrs', 'asociados', 'admin'],
    queryFn: () => api.get('/pqrs/asociados/todos').then(r => r.data),
  })
  const grupos = [...new Set(lista.map(a => a.grupo))]
  const refrescar = () => queryClient.invalidateQueries({ queryKey: ['pqrs', 'asociados'] })

  const crear = useMutation({
    mutationFn: () => api.post('/pqrs/asociados', { ...nuevo, area_sugerida: nuevo.area_sugerida || null, aplica_a: nuevo.aplica_a || null }),
    onSuccess: ({ data }) => {
      setNuevo(VACIO)
      setAviso({ tono: 'positivo', texto: `Se creó «${data.nombre}».` })
      refrescar()
    },
    onError: err => setAviso({ tono: 'negativo', texto: mensajeDeError(err, 'No se pudo crear.') }),
  })

  const cambiar = useMutation({
    mutationFn: ({ id, cambios }) => api.patch(`/pqrs/asociados/${id}`, cambios),
    onError: err => setAviso({ tono: 'negativo', texto: mensajeDeError(err, 'No se pudo guardar el cambio.') }),
  })
  const onCambiar = (asociado) => (cambios, alTerminar) => {
    cambiar.mutate({ id: asociado.id, cambios }, {
      onSuccess: () => { setAviso(null); alTerminar?.(); refrescar() },
    })
  }
  const ocupado = crear.isPending || cambiar.isPending
  const sinArea = lista.filter(a => a.activo && !a.area_sugerida).length

  return (
    <div className="bg-white rounded-xl border border-borde overflow-hidden">
      <div className="px-5 py-4 border-b border-borde">
        <h3 className="font-bold text-acento-fuerte flex items-center gap-2">
          <IconoEtiqueta tam={18} /> «Asociado a» de las PQRS
        </h3>
        <p className="text-xs text-texto-2 mt-0.5">
          La causa con la que Servicio al Cliente clasifica cada PQRS. El área sugerida se
          propone como área causante al elegirlo.
          {sinArea > 0 && ` Hay ${sinArea} sin área sugerida.`}
        </p>
      </div>

      <form className="px-5 py-3 border-b border-borde space-y-2"
            onSubmit={e => { e.preventDefault(); if (completo(nuevo)) crear.mutate() }}>
        <Formulario valores={nuevo} onCambio={setNuevo} areas={areas} grupos={grupos} idBase="asociado-nuevo" />
        <button type="submit" disabled={!completo(nuevo) || ocupado}
                className="px-3 py-1.5 rounded-lg text-sm font-semibold bg-acento-fuerte text-white disabled:opacity-40">
          Crear
        </button>
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
          lista.map(a => (
            <Fila key={`${a.id}-${a.nombre}-${a.area_sugerida}-${a.activo}`} asociado={a} areas={areas}
                  grupos={grupos} ocupado={ocupado} onCambiar={onCambiar(a)} />
          ))
        )}
      </div>
    </div>
  )
}
