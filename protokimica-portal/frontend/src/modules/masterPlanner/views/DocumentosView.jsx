import { useNavigate } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { listarDocumentosPendientes } from "../api"
import { ALERTAS, alertaVencimiento, formatFechaHora, rutaDocumento } from "../constants"
import { ChipDocumento } from "../components/DocumentoPanel"
import Boton from "../../../core/components/Boton.jsx"
import { EsqueletoFilas } from "../../../core/components/Cargando.jsx"

/**
 * Las dos bandejas del flujo de aprobación: lo que espera MI firma y lo mío
 * que me devolvieron. Un flujo con dos manos se traba en cualquiera de las
 * dos, y cada quien tiene que ver de un vistazo qué le toca.
 *
 * Las arma el servidor (`revision.pendientes`): aquí solo se pintan.
 */
function Ficha({ ficha, accion, onSelectTarea }) {
  const navigate = useNavigate()
  const alerta = ficha.fecha_fin ? alertaVencimiento({ fecha_fin: ficha.fecha_fin, estado: "en_proceso" }) : null
  const mov = ficha.ultimo_movimiento
  return (
    <li className="bg-white rounded-xl shadow-sm border border-borde p-4 flex flex-wrap items-start justify-between gap-4">
      <div className="min-w-0 space-y-1">
        <p className="text-xs uppercase tracking-wide text-texto-3">{ficha.proyecto_nombre}</p>
        <button onClick={() => onSelectTarea({ id: ficha.tarea_id })} className="text-left font-semibold text-texto hover:text-acento">
          {ficha.titulo}
        </button>
        <p className="text-xs text-texto-2 flex flex-wrap items-center gap-x-2 gap-y-1">
          <ChipDocumento estado={ficha.version.estado} />
          <span className="cifra">Versión {ficha.version.numero}</span>
          {ficha.version.turno_de && <span>· como {ficha.version.turno_de.nombre}</span>}
          {ficha.version.observaciones_pendientes > 0 && (
            <span className="cifra">· {ficha.version.observaciones_pendientes} observaciones por atender</span>
          )}
        </p>
        {mov && (
          <p className="text-xs text-texto-3">
            {mov.usuario_nombre} · {formatFechaHora(mov.fecha)}
            {mov.comentario && <span className="block text-texto-2">«{mov.comentario}»</span>}
          </p>
        )}
      </div>
      <div className="flex flex-col items-end gap-2">
        {ficha.fecha_fin && (
          <span className={`text-xs font-semibold ${alerta ? ALERTAS[alerta].texto : "text-texto-2"}`}>
            {alerta === "vencida" ? "Venció" : "Vence"} {formatFechaHora(ficha.fecha_fin)}
          </span>
        )}
        <Boton tam="sm" tono="primario" onClick={() => navigate(rutaDocumento(ficha.version.id))}>{accion}</Boton>
      </div>
    </li>
  )
}

function Bandeja({ titulo, ayuda, fichas, vacio, accion, onSelectTarea }) {
  return (
    <section className="space-y-3">
      <div>
        <h2 className="text-lg font-bold text-acento-fuerte">
          {titulo} <span className="cifra text-texto-3 font-semibold">({fichas.length})</span>
        </h2>
        <p className="text-sm text-texto-2">{ayuda}</p>
      </div>
      {fichas.length === 0 ? (
        <p className="text-sm text-positivo bg-positivo-bg border border-positivo/20 rounded-xl px-4 py-3">{vacio}</p>
      ) : (
        <ul className="space-y-3">
          {fichas.map(f => <Ficha key={f.version.id} ficha={f} accion={accion} onSelectTarea={onSelectTarea} />)}
        </ul>
      )}
    </section>
  )
}

export default function DocumentosView({ onSelectTarea }) {
  const { data, isLoading } = useQuery({
    queryKey: ["mp-documentos-pendientes"],
    queryFn: listarDocumentosPendientes,
  })

  if (isLoading || !data) return <EsqueletoFilas filas={4} />

  return (
    <div className="space-y-8">
      <p className="text-sm text-texto-2">
        Los documentos de las tareas que piden aprobación. Una tarea así se cumple sola cuando firma el último paso.
      </p>
      <Bandeja
        titulo="Esperan tu firma"
        ayuda="Ábrelos, marca lo que haya que corregir y apruébalos o devuélvelos."
        fichas={data.por_revisar}
        vacio="Ningún documento espera tu firma."
        accion="Revisar"
        onSelectTarea={onSelectTarea}
      />
      <Bandeja
        titulo="Te los devolvieron"
        ayuda="Tienen observaciones: corrige el original y sube la versión nueva desde la tarea."
        fichas={data.por_corregir}
        vacio="No tienes documentos devueltos."
        accion="Ver observaciones"
        onSelectTarea={onSelectTarea}
      />
    </div>
  )
}
