/**
 * El detalle de una PQRS.
 *
 * Arriba, lo que se pregunta primero —de quién es, en qué va, quién la
 * tiene— y la línea de vida del caso. Luego «Para cerrar», que dice qué falta
 * y lleva a resolverlo, y el panel **Gestionar**: el ÚNICO lugar donde se
 * actúa (`GestionarPQRS.jsx`), incluido responder un concepto. Debajo, lo
 * que se LEE: el caso, los conceptos con sus respuestas y el historial. A la derecha, los datos de consulta
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
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useAuth } from '../../core/useAuth.js'
import { puedeVerModulo } from '../../core/modulos.js'
import api from '../../core/api.js'
import { Esqueleto } from '../../core/components/Cargando.jsx'
import Boton from '../../core/components/Boton.jsx'
import {
  IconoAlDia, IconoAlerta, IconoBuscar, IconoCandado, IconoCheck, IconoClip,
  IconoComentario, IconoEditar, IconoEmpresa, IconoEscalar, IconoEstrella,
  IconoEtiqueta, IconoIdea, IconoRecargar, IconoRecibo, IconoReloj, IconoUsuario,
} from '../../core/components/Iconos.jsx'
import {
  DESTINO_REQUISITO, ESTADOS, FILTROS_HISTORIAL, PRIORIDADES, TIPOS,
  avanceDeCierre, estadoDelPlazo, filtrarHistorial, iniciales, lineaDeVida, nombrePrincipal, tiempoEnArea, estaTerminada,
} from './constants.js'
import { resumenCadena } from './flujo.js'
import { BotonEditar, ModalEditarDatos, PanelAdjuntos } from './EdicionDatos.jsx'
import { ListaProductos } from './ProductosPQRS.jsx'
import GestionarPQRS from './GestionarPQRS.jsx'
import { useFlujo } from './useFlujo.js'
import { Dato, Insignia, InsigniaDe, Mensaje, Tarjeta } from './piezas.jsx'

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
 * La causa marcada pide una OMP («Asociado a» con «puede volverse OMP»): se
 * dice aquí, donde se está mirando el caso, y se abre en Mejora con lo que
 * ya se sabe. Solo para quien abre Mejora (admin y líderes); el formulario
 * de allá avisa si este caso ya tiene una.
 */
function SugiereOmp({ pqrs, onAbrir }) {
  return (
    <section aria-label="Sugiere una OMP"
             className="flex flex-wrap items-center gap-3 bg-superficie rounded-xl border border-borde border-l-[3px] border-l-acento shadow-sm px-4 py-3">
      <IconoIdea tam={18} className="text-acento flex-shrink-0" />
      <div className="flex-1 min-w-48">
        <p className="text-sm font-semibold text-texto">Esta PQRS puede volverse una OMP</p>
        <p className="text-xs text-texto-3 mt-0.5">
          La causa «{pqrs.asociado.nombre}» está marcada para trabajarse como oportunidad de mejora.
        </p>
      </div>
      <Boton tam="sm" tono="primario" icono={IconoIdea} onClick={onAbrir}>Abrir OMP</Boton>
    </section>
  )
}

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
/**
 * Los conceptos pedidos, con lo que se preguntó y lo que se respondió. Es
 * para LEER: firmar se hace arriba, en «Responder concepto» del panel. Con
 * los botones aquí abajo y el panel arriba, la gente escribía la respuesta
 * en «Avanzar» —quedaba un comentario— y la PQRS seguía bloqueada esperando
 * la firma. Al que le toca, la tarjeta lo dice y lo lleva.
 */
