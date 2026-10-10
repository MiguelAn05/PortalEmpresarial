/**
 * «Causa de la PQRS»: a qué está asociada y qué área la causó.
 *
 * Antes el área causante era un desplegable chiquito dentro de la cabecera,
 * opcional, y «Asociado a» no existía: se llevaba en el Excel de Calidad.
 * La mitad de las PQRS se cerraban sin causa y el informe no servía. Ahora
 * van juntas, las marca quien reparte y son obligatorias para
 * cerrar a mano (el servidor lo exige; aquí solo se avisa antes).
 *
 * La lista se busca escribiendo («ME», «peso», «entrega») o bajando por
 * grupos, y el asociado PROPONE el área causante. Ver `asociados.js`.
 */
import { useMemo, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../../core/api.js'
import { areasParaSelect, useAreas } from '../../core/areas.js'
import { useCanales } from '../../core/canales.js'
import { mensajeDeError } from '../../core/errores.js'
import Boton from '../../core/components/Boton.jsx'
import { IconoBuscar } from '../../core/components/Iconos.jsx'
import {
  agruparAsociados, areaPropuesta, etiquetaAsociado, tipoDeCanal, useAsociados,
} from './asociados.js'

/**
 * Vive dentro del modo «Clasificar» del panel Gestionar (`GestionarPQRS.jsx`),
 * sin tarjeta propia: el panel ya dice qué es y si falta para cerrar.
 */
export default function CausaPQRS({ pqrs, puedeMarcar }) {
  return (
    <div>
      <p className="text-xs text-texto-2 mb-3">
        De dónde salió el problema, no quién lo está atendiendo. De aquí salen los informes y las OMP.
      </p>
      {puedeMarcar
        ? <EditorCausa key={`${pqrs.asociado_id}-${pqrs.area_causante}`} pqrs={pqrs} />
        : <LecturaCausa pqrs={pqrs} />}
    </div>
  )
}

function LecturaCausa({ pqrs }) {
  return (
    <div className="grid sm:grid-cols-2 gap-3">
      <div>
        <div className="text-xs text-texto-2 font-semibold uppercase tracking-wide">Asociado a</div>
        <div className="text-sm text-texto font-medium mt-0.5">
          {pqrs.asociado ? etiquetaAsociado(pqrs.asociado) : 'Sin definir'}
        </div>
      </div>
      <div>
        <div className="text-xs text-texto-2 font-semibold uppercase tracking-wide">Área causante</div>
        <div className="text-sm text-texto font-medium mt-0.5">{pqrs.area_causante || 'Sin definir'}</div>
      </div>
      {(!pqrs.asociado_id || !pqrs.area_causante) && (
        <p className="sm:col-span-2 text-xs text-texto-2">
          La marca Servicio al Cliente. Si sabes cuál fue, escríbelo en un comentario.
        </p>
      )}
    </div>
  )
}

function EditorCausa({ pqrs }) {
  const queryClient = useQueryClient()
  const asociados = useAsociados()
  const listaAreas = useAreas()
  const canales = useCanales()

  const [asociadoId, setAsociadoId] = useState(pqrs.asociado_id ?? null)
  const [area, setArea] = useState(pqrs.area_causante || '')
  const [busqueda, setBusqueda] = useState('')
  const [abierta, setAbierta] = useState(!pqrs.asociado_id)
  const [error, setError] = useState('')

  // El que tiene puede estar desactivado: se sigue mostrando, no se pierde.
  const elegido = asociados.find(a => a.id === asociadoId)
    ?? (pqrs.asociado && pqrs.asociado.id === asociadoId ? pqrs.asociado : null)
  const aplicaA = tipoDeCanal(canales, pqrs.canal_atencion)
  const grupos = useMemo(
    () => agruparAsociados(asociados, { aplicaA, busqueda }),
    [asociados, aplicaA, busqueda],
  )

  const cambio = (asociadoId ?? null) !== (pqrs.asociado_id ?? null)
    || (area || null) !== (pqrs.area_causante || null)

  const guardar = useMutation({
    mutationFn: () => api.patch(`/pqrs/${pqrs.id}/causa`, {
      asociado_id: asociadoId, area_causante: area || null,
    }),
    onSuccess: () => {
      setError('')
      queryClient.invalidateQueries({ queryKey: ['pqrs', String(pqrs.id)] })
      queryClient.invalidateQueries({ queryKey: ['pqrs'] })
    },
    onError: (err) => setError(mensajeDeError(err, 'No se pudo guardar la causa.')),
  })

  const elegir = (a) => {
    setArea(areaPropuesta(a, elegido, area))
    setAsociadoId(a.id)
    setBusqueda('')
    setAbierta(false)
  }

  const sugerida = elegido?.area_sugerida

  return (
    <div className="space-y-4">
      {/* Asociado a */}
      <div>
        <label className="block text-xs font-semibold text-texto-2 uppercase tracking-wide mb-1.5">
          Asociado a
        </label>

        {elegido && !abierta ? (
          <div className="flex items-center justify-between gap-3 rounded-lg border border-borde px-3 py-2.5">
            <div className="min-w-0">
              <div className="text-sm font-medium text-texto">{etiquetaAsociado(elegido)}</div>
              {elegido.sugiere_omp && (
                <div className="text-xs text-texto-2 mt-0.5">Puede volverse una OMP.</div>
              )}
            </div>
            <button type="button" onClick={() => setAbierta(true)}
                    className="text-xs font-semibold text-acento hover:underline flex-shrink-0">
              Cambiar
            </button>
          </div>
        ) : (
          <div className="rounded-lg border border-borde">
            <div className="flex items-center gap-2 px-3 border-b border-borde">
              <IconoBuscar tam={15} className="text-texto-3" />
              <input
                value={busqueda}
                onChange={(e) => setBusqueda(e.target.value)}
                placeholder="Busca por sigla o palabra: ME, peso, entrega…"
                aria-label="Buscar asociado"
                autoFocus={Boolean(elegido)}
                className="w-full py-2.5 text-sm text-texto placeholder-texto-3 focus:outline-none bg-transparent"
              />
              {elegido && (
                <button type="button" onClick={() => { setAbierta(false); setBusqueda('') }}
                        className="text-xs font-semibold text-texto-2 hover:text-texto flex-shrink-0">
                  Cancelar
                </button>
              )}
            </div>
            {/* Caja acotada a propósito: veinte opciones no pueden empujar
                fuera de la pantalla el resto del detalle. */}
            <div className="max-h-72 overflow-y-auto py-1" role="listbox" aria-label="Asociado a">
              {asociados.length === 0 && (
                <p className="px-3 py-3 text-xs text-texto-2">Cargando la lista…</p>
              )}
              {asociados.length > 0 && grupos.length === 0 && (
                <p className="px-3 py-3 text-xs text-texto-2">
                  Nada coincide con «{busqueda}». Prueba con la sigla o con otra palabra.
                </p>
              )}
              {grupos.map(({ grupo, items }) => (
                <div key={grupo} className="py-1">
                  <div className="px-3 pt-1 pb-1 text-[11px] font-bold text-texto-3 uppercase tracking-wide">
                    {grupo}
                  </div>
                  {items.map(a => (
                    <button
                      key={a.id} type="button" role="option" aria-selected={a.id === asociadoId}
                      onClick={() => elegir(a)}
                      className={`w-full flex items-baseline gap-2 text-left px-3 py-1.5 text-sm transition-colors ${
                        a.id === asociadoId ? 'bg-acento-suave text-acento-fuerte' : 'text-texto hover:bg-superficie-2'
                      }`}
                    >
                      <span className="cifra text-xs font-bold text-texto-2 w-12 flex-shrink-0">{a.codigo}</span>
                      <span className="flex-1">{a.nombre}</span>
                      {aplicaA && a.aplica_a === aplicaA && (
                        <span className="text-[11px] text-texto-2 flex-shrink-0">por el canal</span>
                      )}
                    </button>
                  ))}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Área causante */}
      <div>
        <label htmlFor={`area-causante-${pqrs.id}`}
               className="block text-xs font-semibold text-texto-2 uppercase tracking-wide mb-1.5">
          Área causante
        </label>
        <select
          id={`area-causante-${pqrs.id}`}
          value={area}
          onChange={(e) => setArea(e.target.value)}
          className="w-full px-3 py-2.5 rounded-lg border border-borde text-sm text-texto focus:outline-none focus:ring-2 focus:ring-acento"
        >
          <option value="">Sin definir</option>
          {areasParaSelect(listaAreas, area).map(a => <option key={a} value={a}>{a}</option>)}
        </select>
        {sugerida && (
          <p className="text-xs text-texto-2 mt-1">
            {area === sugerida
              ? `Propuesta por «${elegido.nombre}». Cámbiala si en este caso fue otra.`
              : `«${elegido.nombre}» suele ser de ${sugerida}.`}
          </p>
        )}
      </div>

      {error && <p role="alert" className="text-sm text-negativo">{error}</p>}

      {cambio && (
        <div className="flex justify-end gap-2">
          <Boton onClick={() => {
            setAsociadoId(pqrs.asociado_id ?? null)
            setArea(pqrs.area_causante || '')
            setAbierta(!pqrs.asociado_id)
            setError('')
          }}>
            Descartar
          </Boton>
          <Boton tono="primario" cargando={guardar.isPending} textoCargando="Guardando…"
                 onClick={() => guardar.mutate()}>
            Guardar causa
          </Boton>
        </div>
      )}
    </div>
  )
}
