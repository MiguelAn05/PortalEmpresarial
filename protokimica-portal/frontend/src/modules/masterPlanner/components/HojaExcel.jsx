import { useMemo } from "react"
import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { obtenerHojaDocumento } from "../api"
import { claveCelda, textoCelda } from "../revision.js"
import { Atenuado, Esqueleto } from "../../../core/components/Cargando.jsx"

/**
 * Una hoja del Excel como cuadrícula, para revisarla sin descargarla.
 *
 * Los valores los lee el servidor (`core/hoja_calculo.py`): sin formato, sin
 * colores, sin celdas combinadas; las fórmulas con el último resultado que
 * guardó Excel. Es para SEÑALAR dónde está el problema —«Balance · C14»—, no
 * para reemplazar a Excel: quien corrige lo busca en su archivo por esa
 * dirección.
 *
 * Es una caja con su propio scroll a propósito, como la matriz del año: una
 * hoja de sesenta columnas no cabe en la página y las letras y los números
 * tienen que quedarse a la vista.
 */
export default function HojaExcel({
  versionId, hojas, indice, onCambiarHoja, observaciones, puedeMarcar, pendiente, activa, onMarcar, onElegir,
}) {
  // gcTime 0, como el archivo: los números de un estado financiero no se
  // quedan en la memoria de la pestaña al cerrar el visor.
  const { data: hoja, isFetching, error } = useQuery({
    queryKey: ["mp-documento-hoja", versionId, indice],
    queryFn: () => obtenerHojaDocumento(versionId, indice),
    staleTime: Infinity,
    gcTime: 0,
    placeholderData: keepPreviousData,
  })

  const marcadas = useMemo(() => {
    const mapa = {}
    for (const o of observaciones) if (o.celda) (mapa[claveCelda(o.hoja, o.celda)] ||= []).push(o)
    return mapa
  }, [observaciones])

  return (
    <div className="bg-white rounded-xl shadow-sm border border-borde overflow-hidden">
      {hojas.length > 1 && (
        <div className="flex gap-1 overflow-x-auto border-b border-borde bg-superficie-2 px-2 pt-2">
          {hojas.map((nombre, i) => {
            const cuantas = observaciones.filter(o => o.hoja === nombre).length
            return (
              <button
                key={nombre}
                onClick={() => onCambiarHoja(i)}
                className={`px-3 py-1.5 text-xs font-semibold rounded-t-lg border border-b-0 whitespace-nowrap transition ${
                  i === indice ? "bg-white border-borde text-acento-fuerte" : "border-transparent text-texto-2 hover:text-acento-fuerte"
                }`}
              >
                {nombre}
                {cuantas > 0 && <span className="ml-1.5 cifra text-negativo">({cuantas})</span>}
              </button>
            )
          })}
        </div>
      )}

      {error ? (
        <p className="p-6 text-sm text-negativo">No se pudo leer esta hoja. Descarga el archivo para revisarla en tu computador.</p>
      ) : !hoja ? (
        <div className="p-4"><Esqueleto alto="h-[60vh]" /></div>
      ) : hoja.filas.length === 0 ? (
        <p className="p-6 text-sm text-texto-2">La hoja «{hoja.nombre}» está vacía.</p>
      ) : (
        <Atenuado cargando={isFetching}>
          <div className="max-h-[75vh] overflow-auto">
            <table className="border-collapse text-xs">
              <thead>
                <tr>
                  <th className="sticky top-0 left-0 z-20 bg-superficie-2 border border-borde w-10" />
                  {hoja.columnas.map(c => (
                    <th key={c} className="sticky top-0 z-10 bg-superficie-2 border border-borde px-2 py-1 font-semibold text-texto-2 min-w-[90px]">
                      {c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {hoja.filas.map((fila, f) => (
                  <tr key={f}>
                    <th className="sticky left-0 z-10 bg-superficie-2 border border-borde px-2 py-1 font-semibold text-texto-2 cifra text-right">
                      {f + 1}
                    </th>
                    {fila.map((valor, c) => {
                      const celda = `${hoja.columnas[c]}${f + 1}`
                      const obs = marcadas[claveCelda(hoja.nombre, celda)]
                      const esPendiente = pendiente?.hoja === hoja.nombre && pendiente?.celda === celda
                      const esActiva = obs?.some(o => o.id === activa)
                      const esNumero = typeof valor === "number"
                      return (
                        <td
                          key={c}
                          id={`celda-${claveCelda(hoja.nombre, celda)}`}
                          title={obs ? obs.map(o => `${o.numero}. ${o.texto}`).join("\n") : celda}
                          onClick={() => puedeMarcar ? onMarcar({ hoja: hoja.nombre, celda }) : obs && onElegir(obs[0].id)}
                          className={`relative border border-borde px-2 py-1 whitespace-nowrap max-w-[280px] truncate
                            ${esNumero ? "text-right cifra" : ""}
                            ${puedeMarcar ? "cursor-cell hover:bg-info-bg" : obs ? "cursor-pointer" : ""}
                            ${obs ? (obs.every(o => o.atendida) ? "bg-positivo-bg" : "bg-negativo-bg") : ""}
                            ${esActiva ? "ring-2 ring-inset ring-acento" : ""}
                            ${esPendiente ? "ring-2 ring-inset ring-acento bg-info-bg" : ""}`}
                        >
                          {obs && (
                            <button
                              onClick={(e) => { e.stopPropagation(); onElegir(obs[0].id) }}
                              className={`absolute top-0 left-0 min-w-4 h-4 px-0.5 rounded-br text-[9px] font-bold cifra text-white leading-4 ${
                                obs.every(o => o.atendida) ? "bg-positivo-vivo" : "bg-negativo-vivo"
                              }`}
                            >
                              {obs.map(o => o.numero).join(",")}
                            </button>
                          )}
                          {textoCelda(valor)}
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {hoja.truncada && (
            <p className="px-4 py-2 text-xs text-alerta bg-alerta-bg border-t border-borde">
              Esta hoja es más grande de lo que se muestra aquí (hasta la fila {hoja.max_filas} y la columna {hoja.columnas.at(-1)}).
              Lo que esté más allá, revísalo en el archivo descargado y déjalo como observación general.
            </p>
          )}
        </Atenuado>
      )}
    </div>
  )
}
