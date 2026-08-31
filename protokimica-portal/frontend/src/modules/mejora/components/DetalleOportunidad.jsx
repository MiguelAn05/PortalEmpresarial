import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useAuth } from '../../../core/AuthContext.jsx'
import {
  IconoAlDia, IconoAlerta, IconoCerrar, IconoCheck, IconoHistorial,
  IconoIndicadores, IconoRechazo, IconoReloj,
} from '../../../core/components/Iconos.jsx'
import {
  actualizarAccion, actualizarOportunidad, agregarAccion, agregarSeguimiento,
  cambiarEstado, consultarVerificacion, eliminarAccion, eliminarSeguimiento,
  obtenerHistorial, obtenerOportunidad, registrarVerificacion, validarSGC,
} from '../api.js'
import {
  CAMPOS_6M, CICLO, ESTADOS, ESTADOS_ACCION, MAX_ACCION, MAX_SEGUIMIENTO,
  MAX_TEXTO_LARGO, estaCerrada, loQueFaltaPara, resumen6M, siguienteEstado,
  textoDeAvance,
} from '../constants.js'
import { mensajeDeError } from '../../../core/errores.js'

/**
 * El detalle de una OMP: dónde va en el ciclo, qué falta para avanzar y si
 * funcionó.
 *
 * Lo importante de esta pantalla es que **dice qué falta antes de que la
 * persona toque el botón**. Enterarse de que hace falta la causa raíz por un
 * error rojo, con el formulario ya cerrado, es la forma más rápida de que
 * alguien abandone el módulo y vuelva al Excel.
 *
 * Qué campos se muestran depende del tratamiento, y eso lo decide el
 * SERVIDOR: llegan `pide_causa`, `pide_correccion` y `pide_beneficio` ya
 * resueltos. Los que no aplican se OCULTAN, no se deshabilitan — un campo
 * gris que nadie puede llenar solo genera la pregunta de por qué no sirve.
 */

const TONOS = {
  positivo: 'bg-positivo-bg text-positivo',
  alerta: 'bg-alerta-bg text-alerta',
  negativo: 'bg-negativo-bg text-negativo',
  info: 'bg-info-bg text-info',
  neutro: 'bg-superficie-2 text-texto-2',
}

const claseInput = 'w-full rounded-lg border border-borde-fuerte px-3 py-2 text-sm ' +
  'text-texto placeholder-texto-3 resize-none focus:outline-none focus:border-acento'

