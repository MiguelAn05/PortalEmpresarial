import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useAuth } from '../../../core/AuthContext.jsx'
import {
  IconoAlDia, IconoAlerta, IconoCerrar, IconoCheck, IconoIndicadores,
  IconoRechazo, IconoReloj,
} from '../../../core/components/Iconos.jsx'
import {
  actualizarAccion, actualizarOportunidad, agregarAccion, cambiarEstado,
  consultarVerificacion, eliminarAccion, obtenerOportunidad, registrarVerificacion,
} from '../api.js'
import {
  CICLO, ESTADOS, estaCerrada, loQueFaltaPara, siguienteEstado, textoDeAvance,
} from '../constants.js'

/**
 * El detalle de una OMP: dónde va en el ciclo, qué falta para avanzar y si
 * funcionó.
 *
 * Lo importante de esta pantalla es que **dice qué falta antes de que la
 * persona toque el botón**. Enterarse de que hace falta la causa raíz por un
 * error rojo, con el formulario ya cerrado, es la forma más rápida de que
 * alguien abandone el módulo y vuelva al Excel.
 */

const TONOS = {
  positivo: 'bg-positivo-bg text-positivo',
  alerta: 'bg-alerta-bg text-alerta',
  negativo: 'bg-negativo-bg text-negativo',
  info: 'bg-info-bg text-info',
  neutro: 'bg-superficie-2 text-texto-2',
}

