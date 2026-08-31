import { useState } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { crearPlantilla, actualizarPlantilla, eliminarPlantilla } from "../api"
import { TIPOS_PREGUNTA, normalizarSlug, urlPublica } from "../constants"
import { useCierreSeguro } from "../../../core/components/cierreSeguro"
import { IconoCerrar } from '../../../core/components/Iconos.jsx'
import { mensajeDeError } from '../../../core/errores.js'

/**
 * Crear o editar una encuesta.
 *
 * Las preguntas se arman aquí y se guardan como datos: no hace falta tocar
 * código ni desplegar para tener una encuesta nueva.
 *
 * Una ya respondida no deja cambiar sus preguntas — el servidor lo bloquea y
 * aquí se avisa antes, para no dejar que alguien edite media pantalla y
 * reciba el error al guardar.
 */
export default function FormPlantilla({ plantilla, onCerrar }) {
  const queryClient = useQueryClient()
  const esNueva = !plantilla
  const bloqueada = !esNueva && plantilla.total_respuestas > 0

  const [form, setForm] = useState(() => ({
    nombre: plantilla?.nombre || '',
    descripcion: plantilla?.descripcion || '',
    slug: plantilla?.slug || '',
    sujeto_tipo: plantilla?.sujeto_tipo || '',
    sujetos: plantilla?.sujetos || '',
    mensaje_final: plantilla?.mensaje_final || '',
    activa: plantilla?.activa ?? true,
  }))
  const [preguntas, setPreguntas] = useState(() =>
    plantilla?.preguntas?.length
      ? plantilla.preguntas.map(p => ({ ...p, opciones: p.opciones || '' }))
      : [{ texto: '', tipo: 'escala', opciones: '', clave: '', obligatoria: true }]
  )
  const [error, setError] = useState('')
  const [sucio, setSucio] = useState(false)

  // Un clic fuera o un Escape no pueden borrar lo escrito.
  const { intentarCerrar, dialogoDescarte } = useCierreSeguro({
    hayCambios: sucio, onCerrar,
  })

  const set = (campo) => (e) => {
    const valor = e.target.type === 'checkbox' ? e.target.checked : e.target.value
    setForm(f => ({ ...f, [campo]: valor }))
    setSucio(true)
  }

  const setPregunta = (i, campo, valor) => {
    setPreguntas(ps => ps.map((p, j) => j === i ? { ...p, [campo]: valor } : p))
    setSucio(true)
  }

  const agregar = () => {
    setPreguntas(ps => [...ps, { texto: '', tipo: 'escala', opciones: '', clave: '', obligatoria: true }])
    setSucio(true)
  }

  const quitar = (i) => {
    setPreguntas(ps => ps.filter((_, j) => j !== i))
    setSucio(true)
  }

  const mutacion = useMutation({
    mutationFn: () => {
      const payload = {
        ...form,
        slug: normalizarSlug(form.slug || form.nombre),
        preguntas: preguntas.map((p, orden) => ({
          texto: p.texto.trim(),
          ayuda: p.ayuda || null,
          tipo: p.tipo,
          opciones: p.tipo === 'opcion' ? p.opciones : null,
          clave: p.clave || null,
          obligatoria: p.obligatoria,
          orden,
        })),
      }
      // A una encuesta ya respondida no se le mandan preguntas: el servidor
      // rechazaría el cambio completo, incluido el renombrar.
      if (bloqueada) delete payload.preguntas
      return esNueva ? crearPlantilla(payload) : actualizarPlantilla(plantilla.id, payload)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["enc-plantillas"] })
      queryClient.invalidateQueries({ queryKey: ["enc-panel"] })
      onCerrar()
    },
    onError: (e) => setError(mensajeDeError(e, 'No se pudo guardar. Intenta de nuevo.')),
  })

  const mutBorrar = useMutation({
    mutationFn: () => eliminarPlantilla(plantilla.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["enc-plantillas"] })
      onCerrar()
    },
    onError: (e) => setError(mensajeDeError(e, 'No se pudo eliminar.')),
  })

  const guardar = (e) => {
    e.preventDefault()
    setError('')
    if (!form.nombre.trim()) return setError('La encuesta necesita un nombre.')
    if (!bloqueada && preguntas.every(p => !p.texto.trim())) {
      return setError('Agrega al menos una pregunta.')
    }
    mutacion.mutate()
  }

  const slugPropuesto = normalizarSlug(form.slug || form.nombre)

  return (
    <div className="fixed inset-0 bg-black/40 flex items-start justify-center p-4 z-50 overflow-y-auto"
         onClick={intentarCerrar}>
      <form
        onSubmit={guardar}
        onClick={(e) => e.stopPropagation()}
        className="bg-white rounded-2xl w-full max-w-2xl my-8 shadow-xl"
      >
        <div className="px-6 py-4 border-b border-borde">
          <h2 className="text-xl font-bold text-acento-fuerte">
            {esNueva ? 'Nueva encuesta' : 'Editar encuesta'}
          </h2>
        </div>

        <div className="p-6 space-y-4">
          {error && (
            <div className="bg-negativo-bg border border-negativo/25 text-negativo text-sm rounded-lg px-4 py-3">
              {error}
            </div>
          )}

          {bloqueada && (
            <div className="bg-alerta-bg border border-ambar/30 text-alerta text-sm rounded-lg px-4 py-3">
              Esta encuesta ya tiene {plantilla.total_respuestas} respuesta(s), así que sus
              preguntas no se pueden cambiar: las respuestas quedarían contestando algo que
              ya no se pregunta. Puedes renombrarla o desactivarla, y crear una versión nueva.
            </div>
          )}

          <div>
            <label className="block text-xs font-semibold text-texto-2 uppercase mb-1">Nombre</label>
            <input
              value={form.nombre} onChange={set('nombre')}
              placeholder="Calificación de vendedores"
              className="w-full rounded-lg border border-borde px-3 py-2 text-sm"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-texto-2 uppercase mb-1">
              Descripción <span className="normal-case font-normal">(opcional)</span>
            </label>
            <input
              value={form.descripcion} onChange={set('descripcion')}
              placeholder="La responde el cliente en el punto de venta"
              className="w-full rounded-lg border border-borde px-3 py-2 text-sm"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-texto-2 uppercase mb-1">
                Dirección del enlace
              </label>
              <input
                value={form.slug} onChange={set('slug')}
                placeholder={normalizarSlug(form.nombre) || 'vendedores'}
                disabled={!esNueva}
                className="w-full rounded-lg border border-borde px-3 py-2 text-sm disabled:bg-superficie-2 disabled:text-texto-3"
              />
              <p className="text-[11px] text-texto-3 mt-1 break-all">
                {slugPropuesto ? urlPublica(slugPropuesto) : 'Se propone del nombre'}
              </p>
              {!esNueva && (
                <p className="text-[11px] text-texto-3 mt-1">
                  No se cambia: los códigos QR ya impresos apuntan aquí.
                </p>
              )}
            </div>
            <div>
              <label className="block text-xs font-semibold text-texto-2 uppercase mb-1">
                ¿A quién califica?
              </label>
              <input
                value={form.sujeto_tipo} onChange={set('sujeto_tipo')}
                placeholder="vendedor, punto de venta..."
                className="w-full rounded-lg border border-borde px-3 py-2 text-sm"
              />
              <p className="text-[11px] text-texto-3 mt-1">
                Déjalo vacío si no califica a nadie en particular.
              </p>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-texto-2 uppercase mb-1">
              Opciones a calificar <span className="normal-case font-normal">(separadas por |)</span>
            </label>
            <input
              value={form.sujetos} onChange={set('sujetos')}
              placeholder="Sede Centro|Sede Norte|Sede Sur"
              className="w-full rounded-lg border border-borde px-3 py-2 text-sm"
            />
            <p className="text-[11px] text-texto-3 mt-1">
              Si las llenas, el cliente elige de una lista en vez de escribir. Evita que el
              mismo punto llegue como «Centro», «centro» y «Sede Centro» y termine contado
              como tres lugares distintos. Puedes agregar opciones después sin problema.
            </p>
          </div>

          {/* Preguntas */}
          <div className="border-t border-borde pt-4">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-bold text-acento-fuerte">Preguntas</h3>
              {!bloqueada && (
                <button type="button" onClick={agregar}
                  className="text-sm font-semibold text-acento hover:underline">
                  + Agregar
                </button>
              )}
            </div>

            <div className="space-y-3">
              {preguntas.map((p, i) => (
                <div key={i} className="bg-superficie-2 border border-borde rounded-lg p-3 space-y-2">
                  <div className="flex gap-2">
                    <input
                      value={p.texto}
                      onChange={(e) => setPregunta(i, 'texto', e.target.value)}
                      disabled={bloqueada}
                      placeholder="¿Cómo calificas la atención?"
                      className="flex-1 rounded-lg border border-borde px-3 py-2 text-sm disabled:bg-white disabled:text-texto-2"
                    />
                    {!bloqueada && preguntas.length > 1 && (
                      <button type="button" onClick={() => quitar(i)}
                        className="text-negativo-vivo text-sm px-2 hover:bg-negativo-bg rounded"
                        aria-label="Quitar pregunta">
                        <IconoCerrar tam={16} />
                      </button>
                    )}
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <select
                      value={p.tipo}
                      onChange={(e) => setPregunta(i, 'tipo', e.target.value)}
                      disabled={bloqueada}
                      className="rounded-lg border border-borde px-3 py-2 text-sm bg-white disabled:text-texto-2"
                    >
                      {Object.entries(TIPOS_PREGUNTA).map(([valor, cfg]) => (
                        <option key={valor} value={valor}>{cfg.label}</option>
                      ))}
                    </select>

                    <label className="flex items-center gap-2 text-sm text-texto-2">
                      <input
                        type="checkbox" checked={p.obligatoria}
                        onChange={(e) => setPregunta(i, 'obligatoria', e.target.checked)}
                        disabled={bloqueada}
                        className="rounded border-borde accent-acento"
                      />
                      Obligatoria
                    </label>
                  </div>

                  {p.tipo === 'opcion' && (
                    <input
                      value={p.opciones}
                      onChange={(e) => setPregunta(i, 'opciones', e.target.value)}
                      disabled={bloqueada}
                      placeholder="Sí|Parcialmente|No"
                      className="w-full rounded-lg border border-borde px-3 py-2 text-sm disabled:bg-white"
                    />
                  )}

                  <p className="text-[11px] text-texto-3">{TIPOS_PREGUNTA[p.tipo]?.ayuda}</p>
                </div>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-texto-2 uppercase mb-1">
              Mensaje al terminar
            </label>
            <input
              value={form.mensaje_final} onChange={set('mensaje_final')}
              placeholder="¡Gracias! Tu opinión nos ayuda a mejorar."
              className="w-full rounded-lg border border-borde px-3 py-2 text-sm"
            />
          </div>

          <label className="flex items-center gap-2 text-sm text-texto-2">
            <input
              type="checkbox" checked={form.activa} onChange={set('activa')}
              className="rounded border-borde accent-acento"
            />
            Activa — mientras lo esté, el enlace recibe respuestas
          </label>
        </div>

        <div className="px-6 py-4 border-t border-borde flex justify-between gap-3">
          {!esNueva && plantilla.total_respuestas === 0 ? (
            <button type="button" onClick={() => mutBorrar.mutate()}
              className="text-sm font-semibold text-negativo-vivo hover:underline">
              Eliminar
            </button>
          ) : <span />}

          <div className="flex gap-3">
            <button type="button" onClick={onCerrar}
              className="px-4 py-2 text-sm font-semibold text-texto-2 hover:text-acento-fuerte">
              Cancelar
            </button>
            <button type="submit" disabled={mutacion.isPending}
              className="bg-acento hover:bg-acento-fuerte text-white font-semibold px-5 py-2 rounded-xl text-sm transition disabled:opacity-50">
              {mutacion.isPending ? 'Guardando...' : 'Guardar'}
            </button>
          </div>
        </div>
      </form>

      {dialogoDescarte}
    </div>
  )
}
