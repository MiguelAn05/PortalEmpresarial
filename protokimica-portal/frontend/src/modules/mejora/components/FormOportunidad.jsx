import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AREAS } from '../../../core/areas.js'
import { IconoCerrar } from '../../../core/components/Iconos.jsx'
import { useCierreSeguro } from '../../../core/components/cierreSeguro.jsx'
import { obtenerTablero } from '../../indicadores/api.js'
import { crearOportunidad } from '../api.js'
import { ORIGENES } from '../constants.js'

/**
 * Abrir una oportunidad de mejora.
 *
 * Cuando nace de un indicador se pide el periodo: es el mes cuya medición
 * falló, y es contra el que se compara después para saber si funcionó. Sin
 * él la OMP nacería sin forma de demostrar nada, así que el campo aparece
 * solo, explicado, en vez de dejar que el servidor lo rechace al guardar.
 */
export default function FormOportunidad({ indicador = null, periodo = null,
                                          valorInicial = null, onCerrar, onCreada }) {
  const hoy = new Date()
  const [form, setForm] = useState({
    titulo: '',
    descripcion: '',
    origen: indicador ? 'indicador' : 'otro',
    indicador_id: indicador?.id ?? '',
    periodo_anio: periodo?.anio ?? hoy.getFullYear(),
    periodo_mes: periodo?.mes ?? hoy.getMonth() + 1,
    valor_inicial: valorInicial ?? '',
    meta_esperada: '',
    area: indicador?.area ?? '',
    prioridad: 'media',
    fecha_limite: '',
  })
  const [error, setError] = useState('')

  const queryClient = useQueryClient()
  const hayCambios = Boolean(form.titulo || form.descripcion)
  const { intentarCerrar, dialogoDescarte } = useCierreSeguro({ hayCambios, onCerrar })

  // Solo para elegir el indicador cuando la OMP no viene de uno concreto.
  const { data: tablero } = useQuery({
    queryKey: ['ind-tablero-omp'],
    queryFn: () => obtenerTablero({}),
    enabled: !indicador,
  })

  const mutacion = useMutation({
    mutationFn: () => crearOportunidad({
      titulo: form.titulo,
      descripcion: form.descripcion || null,
      origen: form.origen,
      indicador_id: form.origen === 'indicador' && form.indicador_id
        ? Number(form.indicador_id) : null,
      periodo_anio: form.origen === 'indicador' ? Number(form.periodo_anio) : null,
      periodo_mes: form.origen === 'indicador' ? Number(form.periodo_mes) : null,
      valor_inicial: form.valor_inicial === '' ? null : Number(form.valor_inicial),
      meta_esperada: form.meta_esperada === '' ? null : Number(form.meta_esperada),
      area: form.area || null,
      prioridad: form.prioridad,
      fecha_limite: form.fecha_limite ? new Date(form.fecha_limite).toISOString() : null,
    }),
    onSuccess: (creada) => {
      queryClient.invalidateQueries({ queryKey: ['omp'] })
      onCreada?.(creada.id)
    },
    onError: (err) => setError(
      err.response?.data?.detail || 'No se pudo abrir la oportunidad. Intenta de nuevo.',
    ),
  })

  const cambiar = (campo) => (e) => {
    setForm({ ...form, [campo]: e.target.value })
    setError('')
  }

  const enviar = (e) => {
    e.preventDefault()
    if (form.titulo.trim().length < 5) {
      setError('Ponle un título que diga qué se va a mejorar.')
      return
    }
    mutacion.mutate()
  }

  const input = 'w-full rounded-lg border border-borde-fuerte px-3 py-2 text-sm ' +
    'text-texto placeholder-texto-3 focus:outline-none focus:border-acento'

  return (
    <>
      <div
        className="fixed inset-0 bg-texto/40 flex items-start justify-center z-50 p-4 overflow-y-auto"
        onClick={intentarCerrar}
      >
        <form
          onSubmit={enviar}
          onClick={(e) => e.stopPropagation()}
          className="bg-superficie rounded-2xl shadow-lg w-full max-w-xl my-8"
        >
          <header className="flex items-start justify-between gap-3 px-6 py-4 border-b border-borde">
            <div>
              <h2 className="text-lg font-semibold text-texto">Abrir oportunidad de mejora</h2>
              <p className="text-xs text-texto-2 mt-0.5">
                {indicador
                  ? `Nace de: ${indicador.nombre}`
                  : 'Queda abierta; la causa raíz se escribe en el análisis.'}
              </p>
            </div>
            <button
              type="button" onClick={intentarCerrar} aria-label="Cerrar"
              className="w-8 h-8 flex items-center justify-center rounded-lg text-texto-3
                hover:bg-superficie-2 hover:text-texto transition-colors duration-150"
            >
              <IconoCerrar tam={16} />
            </button>
          </header>

          <div className="px-6 py-5 space-y-4">
            <div>
              <label className="etiqueta block mb-1.5">
                Qué se va a mejorar <span className="text-negativo">*</span>
              </label>
              <input
                value={form.titulo} onChange={cambiar('titulo')} className={input}
                placeholder="Ej: Entregas a tiempo por debajo de la meta"
              />
            </div>

            <div>
              <label className="etiqueta block mb-1.5">Detalle</label>
              <textarea
                value={form.descripcion} onChange={cambiar('descripcion')} rows={3}
                className={`${input} resize-none`}
                placeholder="Qué se observó, dónde y desde cuándo."
              />
            </div>

            {!indicador && (
              <div>
                <label className="etiqueta block mb-1.5">De dónde sale</label>
                <select value={form.origen} onChange={cambiar('origen')} className={input}>
                  {Object.entries(ORIGENES).map(([v, l]) => (
                    <option key={v} value={v}>{l}</option>
                  ))}
                </select>
              </div>
            )}

            {form.origen === 'indicador' && (
              <div className="rounded-xl border border-borde bg-superficie-2 p-4 space-y-3">
                {!indicador && (
                  <div>
                    <label className="etiqueta block mb-1.5">Indicador</label>
                    <select
                      value={form.indicador_id} onChange={cambiar('indicador_id')}
                      className={`${input} bg-superficie`}
                    >
                      <option value="">Selecciona uno</option>
                      {(tablero?.indicadores ?? []).map(i => (
                        <option key={i.id} value={i.id}>{i.nombre}</option>
                      ))}
                    </select>
                  </div>
                )}

                {/* El periodo no es un capricho del formulario: es contra lo
                    que se compara para saber si la mejora funcionó. */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="etiqueta block mb-1.5">Mes que falló</label>
                    <select value={form.periodo_mes} onChange={cambiar('periodo_mes')}
                      className={`${input} bg-superficie`}>
                      {['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio',
                        'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
                        .map((m, i) => <option key={m} value={i + 1}>{m}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="etiqueta block mb-1.5">Año</label>
                    <input
                      type="number" value={form.periodo_anio} onChange={cambiar('periodo_anio')}
                      className={`${input} bg-superficie cifra`}
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="etiqueta block mb-1.5">Valor que dio</label>
                    <input
                      type="number" step="any" value={form.valor_inicial}
                      onChange={cambiar('valor_inicial')}
                      className={`${input} bg-superficie cifra`} placeholder="62"
                    />
                  </div>
                  <div>
                    <label className="etiqueta block mb-1.5">A dónde se quiere llegar</label>
                    <input
                      type="number" step="any" value={form.meta_esperada}
                      onChange={cambiar('meta_esperada')}
                      className={`${input} bg-superficie cifra`} placeholder="95"
                    />
                  </div>
                </div>

                <p className="text-xs text-texto-3">
                  Se compara con la medición del mes siguiente para saber si la
                  oportunidad funcionó.
                </p>
              </div>
            )}

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label className="etiqueta block mb-1.5">Área</label>
                <select value={form.area} onChange={cambiar('area')} className={input}>
                  <option value="">La mía</option>
                  {AREAS.map(a => <option key={a} value={a}>{a}</option>)}
                </select>
              </div>
              <div>
                <label className="etiqueta block mb-1.5">Prioridad</label>
                <select value={form.prioridad} onChange={cambiar('prioridad')} className={input}>
                  {['baja', 'media', 'alta', 'critica'].map(p => (
                    <option key={p} value={p}>{p[0].toUpperCase() + p.slice(1)}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="etiqueta block mb-1.5">Fecha límite</label>
                <input
                  type="date" value={form.fecha_limite} onChange={cambiar('fecha_limite')}
                  className={input}
                />
              </div>
            </div>

            {error && (
              <p role="alert" className="text-sm text-negativo bg-negativo-bg
                border border-negativo/25 rounded-lg px-3 py-2">
                {error}
              </p>
            )}
          </div>

          <footer className="flex justify-end gap-3 px-6 py-4 border-t border-borde">
            <button
              type="button" onClick={intentarCerrar}
              className="px-4 py-2 rounded-lg border border-borde-fuerte text-sm
                font-medium text-texto-2 hover:bg-superficie-2 transition-colors duration-150"
            >
              Cancelar
            </button>
            <button
              type="submit" disabled={mutacion.isPending}
              className="px-5 py-2 rounded-lg bg-acento-fuerte text-white text-sm
                font-semibold hover:bg-acento disabled:opacity-60
                transition-colors duration-150 ease-suave"
            >
              {mutacion.isPending ? 'Abriendo…' : 'Abrir oportunidad'}
            </button>
          </footer>
        </form>
      </div>
      {dialogoDescarte}
    </>
  )
}
