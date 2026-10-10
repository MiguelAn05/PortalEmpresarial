/**
 * El detalle de una PQRS.
 *
 * Arriba, lo que se pregunta primero —de quién es, en qué va, quién la
 * tiene— y la línea de vida del caso. Luego «Para cerrar», que dice qué falta
 * y lleva a resolverlo, y el panel **Gestionar**: el ÚNICO lugar donde se
 * actúa (`GestionarPQRS.jsx`). Debajo, lo que se LEE: el caso, los conceptos
 * con sus respuestas y el historial. A la derecha, los datos de consulta
 * (cliente, productos, evidencias, encuesta).
 *
 * Antes eran cinco tarjetas de acción apiladas —causa, flujo, gestionar,
 * autorizaciones, clasificación—, cada una con su botón, y para hacer una
 * sola cosa había que encontrar primero cuál era.
 *
 * Qué puede hacer quien mira lo dice el servidor en `alcance`, y qué falta
 * para cerrar, en `requisitos_cierre`: la pantalla esconde lo que no aplica,
 * no repite las reglas.
 */
import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useAuth } from '../../core/useAuth.js'
import api from '../../core/api.js'
import { Esqueleto } from '../../core/components/Cargando.jsx'
import Boton from '../../core/components/Boton.jsx'
import {
  IconoAlDia, IconoAlerta, IconoBuscar, IconoCandado, IconoCheck, IconoClip,
  IconoComentario, IconoEditar, IconoEmpresa, IconoEscalar, IconoEstrella,
  IconoEtiqueta, IconoFlecha, IconoRecargar, IconoRechazo, IconoRecibo, IconoReloj, IconoUsuario,
} from '../../core/components/Iconos.jsx'
import { mensajeDeError } from '../../core/errores.js'
import {
  DESTINO_REQUISITO, ESTADOS, FILTROS_HISTORIAL, PRIORIDADES, TIPOS,
  avanceDeCierre, estadoDelPlazo, filtrarHistorial, iniciales, lineaDeVida, nombrePrincipal, tiempoEnArea,
} from './constants.js'
import { resumenCadena } from './flujo.js'
import { BotonEditar, ModalEditarDatos, PanelAdjuntos } from './EdicionDatos.jsx'
import { ListaProductos } from './ProductosPQRS.jsx'
import GestionarPQRS from './GestionarPQRS.jsx'
import { useFlujo } from './useFlujo.js'
import { Dato, Insignia, InsigniaDe, Tarjeta } from './piezas.jsx'

const EVENTOS = {
  cambio_estado:           { Icono: IconoRecargar,   label: 'Cambio de estado'        },
  asignacion:              { Icono: IconoUsuario,    label: 'Asignación'              },
  asignacion_area:         { Icono: IconoEmpresa,    label: 'Área asignada'           },
  comentario:              { Icono: IconoComentario, label: 'Comentario'              },
  escalamiento:            { Icono: IconoEscalar,    label: 'Escalamiento'            },
  autorizacion_solicitada: { Icono: IconoCandado,    label: 'Concepto solicitado'     },
  autorizacion_respondida: { Icono: IconoAlDia,      label: 'Concepto respondido'     },
  reclasificacion:         { Icono: IconoEtiqueta,   label: 'Reclasificación'         },
  confirmacion_producto:   { Icono: IconoRecibo,     label: 'Producto confirmado'     },
  edicion_datos:           { Icono: IconoEditar,     label: 'Datos corregidos'        },
  cambio_adjunto:          { Icono: IconoClip,       label: 'Adjunto cambiado'        },
  cambio_producto:         { Icono: IconoRecibo,     label: 'Productos'               },
  causa:                   { Icono: IconoEtiqueta,   label: 'Causa'                   },
  flujo:                   { Icono: IconoRecargar,   label: 'Flujo de conceptos'      },
}

// Los eventos que cuentan un avance del caso llevan el icono en verde.
const EVENTOS_DE_AVANCE = new Set(['autorizacion_respondida', 'confirmacion_producto'])

