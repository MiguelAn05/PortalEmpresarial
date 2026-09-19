/**
 * El año completo: indicadores en filas, meses en columnas.
 *
 * Vivía dentro de «Cómo vamos» y ahí no cabía. Son 73 filas por 12 meses:
 * casi novecientas celdas que empujan fuera de pantalla todo lo demás, así
 * que quien entraba a ver cómo va el mes tenía que pasar por encima. Aquí es
 * lo único que hay, que es cuando esta vista sirve: muestra lo que ninguna
 * gráfica de líneas deja ver de un vistazo —qué indicador lleva cuatro meses
 * en rojo, o qué mes fue malo para todas las áreas a la vez—.
 *
 * Tres decisiones que la hacen legible:
 *
 * - **La columna del nombre queda fija** al desplazar en horizontal. Sin eso
 *   se llega a octubre sin saber de qué fila se está leyendo.
 * - **Se agrupa lo que nadie lee de a uno.** Los «Gestión de OMP» son uno
 *   por área —veinte renglones idénticos— y las filas sin un solo registro
 *   del año son otra cosa distinta: no son ruido, son la pregunta de si ese
 *   indicador sigue vivo. Los dos bloques se pliegan.
 * - **Un mes que aún no llega no es un hueco.** Va rayado, no vacío: nadie
 *   incumplió por no haber reportado noviembre en agosto.
 */
import { useState } from 'react'
import { IconoChevron } from '../../../core/components/Iconos.jsx'
import {
  GRUPO_GESTION_OMP, GRUPO_SIN_REGISTROS, GRUPO_SUELTAS,
  SEMAFOROS, agruparMatriz, coincideBusqueda, formatValor,
} from '../constants'

// El color de la celda sale de los tokens, como todo lo demás. El semáforo
// no se comunica solo con color: la celda lleva el VALOR, que es lo que se
// lee en una fotocopia en gris o con daltonismo.
const CELDA = {
  verde: 'bg-positivo-bg text-positivo',
  amarillo: 'bg-alerta-bg text-alerta',
  rojo: 'bg-negativo-bg text-negativo',
  sin_datos: 'bg-superficie-2 text-texto-3 font-normal',
  futuro: 'celda-futura',
}

