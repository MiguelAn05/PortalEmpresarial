import { useMemo, useState } from "react"
import Avatar from "./Avatar"
import {
  CAMPOS_HISTORIAL, etiquetaCampo, valorHistorial, diasDesplazados, formatFecha,
} from "../constants"

/**
 * Historial de cambios. Agrupa por momento y autor: cuando alguien guarda
 * tres campos de un solo golpe, gerencia lo tiene que leer como un cambio,
 * no como tres líneas sueltas.
 */
export default function HistorialPanel({ entradas = [], mostrarEntidad = false, vacio }) {
  const [soloFechas, setSoloFechas] = useState(false)

  const cambiosDeFecha = entradas.filter(e => CAMPOS_HISTORIAL[e.campo]?.tipo === 'fecha').length

  const grupos = useMemo(() => {
    const visibles = soloFechas
      ? entradas.filter(e => CAMPOS_HISTORIAL[e.campo]?.tipo === 'fecha')
      : entradas

    const mapa = new Map()
    for (const e of visibles) {
      // Al minuto: un mismo guardado escribe todas sus filas en el mismo
      // instante, pero no queremos partir el grupo por milisegundos.
      const clave = `${e.fecha?.slice(0, 16)}|${e.usuario_id}|${e.entidad}|${e.entidad_id}`
      if (!mapa.has(clave)) mapa.set(clave, { clave, entrada: e, cambios: [] })
      mapa.get(clave).cambios.push(e)
    }
    return [...mapa.values()]
  }, [entradas, soloFechas])

  if (entradas.length === 0) {
    return (
      <p className="text-xs text-texto-3 py-4">
        {vacio || 'Todavía no hay cambios registrados. Aquí aparecerá quién movió una fecha, cambió un estado o reasignó una tarea.'}
      </p>
    )
  }

  return (
    <div>
      {cambiosDeFecha > 0 && (
        <div className="flex items-center justify-between mb-3">
          <label className="flex items-center gap-2 text-xs text-texto-2 cursor-pointer select-none">
            <input
              type="checkbox" checked={soloFechas}
              onChange={(e) => setSoloFechas(e.target.checked)}
              className="rounded border-borde accent-acento"
            />
            Ver solo cambios de fecha ({cambiosDeFecha})
          </label>
        </div>
      )}

      <div className="space-y-3">
        {grupos.map(({ clave, entrada, cambios }) => (
          <div key={clave} className="border-l-2 border-borde pl-4 py-1">
            <div className="flex items-center justify-between gap-3 mb-1.5">
              <Avatar name={entrada.usuario_nombre} compact />
              <span className="text-[11px] text-texto-3 shrink-0">
                {formatFecha(entrada.fecha, { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })}
              </span>
            </div>

            {mostrarEntidad && entrada.entidad === 'tarea' && (
              <p className="text-[11px] font-semibold text-texto-2 uppercase tracking-wide mb-1">
                Tarea · {entrada.entidad_nombre || `#${entrada.entidad_id}`}
              </p>
            )}

            <div className="space-y-1">
              {cambios.map(c => <LineaCambio key={c.id} cambio={c} />)}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function LineaCambio({ cambio }) {
  const tipo = CAMPOS_HISTORIAL[cambio.campo]?.tipo
  const etiqueta = etiquetaCampo(cambio.campo)

  if (tipo === 'texto_largo') {
    return <p className="text-sm text-texto-2 italic">Se modificó {etiqueta.toLowerCase()}</p>
  }

  if (tipo === 'evento') {
    return (
      <p className="text-sm text-texto">
        <span className="text-texto-2">{etiqueta}: </span>
        {cambio.valor_nuevo || cambio.valor_anterior}
      </p>
    )
  }

  const dias = diasDesplazados(cambio)

  return (
    <p className="text-sm text-texto flex flex-wrap items-baseline gap-x-1.5">
      <span className="text-texto-2">{etiqueta}:</span>
      <span className="line-through text-texto-3">{valorHistorial(cambio.campo, cambio.valor_anterior)}</span>
      <span className="text-texto-3">→</span>
      <span className="font-semibold">{valorHistorial(cambio.campo, cambio.valor_nuevo)}</span>
      {dias !== null && dias !== 0 && (
        <span className={`text-[11px] font-semibold rounded-full px-2 py-0.5 ${
          dias > 0 ? 'bg-negativo-bg text-negativo' : 'bg-positivo-bg text-positivo'
        }`}>
          {dias > 0 ? `aplazada ${dias} día${dias === 1 ? '' : 's'}` : `adelantada ${Math.abs(dias)} día${Math.abs(dias) === 1 ? '' : 's'}`}
        </span>
      )}
    </p>
  )
}
