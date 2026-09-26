import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import PriorityBadge from "./PriorityBadge"
import Avatar from "./Avatar"
import SubtareasPanel from "./SubtareasPanel"
import HistorialPanel from "./HistorialPanel"
import ConfirmarCambios, { ConfirmarDescarte } from "./ConfirmarCambios"
import { calcularCambios } from "../cambiosFormulario"
import { useAuth } from "../../../core/AuthContext"
import {
  obtenerTarea, listarActualizaciones, agregarActualizacion, actualizarTarea,
  eliminarTarea, listarHistorialTarea, responderActualizacion,
} from "../api"
import { mensajeDeError } from "../../../core/errores.js"
import {
  IconoAlerta, IconoCerrar, IconoClip,
} from '../../../core/components/Iconos.jsx'
import {
  ESTADOS_TAREA, PRIORIDADES, AREAS, ALERTAS,
  alertaVencimiento, colorAvance, formatFecha, formatFechaHora,
  isoADatetimeLocal, datetimeLocalAIso,
  puedeEditar, puedeReportarAvance, puedeComentar,
  MAX_ENTREGABLE, MAX_HORAS, textoAplazamientos, textoHoras,
} from "../constants"

// Qué campos del formulario se confirman antes de guardar y cómo leer su
// valor original para poder compararlos.
const CAMPOS_CONFIRMABLES = {
  titulo:       (t) => t.titulo,
  prioridad:    (t) => t.prioridad,
  area:         (t) => t.area || "",
  fecha_inicio: (t) => isoADatetimeLocal(t.fecha_inicio),
  fecha_fin:    (t) => isoADatetimeLocal(t.fecha_fin),
}

/**
 * Las respuestas a un avance, y la caja para escribir una más.
 *
 * Preguntar «¿esto incluye la revisión de Calidad?» sobre un avance obligaba
 * a escribir OTRO avance: el historial quedaba con entradas que no eran
 * avances sino conversación, mezcladas y sin decir a cuál contestaban.
 *
 * La caja aparece al pulsar «Responder» y no siempre abierta: con diez
 * avances en pantalla, diez cajas de texto convierten la línea de tiempo en
 * un formulario.
 */
