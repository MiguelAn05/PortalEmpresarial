import { useEffect, useMemo, useRef, useState } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import * as pdfjs from "pdfjs-dist"
// El worker sale del propio build (`dist/assets`), no de un CDN: el
// servidor no tiene internet estable y un estado financiero no se le pasa a
// un tercero para dibujarlo.
import urlWorker from "pdfjs-dist/build/pdf.worker.min.mjs?url"
import {
  agregarObservacion, atenderObservacion, borrarObservacion, descargarArchivoDocumento,
  listarHojasDocumento, obtenerDocumento, responderDocumento,
} from "./api"
import {
  MAX_OBSERVACION, formatFechaHora, textoEventoRevision, textoTamano,
} from "./constants"
import { claveCelda, lugarObservacion, marcaEnPagina, numerarObservaciones } from "./revision.js"
import { ChipDocumento } from "./components/DocumentoPanel"
import HojaExcel from "./components/HojaExcel"
import { mensajeDeError } from "../../core/errores.js"
import Boton from "../../core/components/Boton.jsx"
import { Esqueleto } from "../../core/components/Cargando.jsx"
import { IconoChevron, IconoComentario, IconoPapelera } from "../../core/components/Iconos.jsx"

pdfjs.GlobalWorkerOptions.workerSrc = urlWorker

/** El recuadro de una marca, en porcentajes de la página. */
const estiloRecuadro = (m) => ({
  left: `${m.pos_x * 100}%`, top: `${m.pos_y * 100}%`,
  width: `${m.ancho * 100}%`, height: `${m.alto * 100}%`,
})

/**
 * Una página del PDF dibujada en un canvas, con las observaciones encima:
 * un punto, o un recuadro si quien revisa arrastró. Las coordenadas son
 * fracciones de la página (ver `marcaEnPagina`), así caen en el mismo sitio
 * con cualquier ancho.
 */