/** Fecha corta y legible, sin la hora que a nadie le sirve aquí. */
function fechaCorta(valor) {
  if (!valor) return ''
  const d = new Date(valor.length === 10 ? `${valor}T12:00:00` : valor)
  return d.toLocaleDateString('es-CO', { day: 'numeric', month: 'short', year: 'numeric' })
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

/**
 * Un campo largo del formato que se lee y se edita en el mismo sitio.
 *
 * Existe porque el formato tiene cinco de estos —causa raíz, corrección,
 * beneficio, verificación planeada y nota de cierre— y repetir el bloque
 * cinco veces era garantizar que el quinto se comportara distinto.
 */
function CampoLargo({ titulo, valor, vacio, ayuda, editable, onGuardar }) {
  const [borrador, setBorrador] = useState(null)   // null = no se está editando

  if (borrador !== null) {
    return (
      <section>
        <h3 className="etiqueta mb-2">{titulo}</h3>
        <div className="space-y-2">
          <textarea
            value={borrador} onChange={(e) => setBorrador(e.target.value)} rows={3} autoFocus
            placeholder={ayuda} maxLength={MAX_TEXTO_LARGO} className={claseInput}
          />
          <div className="flex gap-2">
            <button
              onClick={() => { onGuardar(borrador); setBorrador(null) }}
              className="px-3 py-1.5 rounded-lg bg-acento-fuerte text-white text-xs font-semibold"
            >
              Guardar
            </button>
            <button
              onClick={() => setBorrador(null)}
              className="px-3 py-1.5 rounded-lg border border-borde-fuerte text-xs
                font-medium text-texto-2"
            >
              Cancelar
            </button>
          </div>
        </div>
      </section>
    )
  }

  return (
    <section>
      <h3 className="etiqueta mb-2">{titulo}</h3>
      <div className="flex items-start gap-3">
        <p className={`text-sm flex-1 whitespace-pre-line ${valor ? 'text-texto' : 'text-texto-3'}`}>
          {valor || vacio}
        </p>
        {editable && (
          <button
            onClick={() => setBorrador(valor || '')}
            className="text-xs font-medium text-acento hover:underline flex-shrink-0"
          >
            {valor ? 'Editar' : 'Escribir'}
          </button>
        )}
      </div>
    </section>
  )
}

/**
 * El análisis de causas en 6M.
 *
 * Siete campos y no un textarea porque en el Excel ya venían estas mismas
 * etiquetas escritas a mano dentro de la celda. Al exportar se reconstruye
 * el bloque con este orden, así que el formato impreso no cambia.
 */
function Analisis6M({ omp, editable, onGuardar }) {
  const [borrador, setBorrador] = useState(null)
  const escritas = resumen6M(omp)

  if (borrador !== null) {
    return (
      <section>
        <h3 className="etiqueta mb-2">Análisis de causas (6M)</h3>
        <div className="space-y-3">
          {CAMPOS_6M.map(({ campo, label, ayuda }) => (
            <div key={campo}>
              <label className="text-xs font-medium text-texto-2 block mb-1">{label}</label>
              <textarea
                value={borrador[campo] ?? ''} rows={2} placeholder={ayuda}
                maxLength={MAX_TEXTO_LARGO}
                onChange={(e) => setBorrador({ ...borrador, [campo]: e.target.value })}
                className={claseInput}
              />
            </div>
          ))}
          <p className="text-xs text-texto-3">
            Las que se dejen en blanco salen como «No aplica» en el reporte del SGC.
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => { onGuardar(borrador); setBorrador(null) }}
              className="px-3 py-1.5 rounded-lg bg-acento-fuerte text-white text-xs font-semibold"
            >
              Guardar
            </button>
            <button
              onClick={() => setBorrador(null)}
              className="px-3 py-1.5 rounded-lg border border-borde-fuerte text-xs
                font-medium text-texto-2"
            >
              Cancelar
            </button>
          </div>
        </div>
      </section>
    )
  }

  return (
    <section>
      <div className="flex items-baseline justify-between gap-3 mb-2">
        <h3 className="etiqueta">Análisis de causas (6M)</h3>
        {editable && (
          <button
            onClick={() => setBorrador(
              Object.fromEntries(CAMPOS_6M.map(({ campo }) => [campo, omp[campo] ?? ''])),
            )}
            className="text-xs font-medium text-acento hover:underline"
          >
            {escritas.length ? 'Editar' : 'Escribir'}
          </button>
        )}
      </div>
      {escritas.length === 0 ? (
        <p className="text-sm text-texto-3">
          Sin escribir. Es el paso que separa la causa raíz de una corazonada.
        </p>
      ) : (
        <dl className="space-y-1.5">
          {escritas.map(({ label, texto }) => (
            <div key={label} className="text-sm">
              <dt className="inline font-medium text-texto-2">{label}: </dt>
              <dd className="inline text-texto">{texto}</dd>
            </div>
          ))}
        </dl>
      )}
    </section>
  )
}

/**
 * La bitácora: una entrada por vez, en orden y con fecha y autor.
 *
 * En el Excel esto son tres columnas con hasta veinticinco entradas
 * apretadas dentro de una celda de seis mil caracteres. Aquí es lo que
 * siempre fue — un histórico que se lee de arriba abajo.
 */