function TarjetaConceptos({ pqrsId, autorizaciones, hayPendiente, onResponder }) {
  const { data: flujo } = useFlujo(pqrsId)

  // En qué va el flujo lo ve también el área que firma: qué viene después.
  const cadena = resumenCadena(flujo?.estado, flujo?.pasos)
  if (!autorizaciones.length && !cadena) return null

  const respondidas = autorizaciones.filter(a => a.estado !== 'pendiente').length
  const resumen = cadena
    ? <span className="text-xs text-texto-3 truncate">{cadena}</span>
    : hayPendiente
      ? <Insignia tono="alerta">Esperando respuesta</Insignia>
      : <span className="cifra text-xs text-texto-3">{respondidas} de {autorizaciones.length} respondidos</span>

  return (
    <Tarjeta titulo="Conceptos" accion={resumen} sinRelleno>
      {!autorizaciones.length && (
        <p className="px-5 py-4 text-sm text-texto-2">Todavía no se ha pedido ningún concepto.</p>
      )}
      <div className="divide-y divide-borde">
        {autorizaciones.map((aut) => {
          const estado = ESTADO_AUTORIZACION[aut.estado] || { label: aut.estado, tono: 'neutro' }
          const firma = aut.autorizador_nombre || aut.tipo.area_autorizadora
          const teToca = aut.estado === 'pendiente' && aut.puede_responder
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
                  {teToca
                    ? <Boton tam="sm" tono="primario" onClick={onResponder}>Responder</Boton>
                    : <Insignia tono={estado.tono}>{estado.label}</Insignia>}
                </div>
              </div>

              {(aut.comentario_solicitud || aut.adjunto_solicitud || aut.comentario_respuesta || aut.adjunto_respuesta) && (
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
                </div>
              )}
            </div>
          )
        })}
      </div>
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
            const avance = EVENTOS_DE_AVANCE.has(seg.tipo_evento) || ['resuelto', 'cerrado', 'anulado'].includes(seg.estado_nuevo)
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
  // Sin modo elegido, el panel abre en el primero que toca: «Responder
  // concepto» si hay uno que esta persona puede firmar.
  const [modo, setModo] = useState(null)

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
  const gestionable = Boolean(alcance?.puede_gestionar) && !estaTerminada(pqrs)
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
            <Boton tono="primario" icono={IconoComentario} onClick={() => abrirModo(null)}>Gestionar</Boton>
          )}
        </div>
      </header>

      <LineaDeVida pqrs={pqrs} autorizaciones={autorizaciones} />

      <div className="grid lg:grid-cols-[minmax(0,1fr)_330px] gap-5 items-start">
        <div className="space-y-5 min-w-0">
          {/* Lo que falta para cerrar y el único lugar donde se actúa. */}
          <ParaCerrar pqrs={pqrs} onIr={irARequisito} />
          {pqrs.asociado?.sugiere_omp && puedeVerModulo(user, 'mejora') && (
            <SugiereOmp pqrs={pqrs} onAbrir={() => navigate(`/mejora?desde=pqrs&desde_id=${pqrs.id}`)} />
          )}
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

          <TarjetaConceptos pqrsId={pqrs.id} autorizaciones={autorizaciones} hayPendiente={hayPendiente}
                            onResponder={() => abrirModo('responder')} />

          <Historial seguimientos={pqrs.seguimientos} />
        </div>

        {/* Lo que se consulta */}
        <aside className="space-y-5 min-w-0">
          <Tarjeta titulo="Cliente"
                   accion={puedeEditarDatos && <BotonEditar onClick={() => setEditandoDatos(true)} etiqueta="Editar los datos del cliente" />}>
            <div className="space-y-2.5">
              <Dato etiqueta="Empresa">{pqrs.empresa}</Dato>
              <Dato etiqueta="NIT / CC">
                {pqrs.nit_cedula && (
                  <span className="inline-flex flex-wrap items-center gap-2">
                    <span className="cifra">{pqrs.nit_cedula}</span>
                    {/* Lo dice el servidor (`catalogo/clientes.py`). Sin dato
                        no se pinta nada: «no aparece» sería afirmar algo que
                        nadie revisó. Y no aparecer no es un error —cliente
                        nuevo, persona natural, NIT mal escrito—: va en gris. */}
                    {pqrs.cliente_en_erp === true && <Insignia tono="positivo">Cliente en el ERP</Insignia>}
                    {pqrs.cliente_en_erp === false && (
                      <span title="Puede ser un cliente nuevo, una persona natural o un NIT mal escrito. No impide nada.">
                        <Insignia tono="neutro">No aparece en el ERP</Insignia>
                      </span>
                    )}
                  </span>
                )}
              </Dato>
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
              puedeConfirmar={esServicioCliente && !estaTerminada(pqrs)}
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