function PaginaPdf({ pdf, numero, ancho, observaciones, puedeMarcar, pendiente, activa, onMarcar, onElegir }) {
  const canvas = useRef(null)
  const [proporcion, setProporcion] = useState(1.294)   // A4 hasta que llegue la de verdad
  // Mientras se arrastra: dónde se apretó, dónde va el mouse (en píxeles de
  // la pantalla) y el tamaño de la página. Al soltar es un punto o un recuadro.
  const [arrastre, setArrastre] = useState(null)

  useEffect(() => {
    let cancelado = false
    let dibujo = null
    pdf.getPage(numero).then((pagina) => {
      if (cancelado || !canvas.current) return
      const base = pagina.getViewport({ scale: 1 })
      // Nítido en pantallas de alta densidad: se dibuja al doble y se muestra al tamaño.
      const densidad = window.devicePixelRatio || 1
      const vista = pagina.getViewport({ scale: (ancho / base.width) * densidad })
      canvas.current.width = vista.width
      canvas.current.height = vista.height
      setProporcion(base.height / base.width)
      dibujo = pagina.render({ canvasContext: canvas.current.getContext("2d"), viewport: vista })
      return dibujo.promise
    }).catch(() => { /* cancelado al cambiar el ancho: no es un error */ })
    return () => { cancelado = true; dibujo?.cancel() }
  }, [pdf, numero, ancho])

  const posicion = (e) => ({ x: e.clientX, y: e.clientY })
  const alApretar = (e) => {
    if (!puedeMarcar || e.button !== 0 || e.target.closest("[data-punto]")) return
    // Captura el puntero: si se suelta fuera de la página, igual llega aquí.
    e.currentTarget.setPointerCapture(e.pointerId)
    // El tamaño de la página se toma al apretar: durante el arrastre no cambia.
    setArrastre({ inicio: posicion(e), actual: posicion(e), rect: e.currentTarget.getBoundingClientRect() })
  }
  const alMover = (e) => { if (arrastre) setArrastre({ ...arrastre, actual: posicion(e) }) }
  const alSoltar = (e) => {
    if (!arrastre) return
    onMarcar({ pagina: numero, ...marcaEnPagina(arrastre.inicio, posicion(e), e.currentTarget.getBoundingClientRect()) })
    setArrastre(null)
  }
  const dibujando = arrastre ? marcaEnPagina(arrastre.inicio, arrastre.actual, arrastre.rect) : null

  return (
    <div
      id={`pagina-${numero}`}
      onPointerDown={alApretar}
      onPointerMove={alMover}
      onPointerUp={alSoltar}
      onPointerCancel={() => setArrastre(null)}
      className={`relative bg-white shadow-md mx-auto select-none ${puedeMarcar ? "cursor-crosshair touch-none" : ""}`}
      style={{ width: ancho, height: ancho * proporcion }}
    >
      <canvas ref={canvas} className="block w-full h-full" />
      {/* Los recuadros no atrapan el mouse: se puede dibujar otro encima.
          Lo que se pulsa es su número, en la esquina. */}
      {observaciones.filter(o => o.ancho).map((o) => (
        <span
          key={`recuadro-${o.id}`} aria-hidden="true"
          className={`absolute pointer-events-none border-2 rounded-sm transition
            ${o.atendida ? "border-positivo-vivo bg-positivo-vivo/10" : "border-negativo-vivo bg-negativo-vivo/10"}
            ${activa === o.id ? "ring-4 ring-acento/30" : ""}`}
          style={estiloRecuadro(o)}
        />
      ))}
      {observaciones.map((o) => (
        <button
          key={o.id} data-punto
          onClick={() => onElegir(o.id)}
          title={o.texto}
          className={`absolute -translate-x-1/2 -translate-y-1/2 w-7 h-7 rounded-full text-xs font-bold cifra shadow-md border-2 border-white transition
            ${o.atendida ? "bg-positivo-vivo text-white" : "bg-negativo-vivo text-white"}
            ${activa === o.id ? "ring-4 ring-acento/40 scale-110" : ""}`}
          style={{ left: `${o.pos_x * 100}%`, top: `${o.pos_y * 100}%` }}
        >
          {o.numero}
        </button>
      ))}
      {dibujando?.ancho && (
        <span className="absolute pointer-events-none border-2 border-dashed border-acento bg-acento/10 rounded-sm"
              style={estiloRecuadro(dibujando)} />
      )}
      {pendiente?.pagina === numero && pendiente.ancho && (
        <span className="absolute pointer-events-none border-2 border-dashed border-acento bg-acento/10 rounded-sm animate-pulse"
              style={estiloRecuadro(pendiente)} />
      )}
      {pendiente?.pagina === numero && !pendiente.ancho && (
        <span
          className="absolute -translate-x-1/2 -translate-y-1/2 w-7 h-7 rounded-full bg-acento text-white text-xs font-bold flex items-center justify-center shadow-md border-2 border-white animate-pulse"
          style={{ left: `${pendiente.pos_x * 100}%`, top: `${pendiente.pos_y * 100}%` }}
        >
          +
        </span>
      )}
      <span className="absolute bottom-2 right-3 text-[11px] text-texto-3 cifra bg-white/80 rounded px-1.5">
        Página {numero}
      </span>
    </div>
  )
}

function bajarArchivo(blob, nombre) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = nombre
  a.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

/**
 * El documento a pantalla completa, para leerlo y firmarlo.
 *
 * Quien tiene el turno hace clic donde está el problema y escribe la
 * observación; después aprueba o devuelve desde el panel de la derecha. Se
 * firma aquí y no desde el detalle de la tarea a propósito: se firma lo que
 * se leyó. El documento no se edita en el portal —se corrige en el original y
 * se sube otra versión—, que es lo que deja constancia de qué se aprobó.
 */