export default function ElAno({ matriz = [], anio, busqueda, onVerIndicador }) {
  const [soloConDatos, setSoloConDatos] = useState(false)
  const [abiertos, setAbiertos] = useState({})

  const filtrada = matriz.filter(f => coincideBusqueda(f, busqueda))
  const grupos = agruparMatriz(filtrada)
  const meses = matriz[0]?.meses ?? []

  const alternar = (clave) => setAbiertos(a => ({ ...a, [clave]: !a[clave] }))

  if (matriz.length === 0) {
    return <Vacio texto="No hay indicadores en este alcance." />
  }
  if (filtrada.length === 0) {
    return <Vacio texto={`Ningún indicador coincide con «${busqueda}».`} />
  }

  return (
    <section className="bg-superficie rounded-xl border border-borde shadow-sm overflow-hidden">
      <header className="flex flex-wrap items-center justify-between gap-3 px-5 py-3.5 border-b border-borde">
        <div>
          <h2 className="text-sm font-semibold text-texto">El año completo · {anio}</h2>
          <p className="text-xs text-texto-3 mt-0.5">
            Una celda por mes. El color dice cómo quedó frente a la meta; el número, cuánto dio.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setSoloConDatos(v => !v)}
          aria-pressed={soloConDatos}
          className={`h-8 px-3 rounded-lg border text-xs font-semibold transition ${
            soloConDatos
              ? 'border-acento text-acento bg-acento-suave'
              : 'border-borde-fuerte text-texto-2 hover:bg-superficie-2'
          }`}
        >
          Solo con datos
        </button>
      </header>

      <div className="overflow-x-auto">
        <table className="w-full border-separate border-spacing-0 text-xs">
          <thead>
            <tr>
              <th scope="col"
                  className="sticky left-0 z-20 bg-superficie-2 etiqueta text-left
                             px-5 py-2 border-b border-borde w-[17rem] min-w-[17rem]">
                Indicador
              </th>
              {meses.map(m => (
                <th key={m.mes} scope="col"
                    className="bg-superficie-2 etiqueta text-center px-1.5 py-2 border-b border-borde">
                  {m.etiqueta}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {grupos[GRUPO_SUELTAS].map(fila => (
              <Fila key={fila.id} fila={fila} onVer={onVerIndicador} />
            ))}

            {/* Uno por área y todos con la misma pinta: de a uno no dicen
                nada, y en medio de la matriz separan los que sí se comparan
                entre sí. Se reconocen por la FUENTE, no por el nombre —
                renombrar uno desde Administración no puede romper esto. */}
            <Grupo
              columnas={meses.length + 1}
              titulo="Gestión de OMP · uno por área"
              detalle={`${grupos[GRUPO_GESTION_OMP].length} indicadores automáticos`}
              abierto={abiertos[GRUPO_GESTION_OMP]}
              onAlternar={() => alternar(GRUPO_GESTION_OMP)}
              filas={grupos[GRUPO_GESTION_OMP]}
              onVer={onVerIndicador}
            />

            {!soloConDatos && (
              <Grupo
                columnas={meses.length + 1}
                titulo={`Sin ningún registro en ${anio}`}
                detalle={`${grupos[GRUPO_SIN_REGISTROS].length} indicadores · revisar si siguen vigentes`}
                abierto={abiertos[GRUPO_SIN_REGISTROS]}
                onAlternar={() => alternar(GRUPO_SIN_REGISTROS)}
                filas={grupos[GRUPO_SIN_REGISTROS]}
                onVer={onVerIndicador}
              />
            )}
          </tbody>
        </table>
      </div>

      <Leyenda />
    </section>
  )
}

function Fila({ fila, onVer }) {
  return (
    <tr className="group">
      <th scope="row"
          className="sticky left-0 z-10 bg-superficie group-hover:bg-superficie-2
                     text-left font-normal px-5 py-0 border-b border-r border-borde transition">
        <button
          type="button"
          onClick={() => onVer?.(fila.id)}
          className="block w-full text-left py-2"
        >
          <span className="block text-[12.5px] font-medium text-texto truncate max-w-[14rem]
                           group-hover:text-acento transition">
            {fila.nombre}
          </span>
          <span className="block text-[10.5px] text-texto-3 truncate max-w-[14rem]">
            {fila.area || 'Sin área'}
            {fila.responsable_nombre && ` · ${fila.responsable_nombre}`}
          </span>
        </button>
      </th>

      {fila.meses.map(m => (
        <td key={m.mes} className="border-b border-borde p-0 text-center align-middle">
          <span
            title={tituloCelda(m, fila)}
            className={`block mx-[3px] my-[3px] h-[26px] leading-[26px] rounded-md
                        text-[11px] font-semibold cifra ${CELDA[m.semaforo]}`}
          >
            {m.semaforo === 'futuro' ? '' : m.valor === null ? '—' : formatValor(m.valor, '')}
          </span>
        </td>
      ))}
    </tr>
  )
}

function tituloCelda(mes, fila) {
  if (mes.semaforo === 'futuro') return `${mes.etiqueta}: aún no llega`
  if (mes.valor === null) return `${mes.etiqueta}: sin reportar`
  return `${mes.etiqueta}: ${formatValor(mes.valor, fila.unidad)} · ${SEMAFOROS[mes.semaforo].label}`
}

/** Un bloque plegable dentro de la tabla. Si está vacío no se pinta. */
function Grupo({ columnas, titulo, detalle, abierto, onAlternar, filas, onVer }) {
  if (filas.length === 0) return null

  return (
    <>
      <tr>
        <td colSpan={columnas} className="bg-superficie-2 border-b border-borde p-0">
          <button
            type="button"
            onClick={onAlternar}
            aria-expanded={abierto}
            className="flex items-center gap-2.5 w-full px-5 py-2 text-left
                       text-xs font-semibold text-texto-2 hover:text-texto transition"
          >
            <IconoChevron
              tam={12}
              className={`transition-transform duration-150 ease-suave ${abierto ? 'rotate-90' : ''}`}
            />
            {titulo}
            <span className="ml-auto text-[11px] font-normal text-texto-3">{detalle}</span>
          </button>
        </td>
      </tr>
      {abierto && filas.map(fila => <Fila key={fila.id} fila={fila} onVer={onVer} />)}
    </>
  )
}

function Leyenda() {
  return (
    <div className="flex flex-wrap gap-x-5 gap-y-2 px-5 py-3 border-t border-borde text-[11px] text-texto-3">
      {['verde', 'amarillo', 'rojo', 'sin_datos'].map(estado => (
        <span key={estado} className="inline-flex items-center gap-1.5">
          <span className={`inline-block w-2.5 h-2.5 rounded-sm ${CELDA[estado].split(' ')[0]}`} aria-hidden="true" />
          {estado === 'sin_datos' ? 'Sin registro' : SEMAFOROS[estado].label}
        </span>
      ))}
      <span className="inline-flex items-center gap-1.5">
        <span className="inline-block w-2.5 h-2.5 rounded-sm celda-futura" aria-hidden="true" />
        Mes que aún no llega
      </span>
    </div>
  )
}

function Vacio({ texto }) {
  return (
    <section className="bg-superficie rounded-xl border border-dashed border-borde p-16 text-center">
      <p className="text-sm text-texto-2">{texto}</p>
    </section>
  )
}
