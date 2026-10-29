import { useRef, useState } from "react"
import { useNavigate } from "react-router-dom"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  configurarRevision, enviarDocumento, obtenerRevision, quitarRevision, subirDocumento,
} from "../api"
import {
  ACEPTA_DOCUMENTO, ESTADOS_DOCUMENTO, MAX_OBSERVACION, documentoDemasiadoGrande,
  formatFechaHora, rutaDocumento, textoEventoRevision, textoTamano,
} from "../constants"
import { REVISION_VACIA } from "../revision.js"
import { mensajeDeError } from "../../../core/errores.js"
import Boton from "../../../core/components/Boton.jsx"
import { IconoCheck, IconoClip, IconoFicha, IconoFlecha } from "../../../core/components/Iconos.jsx"
import SelectorRevisores from "./SelectorRevisores"

/** El estado del documento con punto y palabra: el color solo no se lee. */
/** `compacto` es el de las tarjetas: más chico y diciendo de qué es el estado. */
export function ChipDocumento({ estado, compacto = false }) {
  const cfg = ESTADOS_DOCUMENTO[estado]
  if (!cfg) return null
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-md font-semibold ${cfg.chip} ${compacto ? 'px-2 py-0.5 text-[10px]' : 'px-2.5 py-0.5 text-xs'}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} aria-hidden="true" />
      {compacto ? `Documento: ${cfg.label.toLowerCase()}` : cfg.label}
    </span>
  )
}

/**
 * La cadena, de izquierda a derecha: quien hace el documento y cada firma.
 * El paso que tiene el turno se marca; los anteriores, si ya firmaron esta
 * versión, llevan su visto.
 */
function Cadena({ revision, asignadoNombre }) {
  const actual = revision.versiones[0]
  const firmaron = new Set(
    (actual?.eventos || []).filter(e => e.accion === 'aprobado').map(e => e.paso_nombre),
  )
  const eslabones = [
    { clave: 'autor', nombre: 'Lo prepara', persona: asignadoNombre || 'Sin asignar', enTurno: ['borrador', 'devuelta', 'sin_documento'].includes(revision.estado), listo: false },
    ...revision.pasos.map(p => ({
      clave: p.orden, nombre: p.nombre, persona: p.revisor_nombre,
      enTurno: p.en_turno, listo: revision.estado === 'aprobada' || firmaron.has(p.nombre),
    })),
  ]
  return (
    <ol className="flex flex-wrap items-center gap-2">
      {eslabones.map((e, i) => (
        <li key={e.clave} className="flex items-center gap-2">
          {i > 0 && <IconoFlecha tam={14} className="text-texto-3" />}
          <span className={`rounded-lg border px-3 py-1.5 ${e.enTurno ? 'border-acento bg-info-bg' : 'border-borde bg-white'}`}>
            <span className="block text-[11px] font-semibold uppercase tracking-wide text-texto-3">{e.nombre}</span>
            <span className="flex items-center gap-1 text-sm font-semibold text-texto">
              {e.listo && <IconoCheck tam={14} className="text-positivo" />}
              {e.persona}
            </span>
            {e.enTurno && <span className="block text-[11px] font-semibold text-info">Tiene el turno</span>}
          </span>
        </li>
      ))}
    </ol>
  )
}

/**
 * El documento de una tarea que lo pide aprobado: quién firma, la versión
 * vigente y lo que cada quien puede hacer ahora. Qué puede hacer cada uno lo
 * dice el servidor (`puede_subir`, `puede_enviar`, `puede_responder`…).
 *
 * Aprobar y devolver no viven aquí sino en el visor: se firma lo que se leyó.
 */