function formatFecha(fecha) {
  if (!fecha) return '—'
  return new Date(fecha).toLocaleString('es-CO', {
    day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

/** «25 sept · 3:09 p. m.»: la fecha corta de la línea de vida y de las firmas. */
function fechaCorta(fecha) {
  if (!fecha) return null
  const d = new Date(fecha)
  const dia = d.toLocaleDateString('es-CO', { day: 'numeric', month: 'short' })
  const hora = d.toLocaleTimeString('es-CO', { hour: 'numeric', minute: '2-digit' })
  return `${dia} · ${hora}`
}

const claseCampo = 'w-full px-3 py-2 rounded-lg border border-borde text-sm text-texto placeholder-texto-3 focus:outline-none focus:ring-2 focus:ring-acento'
const claseArchivo = 'w-full text-xs text-texto-2 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-acento-suave file:text-acento hover:file:bg-borde'

// ── Cabecera y línea de vida ──────────────────────────────────────

/** El plazo legal en una insignia. Sin plazo que correr, nada. */
function InsigniaPlazo({ pqrs }) {
  const plazo = estadoDelPlazo(pqrs)
  if (!plazo) return null
  const tono = plazo.tono === 'neutro' ? 'positivo' : plazo.tono
  return <Insignia tono={tono}>{plazo.texto === 'Vencida' ? 'Plazo vencido' : plazo.texto}</Insignia>
}

/**
 * El recorrido del caso de izquierda a derecha. Las fechas salen del
 * historial, y el paso de autorizaciones solo aparece si hubo alguna. Ver
 * `lineaDeVida()`.
 */
function LineaDeVida({ pqrs, autorizaciones }) {
  const pasos = lineaDeVida(pqrs, autorizaciones)
  return (
    <ol className="flex bg-superficie border border-borde rounded-xl shadow-sm overflow-x-auto mb-5">
      {pasos.map(p => (
        <li key={p.clave}
            aria-current={p.estado === 'actual' ? 'step' : undefined}
            className={`flex-1 min-w-[9.5rem] px-4 py-3 border-r border-borde last:border-r-0 ${p.estado === 'actual' ? 'bg-acento-suave' : ''}`}>
          <div className={`flex items-center gap-2 text-xs font-semibold ${
            p.estado === 'actual' ? 'text-acento-fuerte' : p.estado === 'hecho' ? 'text-texto' : 'text-texto-3'
          }`}>
            {p.estado === 'hecho' && (
              <span className="w-4 h-4 rounded-full bg-positivo-vivo text-white grid place-items-center flex-shrink-0">
                <IconoCheck tam={10} />
              </span>
            )}
            {p.estado === 'actual' && <span className="w-4 h-4 rounded-full border-4 border-acento flex-shrink-0" />}
            {p.estado === 'pendiente' && <span className="w-4 h-4 rounded-full border border-dashed border-borde-fuerte flex-shrink-0" />}
            <span className="truncate">{p.titulo}</span>
          </div>
          <div className="cifra text-[11px] text-texto-3 mt-1 truncate">
            {p.detalle || fechaCorta(p.fecha) || (p.estado === 'pendiente' ? 'Pendiente' : 'En curso')}
          </div>
        </li>
      ))}
    </ol>
  )
}

// ── Para cerrar ───────────────────────────────────────────────────

/**
 * Qué falta para poder cerrar, a la vista y no como un 400 al guardar. Los
 * requisitos los manda el servidor (`gestion.requisitos_para_cerrar`, la
 * misma regla que rechaza el cierre) y cada uno que falta lleva a donde se
 * resuelve: un modo del panel o la tarjeta del producto.
 */
function ParaCerrar({ pqrs, onIr }) {
  const { total, hechos, faltan } = avanceDeCierre(pqrs.requisitos_cierre)
  if (!total) return null
  const listo = faltan.length === 0
  const radio = 14.5
  const largo = 2 * Math.PI * radio

  return (
    <section aria-label="Para cerrar"
             className={`bg-superficie rounded-xl border border-borde border-l-[3px] shadow-sm ${listo ? 'border-l-positivo-vivo' : 'border-l-ambar'}`}>
      <div className="flex items-center gap-3 px-4 pt-3 pb-2.5">
        <div className="relative w-9 h-9 flex-shrink-0">
          <svg width="36" height="36" viewBox="0 0 34 34" className="-rotate-90" aria-hidden="true">
            <circle cx="17" cy="17" r={radio} fill="none" strokeWidth="3.2" className="stroke-borde" />
            <circle cx="17" cy="17" r={radio} fill="none" strokeWidth="3.2" strokeLinecap="round"
                    strokeDasharray={largo} strokeDashoffset={largo * (1 - hechos / total)}
                    className={listo ? 'stroke-positivo-vivo' : 'stroke-ambar'} />
          </svg>
          <span className="cifra absolute inset-0 grid place-items-center text-[10px] font-semibold text-texto-2">{hechos}/{total}</span>
        </div>
        <div className="min-w-0">
          <p className="text-sm font-semibold text-texto">
            {listo
              ? 'Lista para cerrar'
              : `${faltan.length === 1 ? 'Falta 1 cosa' : `Faltan ${faltan.length} cosas`} para poder cerrar`}
          </p>
          <p className="text-xs text-texto-3 mt-0.5">
            {listo
              ? (pqrs.alcance?.puede_cerrar ? 'Se cierra desde «Avanzar».' : 'La cierra Servicio al Cliente.')
              : 'Pulsa lo que falta y te lleva a resolverlo.'}
          </p>
        </div>
      </div>
      <div className="flex flex-wrap gap-2 px-4 pb-3">
        {pqrs.requisitos_cierre.map(r => (r.cumple ? (
          <span key={r.clave} className="inline-flex items-center gap-1.5 rounded-full border border-positivo/25 bg-positivo-bg px-3 py-1 text-xs font-medium text-positivo">
            <IconoCheck tam={12} /> {r.etiqueta}
          </span>
        ) : (
          <button key={r.clave} type="button" onClick={() => onIr(r.clave)} title={r.mensaje}
                  className="inline-flex items-center gap-1.5 rounded-full border border-ambar/40 bg-alerta-bg px-3 py-1 text-xs font-medium text-alerta hover:brightness-95 transition">
            <IconoAlerta tam={12} /> {r.etiqueta}
          </button>
        )))}
      </div>
    </section>
  )
}

// ── Conceptos: lo que se pidió y lo que respondió cada área ───────

// «Devuelta» se cuenta aparte de «Rechazada»: el área no dijo que no, dijo
// que no le correspondía o que le faltaba información.
const ESTADO_AUTORIZACION = {
  pendiente: { label: 'Pendiente', tono: 'alerta'   },
  aprobada:  { label: 'Aprobada',  tono: 'positivo' },
  rechazada: { label: 'Rechazada', tono: 'negativo' },
  devuelta:  { label: 'Devuelta',  tono: 'neutro'   },
}
const FONDO_RESPUESTA = {
  aprobada: 'bg-positivo-bg',
  rechazada: 'bg-negativo-bg',
  devuelta: 'bg-superficie-2',
}
const LARGO_RECORTE = 260

/** Un mensaje de la conversación de un concepto: quién, y qué dijo. */
function Mensaje({ quien, texto, soporte, etiquetaSoporte, fondo = 'bg-superficie-2' }) {
  const [completo, setCompleto] = useState(false)
  const largo = (texto || '').length > LARGO_RECORTE
  return (
    <div className={`rounded-lg px-3.5 py-2.5 text-sm text-texto-2 leading-relaxed ${fondo}`}>
      <span className="etiqueta block mb-1">{quien}</span>
      {texto && (
        <p className={`whitespace-pre-wrap ${largo && !completo ? 'line-clamp-3' : ''}`}>{texto}</p>
      )}
      {largo && (
        <button type="button" onClick={() => setCompleto(v => !v)} className="text-xs font-semibold text-acento mt-1.5 hover:underline">
          {completo ? 'Ver menos' : 'Ver completo'}
        </button>
      )}
      {soporte && (
        <a href={soporte} target="_blank" rel="noreferrer"
           className="flex items-center gap-1.5 text-xs text-acento font-semibold hover:underline mt-2">
          <IconoClip tam={13} /> {etiquetaSoporte}
        </a>
      )}
    </div>
  )
}

/**
 * Los conceptos pedidos, con lo que se preguntó y lo que se respondió. Aquí
 * responde el ÁREA que firma (`puede_responder` lo resuelve el servidor): es
 * donde llega quien abre el enlace del correo. Pedirlos y mover el flujo es
 * de quien reparte, y vive en el panel Gestionar.
 */
function TarjetaConceptos({ pqrsId, autorizaciones, hayPendiente, invalidar }) {
  const { data: flujo } = useFlujo(pqrsId)
  const [respuesta, setRespuesta] = useState({ id: null, comentario: '', adjunto: null })
  const [error, setError] = useState('')

  const mutResponder = useMutation({
    mutationFn: ({ autId, decision, comentario, adjunto }) => {
      const datos = new FormData()
      datos.append('decision', decision)
      if (comentario?.trim()) datos.append('comentario_respuesta', comentario.trim())
      if (adjunto) datos.append('adjunto', adjunto)
      return api.post(`/autorizaciones/pqrs/${pqrsId}/${autId}/responder`, datos)
    },
    onSuccess: () => {
      invalidar()
      setRespuesta({ id: null, comentario: '', adjunto: null })
      setError('')
    },
    onError: (err) => setError(mensajeDeError(err, 'No se pudo registrar la decisión.')),
  })

  // En qué va el flujo lo ve también el área que firma: qué viene después.
  const cadena = resumenCadena(flujo?.estado, flujo?.pasos)
  if (!autorizaciones.length && !cadena) return null

  const respondidas = autorizaciones.filter(a => a.estado !== 'pendiente').length
  const resumen = cadena
    ? <span className="text-xs text-texto-3 truncate">{cadena}</span>
    : hayPendiente
      ? <Insignia tono="alerta">Esperando respuesta</Insignia>
      : <span className="cifra text-xs text-texto-3">{respondidas} de {autorizaciones.length} respondidos</span>

  const responder = (aut, decision) => mutResponder.mutate({
    autId: aut.id,
    decision,
    comentario: respuesta.id === aut.id ? respuesta.comentario : '',
    adjunto: respuesta.id === aut.id ? respuesta.adjunto : null,
  })

  return (
    <Tarjeta titulo="Conceptos" accion={resumen} sinRelleno>
      {!autorizaciones.length && (
        <p className="px-5 py-4 text-sm text-texto-2">Todavía no se ha pedido ningún concepto.</p>
      )}
      <div className="divide-y divide-borde">
        {autorizaciones.map((aut) => {
          const estado = ESTADO_AUTORIZACION[aut.estado] || { label: aut.estado, tono: 'neutro' }
          const firma = aut.autorizador_nombre || aut.tipo.area_autorizadora
          const comentarioPropio = respuesta.id === aut.id ? respuesta.comentario : ''
          return (
            <div key={aut.id} className="px-5 py-4">
              <div className="flex items-center gap-3">
                <span className="w-8 h-8 rounded-full bg-acento-suave text-acento-fuerte text-[11px] font-semibold grid place-items-center flex-shrink-0">
                  {iniciales(firma)}
                </span>
                <div className="min-w-0">
                  <div className="text-sm font-semibold text-texto truncate">{aut.tipo.nombre}</div>
                  <div className="text-xs text-texto-3 truncate">
                    {aut.tipo.area_autorizadora}{aut.autorizador_nombre ? ` · ${aut.autorizador_nombre}` : ''}
                  </div>
                </div>
                <div className="ml-auto flex items-center gap-2.5 flex-shrink-0">
                  <span className="cifra text-xs text-texto-3 hidden sm:inline">
                    {fechaCorta(aut.fecha_respuesta || aut.fecha_solicitud)}
                  </span>
                  <Insignia tono={estado.tono}>{estado.label}</Insignia>
                </div>
              </div>

              <div className="sm:pl-11 mt-3 space-y-2.5">
                {(aut.comentario_solicitud || aut.adjunto_solicitud) && (
                  <Mensaje quien={`Solicitó${aut.solicitante_nombre ? ` · ${aut.solicitante_nombre}` : ''}`}
                           texto={aut.comentario_solicitud} soporte={aut.adjunto_solicitud}
                           etiquetaSoporte="Soporte de la solicitud" />
                )}
                {(aut.comentario_respuesta || aut.adjunto_respuesta) && (
                  <Mensaje quien={`Respondió${aut.autorizador_nombre ? ` · ${aut.autorizador_nombre}` : ''}`}
                           texto={aut.comentario_respuesta} soporte={aut.adjunto_respuesta}
                           etiquetaSoporte="Soporte de la respuesta" fondo={FONDO_RESPUESTA[aut.estado]} />
                )}

                {/* Firma quien pertenece al área autorizadora, sea líder o
                    agente. El servidor ya lo resolvió en `puede_responder`. */}
                {aut.puede_responder && (
                  <div className="space-y-2 pt-1">
                    <textarea
                      value={comentarioPropio}
                      onChange={(e) => setRespuesta({ id: aut.id, comentario: e.target.value, adjunto: respuesta.id === aut.id ? respuesta.adjunto : null })}
                      placeholder="Comentario de la decisión (obligatorio para devolver)..."
                      rows={2} className={`${claseCampo} resize-none`}
                    />
                    <input type="file" accept=".jpg,.jpeg,.png,.webp,.pdf" aria-label="Soporte de la decisión (opcional)"
                           onChange={(e) => setRespuesta({ id: aut.id, comentario: comentarioPropio, adjunto: e.target.files?.[0] || null })}
                           className={claseArchivo} />
                    <div className="flex flex-wrap gap-2">
                      <button onClick={() => responder(aut, 'aprobada')} disabled={mutResponder.isPending}
                              className="flex-1 inline-flex items-center justify-center gap-1.5 bg-positivo-vivo text-white font-semibold py-2 rounded-lg text-xs transition disabled:opacity-50">
                        <IconoAlDia tam={15} /> Aprobar
                      </button>
                      <button onClick={() => responder(aut, 'rechazada')} disabled={mutResponder.isPending}
                              className="flex-1 inline-flex items-center justify-center gap-1.5 bg-negativo-vivo text-white font-semibold py-2 rounded-lg text-xs transition disabled:opacity-50">
                        <IconoRechazo tam={15} /> Rechazar
                      </button>
                      {/* Devolver no es rechazar: «esto no le toca a mi área» o
                          «falta información». Vuelve a Servicio al Cliente y
                          exige comentario — una devolución muda obliga a una
                          llamada. */}
                      <button onClick={() => responder(aut, 'devuelta')}
                              disabled={mutResponder.isPending || !comentarioPropio.trim()}
                              title={comentarioPropio.trim() ? 'No le corresponde a mi área o falta información' : 'Escribe primero por qué la devuelves'}
                              className="flex-1 inline-flex items-center justify-center gap-1.5 border border-borde-fuerte bg-white text-texto font-semibold py-2 rounded-lg text-xs transition hover:bg-superficie-2 disabled:opacity-50">
                        <IconoFlecha tam={15} className="rotate-180" /> Devolver
                      </button>
                    </div>
                    <p className="text-xs text-texto-3">
                      Devolver es para cuando no le corresponde a tu área o falta información: vuelve a Servicio al Cliente.
                    </p>
                  </div>
                )}
              </div>
            </div>
          )
        })}
      </div>
      {error && <p role="alert" className="text-sm text-negativo px-5 pb-4">{error}</p>}
    </Tarjeta>
  )
}

// ── Historial ─────────────────────────────────────────────────────

const VISIBLES_AL_INICIO = 8

function Historial({ seguimientos }) {
  const [filtro, setFiltro] = useState('todo')
  const [todos, setTodos] = useState(false)
  const eventos = filtrarHistorial(seguimientos, filtro)
  const mostrados = todos ? eventos : eventos.slice(0, VISIBLES_AL_INICIO)
  const restantes = eventos.length - mostrados.length

  const chips = (
    <div role="group" aria-label="Filtrar el historial" className="flex flex-wrap gap-1.5">
      {FILTROS_HISTORIAL.map(f => (
        <button key={f.clave} type="button" aria-pressed={filtro === f.clave} onClick={() => setFiltro(f.clave)}
                className={`px-2.5 py-1 rounded-full text-xs font-medium transition ${
                  filtro === f.clave ? 'bg-acento-fuerte text-white' : 'bg-superficie-2 text-texto-2 hover:text-texto'
                }`}>
          {f.label}
        </button>
      ))}
    </div>
  )

  return (
    <Tarjeta titulo="Historial interno" accion={chips} sinRelleno>
      {eventos.length === 0 ? (
        <p className="text-sm text-texto-2 text-center py-6">
          {seguimientos?.length ? 'Ningún evento de este tipo.' : 'Sin eventos registrados.'}
        </p>
      ) : (
        <ol className="py-2">
          {mostrados.map((seg, i) => {
            const evento = EVENTOS[seg.tipo_evento] || { Icono: IconoEtiqueta, label: seg.tipo_evento }
            const avance = EVENTOS_DE_AVANCE.has(seg.tipo_evento) || ['resuelto', 'cerrado'].includes(seg.estado_nuevo)
            return (
              <li key={seg.id} className="relative flex gap-3 px-5 py-2.5 hover:bg-superficie-2 transition-colors">
                <span aria-hidden="true" className={`absolute left-[31px] w-px bg-borde ${i === 0 ? 'top-5' : 'top-0'} ${i === mostrados.length - 1 ? 'h-5' : 'bottom-0'}`} />
                <span className={`relative z-10 w-6 h-6 rounded-full border grid place-items-center flex-shrink-0 ${
                  avance ? 'bg-positivo-bg border-positivo/30 text-positivo' : 'bg-superficie border-borde text-texto-3'
                }`}>
                  <evento.Icono tam={12} />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="text-sm text-texto-2 leading-snug">
                    <span className="font-semibold text-texto">{evento.label}</span>
                    {seg.comentario && <span className="whitespace-pre-wrap"> — {seg.comentario}</span>}
                  </div>
                  <div className="cifra text-[11px] text-texto-3 mt-0.5">
                    {seg.usuario_nombre
                      ? `${seg.usuario_nombre}${seg.usuario_area ? ` · ${seg.usuario_area}` : ''}`
                      : 'Cliente o sistema'}
                    {' · '}{formatFecha(seg.fecha)}
                  </div>
                  {seg.adjunto_evidencia && (
                    /\.(jpg|jpeg|png|webp)$/i.test(seg.adjunto_evidencia) ? (
                      <a href={seg.adjunto_evidencia} target="_blank" rel="noreferrer" className="inline-block mt-2">
                        <img src={seg.adjunto_evidencia} alt="Evidencia adjunta"
                             className="max-h-28 rounded-lg border border-borde hover:opacity-90 transition"
                             onError={(e) => { e.target.style.display = 'none' }} />
                      </a>
                    ) : (
                      <a href={seg.adjunto_evidencia} target="_blank" rel="noreferrer"
                         className="inline-flex items-center gap-1.5 mt-1.5 text-xs text-acento font-semibold hover:underline">
                        <IconoClip tam={13} /> Ver evidencia adjunta
                      </a>
                    )
                  )}
                </div>
              </li>
            )
          })}
        </ol>
      )}
      <div className="flex items-center justify-between px-5 py-2.5 border-t border-borde text-xs text-texto-3">
        <span className="cifra">
          {eventos.length} {eventos.length === 1 ? 'evento' : 'eventos'}
          {filtro !== 'todo' && ` de ${seguimientos?.length || 0}`}
        </span>
        {(restantes > 0 || todos) && eventos.length > VISIBLES_AL_INICIO && (
          <button type="button" onClick={() => setTodos(v => !v)} className="font-semibold text-acento hover:underline">
            {todos ? 'Ver menos' : `Ver los ${restantes} anteriores`}
          </button>
        )}
      </div>
    </Tarjeta>
  )
}

// ── Encuesta (solo lectura) ───────────────────────────────────────
// El agente no puede registrar la satisfacción del cliente: solo se ve lo
// que el cliente respondió por el enlace que le llega al cerrarse la PQRS.
const SOLUCIONADA_LABEL = { si: 'Sí', parcial: 'Parcialmente', no: 'No' }
const TIEMPO_LABEL = { excelente: 'Excelente', bueno: 'Bueno', regular: 'Regular', malo: 'Malo' }

function EncuestaSection({ encuesta }) {
  const [abierta, setAbierta] = useState(false)
  if (!encuesta) return null

  if (!encuesta.respondida_en) {
    return (
      <Tarjeta titulo="Encuesta">
        <div className="flex items-center gap-2.5 text-xs text-texto-2">
          <Insignia tono="neutro">Sin respuesta</Insignia>
          <span>Enviada el {formatFecha(encuesta.enviada_en)}</span>
        </div>
      </Tarjeta>
    )
  }

  return (
    <Tarjeta
      titulo="Encuesta"
      accion={
        <button type="button" onClick={() => setAbierta(v => !v)} aria-expanded={abierta}
                className="text-xs font-semibold text-acento hover:underline">
          {abierta ? 'Ocultar' : 'Ver respuestas'}
        </button>
      }
    >
      <div className="flex items-center gap-1">
        {[1, 2, 3, 4, 5].map(n => (
          <IconoEstrella key={n} tam={17} relleno={n <= encuesta.calificacion}
                         className={n <= encuesta.calificacion ? 'text-ambar' : 'text-borde-fuerte'} />
        ))}
        <span className="cifra text-xs text-texto-2 ml-1">{encuesta.calificacion}/5</span>
      </div>
      <p className="text-xs text-texto-3 mt-1">Respondida el {formatFecha(encuesta.respondida_en)}</p>
      {abierta && (
        <div className="mt-4 pt-4 border-t border-borde space-y-2.5">
          <Dato etiqueta="Tipo">{TIPOS[encuesta.tipo_solicitud]?.label || encuesta.tipo_solicitud}</Dato>
          <Dato etiqueta="Solucionada">{SOLUCIONADA_LABEL[encuesta.solucionada] || '—'}</Dato>
          <Dato etiqueta="Tiempo">{TIEMPO_LABEL[encuesta.calificacion_tiempo_respuesta] || '—'}</Dato>
          <Dato etiqueta="Recomienda">{encuesta.recomendaria ? 'Sí' : 'No'}</Dato>
          {encuesta.comentario && <p className="text-sm text-texto italic pt-1">«{encuesta.comentario}»</p>}
        </div>
      )}
    </Tarjeta>
  )
}

// ── Pantalla principal ────────────────────────────────────────────

function Cargando() {
  return (
    <div className="max-w-6xl mx-auto space-y-4" role="status" aria-label="Cargando la PQRS">
      <Esqueleto ancho="w-40" alto="h-3" />
      <Esqueleto ancho="w-72" alto="h-7" />
      <Esqueleto alto="h-14" className="rounded-xl" />
      <div className="grid lg:grid-cols-[1fr_330px] gap-4">
        <Esqueleto alto="h-64" className="rounded-xl" />
        <Esqueleto alto="h-64" className="rounded-xl" />
      </div>
    </div>
  )
}

/** Lleva a una tarjeta y la resalta un momento, para que se vea a dónde se llegó. */
function irA(id) {
  const el = document.getElementById(id)
  if (!el) return
  el.scrollIntoView({ behavior: 'smooth', block: 'center' })
  el.classList.add('ring-2', 'ring-acento')
  setTimeout(() => el.classList.remove('ring-2', 'ring-acento'), 1600)
}

export default function PQRSDetail() {
  const { id }      = useParams()
  const navigate    = useNavigate()
  const queryClient = useQueryClient()
  const { user }    = useAuth()
  const [editandoDatos, setEditandoDatos] = useState(false)
  const [modo, setModo] = useState('avanzar')

  const { data: pqrs, isLoading, isError } = useQuery({
    queryKey: ['pqrs', id],
    queryFn: async () => { const { data } = await api.get(`/pqrs/${id}`); return data },
  })
  const { data: tipos = [] } = useQuery({
    queryKey: ['tipos-autorizacion'],
    queryFn: async () => { const { data } = await api.get('/autorizaciones/tipos'); return data },
  })
  const { data: autorizaciones = [] } = useQuery({
    queryKey: ['autorizaciones', id],
    queryFn: async () => { const { data } = await api.get(`/autorizaciones/pqrs/${id}`); return data },
  })

  const hayPendiente = autorizaciones.some(a => a.estado === 'pendiente')

  // Única fuente de invalidación: la usan el panel y la tarjeta de
  // conceptos, así todo se refresca al instante (incluidos los requisitos de
  // cierre y el flujo, que cuelgan de ['pqrs', id]).
  const invalidar = () => {
    queryClient.invalidateQueries({ queryKey: ['autorizaciones', id] })
    queryClient.invalidateQueries({ queryKey: ['pqrs'] })
  }

  if (isLoading) return <Cargando />
  if (isError || !pqrs) return (
    <div className="flex flex-col items-center justify-center py-20 text-texto-2">
      <IconoBuscar tam={26} className="mb-3 text-texto-3" />
      <span className="text-sm">No se encontró esta PQRS. Puede que la hayan borrado o que el enlace esté mal.</span>
      <button onClick={() => navigate('/pqrs')} className="mt-4 text-acento text-sm font-medium hover:underline">Volver al listado</button>
    </div>
  )

  // Qué puede hacer esta persona lo decide el servidor y llega en `alcance`.
  const alcance = pqrs.alcance
  // Confirmar el producto es de quien reparte (Servicio al Cliente).
  const esServicioCliente = Boolean(alcance?.puede_reclasificar)
  // Corregir datos y adjuntos: el servidor ya descartó la PQRS cerrada.
  const puedeEditarDatos = Boolean(alcance?.puede_editar_datos)
  const gestionable = Boolean(alcance?.puede_gestionar) && pqrs.estado !== 'cerrado'
  const { titulo, subtitulo } = nombrePrincipal(pqrs)
  const tiempo = tiempoEnArea(pqrs)
  const refrescarDetalle = () => queryClient.invalidateQueries({ queryKey: ['pqrs'] })

  const abrirModo = (m) => { setModo(m); irA('gestionar') }
  const irARequisito = (clave) => {
    const destino = DESTINO_REQUISITO[clave]
    if (destino?.modo) abrirModo(destino.modo)
    else if (destino?.tarjeta) irA(destino.tarjeta)
  }

  return (
    <div className="max-w-6xl mx-auto">
      {/* Migas */}
      <nav aria-label="Ruta" className="flex items-center gap-1.5 text-xs text-texto-3 mb-3">
        <button onClick={() => navigate('/pqrs')} className="hover:text-acento hover:underline">PQRS</button>
        <span aria-hidden="true">›</span>
        <span className="text-texto-2 font-mono">{pqrs.codigo_seguimiento || `#${pqrs.id}`}</span>
      </nav>

      {/* Cabecera: de quién es, en qué va y quién la tiene. */}
      <header className="flex flex-wrap items-start justify-between gap-4 mb-4">
        <div className="min-w-0">
          <div className="font-mono text-xs text-texto-3">
            {pqrs.codigo_seguimiento || `PQRS #${pqrs.id}`} · radicada el {formatFecha(pqrs.fecha_creacion)}
            {pqrs.radicado_calidad && ` · Calidad: ${pqrs.radicado_calidad}`}
          </div>
          {/* Una empresa se reconoce por la empresa; una persona natural, por
              su nombre, sin repetirlo debajo. Ver `nombrePrincipal`. */}
          <h1 className="text-2xl font-semibold tracking-tight text-texto mt-1 mb-2">{titulo}</h1>
          <div className="flex flex-wrap items-center gap-1.5">
            <InsigniaDe mapa={TIPOS} valor={pqrs.tipo} />
            <InsigniaDe mapa={ESTADOS} valor={pqrs.estado} />
            <InsigniaDe mapa={PRIORIDADES} valor={pqrs.prioridad} />
            <InsigniaPlazo pqrs={pqrs} />
            {hayPendiente && <Insignia tono="alerta">Esperando un concepto</Insignia>}
            <Insignia plana>{pqrs.origen_publico === 'publico' ? 'Formulario web' : 'Interno'}</Insignia>
            {pqrs.canal_atencion && <Insignia plana>{pqrs.canal_atencion}</Insignia>}
          </div>
          {/* En qué área está el caso es la primera pregunta de quien abre
              una PQRS ajena: va aquí, no dentro del control de reasignar. */}
          <p className="text-xs text-texto-3 mt-2.5">
            Responsable: <strong className="text-texto-2 font-semibold">{pqrs.area_responsable || 'Sin asignar'}</strong>
            {tiempo && (
              <span className={pqrs.area_vencida ? 'text-negativo font-semibold' : ''}> ({tiempo.texto.toLowerCase()})</span>
            )}
            {pqrs.area_causante && <> · Causante: <strong className="text-texto-2 font-semibold">{pqrs.area_causante}</strong></>}
            {subtitulo && <> · Contacto: <strong className="text-texto-2 font-semibold">{subtitulo}</strong></>}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {puedeEditarDatos && (
            <Boton icono={IconoEditar} onClick={() => setEditandoDatos(true)}>Editar datos</Boton>
          )}
          {gestionable && (
            <Boton tono="primario" icono={IconoComentario} onClick={() => abrirModo('avanzar')}>Gestionar</Boton>
          )}
        </div>
      </header>

      <LineaDeVida pqrs={pqrs} autorizaciones={autorizaciones} />

      <div className="grid lg:grid-cols-[minmax(0,1fr)_330px] gap-5 items-start">
        <div className="space-y-5 min-w-0">
          {/* Lo que falta para cerrar y el único lugar donde se actúa. */}
          <ParaCerrar pqrs={pqrs} onIr={irARequisito} />
          <GestionarPQRS pqrs={pqrs} user={user} tipos={tipos} autorizaciones={autorizaciones}
                         hayPendiente={hayPendiente} modo={modo} onModo={setModo} invalidar={invalidar} />

          {/* Lo que se lee. */}
          <Tarjeta titulo="El caso">
            <p className="text-sm text-texto-2 leading-relaxed whitespace-pre-wrap">{pqrs.descripcion}</p>
            {/* Qué se le respondió al cliente y hasta cuándo puede confirmar:
                así nadie tiene que adivinar por qué lleva días «resuelto». */}
            {pqrs.solucion && (
              <div className={`mt-4 rounded-lg p-3.5 ${pqrs.estado === 'resuelto' ? 'bg-info-bg' : 'bg-positivo-bg'}`}>
                <span className="etiqueta block mb-1">
                  {pqrs.estado === 'resuelto' ? 'Respuesta enviada · esperando confirmación del cliente' : 'Respuesta al cliente'}
                </span>
                <p className="text-sm text-texto whitespace-pre-wrap">{pqrs.solucion}</p>
                {pqrs.estado === 'resuelto' && pqrs.plazo_confirmacion && (
                  <p className="text-xs text-texto-2 mt-1.5 flex items-center gap-1.5">
                    <IconoReloj tam={13} /> Si no responde antes del {formatFecha(pqrs.plazo_confirmacion)}, se cierra sola.
                  </p>
                )}
              </div>
            )}
          </Tarjeta>

          <TarjetaConceptos pqrsId={pqrs.id} autorizaciones={autorizaciones} hayPendiente={hayPendiente} invalidar={invalidar} />

          <Historial seguimientos={pqrs.seguimientos} />
        </div>

        {/* Lo que se consulta */}
        <aside className="space-y-5 min-w-0">
          <Tarjeta titulo="Cliente"
                   accion={puedeEditarDatos && <BotonEditar onClick={() => setEditandoDatos(true)} etiqueta="Editar los datos del cliente" />}>
            <div className="space-y-2.5">
              <Dato etiqueta="Empresa">{pqrs.empresa}</Dato>
              <Dato etiqueta="NIT / CC"><span className="cifra">{pqrs.nit_cedula}</span></Dato>
              <Dato etiqueta="Contacto">{pqrs.cliente_nombre}</Dato>
              <Dato etiqueta="Teléfono">{pqrs.cliente_telefono && <span className="cifra">{pqrs.cliente_telefono}</span>}</Dato>
              <Dato etiqueta="Email">{pqrs.cliente_email}</Dato>
              <Dato etiqueta="Ciudad">{[pqrs.ciudad, pqrs.departamento].filter(Boolean).join(', ') || null}</Dato>
            </div>
          </Tarjeta>

          <Tarjeta
            id="productos"
            className="transition-shadow scroll-mt-20"
            titulo={(pqrs.productos?.length ?? 0) > 1 ? `Productos (${pqrs.productos.length})` : 'Producto y factura'}
            accion={puedeEditarDatos && <BotonEditar onClick={() => setEditandoDatos(true)} etiqueta="Editar el número de factura" />}
          >
            {/* El que escribió el cliente a mano se confirma aquí contra el
                catálogo: después de cerrar ya no se puede. */}
            <ListaProductos
              pqrs={pqrs}
              puedeEditar={puedeEditarDatos}
              puedeConfirmar={esServicioCliente && pqrs.estado !== 'cerrado'}
              onCambio={refrescarDetalle}
            />
            {(pqrs.factura_numero || pqrs.canal_atencion) && (
              <div className="space-y-2.5 mt-4 pt-4 border-t border-borde">
                <Dato etiqueta="Factura">{pqrs.factura_numero && <span className="cifra">{pqrs.factura_numero}</span>}</Dato>
                <Dato etiqueta="Canal">{pqrs.canal_atencion}</Dato>
              </div>
            )}
          </Tarjeta>

          {/* Adjuntos: se ven, se cambian y se quitan. */}
          <PanelAdjuntos pqrs={pqrs} puedeEditar={puedeEditarDatos} onCambio={refrescarDetalle} />

          <EncuestaSection encuesta={pqrs.encuesta} />
        </aside>
      </div>

      {editandoDatos && (
        <ModalEditarDatos pqrs={pqrs} onCerrar={() => setEditandoDatos(false)} onGuardado={refrescarDetalle} />
      )}
    </div>
  )
}