/** El ciclo dibujado: dónde está y qué viene. */
function Ciclo({ estado }) {
  const actual = CICLO.indexOf(estado)

  if (estado === 'descartada') {
    return (
      <p className="text-xs text-texto-2">
        Se descartó. Queda el registro de que se evaluó y no se siguió.
      </p>
    )
  }

  return (
    <ol className="flex flex-wrap items-center gap-x-1 gap-y-2">
      {CICLO.map((paso, i) => {
        const hecho = i < actual
        const aqui = i === actual
        return (
          <li key={paso} className="flex items-center gap-1">
            <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md
              text-[11.5px] font-semibold whitespace-nowrap ${
              aqui ? TONOS[ESTADOS[paso].tono]
                : hecho ? 'bg-superficie-2 text-texto-2' : 'text-texto-3'
            }`}>
              {hecho && <IconoCheck tam={11} />}
              {ESTADOS[paso].label}
            </span>
            {i < CICLO.length - 1 && (
              <span className="text-texto-3 text-xs" aria-hidden="true">›</span>
            )}
          </li>
        )
      })}
    </ol>
  )
}

/** La comparación antes/después: el corazón del módulo. */
function Verificacion({ omp, datos, onRegistrar, puedeGestionar, guardando }) {
  const [nota, setNota] = useState('')

  if (!omp.indicador_id) {
    return (
      <p className="text-sm text-texto-2">
        Esta oportunidad no salió de un indicador, así que la eficacia se
        registra a criterio de quien la cierra.
        {puedeGestionar && (
          <span className="flex gap-2 mt-3">
            <button
              onClick={() => onRegistrar({ eficaz: true, nota })}
              className="px-3 py-1.5 rounded-lg bg-positivo text-white text-xs font-semibold"
            >
              Funcionó
            </button>
            <button
              onClick={() => onRegistrar({ eficaz: false, nota })}
              className="px-3 py-1.5 rounded-lg border border-borde-fuerte text-xs
                font-semibold text-texto-2"
            >
              No funcionó
            </button>
          </span>
        )}
      </p>
    )
  }

  if (!datos?.hay_medicion) {
    const p = datos?.periodo_esperado
    return (
      <div className="flex items-start gap-3">
        <IconoReloj tam={18} className="text-texto-3 mt-0.5 flex-shrink-0" />
        <div>
          <p className="text-sm font-medium text-texto">Todavía no se puede verificar</p>
          <p className="text-xs text-texto-3 mt-0.5">
            Falta registrar la medición de {p?.mes ? `${p.mes}/${p.anio}` : 'el mes siguiente'}.
            Cuando entre, aquí aparece la comparación y se puede cerrar.
          </p>
        </div>
      </div>
    )
  }

  const mejoro = datos.mejoro

  return (
    <div className="space-y-3">
      {/* Antes y después, uno al lado del otro: es toda la evidencia. */}
      <div className="flex items-center gap-4">
        <div>
          <div className="etiqueta">Cuando se abrió</div>
          <div className="cifra text-xl font-semibold text-texto-2">
            {datos.valor_inicial ?? '—'}
          </div>
        </div>
        <span className="text-texto-3" aria-hidden="true">→</span>
        <div>
          <div className="etiqueta">Después</div>
          <div className={`cifra text-xl font-semibold ${
            mejoro ? 'text-positivo' : 'text-negativo'}`}>
            {datos.valor_nuevo ?? '—'}
          </div>
        </div>
        <span className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-md
          text-[11.5px] font-semibold ${mejoro ? TONOS.positivo : TONOS.negativo}`}>
          {mejoro ? <IconoAlDia tam={12} /> : <IconoAlerta tam={12} />}
          {mejoro ? 'Mejoró' : 'No mejoró'}
        </span>
      </div>

      {puedeGestionar && omp.eficaz === null && (
        <>
          <textarea
            value={nota} onChange={(e) => setNota(e.target.value)} rows={2}
            placeholder="Qué se concluye de la comparación (opcional)."
            className="w-full rounded-lg border border-borde-fuerte px-3 py-2 text-sm resize-none
              focus:outline-none focus:border-acento"
          />
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => onRegistrar({ eficaz: true, nota })}
              disabled={guardando}
              className="px-3 py-1.5 rounded-lg bg-positivo text-white text-xs font-semibold
                disabled:opacity-60"
            >
              Fue eficaz
            </button>
            <button
              onClick={() => onRegistrar({ eficaz: false, nota })}
              disabled={guardando}
              className="px-3 py-1.5 rounded-lg border border-borde-fuerte text-xs
                font-semibold text-texto-2 disabled:opacity-60"
            >
              No fue eficaz — vuelve a análisis
            </button>
          </div>
          {/* Se dice antes de pulsar, no después. */}
          <p className="text-xs text-texto-3">
            Si no fue eficaz, la oportunidad vuelve a análisis en vez de cerrarse:
            el problema sigue ahí.
          </p>
        </>
      )}

      {omp.eficaz !== null && (
        <p className={`text-sm font-medium ${omp.eficaz ? 'text-positivo' : 'text-negativo'}`}>
          {omp.eficaz ? 'Registrada como eficaz.' : 'Registrada como NO eficaz.'}
          {omp.nota_eficacia && (
            <span className="block text-xs text-texto-2 font-normal mt-1">
              {omp.nota_eficacia}
            </span>
          )}
        </p>
      )}
    </div>
  )
}

export default function DetalleOportunidad({ ompId, onCerrar }) {
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const [causa, setCausa] = useState(null)   // null = no se está editando
  const [nuevaAccion, setNuevaAccion] = useState('')
  const [error, setError] = useState('')

  const puedeGestionar = user?.rol === 'admin' || user?.rol === 'lider'

  const { data: omp, isLoading } = useQuery({
    queryKey: ['omp', ompId],
    queryFn: () => obtenerOportunidad(ompId),
  })

  const { data: verificacion } = useQuery({
    queryKey: ['omp-verificacion', ompId],
    queryFn: () => consultarVerificacion(ompId),
    enabled: Boolean(omp),
  })

  const refrescar = () => {
    queryClient.invalidateQueries({ queryKey: ['omp'] })
    queryClient.invalidateQueries({ queryKey: ['omp-verificacion', ompId] })
  }

  const conError = (accion) => ({
    mutationFn: accion,
    onSuccess: () => { setError(''); refrescar() },
    onError: (err) => setError(err.response?.data?.detail || 'No se pudo guardar.'),
  })

  const mutEstado = useMutation(conError((estado) => cambiarEstado(ompId, estado)))
  const mutCampos = useMutation(conError((datos) => actualizarOportunidad(ompId, datos)))
  const mutAccion = useMutation(conError((datos) => agregarAccion(ompId, datos)))
  const mutMarcar = useMutation(conError(({ id, completada }) =>
    actualizarAccion(ompId, id, { completada })))
  const mutBorrarAccion = useMutation(conError((id) => eliminarAccion(ompId, id)))
  const mutVerificar = useMutation(conError((datos) => registrarVerificacion(ompId, datos)))

  if (isLoading || !omp) {
    return (
      <div className="fixed inset-0 bg-texto/40 flex items-center justify-center z-50 p-4">
        <div className="bg-superficie rounded-2xl px-6 py-5 text-sm text-texto-2">Cargando…</div>
      </div>
    )
  }

  const estado = ESTADOS[omp.estado] ?? ESTADOS.abierta
  const siguiente = siguienteEstado(omp)
  const falta = siguiente ? loQueFaltaPara(omp, siguiente) : null
  const cerrada = estaCerrada(omp)

  return (
    <div
      className="fixed inset-0 bg-texto/40 flex items-start justify-center z-50 p-4 overflow-y-auto"
      onClick={onCerrar}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="bg-superficie rounded-2xl shadow-lg w-full max-w-2xl my-8"
      >
        <header className="flex items-start justify-between gap-3 px-6 py-4 border-b border-borde">
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="cifra text-xs font-semibold text-texto-3">{omp.codigo}</span>
              <span className={`inline-flex items-center px-2 py-0.5 rounded-md
                text-[11.5px] font-semibold ${TONOS[estado.tono]}`}>
                {estado.label}
              </span>
            </div>
            <h2 className="text-lg font-semibold text-texto mt-1">{omp.titulo}</h2>
            <p className="text-xs text-texto-3 mt-0.5">
              {omp.area || 'Toda la empresa'}
              {omp.autor_nombre && ` · la abrió ${omp.autor_nombre}`}
            </p>
          </div>
          <button
            onClick={onCerrar} aria-label="Cerrar"
            className="w-8 h-8 flex items-center justify-center rounded-lg text-texto-3
              hover:bg-superficie-2 hover:text-texto transition-colors duration-150"
          >
            <IconoCerrar tam={16} />
          </button>
        </header>

        <div className="px-6 py-5 space-y-6">
          <Ciclo estado={omp.estado} />

          {omp.descripcion && (
            <p className="text-sm text-texto-2">{omp.descripcion}</p>
          )}

          {omp.indicador_nombre && (
            <div className="flex items-center gap-2 text-sm text-texto-2">
              <IconoIndicadores tam={16} className="text-texto-3" />
              Nace de <b className="text-texto font-medium">{omp.indicador_nombre}</b>
              {omp.periodo_mes && (
                <span className="cifra text-texto-3">
                  ({omp.periodo_mes}/{omp.periodo_anio})
                </span>
              )}
            </div>
          )}

          {/* ── Causa raíz ── */}
          <section>
            <h3 className="etiqueta mb-2">Causa raíz</h3>
            {causa === null ? (
              <div className="flex items-start gap-3">
                <p className={`text-sm flex-1 ${omp.causa_raiz ? 'text-texto' : 'text-texto-3'}`}>
                  {omp.causa_raiz || 'Sin escribir. Hace falta para pasar a ejecución.'}
                </p>
                {puedeGestionar && !cerrada && (
                  <button
                    onClick={() => setCausa(omp.causa_raiz || '')}
                    className="text-xs font-medium text-acento hover:underline flex-shrink-0"
                  >
                    {omp.causa_raiz ? 'Editar' : 'Escribir'}
                  </button>
                )}
              </div>
            ) : (
              <div className="space-y-2">
                <textarea
                  value={causa} onChange={(e) => setCausa(e.target.value)} rows={3} autoFocus
                  placeholder="Por qué pasó, no qué pasó."
                  className="w-full rounded-lg border border-borde-fuerte px-3 py-2 text-sm
                    resize-none focus:outline-none focus:border-acento"
                />
                <div className="flex gap-2">
                  <button
                    onClick={() => { mutCampos.mutate({ causa_raiz: causa }); setCausa(null) }}
                    className="px-3 py-1.5 rounded-lg bg-acento-fuerte text-white text-xs font-semibold"
                  >
                    Guardar
                  </button>
                  <button
                    onClick={() => setCausa(null)}
                    className="px-3 py-1.5 rounded-lg border border-borde-fuerte text-xs
                      font-medium text-texto-2"
                  >
                    Cancelar
                  </button>
                </div>
              </div>
            )}
          </section>

          {/* ── Plan de acciones ── */}
          <section>
            <div className="flex items-baseline justify-between gap-3 mb-2">
              <h3 className="etiqueta">Qué se va a hacer</h3>
              {omp.total_acciones > 0 && (
                <span className="cifra text-xs text-texto-3">
                  {omp.acciones_completadas} de {omp.total_acciones} · {omp.avance_pct}%
                </span>
              )}
            </div>

            {omp.acciones.length === 0 ? (
              <p className="text-sm text-texto-3">
                Todavía no hay acciones. Sin al menos una no se puede verificar
                nada.
              </p>
            ) : (
              <ul className="divide-y divide-borde border-y border-borde">
                {omp.acciones.map(a => (
                  <li key={a.id} className="flex items-center gap-3 py-2.5">
                    <button
                      onClick={() => mutMarcar.mutate({ id: a.id, completada: !a.completada })}
                      disabled={!puedeGestionar && a.responsable_id !== user?.id}
                      aria-label={a.completada ? 'Marcar como pendiente' : 'Marcar como hecha'}
                      className={`w-5 h-5 rounded border flex items-center justify-center
                        flex-shrink-0 transition-colors duration-150 ${
                        a.completada
                          ? 'bg-positivo border-positivo text-white'
                          : 'border-borde-fuerte hover:border-acento'
                      }`}
                    >
                      {a.completada && <IconoCheck tam={12} />}
                    </button>
                    <span className={`flex-1 text-sm ${
                      a.completada ? 'text-texto-3 line-through' : 'text-texto'}`}>
                      {a.descripcion}
                      {a.responsable_nombre && (
                        <span className="block text-xs text-texto-3">
                          {a.responsable_nombre}
                        </span>
                      )}
                    </span>
                    {puedeGestionar && !cerrada && (
                      <button
                        onClick={() => mutBorrarAccion.mutate(a.id)}
                        aria-label="Quitar acción"
                        className="text-texto-3 hover:text-negativo transition-colors"
                      >
                        <IconoRechazo tam={15} />
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            )}

            {puedeGestionar && !cerrada && (
              <form
                onSubmit={(e) => {
                  e.preventDefault()
                  if (nuevaAccion.trim().length < 3) return
                  mutAccion.mutate({ descripcion: nuevaAccion })
                  setNuevaAccion('')
                }}
                className="flex gap-2 mt-3"
              >
                <input
                  value={nuevaAccion} onChange={(e) => setNuevaAccion(e.target.value)}
                  placeholder="Agregar una acción…"
                  className="flex-1 rounded-lg border border-borde-fuerte px-3 py-2 text-sm
                    focus:outline-none focus:border-acento"
                />
                <button
                  type="submit"
                  className="px-3 py-2 rounded-lg border border-borde-fuerte text-sm
                    font-medium text-texto-2 hover:bg-superficie-2 transition-colors"
                >
                  Agregar
                </button>
              </form>
            )}
          </section>

          {/* ── Verificación ── */}
          <section>
            <h3 className="etiqueta mb-2">¿Funcionó?</h3>
            <Verificacion
              omp={omp} datos={verificacion} puedeGestionar={puedeGestionar}
              guardando={mutVerificar.isPending}
              onRegistrar={(datos) => mutVerificar.mutate(datos)}
            />
          </section>

          {error && (
            <p role="alert" className="text-sm text-negativo bg-negativo-bg
              border border-negativo/25 rounded-lg px-3 py-2">
              {error}
            </p>
          )}
        </div>

        {puedeGestionar && !cerrada && (
          <footer className="flex flex-wrap items-center justify-between gap-3
            px-6 py-4 border-t border-borde">
            <button
              onClick={() => mutEstado.mutate('descartada')}
              className="text-xs font-medium text-texto-3 hover:text-negativo transition-colors"
            >
              Descartar
            </button>

            <div className="flex items-center gap-3">
              {/* Qué falta, dicho antes de pulsar. */}
              {falta && <span className="text-xs text-texto-3">{falta}</span>}
              {siguiente && (
                <button
                  onClick={() => mutEstado.mutate(siguiente)}
                  disabled={Boolean(falta) || mutEstado.isPending}
                  title={falta || undefined}
                  className="px-4 py-2 rounded-lg bg-acento-fuerte text-white text-sm
                    font-semibold hover:bg-acento disabled:opacity-40
                    disabled:cursor-not-allowed transition-colors duration-150 ease-suave"
                >
                  {textoDeAvance(siguiente)}
                </button>
              )}
            </div>
          </footer>
        )}
      </div>
    </div>
  )
}