export default function DocumentoPanel({ tarea, usuarios = [], editable }) {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const inputArchivo = useRef(null)
  const [configurando, setConfigurando] = useState(false)
  const [eleccion, setEleccion] = useState(REVISION_VACIA)
  const [comentario, setComentario] = useState("")
  const [error, setError] = useState(null)

  const clave = ["mp-revision", tarea.id]
  const { data: revision } = useQuery({ queryKey: clave, queryFn: () => obtenerRevision(tarea.id) })

  const alTerminar = (datos) => {
    queryClient.setQueryData(clave, datos)
    queryClient.invalidateQueries({ queryKey: ["mp-tarea", tarea.id] })
    queryClient.invalidateQueries({ queryKey: ["mp-tareas"] })
    queryClient.invalidateQueries({ queryKey: ["mp-historial-tarea", tarea.id] })
    queryClient.invalidateQueries({ queryKey: ["mp-documentos-pendientes"] })
    setError(null)
  }
  const conError = (porDefecto) => (err) => setError(mensajeDeError(err, porDefecto))

  const mutConfigurar = useMutation({
    mutationFn: () => configurarRevision(tarea.id, eleccion),
    onSuccess: (d) => { alTerminar(d); setConfigurando(false) },
    onError: conError('No se pudo guardar quién firma.'),
  })
  const mutQuitar = useMutation({
    mutationFn: () => quitarRevision(tarea.id),
    onSuccess: alTerminar,
    onError: conError('No se pudo quitar la aprobación.'),
  })
  const mutSubir = useMutation({
    mutationFn: (archivo) => subirDocumento(tarea.id, archivo),
    onSuccess: alTerminar,
    onError: conError('No se pudo subir el documento.'),
  })
  const mutEnviar = useMutation({
    mutationFn: () => enviarDocumento(tarea.id, comentario),
    onSuccess: (d) => { alTerminar(d); setComentario("") },
    onError: conError('No se pudo enviar el documento.'),
  })

  if (!revision) return null

  const elegirArchivo = (e) => {
    const archivo = e.target.files?.[0]
    // Se limpia siempre: si no, volver a elegir el mismo archivo no avisa.
    e.target.value = ""
    if (!archivo) return
    const grande = documentoDemasiadoGrande(archivo)
    if (grande) { setError(grande); return }
    mutSubir.mutate(archivo)
  }

  const empezarConfiguracion = () => {
    setEleccion(REVISION_VACIA)
    setConfigurando(true)
  }

  const selector = configurando && (
    <div className="bg-superficie-2 rounded-xl p-4 space-y-3">
      <SelectorRevisores valor={eleccion} onChange={setEleccion} usuarios={usuarios} asignadoId={tarea.asignado_a} />
      <div className="flex gap-2 justify-end">
        <Boton tam="sm" tono="fantasma" onClick={() => setConfigurando(false)}>Cancelar</Boton>
        <Boton
          tam="sm" tono="primario" cargando={mutConfigurar.isPending}
          disabled={!eleccion.plantilla_id || eleccion.revisores.some(r => !r)}
          onClick={() => mutConfigurar.mutate()}
        >
          Guardar quién firma
        </Boton>
      </div>
    </div>
  )

  // Sin flujo: solo la puerta para activarlo.
  if (!revision.activo) {
    if (!editable || !revision.puede_configurar) return null
    return (
      <div className="border-t border-borde pt-5 space-y-3">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-bold text-acento-fuerte">Aprobación de documento</h3>
            <p className="text-xs text-texto-3">Para lo que otra persona tiene que firmar antes de darlo por cumplido.</p>
          </div>
          {!configurando && <Boton tam="sm" onClick={empezarConfiguracion}>Pedir aprobación</Boton>}
        </div>
        {selector}
        {error && <p className="text-sm text-negativo">{error}</p>}
      </div>
    )
  }

  const vigente = revision.versiones[0] || null
  const anteriores = revision.versiones.slice(1)
  const nadaEnviado = revision.versiones.every(v => !v.enviado_en)

  return (
    <div className="border-t border-borde pt-5 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-bold text-acento-fuerte">Aprobación de documento</h3>
          <ChipDocumento estado={revision.estado} />
          {revision.veces_devuelto > 0 && (
            <span className="text-xs font-semibold text-alerta cifra">
              Devuelto {revision.veces_devuelto} {revision.veces_devuelto === 1 ? 'vez' : 'veces'}
            </span>
          )}
        </div>
        {editable && revision.puede_configurar && !configurando && (
          <div className="flex gap-1">
            <Boton tam="sm" tono="fantasma" onClick={empezarConfiguracion}>Cambiar quién firma</Boton>
            {nadaEnviado && (
              <Boton tam="sm" tono="fantasma" cargando={mutQuitar.isPending} onClick={() => {
                if (confirm('¿Quitar la aprobación de documento? La tarea se podrá completar a mano.')) mutQuitar.mutate()
              }}>
                Quitar
              </Boton>
            )}
          </div>
        )}
      </div>

      {selector}
      <Cadena revision={revision} asignadoNombre={tarea.asignado_nombre} />

      {/* La versión vigente: lo que hay que mirar ahora. */}
      {vigente ? (
        <div className="bg-superficie-2 rounded-xl p-4 space-y-3">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-sm font-semibold text-texto flex items-center gap-1.5 truncate">
                <IconoFicha tam={16} className="text-texto-3" />
                <span className="truncate">{vigente.nombre_original}</span>
              </p>
              <p className="text-xs text-texto-3 cifra">
                Versión {vigente.numero} · {vigente.tipo === 'pdf' ? 'PDF' : 'Excel'} · {textoTamano(vigente.tamano)}
                {' · '}subida por {vigente.subido_por_nombre} el {formatFechaHora(vigente.subido_en)}
              </p>
              {vigente.turno_de && (
                <p className="text-xs font-semibold text-info mt-1">
                  La está revisando {vigente.turno_de.revisor_nombre} ({vigente.turno_de.nombre})
                </p>
              )}
            </div>
            <Boton
              tam="sm" tono={vigente.puede_responder ? 'primario' : 'secundario'}
              onClick={() => navigate(rutaDocumento(vigente.id))}
            >
              {vigente.puede_responder ? 'Abrir para revisar' : 'Abrir documento'}
            </Boton>
          </div>

          {vigente.puede_responder && (
            <p className="text-sm text-texto bg-info-bg border border-acento/20 rounded-lg px-3 py-2">
              Te toca revisarlo. Ábrelo, marca lo que haya que corregir y apruébalo o devuélvelo desde ahí.
            </p>
          )}

          {vigente.estado === 'devuelta' && (
            <p className="text-sm text-alerta bg-alerta-bg border border-ambar/30 rounded-lg px-3 py-2">
              Lo devolvieron con {vigente.observaciones_pendientes} {vigente.observaciones_pendientes === 1 ? 'observación' : 'observaciones'} por atender.
              Ábrelo para verlas y sube la versión corregida.
            </p>
          )}

          {revision.puede_enviar && (
            <div className="space-y-2">
              <textarea
                value={comentario} onChange={(e) => setComentario(e.target.value)}
                maxLength={MAX_OBSERVACION} rows={2}
                placeholder={vigente.numero > 1 ? 'Qué corregiste (opcional)' : 'Algo que deba saber quien lo revisa (opcional)'}
                className="w-full rounded-lg border border-borde px-3 py-2 text-sm resize-none bg-white"
              />
              <div className="flex justify-end">
                <Boton tono="primario" tam="sm" cargando={mutEnviar.isPending} onClick={() => mutEnviar.mutate()}>
                  Enviar a {revision.pasos[0]?.revisor_nombre}
                </Boton>
              </div>
            </div>
          )}

          {vigente.eventos.length > 0 && (
            <ul className="space-y-1.5 border-t border-borde pt-3">
              {vigente.eventos.map((e, i) => (
                <li key={i} className="text-xs text-texto-2">
                  <span className="font-semibold text-texto">{textoEventoRevision(e)}</span>
                  {' · '}{formatFechaHora(e.fecha)}
                  {e.comentario && <span className="block text-texto mt-0.5">«{e.comentario}»</span>}
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : (
        <p className="text-sm text-texto-3">
          Todavía no hay documento. {revision.puede_subir ? 'Súbelo cuando esté listo y envíalo a revisión.' : `Lo sube ${tarea.asignado_nombre || 'quien tenga la tarea'}.`}
        </p>
      )}

      {revision.puede_subir && (
        <div>
          <input ref={inputArchivo} type="file" accept={ACEPTA_DOCUMENTO} onChange={elegirArchivo} className="hidden" />
          <Boton tam="sm" icono={IconoClip} cargando={mutSubir.isPending} textoCargando="Subiendo…"
            onClick={() => inputArchivo.current?.click()}>
            {!vigente ? 'Subir documento'
              : vigente.estado === 'borrador' ? 'Cambiar el archivo'
              : 'Subir versión corregida'}
          </Boton>
          <span className="text-xs text-texto-3 ml-2">PDF o Excel, hasta 20 MB.</span>
        </div>
      )}

      {error && <p className="text-sm text-negativo">{error}</p>}

      {anteriores.length > 0 && (
        <details className="text-sm">
          <summary className="cursor-pointer text-xs font-semibold text-texto-2">
            Versiones anteriores ({anteriores.length})
          </summary>
          <ul className="mt-2 space-y-1.5">
            {anteriores.map(v => (
              <li key={v.id} className="flex items-center justify-between gap-2 text-xs">
                <span className="text-texto-2 truncate">
                  <span className="cifra">v{v.numero}</span> · {v.nombre_original} · <ChipDocumento estado={v.estado} />
                  {v.total_observaciones > 0 && <span className="cifra"> · {v.total_observaciones} observaciones</span>}
                </span>
                <button onClick={() => navigate(rutaDocumento(v.id))} className="text-acento font-semibold hover:underline">
                  Ver
                </button>
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  )
}