function Visor({ versionId }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const clave = ["mp-documento", versionId]

  const { data, isLoading, error } = useQuery({ queryKey: clave, queryFn: () => obtenerDocumento(versionId) })
  // gcTime 0: un estado financiero no se queda en la memoria de la pestaña
  // después de cerrar el visor.
  const { data: archivo } = useQuery({
    queryKey: ["mp-documento-archivo", versionId],
    queryFn: () => descargarArchivoDocumento(versionId),
    enabled: Boolean(data),
    staleTime: Infinity,
    gcTime: 0,
  })

  const [pdf, setPdf] = useState(null)
  const [errorPdf, setErrorPdf] = useState(null)
  const [ancho, setAncho] = useState(760)
  const columna = useRef(null)
  const [pendiente, setPendiente] = useState(null)       // { pagina, pos_x, pos_y } | { hoja, celda } | { general: true }
  const [hojaActiva, setHojaActiva] = useState(0)
  const [textoObs, setTextoObs] = useState("")
  const [activa, setActiva] = useState(null)
  const [comentario, setComentario] = useState("")
  const [errorAccion, setErrorAccion] = useState(null)

  const esPdf = data?.version.tipo === "pdf"
  const esExcel = data?.version.tipo === "xlsx"

  // Los nombres de las hojas los lee el servidor; con ellos se salta a la
  // hoja de una observación al elegirla en el panel.
  const { data: hojas, isError: errorHojas } = useQuery({
    queryKey: ["mp-documento-hojas", versionId],
    queryFn: () => listarHojasDocumento(versionId),
    enabled: esExcel,
    staleTime: Infinity,
  })

  useEffect(() => {
    if (!archivo || !esPdf) return
    let cancelado = false
    let carga = null
    archivo.arrayBuffer()
      .then((datos) => {
        // isEvalSupported en false: pdf.js no compila nada que venga dentro
        // del archivo, aunque el archivo lo pida.
        carga = pdfjs.getDocument({ data: new Uint8Array(datos), isEvalSupported: false })
        return carga.promise
      })
      .then((doc) => { if (!cancelado) setPdf(doc) })
      .catch(() => { if (!cancelado) setErrorPdf("No se pudo abrir el PDF. Descárgalo para verlo en tu computador.") })
    return () => { cancelado = true; carga?.destroy() }
  }, [archivo, esPdf])

  // El ancho de la columna decide el de las páginas: así un portátil y un
  // monitor grande ven el documento entero sin barra horizontal.
  useEffect(() => {
    if (!columna.current) return
    const observador = new ResizeObserver(([entrada]) => {
      setAncho(Math.max(320, Math.min(1000, Math.floor(entrada.contentRect.width))))
    })
    observador.observe(columna.current)
    return () => observador.disconnect()
  }, [data])

  const observaciones = useMemo(() => numerarObservaciones(data?.version.observaciones), [data])
  const porPagina = useMemo(() => {
    const mapa = {}
    for (const o of observaciones) if (o.pagina) (mapa[o.pagina] ||= []).push(o)
    return mapa
  }, [observaciones])

  const refrescar = () => {
    queryClient.invalidateQueries({ queryKey: clave })
    queryClient.invalidateQueries({ queryKey: ["mp-revision", data?.tarea.id] })
    queryClient.invalidateQueries({ queryKey: ["mp-tarea", data?.tarea.id] })
    queryClient.invalidateQueries({ queryKey: ["mp-tareas"] })
    queryClient.invalidateQueries({ queryKey: ["mp-documentos-pendientes"] })
  }
  const conError = (porDefecto) => (err) => setErrorAccion(mensajeDeError(err, porDefecto))

  const mutObs = useMutation({
    mutationFn: () => agregarObservacion(versionId, {
      texto: textoObs,
      ...(pendiente?.general ? {} : pendiente),
    }),
    onSuccess: () => { setPendiente(null); setTextoObs(""); setErrorAccion(null); refrescar() },
    onError: conError("No se pudo guardar la observación."),
  })
  const mutBorrar = useMutation({
    mutationFn: (id) => borrarObservacion(id),
    onSuccess: refrescar,
    onError: conError("No se pudo quitar la observación."),
  })
  const mutAtender = useMutation({
    mutationFn: ({ id, atendida }) => atenderObservacion(id, atendida),
    onSuccess: refrescar,
    onError: conError("No se pudo marcar la observación."),
  })
  const mutResponder = useMutation({
    mutationFn: (decision) => responderDocumento(versionId, decision, comentario),
    onSuccess: () => { setComentario(""); setErrorAccion(null); refrescar() },
    onError: conError("No se pudo guardar tu respuesta."),
  })

  if (error) {
    return (
      <div className="max-w-xl mx-auto px-6 py-16 text-center space-y-3">
        <p className="text-texto">{mensajeDeError(error, "No se pudo abrir el documento.")}</p>
        <Boton onClick={() => navigate("/master-planner")}>Volver a Master Planner</Boton>
      </div>
    )
  }
  if (isLoading || !data) {
    return (
      <div className="max-w-[1400px] mx-auto px-6 py-8 space-y-4">
        <Esqueleto ancho="w-1/3" alto="h-8" />
        <Esqueleto alto="h-[70vh]" />
      </div>
    )
  }

  const { tarea, revision, version } = data
  const puedeMarcar = version.puede_responder
  const esUltimoPaso = revision.pasos.at(-1)?.en_turno
  const elegir = (id) => {
    setActiva(id)
    const o = observaciones.find(x => x.id === id)
    if (o?.pagina) document.getElementById(`pagina-${o.pagina}`)?.scrollIntoView({ behavior: "smooth", block: "center" })
    if (o?.celda) {
      const i = hojas?.indexOf(o.hoja) ?? -1
      if (i >= 0) setHojaActiva(i)
      // Después de pintar la hoja nueva, si hubo que cambiar de pestaña.
      setTimeout(() => document.getElementById(`celda-${claveCelda(o.hoja, o.celda)}`)
        ?.scrollIntoView({ behavior: "smooth", block: "center", inline: "center" }), 150)
    }
    document.getElementById(`obs-${id}`)?.scrollIntoView({ behavior: "smooth", block: "nearest" })
  }
  const aprobar = () => {
    const aviso = esUltimoPaso
      ? `Vas a aprobar como ${version.turno_de.nombre}. Es la última firma: la tarea queda cumplida.`
      : `Vas a aprobar como ${version.turno_de.nombre}. Pasa a ${revision.pasos.find(p => p.orden > version.paso_actual)?.revisor_nombre}.`
    if (confirm(aviso)) mutResponder.mutate("aprobar")
  }

  return (
    <div className="max-w-[1400px] mx-auto px-4 sm:px-6 py-6 space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-4 print:hidden">
        <div className="min-w-0">
          <button
            onClick={() => navigate(`/master-planner?tarea=${tarea.id}`)}
            className="text-xs font-semibold text-acento hover:underline inline-flex items-center gap-1 mb-1"
          >
            <IconoChevron tam={14} className="rotate-180" /> Volver a la tarea
          </button>
          <h1 className="text-2xl font-bold text-acento-fuerte truncate">{tarea.titulo}</h1>
          <p className="text-sm text-texto-2">
            {tarea.proyecto_nombre || "Sin proyecto"} · Lo preparó {tarea.asignado_nombre || "sin asignar"}
            {tarea.fecha_fin && <> · Vence {formatFechaHora(tarea.fecha_fin)}</>}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <ChipDocumento estado={version.estado} />
          <Boton tam="sm" disabled={!archivo} onClick={() => bajarArchivo(archivo, version.nombre_original)}>
            Descargar
          </Boton>
        </div>
      </div>

      {!data.es_la_ultima && (
        <p className="text-sm text-alerta bg-alerta-bg border border-ambar/30 rounded-xl px-4 py-2.5">
          Esta es la versión {version.numero}. Ya hay una más reciente: lo que se ve aquí es lo que se revisó en su momento.
        </p>
      )}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px] items-start">
        {/* El documento */}
        <div ref={columna} className="space-y-4 min-w-0">
          {esPdf ? (
            errorPdf ? <p className="text-sm text-negativo">{errorPdf}</p>
            : !pdf ? <Esqueleto alto="h-[70vh]" />
            : Array.from({ length: pdf.numPages }, (_, i) => (
              <PaginaPdf
                key={i + 1} pdf={pdf} numero={i + 1} ancho={ancho}
                observaciones={porPagina[i + 1] || []}
                puedeMarcar={puedeMarcar} pendiente={pendiente} activa={activa}
                onMarcar={(p) => { setPendiente(p); setActiva(null) }}
                onElegir={elegir}
              />
            ))
          ) : hojas && !errorHojas ? (
            <HojaExcel
              versionId={versionId} hojas={hojas} indice={hojaActiva} onCambiarHoja={setHojaActiva}
              observaciones={observaciones} puedeMarcar={puedeMarcar} pendiente={pendiente} activa={activa}
              onMarcar={(p) => { setPendiente(p); setActiva(null) }}
              onElegir={elegir}
            />
          ) : errorHojas ? (
            <div className="bg-white rounded-xl shadow-sm border border-borde p-8 text-center space-y-3">
              <p className="text-texto font-semibold">Este Excel no se pudo leer en el portal ({textoTamano(version.tamano)}).</p>
              <p className="text-sm text-texto-2">
                Descárgalo para revisarlo en tu computador y deja las observaciones generales en el panel.
              </p>
              <Boton tono="primario" disabled={!archivo} onClick={() => bajarArchivo(archivo, version.nombre_original)}>
                Descargar {version.nombre_original}
              </Boton>
            </div>
          ) : <Esqueleto alto="h-[70vh]" />}
        </div>

        {/* El panel: sticky, para que las observaciones y la firma no se
            pierdan al bajar por un documento de cuarenta páginas. */}
        <aside className="space-y-4 lg:sticky lg:top-20">
          <section className="bg-white rounded-xl shadow-sm border border-borde p-4 space-y-2">
            <p className="text-sm font-semibold text-texto truncate">{version.nombre_original}</p>
            <p className="text-xs text-texto-3 cifra">
              Versión {version.numero} · subida por {version.subido_por_nombre} el {formatFechaHora(version.subido_en)}
            </p>
            {version.turno_de && (
              <p className="text-xs font-semibold text-info">
                Turno de {version.turno_de.revisor_nombre} ({version.turno_de.nombre})
              </p>
            )}
            {version.eventos.length > 0 && (
              <ul className="space-y-1 pt-2 border-t border-borde">
                {version.eventos.map((e, i) => (
                  <li key={i} className="text-xs text-texto-2">
                    <span className="font-semibold text-texto">{textoEventoRevision(e)}</span> · {formatFechaHora(e.fecha)}
                    {e.comentario && <span className="block text-texto">«{e.comentario}»</span>}
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="bg-white rounded-xl shadow-sm border border-borde p-4 space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-bold text-acento-fuerte">
                Observaciones <span className="cifra text-texto-3 font-semibold">({observaciones.length})</span>
              </h2>
              {puedeMarcar && !pendiente && (
                <button onClick={() => setPendiente({ general: true })} className="text-xs font-semibold text-acento hover:underline">
                  + General
                </button>
              )}
            </div>

            {puedeMarcar && !pendiente && (
              <p className="text-xs text-texto-3">
                {esPdf
                  ? "Haz clic donde está lo que hay que corregir, o arrastra para enmarcar una zona: una tabla, un párrafo, una cifra."
                  : "Haz clic en la celda donde está lo que hay que corregir, para dejar ahí la observación."}
              </p>
            )}

            {pendiente && (
              <div className="bg-info-bg border border-acento/20 rounded-lg p-3 space-y-2">
                <p className="text-xs font-semibold text-info">
                  {pendiente.general ? "Observación general" : `Observación en ${lugarObservacion(pendiente)}`}
                </p>
                <textarea
                  autoFocus value={textoObs} onChange={(e) => setTextoObs(e.target.value)}
                  maxLength={MAX_OBSERVACION} rows={3}
                  placeholder="Qué hay que corregir y por qué"
                  className="w-full rounded-lg border border-borde px-3 py-2 text-sm resize-y bg-white"
                />
                <div className="flex justify-end gap-2">
                  <Boton tam="sm" tono="fantasma" onClick={() => { setPendiente(null); setTextoObs("") }}>Cancelar</Boton>
                  <Boton tam="sm" tono="primario" disabled={!textoObs.trim()} cargando={mutObs.isPending} onClick={() => mutObs.mutate()}>
                    Guardar
                  </Boton>
                </div>
              </div>
            )}

            {observaciones.length === 0 && !pendiente && (
              <p className="text-xs text-texto-3">Nadie ha dejado observaciones en esta versión.</p>
            )}

            <ol className="space-y-2">
              {observaciones.map((o) => (
                <li
                  key={o.id} id={`obs-${o.id}`}
                  onClick={() => elegir(o.id)}
                  className={`rounded-lg border p-3 cursor-pointer transition ${activa === o.id ? "border-acento bg-info-bg" : "border-borde hover:bg-superficie-2"}`}
                >
                  <div className="flex items-start gap-2">
                    <span className={`w-6 h-6 rounded-full text-[11px] font-bold cifra flex items-center justify-center flex-shrink-0 text-white ${o.atendida ? "bg-positivo-vivo" : "bg-negativo-vivo"}`}>
                      {o.pagina || o.celda ? o.numero : <IconoComentario tam={12} />}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className={`text-sm text-texto whitespace-pre-wrap ${o.atendida ? "line-through text-texto-3" : ""}`}>{o.texto}</p>
                      <p className="text-[11px] text-texto-3 mt-1">
                        {o.usuario_nombre} ({o.paso_nombre}) · {lugarObservacion(o)}
                      </p>
                    </div>
                    {o.puede_borrar && (
                      <button
                        aria-label="Quitar observación"
                        onClick={(e) => { e.stopPropagation(); mutBorrar.mutate(o.id) }}
                        className="text-texto-3 hover:text-negativo"
                      >
                        <IconoPapelera tam={14} />
                      </button>
                    )}
                  </div>
                  {o.puede_atender && (
                    <label className="flex items-center gap-2 mt-2 text-xs text-texto-2" onClick={(e) => e.stopPropagation()}>
                      <input
                        type="checkbox" checked={o.atendida}
                        onChange={(e) => mutAtender.mutate({ id: o.id, atendida: e.target.checked })}
                      />
                      Ya lo corregí
                    </label>
                  )}
                </li>
              ))}
            </ol>
          </section>

          {version.puede_responder && (
            <section className="bg-white rounded-xl shadow-md border border-acento/30 p-4 space-y-3">
              <h2 className="text-sm font-bold text-acento-fuerte">Tu firma como {version.turno_de.nombre}</h2>
              <textarea
                value={comentario} onChange={(e) => setComentario(e.target.value)}
                maxLength={MAX_OBSERVACION} rows={3}
                placeholder="Comentario (obligatorio para devolver si no marcaste observaciones)"
                className="w-full rounded-lg border border-borde px-3 py-2 text-sm resize-y"
              />
              <div className="grid grid-cols-2 gap-2">
                <Boton cargando={mutResponder.isPending && mutResponder.variables === "devolver"}
                  disabled={mutResponder.isPending} onClick={() => mutResponder.mutate("devolver")}>
                  Devolver
                </Boton>
                <Boton tono="primario" cargando={mutResponder.isPending && mutResponder.variables === "aprobar"}
                  disabled={mutResponder.isPending} onClick={aprobar}>
                  Aprobar
                </Boton>
              </div>
              <p className="text-xs text-texto-3">
                Devolver lo regresa a {tarea.asignado_nombre || "quien lo preparó"}, y la versión corregida empieza otra vez por {revision.pasos[0]?.nombre}.
              </p>
            </section>
          )}

          {errorAccion && <p className="text-sm text-negativo">{errorAccion}</p>}
        </aside>
      </div>
    </div>
  )
}

/** La `key` reinicia el visor al pasar de una versión a otra: nada del PDF anterior sobrevive. */
export default function VisorDocumento() {
  const { versionId } = useParams()
  return <Visor key={versionId} versionId={Number(versionId)} />
}