function Seguimientos({ omp, usuarioId, esAdmin, cerrada, onAgregar, onQuitar }) {
  const [texto, setTexto] = useState('')

  return (
    <section>
      <div className="flex items-baseline justify-between gap-3 mb-2">
        <h3 className="etiqueta">Seguimiento</h3>
        {omp.total_seguimientos > 0 && (
          <span className="cifra text-xs text-texto-3">
            {omp.total_seguimientos} {omp.total_seguimientos === 1 ? 'entrada' : 'entradas'}
          </span>
        )}
      </div>

      {omp.seguimientos.length === 0 ? (
        <p className="text-sm text-texto-3">
          Todavía nadie ha escrito cómo va. Una acción sin seguimiento es una
          que nadie sabe si se está trabajando.
        </p>
      ) : (
        <ol className="space-y-3 border-l-2 border-borde pl-4">
          {omp.seguimientos.map(s => (
            <li key={s.id} className="relative">
              <span
                className="absolute -left-[21px] top-1.5 w-2 h-2 rounded-full bg-borde-fuerte"
                aria-hidden="true"
              />
              <div className="flex items-baseline justify-between gap-3">
                <p className="text-xs text-texto-3">
                  <span className="cifra">{fechaCorta(s.fecha)}</span>
                  {s.autor_nombre && ` · ${s.autor_nombre}`}
                </p>
                {!cerrada && (esAdmin || s.autor_id === usuarioId) && (
                  <button
                    onClick={() => onQuitar(s.id)} aria-label="Quitar seguimiento"
                    className="text-texto-3 hover:text-negativo transition-colors flex-shrink-0"
                  >
                    <IconoRechazo tam={14} />
                  </button>
                )}
              </div>
              <p className="text-sm text-texto whitespace-pre-line mt-0.5">{s.contenido}</p>
              {s.requiere_revision && (
                <p className="text-xs text-alerta mt-1">
                  Viene del archivo viejo y no se pudo separar por fechas. Revísalo.
                </p>
              )}
            </li>
          ))}
        </ol>
      )}

      {/* Lo escribe cualquiera que vea la oportunidad, no solo el líder:
          quien ejecuta la acción es quien sabe cómo va. */}
      {!cerrada && (
        <form
          onSubmit={(e) => {
            e.preventDefault()
            const limpio = texto.trim()
            if (limpio.length < 3) return
            onAgregar(limpio)
            setTexto('')
          }}
          className="mt-3 space-y-2"
        >
          <textarea
            value={texto} onChange={(e) => setTexto(e.target.value)} rows={2}
            maxLength={MAX_SEGUIMIENTO}
            placeholder="Qué pasó desde la última vez…"
            className={claseInput}
          />
          <button
            type="submit" disabled={texto.trim().length < 3}
            className="px-3 py-1.5 rounded-lg border border-borde-fuerte text-xs
              font-medium text-texto-2 hover:bg-superficie-2 disabled:opacity-40
              transition-colors duration-150"
          >
            Agregar seguimiento
          </button>
        </form>
      )}
    </section>
  )
}