function Respuestas({ avance, puedeResponder, onResponder, guardando }) {
  const [abierta, setAbierta] = useState(false)
  const [texto, setTexto] = useState("")

  const enviar = () => {
    const limpio = texto.trim()
    if (!limpio) return
    onResponder(limpio, () => { setTexto(""); setAbierta(false) })
  }

  return (
    <div className="mt-2">
      {avance.respuestas?.length > 0 && (
        <ul className="space-y-2 border-l-2 border-borde pl-3 ml-1 mb-2">
          {avance.respuestas.map(r => (
            <li key={r.id}>
              <div className="flex items-center justify-between">
                <Avatar name={r.usuario_nombre} compact />
                <span className="text-[11px] text-texto-3">
                  {formatFecha(r.fecha, { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}
                </span>
              </div>
              {r.comentario && <p className="text-sm text-texto">{r.comentario}</p>}
            </li>
          ))}
        </ul>
      )}

      {puedeResponder && !abierta && (
        <button
          onClick={() => setAbierta(true)}
          className="text-[11px] font-semibold text-acento hover:underline"
        >
          Responder
        </button>
      )}

      {abierta && (
        <div className="space-y-2">
          <textarea
            value={texto} onChange={(e) => setTexto(e.target.value)} rows={2} autoFocus
            placeholder="Pregunta o aclaración sobre este avance"
            className="w-full rounded-lg border border-borde px-3 py-2 text-sm resize-none"
          />
          <div className="flex gap-2">
            <button
              onClick={enviar}
              disabled={!texto.trim() || guardando}
              className="px-3 py-1.5 rounded-lg bg-acento hover:bg-acento-fuerte
                disabled:opacity-40 text-white text-xs font-semibold transition"
            >
              {guardando ? 'Enviando…' : 'Responder'}
            </button>
            <button
              onClick={() => { setTexto(""); setAbierta(false) }}
              className="px-3 py-1.5 rounded-lg border border-borde text-xs font-semibold text-texto-2"
            >
              Cancelar
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

/**
 * Detalle de una TAREA. Relee la tarea del servidor por su id en vez de
 * arrastrar la copia que venía del listado: así los cambios hechos aquí
 * (estado, asignado, subtareas) se reflejan sin depender de que el listado
 * se refresque primero.
 */
export default function TareaDetailModal({ tareaId, usuarios = [], onClose }) {
  const queryClient = useQueryClient()
  const { user } = useAuth()
  const editable = puedeEditar(user)
  const puedeAvance = puedeReportarAvance(user)
  // Responder es comentar, no editar: **gerencia sí pregunta.** Es el caso
  // que motivó esto — quien lee el avance y necesita una aclaración es
  // justamente quien no mueve el avance.
  const puedeResponder = puedeComentar(user)
  const [confirmacion, setConfirmacion] = useState(null) // { cambios, ejecutar }
  const [pidiendoDescarte, setPidiendoDescarte] = useState(false)
  // `form` distinto de null es el modo edición. Se llena al pulsar "Editar
  // detalles" con los valores de ese momento, no en un efecto: así una
  // recarga de fondo de la query no pisa lo que se está escribiendo.
  const [form, setForm] = useState(null)
  const [comentario, setComentario] = useState("")
  const [avanceNuevo, setAvanceNuevo] = useState("")
  const [evidencia, setEvidencia] = useState(null)

  const { data: tarea, isLoading } = useQuery({
    queryKey: ["mp-tarea", tareaId],
    queryFn: () => obtenerTarea(tareaId),
  })

  const { data: actualizaciones = [] } = useQuery({
    queryKey: ["mp-actualizaciones", tareaId],
    queryFn: () => listarActualizaciones(tareaId),
  })

  const { data: historial = [] } = useQuery({
    queryKey: ["mp-historial-tarea", tareaId],
    queryFn: () => listarHistorialTarea(tareaId),
  })

  const empezarEdicion = () => setForm({
    titulo: tarea.titulo,
    descripcion: tarea.descripcion || "",
    area: tarea.area || "",
    riesgos: tarea.riesgos || "",
    entregable: tarea.entregable || "",
    // Vacío y no 0: el input tiene que poder quedar en blanco para volver a
    // «no se sabe», y un 0 diría que la tarea no cuesta nada.
    horas_estimadas: tarea.horas_estimadas ?? "",
    prioridad: tarea.prioridad,
    fecha_inicio: isoADatetimeLocal(tarea.fecha_inicio),
    fecha_fin: isoADatetimeLocal(tarea.fecha_fin),
  })

  const invalidar = () => {
    queryClient.invalidateQueries({ queryKey: ["mp-tarea", tareaId] })
    queryClient.invalidateQueries({ queryKey: ["mp-tareas"] })
    queryClient.invalidateQueries({ queryKey: ["mp-proyectos"] })
    queryClient.invalidateQueries({ queryKey: ["mp-historial-tarea", tareaId] })
    queryClient.invalidateQueries({ queryKey: ["mp-historial-general"] })
    queryClient.invalidateQueries({ queryKey: ["mp-resumen"] })
  }

  const mutCampo = useMutation({
    mutationFn: (payload) => actualizarTarea(tareaId, payload),
    onSuccess: () => { invalidar(); setConfirmacion(null) },
  })

  /**
   * Los cambios rápidos (estado, responsable) también pasan por confirmación:
   * son de los que más aparecen en el historial y de los que más se hacen sin
   * querer al abrir un desplegable.
   */
  const pedirConfirmacion = (campo, antes, despues, payload) => {
    setConfirmacion({
      cambios: [{ campo, antes, despues }],
      ejecutar: () => mutCampo.mutate(payload),
    })
  }

  const mutGuardarEdicion = useMutation({
    mutationFn: () => actualizarTarea(tareaId, {
      ...form,
      horas_estimadas: form.horas_estimadas === "" ? null : Number(form.horas_estimadas),
      fecha_inicio: datetimeLocalAIso(form.fecha_inicio),
      fecha_fin: datetimeLocalAIso(form.fecha_fin),
    }),
    onSuccess: () => { invalidar(); setForm(null); setConfirmacion(null) },
  })

  const cambiosPendientes = form && tarea
    ? calcularCambios(form, tarea, {
        ...CAMPOS_CONFIRMABLES,
        descripcion: (t) => t.descripcion || "",
        riesgos: (t) => t.riesgos || "",
        // Cambiar el entregable es mover la portería, así que se confirma
        // como el título y las fechas, no en silencio.
        entregable: (t) => t.entregable || "",
        horas_estimadas: (t) => (t.horas_estimadas ?? "").toString(),
      })
    : []

  const intentarGuardarEdicion = () => {
    if (cambiosPendientes.length === 0) { setForm(null); return }
    setConfirmacion({
      cambios: cambiosPendientes.filter(c => c.campo in CAMPOS_CONFIRMABLES || true),
      ejecutar: () => mutGuardarEdicion.mutate(),
    })
  }

  const intentarCerrarEdicion = () => {
    if (cambiosPendientes.length > 0) setPidiendoDescarte(true)
    else setForm(null)
  }

  // Cerrar el modal completo con la edición abierta también avisa.
  const intentarCerrarModal = () => {
    if (cambiosPendientes.length > 0) setPidiendoDescarte(true)
    else onClose()
  }

  const mutActualizacion = useMutation({
    mutationFn: () => {
      const fd = new FormData()
      if (comentario) fd.append('comentario', comentario)
      if (avanceNuevo !== '') fd.append('avance_pct_nuevo', avanceNuevo)
      if (evidencia) fd.append('evidencia', evidencia)
      return agregarActualizacion(tareaId, fd)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["mp-actualizaciones", tareaId] })
      invalidar()
      setComentario(""); setAvanceNuevo(""); setEvidencia(null)
    },
  })

  const mutResponder = useMutation({
    mutationFn: ({ actualizacionId, comentario }) =>
      responderActualizacion(tareaId, actualizacionId, comentario),
    onSuccess: () => queryClient.invalidateQueries({
      queryKey: ["mp-actualizaciones", tareaId],
    }),
    onError: (err) => alert(mensajeDeError(err, 'No se pudo enviar la respuesta.')),
  })

  const mutEliminar = useMutation({
    mutationFn: () => eliminarTarea(tareaId),
    onSuccess: () => { invalidar(); onClose() },
  })

  const alerta = tarea ? alertaVencimiento(tarea) : null

  return (
    <div className="fixed inset-0 bg-acento-fuerte/40 backdrop-blur-sm flex items-center justify-center p-4 z-50" onClick={intentarCerrarModal}>
      <div className="bg-white rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto shadow-xl" onClick={(e) => e.stopPropagation()}>

        {isLoading || !tarea ? (
          <div className="p-16 text-center text-sm text-texto-3">Cargando tarea...</div>
        ) : (
          <>
            <div className="bg-gradient-to-r from-acento-fuerte to-acento rounded-t-2xl p-6 text-white sticky top-0 z-10">
              <button onClick={intentarCerrarModal} aria-label="Cerrar" className="absolute top-4 right-4 text-white/70 hover:text-white"><IconoCerrar tam={18} /></button>
              <p className="text-xs uppercase tracking-wide text-white/70 mb-1">{tarea.proyecto_nombre}</p>
              <h2 className="text-xl font-bold pr-8">{tarea.titulo}</h2>
            </div>

            <div className="p-6 space-y-6">

              {alerta && (
                <div className={`text-sm font-semibold border rounded-xl px-4 py-2.5 ${ALERTAS[alerta].chip}`}>
                  {alerta === 'vencida'
                    ? `Esta tarea venció el ${formatFechaHora(tarea.fecha_fin)} y sigue sin completarse.`
                    : `Vence el ${formatFechaHora(tarea.fecha_fin)}.`}
                </div>
              )}

              {/* Acciones rápidas: estado y asignado, cambian al instante */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-texto-2 uppercase mb-1">Estado</label>
                  <select
                    value={tarea.estado}
                    disabled={!editable}
                    onChange={(e) => pedirConfirmacion(
                      'estado', tarea.estado, e.target.value, { estado: e.target.value },
                    )}
                    className="w-full rounded-lg border border-borde px-3 py-2 text-sm disabled:bg-superficie-2 disabled:text-texto-3"
                  >
                    {Object.entries(ESTADOS_TAREA).map(([v, cfg]) => <option key={v} value={v}>{cfg.label}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-texto-2 uppercase mb-1">Asignado a</label>
                  <select
                    value={tarea.asignado_a || ""}
                    disabled={!editable}
                    onChange={(e) => {
                      const id = e.target.value ? Number(e.target.value) : null
                      pedirConfirmacion(
                        'asignado_a',
                        tarea.asignado_nombre,
                        usuarios.find(u => u.id === id)?.nombre || null,
                        { asignado_a: id },
                      )
                    }}
                    className="w-full rounded-lg border border-borde px-3 py-2 text-sm disabled:bg-superficie-2 disabled:text-texto-3"
                  >
                    <option value="">Sin asignar</option>
                    {usuarios.map(u => <option key={u.id} value={u.id}>{u.nombre}</option>)}
                  </select>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <div className="flex-1 bg-superficie-2 rounded-full h-2.5">
                  <div className="h-2.5 rounded-full" style={{ width: `${tarea.avance_pct}%`, background: colorAvance(tarea.avance_pct) }} />
                </div>
                <span className="text-sm font-bold text-acento-fuerte">{tarea.avance_pct}%</span>
              </div>

              {/* Detalle: modo lectura o edición */}
              {!form ? (
                <div className="bg-superficie-2 rounded-xl p-4 space-y-3">
                  <div className="flex justify-between items-start">
                    <div className="flex gap-2">
                      <PriorityBadge priority={tarea.prioridad} />
                      {tarea.area && <span className="px-3 py-1 rounded-full text-xs font-semibold bg-white border border-borde text-texto-2">{tarea.area}</span>}
                    </div>
                    {editable && (
                      <button onClick={empezarEdicion} className="text-xs font-semibold text-acento hover:underline">
                        Editar detalles
                      </button>
                    )}
                  </div>
                  {tarea.descripcion && <p className="text-sm text-texto">{tarea.descripcion}</p>}

                  {/* El entregable va arriba y destacado: es el criterio con
                      el que se da por cumplida, no un dato más de la ficha. */}
                  {tarea.entregable && (
                    <div className="bg-white border border-borde rounded-lg px-3 py-2">
                      <span className="block text-[11px] font-semibold text-texto-3 uppercase tracking-wide">
                        Entregable
                      </span>
                      <span className="text-sm text-texto">{tarea.entregable}</span>
                    </div>
                  )}

                  {tarea.riesgos && (
                    <p className="text-sm text-negativo bg-negativo-bg border border-negativo/25 rounded-lg px-3 py-2">
                      <IconoAlerta tam={14} className="inline mr-1 -mt-0.5" />{tarea.riesgos}
                    </p>
                  )}
                  <div className="flex justify-between text-xs text-texto-2 pt-1">
                    <span>Inicio: {formatFechaHora(tarea.fecha_inicio)}</span>
                    <span className={alerta ? ALERTAS[alerta].texto : ''}>Fin: {formatFechaHora(tarea.fecha_fin)}</span>
                  </div>

                  {/* Las horas y los aplazamientos, juntos: son las dos
                      preguntas sobre el plan —cuánto cuesta y cuántas veces
                      se ha corrido—. Cada uno se esconde si no aplica: un
                      «0 aplazamientos» solo agrega ruido a lo que va bien. */}
                  {(textoHoras(tarea.horas_estimadas) || textoAplazamientos(tarea.veces_aplazada)) && (
                    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs pt-1">
                      {textoHoras(tarea.horas_estimadas) && (
                        <span className="text-texto-2">
                          <span className="cifra">{textoHoras(tarea.horas_estimadas)}</span> estimadas
                        </span>
                      )}
                      {/* Punto y palabra: el ámbar solo no se lee en voz alta. */}
                      {textoAplazamientos(tarea.veces_aplazada) && (
                        <span
                          className="inline-flex items-center gap-1.5 font-semibold text-alerta"
                          title="Cada movimiento de la fecha de fin queda en el historial, con sus dos fechas y quién lo hizo"
                        >
                          <span className="w-1.5 h-1.5 rounded-full bg-current" aria-hidden="true" />
                          {textoAplazamientos(tarea.veces_aplazada)}
                        </span>
                      )}
                    </div>
                  )}
                </div>
              ) : (
                <div className="bg-superficie-2 rounded-xl p-4 space-y-3">
                  <input value={form.titulo} onChange={(e) => setForm({ ...form, titulo: e.target.value })}
                    className="w-full rounded-lg border border-borde px-3 py-2 text-sm font-semibold" placeholder="Título" />
                  <textarea value={form.descripcion} onChange={(e) => setForm({ ...form, descripcion: e.target.value })}
                    rows={2} className="w-full rounded-lg border border-borde px-3 py-2 text-sm resize-none" placeholder="Descripción" />
                  <textarea value={form.riesgos} onChange={(e) => setForm({ ...form, riesgos: e.target.value })}
                    rows={2} className="w-full rounded-lg border border-borde px-3 py-2 text-sm resize-none" placeholder="Riesgos" />
                  <div>
                    <label className="block text-[11px] font-semibold text-texto-2 uppercase mb-1">
                      Entregable
                    </label>
                    <input value={form.entregable} maxLength={MAX_ENTREGABLE}
                      onChange={(e) => setForm({ ...form, entregable: e.target.value })}
                      placeholder="Qué tiene que quedar hecho"
                      className="w-full rounded-lg border border-borde px-3 py-2 text-sm" />
                  </div>
                  <div>
                    <label className="block text-[11px] font-semibold text-texto-2 uppercase mb-1">
                      Horas estimadas
                    </label>
                    <input type="number" min="0" max={MAX_HORAS} step="0.5"
                      value={form.horas_estimadas}
                      onChange={(e) => setForm({ ...form, horas_estimadas: e.target.value })}
                      className="w-full rounded-lg border border-borde px-3 py-2 text-sm cifra" />
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <select value={form.area} onChange={(e) => setForm({ ...form, area: e.target.value })} className="rounded-lg border border-borde px-3 py-2 text-sm">
                      <option value="">Área</option>
                      {AREAS.map(a => <option key={a} value={a}>{a}</option>)}
                    </select>
                    <select value={form.prioridad} onChange={(e) => setForm({ ...form, prioridad: e.target.value })} className="rounded-lg border border-borde px-3 py-2 text-sm">
                      {Object.entries(PRIORIDADES).map(([v, cfg]) => <option key={v} value={v}>{cfg.label}</option>)}
                    </select>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-[11px] font-semibold text-texto-2 uppercase mb-1">Inicio</label>
                      <input type="datetime-local" value={form.fecha_inicio}
                        onChange={(e) => setForm({ ...form, fecha_inicio: e.target.value })}
                        className="w-full rounded-lg border border-borde px-3 py-2 text-sm" />
                    </div>
                    <div>
                      <label className="block text-[11px] font-semibold text-texto-2 uppercase mb-1">Fin</label>
                      <input type="datetime-local" value={form.fecha_fin}
                        onChange={(e) => setForm({ ...form, fecha_fin: e.target.value })}
                        className="w-full rounded-lg border border-borde px-3 py-2 text-sm" />
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <button onClick={intentarCerrarEdicion} className="flex-1 border border-borde text-sm font-semibold py-2 rounded-lg hover:bg-superficie-2">Cancelar</button>
                    <button
                      onClick={intentarGuardarEdicion}
                      disabled={mutGuardarEdicion.isPending || cambiosPendientes.length === 0}
                      className="flex-1 bg-acento hover:bg-acento-fuerte disabled:opacity-40 text-white text-sm font-semibold py-2 rounded-lg"
                    >
                      {cambiosPendientes.length === 0 ? 'Sin cambios' : 'Guardar'}
                    </button>
                  </div>
                </div>
              )}

              {/* Subtareas — solo tienen sentido en una tarea de primer nivel */}
              {tarea.parent_id === null && (
                <div className="border-t border-borde pt-5">
                  <SubtareasPanel tarea={tarea} usuarios={usuarios} />
                </div>
              )}

              {/* Línea de tiempo de actualizaciones */}
              <div className="border-t border-borde pt-5">
                <h3 className="text-sm font-bold text-acento-fuerte mb-3">Actualizaciones de avance</h3>

                <div className="bg-superficie-2 rounded-xl p-4 mb-4 space-y-2">
                  <textarea
                    value={comentario} onChange={(e) => setComentario(e.target.value)}
                    placeholder="¿Qué avanzó desde la última actualización?"
                    rows={2} className="w-full rounded-lg border border-borde px-3 py-2 text-sm resize-none"
                  />
                  <div className="flex items-center gap-3">
                    {puedeAvance && (
                      <input
                        type="number" min={0} max={100} value={avanceNuevo}
                        onChange={(e) => setAvanceNuevo(e.target.value)}
                        placeholder="% avance"
                        className="w-28 rounded-lg border border-borde px-3 py-1.5 text-sm"
                      />
                    )}
                    <input
                      type="file" accept=".jpg,.jpeg,.png,.webp,.pdf"
                      onChange={(e) => setEvidencia(e.target.files?.[0] || null)}
                      className="flex-1 text-xs text-texto-2 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-acento-suave file:text-acento hover:file:bg-borde"
                    />
                  </div>
                  {evidencia && <p className="flex items-center gap-1.5 text-xs text-texto-2"><IconoClip tam={12} /> {evidencia.name}</p>}
                  <button
                    onClick={() => mutActualizacion.mutate()}
                    disabled={(!comentario && avanceNuevo === '' && !evidencia) || mutActualizacion.isPending}
                    className="w-full bg-acento hover:bg-acento-fuerte disabled:opacity-40 text-white text-sm font-semibold py-2 rounded-lg transition"
                  >
                    Publicar actualización
                  </button>
                </div>

                <div className="space-y-3">
                  {actualizaciones.length === 0 && (
                    <p className="text-xs text-texto-3 text-center py-4">Aún no hay actualizaciones registradas.</p>
                  )}
                  {actualizaciones.map(act => (
                    <div key={act.id} className="border-l-2 border-borde pl-4 py-1">
                      <div className="flex items-center justify-between mb-1">
                        <Avatar name={act.usuario_nombre} compact />
                        <span className="text-[11px] text-texto-3">{formatFecha(act.fecha, { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}</span>
                      </div>
                      {act.avance_pct_nuevo !== null && act.avance_pct_nuevo !== undefined && (
                        <span className="inline-block text-[11px] font-semibold text-acento bg-acento-suave rounded-full px-2 py-0.5 mb-1">
                          Avance actualizado a {act.avance_pct_nuevo}%
                        </span>
                      )}
                      {act.comentario && <p className="text-sm text-texto">{act.comentario}</p>}
                      {act.adjunto_evidencia && (
                        /\.(jpg|jpeg|png|webp)$/i.test(act.adjunto_evidencia) ? (
                          <a href={act.adjunto_evidencia} target="_blank" rel="noreferrer" className="inline-block mt-2">
                            <img src={act.adjunto_evidencia} alt="Evidencia" className="max-h-32 rounded-lg border border-borde" />
                          </a>
                        ) : (
                          <a href={act.adjunto_evidencia} target="_blank" rel="noreferrer" className="inline-block mt-2 text-xs text-acento font-semibold underline">
                            <IconoClip tam={13} /> Ver evidencia adjunta
                          </a>
                        )
                      )}

                      <Respuestas
                        avance={act}
                        puedeResponder={puedeResponder}
                        guardando={mutResponder.isPending}
                        onResponder={(texto, listo) => mutResponder.mutate(
                          { actualizacionId: act.id, comentario: texto },
                          { onSuccess: listo },
                        )}
                      />
                    </div>
                  ))}
                </div>
              </div>

              {/* Historial: quién cambió qué. Va aparte de las actualizaciones
                  porque una cosa es lo que la persona reporta y otra lo que el
                  sistema registró que efectivamente cambió. */}
              <div className="border-t border-borde pt-5">
                <h3 className="text-sm font-bold text-acento-fuerte mb-3">Historial de cambios</h3>
                <HistorialPanel
                  entradas={historial}
                  vacio="Esta tarea no ha tenido cambios desde que se creó."
                />
              </div>

              {editable && (
              <button
                onClick={() => {
                  const aviso = tarea.total_subtareas > 0
                    ? `¿Eliminar esta tarea y sus ${tarea.total_subtareas} subtarea(s)? Esta acción no se puede deshacer.`
                    : '¿Eliminar esta tarea? Esta acción no se puede deshacer.'
                  if (confirm(aviso)) mutEliminar.mutate()
                }}
                className="text-xs text-negativo hover:text-negativo font-semibold"
              >
                Eliminar tarea
              </button>
              )}
            </div>
          </>
        )}
      </div>

      {confirmacion && (
        <ConfirmarCambios
          cambios={confirmacion.cambios}
          guardando={mutCampo.isPending || mutGuardarEdicion.isPending}
          onConfirmar={confirmacion.ejecutar}
          onCancelar={() => setConfirmacion(null)}
        />
      )}

      {pidiendoDescarte && (
        <ConfirmarDescarte
          onSeguir={() => setPidiendoDescarte(false)}
          onDescartar={() => { setPidiendoDescarte(false); setForm(null) }}
        />
      )}
    </div>
  )
}