/** La comparación antes/después: el corazón del módulo. */
function Verificacion({ omp, datos, onRegistrar, puedeGestionar }) {
  const [nota, setNota] = useState('')

  if (!omp.indicador_id) {
    return (
      <div className="text-sm text-texto-2">
        <p>
          Esta oportunidad no salió de un indicador, así que la eficacia se
          registra a criterio de quien la cierra.
        </p>
        {puedeGestionar && !estaCerrada(omp) && (
          <>
            <textarea
              value={nota} onChange={(e) => setNota(e.target.value)} rows={2}
              maxLength={MAX_TEXTO_LARGO}
              placeholder="Con qué se comprobó."
              className={`${claseInput} mt-3`}
            />
            <span className="flex gap-2 mt-2">
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
          </>
        )}
      </div>
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
      <div className="flex items-center gap-4 flex-wrap">
        <div>
          <p className="etiqueta">Antes</p>
          <p className="cifra text-lg font-semibold text-texto">{datos.valor_inicial}</p>
        </div>
        <span className="text-texto-3" aria-hidden="true">→</span>
        <div>
          <p className="etiqueta">Después</p>
          <p className="cifra text-lg font-semibold text-texto">{datos.valor_nuevo}</p>
        </div>
        <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md
          text-[11.5px] font-semibold ${mejoro ? TONOS.positivo : TONOS.negativo}`}>
          {mejoro ? <IconoAlDia tam={12} /> : <IconoAlerta tam={12} />}
          {mejoro ? 'Mejoró' : 'No mejoró'}
        </span>
      </div>

      {omp.eficaz === null && puedeGestionar && (
        <>
          <textarea
            value={nota} onChange={(e) => setNota(e.target.value)} rows={2}
            maxLength={MAX_TEXTO_LARGO}
            placeholder="Qué se concluye de esa comparación."
            className={claseInput}
          />
          <div className="flex gap-2">
            <button
              onClick={() => onRegistrar({
                eficaz: true, nota, valor_verificado: datos.valor_nuevo,
              })}
              className="px-3 py-1.5 rounded-lg bg-positivo text-white text-xs font-semibold"
            >
              Fue eficaz
            </button>
            <button
              onClick={() => onRegistrar({
                eficaz: false, nota, valor_verificado: datos.valor_nuevo,
              })}
              className="px-3 py-1.5 rounded-lg border border-borde-fuerte text-xs
                font-semibold text-texto-2"
            >
              No fue eficaz
            </button>
          </div>
        </>
      )}

      {omp.eficaz !== null && (
        <p className="text-sm text-texto-2">
          Se registró como <b className="text-texto font-medium">
            {omp.eficaz ? 'eficaz' : 'no eficaz'}
          </b>.
          {omp.nota_eficacia && <span className="block text-xs mt-0.5">{omp.nota_eficacia}</span>}
        </p>
      )}
    </div>
  )
}

export default function DetalleOportunidad({ ompId, onCerrar }) {
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const [nuevaAccion, setNuevaAccion] = useState('')
  const [verHistorial, setVerHistorial] = useState(false)
  const [error, setError] = useState('')

  const puedeGestionar = user?.rol === 'admin' || user?.rol === 'lider'
  // Quién valida el cierre se decide por ÁREA, igual que en el servidor.
  // Esto solo esconde un botón; el permiso de verdad lo impone la API.
  const esSGC = user?.rol === 'admin' || user?.area === 'Calidad'

  const { data: omp, isLoading } = useQuery({
    queryKey: ['omp', ompId],
    queryFn: () => obtenerOportunidad(ompId),
  })

  const { data: verificacion } = useQuery({
    queryKey: ['omp-verificacion', ompId],
    queryFn: () => consultarVerificacion(ompId),
    enabled: Boolean(omp),
  })

  const { data: historial } = useQuery({
    queryKey: ['omp-historial', ompId],
    queryFn: () => obtenerHistorial(ompId),
    enabled: verHistorial,
  })

  const refrescar = () => {
    queryClient.invalidateQueries({ queryKey: ['omp'] })
    queryClient.invalidateQueries({ queryKey: ['omp-verificacion', ompId] })
    queryClient.invalidateQueries({ queryKey: ['omp-historial', ompId] })
  }

  const conError = (accion) => ({
    mutationFn: accion,
    onSuccess: () => { setError(''); refrescar() },
    onError: (err) => setError(mensajeDeError(err, 'No se pudo guardar.')),
  })

  const mutEstado = useMutation(conError((estado) => cambiarEstado(ompId, estado)))
  const mutCampos = useMutation(conError((datos) => actualizarOportunidad(ompId, datos)))
  const mutAccion = useMutation(conError((datos) => agregarAccion(ompId, datos)))
  const mutMarcar = useMutation(conError(({ id, estado }) =>
    actualizarAccion(ompId, id, { estado })))
  const mutBorrarAccion = useMutation(conError((id) => eliminarAccion(ompId, id)))
  const mutVerificar = useMutation(conError((datos) => registrarVerificacion(ompId, datos)))
  const mutValidarSGC = useMutation(conError(() => validarSGC(ompId)))
  const mutSeguimiento = useMutation(conError((contenido) =>
    agregarSeguimiento(ompId, { contenido })))
  const mutBorrarSeguimiento = useMutation(conError((id) => eliminarSeguimiento(ompId, id)))

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
  const editable = puedeGestionar && !cerrada

  /** El siguiente estado de una tarea al pulsarla: pendiente → en curso → cumplida. */
  const siguienteDeAccion = (actual) => (
    { pendiente: 'en_curso', en_curso: 'cumplida', cumplida: 'pendiente' }[actual] ?? 'en_curso'
  )

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
              {omp.tratamiento_nombre && (
                <span className="inline-flex items-center px-2 py-0.5 rounded-md
                  text-[11.5px] font-semibold bg-superficie-2 text-texto-2">
                  {omp.tratamiento_nombre}
                </span>
              )}
            </div>
            <h2 className="text-lg font-semibold text-texto mt-1">{omp.titulo}</h2>
            <p className="text-xs text-texto-3 mt-0.5">
              {/* El número que el SGC cita: «la 6 de TIC's». */}
              {omp.proceso_nombre
                ? `${omp.proceso_nombre} · N.º ${omp.consecutivo}`
                : 'Sin proceso asignado'}
              {' · '}{omp.area || 'Toda la empresa'}
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
            <p className="text-sm text-texto-2 whitespace-pre-line">{omp.descripcion}</p>
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

          {omp.responsables.length > 0 && (
            <div className="text-sm">
              <h3 className="etiqueta mb-1.5">Responsables</h3>
              <ul className="flex flex-wrap gap-x-4 gap-y-1 text-texto-2">
                {omp.responsables.map(r => (
                  <li key={r.id}>
                    {r.nombre}
                    <span className="text-texto-3 text-xs">
                      {' '}· {r.tipo === 'seguimiento' ? 'seguimiento' : 'resolución'}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Qué se pide depende del tratamiento, y lo decide el servidor.
              Lo que no aplica se oculta: un campo deshabilitado que nadie
              puede usar solo genera la pregunta de por qué no funciona. */}
          {omp.pide_causa && (
            <>
              <Analisis6M
                omp={omp} editable={editable}
                onGuardar={(datos) => mutCampos.mutate(datos)}
              />
              <CampoLargo
                titulo="Causa raíz" valor={omp.causa_raiz} editable={editable}
                vacio="Sin escribir. Hace falta para pasar a ejecución."
                ayuda="Por qué pasó, no qué pasó."
                onGuardar={(v) => mutCampos.mutate({ causa_raiz: v })}
              />
            </>
          )}

          {omp.pide_correccion && (
            <CampoLargo
              titulo="Corrección" valor={omp.correccion} editable={editable}
              vacio="Sin escribir. Es lo que se hizo para tapar el hueco de inmediato."
              ayuda="Qué se hizo ya, antes de atacar la causa."
              onGuardar={(v) => mutCampos.mutate({ correccion: v })}
            />
          )}

          {omp.pide_beneficio && (
            <CampoLargo
              titulo="Beneficio de la mejora" valor={omp.beneficio_mejora} editable={editable}
              vacio="Sin escribir. Es lo que justifica hacerla."
              ayuda="Qué se gana: tiempo, dinero, menos errores."
              onGuardar={(v) => mutCampos.mutate({ beneficio_mejora: v })}
            />
          )}

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
                {omp.acciones.map(a => {
                  const estadoAccion = ESTADOS_ACCION[a.estado] ?? ESTADOS_ACCION.pendiente
                  return (
                    <li key={a.id} className="flex items-center gap-3 py-2.5">
                      <span className="cifra text-xs text-texto-3 w-4 flex-shrink-0">
                        {a.orden}
                      </span>
                      <button
                        onClick={() => mutMarcar.mutate({
                          id: a.id, estado: siguienteDeAccion(a.estado),
                        })}
                        disabled={!puedeGestionar && a.responsable_id !== user?.id}
                        aria-label={`Cambiar estado, ahora ${estadoAccion.label}`}
                        className={`w-5 h-5 rounded border flex items-center justify-center
                          flex-shrink-0 transition-colors duration-150 ${
                          a.estado === 'cumplida'
                            ? 'bg-positivo border-positivo text-white'
                            : a.estado === 'en_curso'
                              ? 'border-acento bg-acento/20'
                              : 'border-borde-fuerte hover:border-acento'
                        }`}
                      >
                        {a.estado === 'cumplida' && <IconoCheck tam={12} />}
                      </button>
                      <span className={`flex-1 text-sm ${
                        a.completada ? 'text-texto-3 line-through' : 'text-texto'}`}>
                        {a.descripcion}
                        <span className="block text-xs text-texto-3">
                          {/* El estado va en texto y no solo en el color del
                              recuadro: el ámbar de la marca no alcanza el
                              contraste mínimo sobre blanco. */}
                          {estadoAccion.label}
                          {a.responsable_nombre && ` · ${a.responsable_nombre}`}
                        </span>
                      </span>
                      {editable && (
                        <button
                          onClick={() => mutBorrarAccion.mutate(a.id)}
                          aria-label="Quitar acción"
                          className="text-texto-3 hover:text-negativo transition-colors"
                        >
                          <IconoRechazo tam={15} />
                        </button>
                      )}
                    </li>
                  )
                })}
              </ul>
            )}

            {editable && (
              <form
                onSubmit={(e) => {
                  e.preventDefault()
                  const texto = nuevaAccion.trim()
                  if (texto.length < 3) return
                  // Se manda ya recortado: el backend cuenta los espacios
                  // dentro del límite, así que un texto que aquí se ve corto
                  // podría pasarse allá.
                  mutAccion.mutate({ descripcion: texto })
                  setNuevaAccion('')
                }}
                className="flex gap-2 mt-3"
              >
                <input
                  value={nuevaAccion} onChange={(e) => setNuevaAccion(e.target.value)}
                  placeholder="Agregar una acción…"
                  maxLength={MAX_ACCION}
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

          {/* ── Seguimiento ── */}
          <Seguimientos
            omp={omp} usuarioId={user?.id} esAdmin={user?.rol === 'admin'}
            cerrada={cerrada}
            onAgregar={(texto) => mutSeguimiento.mutate(texto)}
            onQuitar={(id) => mutBorrarSeguimiento.mutate(id)}
          />

          {/* ── Cómo se va a comprobar, escrito antes ── */}
          <CampoLargo
            titulo="Cómo se va a comprobar que funciono" valor={omp.verificacion_planeada}
            editable={editable}
            vacio="Sin escribir. Decidirlo después de ver el resultado es cómo se cierran acciones que no funcionaron."
            ayuda="Qué se va a revisar, con qué dato y cuándo."
            onGuardar={(v) => mutCampos.mutate({ verificacion_planeada: v })}
          />

          {/* ── Verificación ── */}
          <section>
            <h3 className="etiqueta mb-2">¿Funcionó?</h3>
            <Verificacion
              omp={omp} datos={verificacion} puedeGestionar={puedeGestionar}
              onRegistrar={(datos) => mutVerificar.mutate(datos)}
            />
          </section>

          {/* ── Visto bueno de Calidad ── */}
          <section>
            <h3 className="etiqueta mb-2">Validación de Calidad</h3>
            {omp.validado_sgc_en ? (
              <p className="text-sm text-texto-2">
                <IconoCheck tam={13} className="inline text-positivo" />{' '}
                Validada por <b className="text-texto font-medium">{omp.validado_sgc_nombre}</b>
                {' '}el <span className="cifra">{fechaCorta(omp.validado_sgc_en)}</span>.
                {omp.nota_sgc && <span className="block text-xs mt-0.5">{omp.nota_sgc}</span>}
              </p>
            ) : (
              <div className="flex items-start gap-3">
                <p className="text-sm text-texto-3 flex-1">
                  Pendiente. Calidad revisa la evidencia antes de que se pueda
                  cerrar: quien ejecuta la acción no la da por buena solo.
                </p>
                {esSGC && !cerrada && omp.eficaz !== null && (
                  <button
                    onClick={() => mutValidarSGC.mutate()}
                    disabled={mutValidarSGC.isPending}
                    className="px-3 py-1.5 rounded-lg bg-acento-fuerte text-white text-xs
                      font-semibold hover:bg-acento disabled:opacity-60
                      transition-colors duration-150 flex-shrink-0"
                  >
                    Dar el visto bueno
                  </button>
                )}
              </div>
            )}
          </section>

          {/* ── Historial ── */}
          <section>
            <button
              onClick={() => setVerHistorial(!verHistorial)}
              className="flex items-center gap-1.5 etiqueta hover:text-texto transition-colors"
            >
              <IconoHistorial tam={13} />
              {verHistorial ? 'Ocultar el historial' : 'Ver quién cambió qué'}
            </button>
            {verHistorial && (
              historial?.length ? (
                <ul className="mt-2 space-y-1.5">
                  {historial.map(c => (
                    <li key={c.id} className="text-xs text-texto-2">
                      <span className="cifra text-texto-3">{fechaCorta(c.fecha)}</span>
                      {' · '}<b className="text-texto font-medium">{c.campo}</b>
                      {c.valor_anterior && <> de «{c.valor_anterior}»</>}
                      {c.valor_nuevo && <> a «{c.valor_nuevo}»</>}
                      {c.usuario_nombre && ` · ${c.usuario_nombre}`}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-2 text-xs text-texto-3">Todavía no se ha movido nada.</p>
              )
            )}
          </section>

          {/* ── Nota de cierre ── */}
          {(cerrada || omp.nota_cierre) && (
            <CampoLargo
              titulo="Cómo terminó" valor={omp.nota_cierre} editable={false}
              vacio="Sin nota de cierre." ayuda=""
              onGuardar={() => {}}
            />
          )}

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
