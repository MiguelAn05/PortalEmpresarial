import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { obtenerComoVamos } from "../api"
import { SEMAFOROS, MESES, formatValor } from "../constants"
import { GraficaTendencia } from "./Graficas"

/**
 * La portada de "cómo vamos": el estado de la empresa en una pantalla.
 *
 * Todo llega calculado del servidor —conteos, movimientos, matriz— porque es
 * lo mismo que alimenta el tablero: si aquí se recalculara algo, tarde o
 * temprano las dos pantallas mostrarían números distintos del mismo mes.
 *
 * Es una vista de LECTURA. Registrar, editar y adjuntar evidencia siguen
 * viviendo en el tablero; aquí no se toca ningún dato.
 */

// El símbolo va además del color, nunca en su lugar: el ámbar de la marca no
// alcanza el contraste mínimo, y un semáforo que solo es color no se lee en
// un proyector malo, impreso en gris, ni por quien no distingue rojo y verde.
const GLIFO = { verde: '✓', amarillo: '!', rojo: '✕', sin_datos: '–' }

const ORDEN_TARJETAS = ['verde', 'amarillo', 'rojo', 'sin_datos']
const BORDE = {
  verde: 'border-t-[#2E9E6B]',
  amarillo: 'border-t-[#F5A800]',
  rojo: 'border-t-[#D93B3B]',
  sin_datos: 'border-t-[#C3CFE2]',
}
const ROTULO = {
  verde: 'Cumplen', amarillo: 'En alerta', rojo: 'No cumplen', sin_datos: 'Sin reportar',
}

export default function ComoVamos({ periodo, onVerIndicador }) {
  const [alcance, setAlcance] = useState('empresa')
  const [filtro, setFiltro] = useState(null)      // semáforo abierto bajo las tarjetas
  const [detalle, setDetalle] = useState(null)    // fila de la matriz en la gráfica

  const { data, isLoading, isError } = useQuery({
    queryKey: ["ind-como-vamos", periodo.anio, periodo.mes, alcance],
    queryFn: () => obtenerComoVamos({ anio: periodo.anio, mes: periodo.mes, alcance }),
  })

  if (isLoading) {
    return <div className="text-center py-16 text-[#9BACC8] text-sm">Cargando...</div>
  }
  if (isError || !data) {
    return <div className="text-center py-16 text-red-500 text-sm">No se pudo cargar el resumen.</div>
  }

  const { resumen, movimientos, por_area: porArea, matriz } = data
  const juzgados = resumen.verde + resumen.amarillo + resumen.rojo
  const elegido = detalle !== null ? matriz.find(m => m.id === detalle) : matriz[0]

  return (
    <div className="space-y-5">

      {/* El interruptor lo decide el backend, no el frontend: si esta persona
          no puede ver la empresa, no se le muestra un control que no va a poder usar. */}
      {data.alcance.puede_cambiar && (
        <div className="flex items-center gap-2">
          <div className="inline-flex bg-white border border-[#D6E0F0] rounded-full p-1">
            {[['empresa', 'Empresa'], ['area', data.alcance.area || 'Mi área']].map(([valor, label]) => (
              <button
                key={valor}
                onClick={() => setAlcance(valor)}
                aria-pressed={alcance === valor}
                className={`px-4 py-1.5 text-sm font-semibold rounded-full transition ${
                  alcance === valor ? 'bg-[#1A4FA0] text-white' : 'text-[#6B7EA8] hover:text-[#1A4FA0]'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Estado del mes */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <div className="bg-white rounded-xl border border-[#D6E0F0] border-t-4 border-t-[#1A4FA0] p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-[#6B7EA8]">Cumplimiento</p>
          <p className="text-3xl font-bold text-[#0D2B5E] mt-1 tabular-nums">
            {resumen.cumplimiento_pct !== null ? `${resumen.cumplimiento_pct}%` : '—'}
          </p>
          <p className="text-xs text-[#6B7EA8] mt-1">
            {juzgados > 0 ? `${resumen.verde} de ${juzgados} con meta` : 'sin datos del periodo'}
          </p>
        </div>

        {ORDEN_TARJETAS.map(estado => (
          <button
            key={estado}
            type="button"
            onClick={() => setFiltro(filtro === estado ? null : estado)}
            aria-pressed={filtro === estado}
            className={`bg-white rounded-xl border border-[#D6E0F0] border-t-4 ${BORDE[estado]} p-4 text-left
              transition hover:-translate-y-0.5 hover:shadow-md
              ${filtro === estado ? 'ring-2 ring-[#1A4FA0] ring-offset-1' : ''}`}
          >
            <p className="text-xs font-semibold uppercase tracking-wide text-[#6B7EA8]">{ROTULO[estado]}</p>
            <p className={`text-3xl font-bold mt-1 tabular-nums ${SEMAFOROS[estado].texto}`}>
              {resumen[estado]}
            </p>
            <p className="text-xs text-[#1A4FA0] font-semibold mt-1">
              {filtro === estado ? 'Ocultar' : 'Ver cuáles'}
            </p>
          </button>
        ))}
      </div>

      {/* De la cifra al detalle: "hay 3 en rojo" -> "estos son" */}
      {filtro && (
        <ListaFiltrada
          estado={filtro}
          indicadores={matriz.filter(m => estadoDelMes(m, periodo.mes) === filtro)}
          onCerrar={() => setFiltro(null)}
          onVer={onVerIndicador}
        />
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Movimientos movimientos={movimientos} mes={periodo.mes} onVer={onVerIndicador} />
        <PorArea areas={porArea} />
      </div>

      <Matriz
        matriz={matriz}
        seleccionado={elegido?.id}
        onSeleccionar={setDetalle}
      />

      {elegido && <Tendencia fila={elegido} mes={periodo.mes} onVer={onVerIndicador} />}
    </div>
  )
}

/** El semáforo del mes que se está viendo, leído de la matriz ya calculada. */
function estadoDelMes(fila, mes) {
  const punto = fila.meses.find(m => m.mes === mes)
  return punto ? punto.semaforo : 'sin_datos'
}

function Chip({ estado }) {
  const cfg = SEMAFOROS[estado]
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-[11px] font-semibold ${cfg.chip}`}>
      <span aria-hidden="true">{GLIFO[estado]}</span> {cfg.label}
    </span>
  )
}

function ListaFiltrada({ estado, indicadores, onCerrar, onVer }) {
  return (
    <section className="bg-white rounded-xl border border-[#D6E0F0] p-5">
      <div className="flex items-baseline justify-between gap-3 mb-3">
        <h3 className="font-bold text-[#0D2B5E]">{ROTULO[estado]} este mes</h3>
        <button onClick={onCerrar} className="text-sm text-[#6B7EA8] hover:text-[#1A4FA0]">Cerrar</button>
      </div>
      {indicadores.length === 0 ? (
        <p className="text-sm text-[#6B7EA8]">Ninguno en este estado.</p>
      ) : (
        <ul className="divide-y divide-[#D6E0F0]">
          {indicadores.map(ind => (
            <li key={ind.id}>
              <button
                onClick={() => onVer?.(ind.id)}
                className="w-full flex items-center justify-between gap-3 py-2.5 text-left hover:bg-[#F7F9FC] rounded px-2 -mx-2"
              >
                <span>
                  <span className="block text-sm font-semibold text-[#1A2B47]">{ind.nombre}</span>
                  <span className="block text-xs text-[#6B7EA8]">{ind.area || 'Sin área'}</span>
                </span>
                <Chip estado={estado} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

/**
 * Lo que cambió de semáforo contra el mes pasado.
 *
 * Es la sección que hace corto el tablero: nadie necesita revisar cuarenta
 * indicadores, necesita ver los tres que se movieron.
 */
function Movimientos({ movimientos, mes, onVer }) {
  const anterior = MESES[(mes + 10) % 12]

  return (
    <section className="bg-white rounded-xl border border-[#D6E0F0] p-5">
      <h3 className="font-bold text-[#0D2B5E]">Qué se movió</h3>
      <p className="text-xs text-[#6B7EA8] mb-3">
        Cambios de semáforo contra {anterior.toLowerCase()}. Lo demás sigue igual.
      </p>

      {movimientos.length === 0 ? (
        <p className="text-sm text-[#6B7EA8] py-2">Ningún indicador cambió de estado este mes.</p>
      ) : (
        <ul className="divide-y divide-[#D6E0F0]">
          {movimientos.map(m => (
            <li key={m.id}>
              <button
                onClick={() => onVer?.(m.id)}
                className="w-full flex items-center justify-between gap-3 py-2.5 text-left hover:bg-[#F7F9FC] rounded px-2 -mx-2"
              >
                <span className="min-w-0">
                  <span className="block text-sm font-semibold text-[#1A2B47] truncate">{m.nombre}</span>
                  <span className="block text-xs text-[#6B7EA8]">{m.area || 'Sin área'}</span>
                </span>
                <span className="flex items-center gap-2 shrink-0">
                  <span className="text-xs text-[#6B7EA8] tabular-nums">
                    {formatValor(m.valor_anterior, m.unidad)} → {formatValor(m.valor, m.unidad)}
                  </span>
                  <span
                    className={`text-sm ${m.empeoro ? 'text-[#D93B3B]' : 'text-[#2E9E6B]'}`}
                    aria-hidden="true"
                  >
                    {m.empeoro ? '▼' : '▲'}
                  </span>
                  <span className={`text-[11px] font-bold uppercase ${m.empeoro ? 'text-[#D93B3B]' : 'text-[#2E9E6B]'}`}>
                    {m.empeoro ? 'Empeoró' : 'Mejoró'}
                  </span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

/**
 * Cumplimiento por área: una sola serie, un color, sin leyenda.
 *
 * El porcentaje solo no basta — un área al 80% con algo en rojo pesa más que
 * una al 75% con todo en amarillo — así que cada fila lleva su desglose.
 */
function PorArea({ areas }) {
  return (
    <section className="bg-white rounded-xl border border-[#D6E0F0] p-5">
      <h3 className="font-bold text-[#0D2B5E]">Cumplimiento por área</h3>
      <p className="text-xs text-[#6B7EA8] mb-3">
        Proporción de indicadores en meta. Las áreas con algo en rojo van primero.
      </p>

      {areas.length === 0 ? (
        <p className="text-sm text-[#6B7EA8] py-2">Todavía no hay áreas con indicadores medidos.</p>
      ) : (
        <div className="space-y-2.5">
          {areas.map(a => (
            <div key={a.area} className="grid grid-cols-[minmax(0,7rem)_1fr_2.5rem] gap-2.5 items-center">
              <span className="text-xs text-[#42557A] text-right truncate" title={a.area}>{a.area}</span>
              <span className="relative h-4 bg-[#EEF2F8] rounded overflow-hidden">
                <span
                  className="absolute inset-y-0 left-0 bg-[#1A4FA0] rounded"
                  style={{ width: `${a.cumplimiento_pct ?? 0}%` }}
                />
              </span>
              <span className="text-xs font-bold tabular-nums text-right text-[#1A2B47]">
                {a.cumplimiento_pct !== null ? `${Math.round(a.cumplimiento_pct)}%` : '—'}
              </span>
              <span className="col-start-2 col-span-2 flex gap-1.5 flex-wrap">
                {a.rojo > 0 && <MiniChip estado="rojo" n={a.rojo} />}
                {a.amarillo > 0 && <MiniChip estado="amarillo" n={a.amarillo} />}
                {a.verde > 0 && <MiniChip estado="verde" n={a.verde} />}
                {a.sin_datos > 0 && <MiniChip estado="sin_datos" n={a.sin_datos} />}
              </span>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

function MiniChip({ estado, n }) {
  return (
    <span className={`inline-flex items-center gap-1 px-1.5 rounded-full border text-[10px] font-bold tabular-nums ${SEMAFOROS[estado].chip}`}>
      <span aria-hidden="true">{GLIFO[estado]}</span>{n}
    </span>
  )
}

/**
 * El año en matriz: indicadores en filas, meses en columnas.
 *
 * Muestra lo que una gráfica de líneas no deja ver de un vistazo: qué
 * indicador lleva meses en rojo, o qué mes fue malo para todas las áreas.
 * Un mes que aún no llega se dibuja vacío, no como un hueco sin reportar.
 */
function Matriz({ matriz, seleccionado, onSeleccionar }) {
  const CELDA = {
    verde: 'bg-green-50 text-green-700 border-green-200',
    amarillo: 'bg-amber-50 text-amber-800 border-amber-200',
    rojo: 'bg-red-50 text-red-700 border-red-200',
    sin_datos: 'bg-gray-50 text-gray-400 border-gray-200 border-dashed',
    futuro: 'border-[#E8EEF7] border-dotted text-transparent',
  }

  return (
    <section className="bg-white rounded-xl border border-[#D6E0F0] p-5">
      <h3 className="font-bold text-[#0D2B5E]">El año completo</h3>
      <p className="text-xs text-[#6B7EA8] mb-3">
        Cada celda es un mes. Elige una fila para ver su tendencia abajo.
      </p>

      {matriz.length === 0 ? (
        <p className="text-sm text-[#6B7EA8] py-2">No hay indicadores en este alcance.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[680px] border-separate border-spacing-[3px]">
            <thead>
              <tr>
                <th className="text-left text-[10px] font-bold uppercase tracking-wide text-[#6B7EA8] w-56 pb-1">
                  Indicador
                </th>
                {matriz[0].meses.map(m => (
                  <th key={m.mes} className="text-[10px] font-bold uppercase text-[#6B7EA8] pb-1">
                    {m.etiqueta}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {matriz.map(fila => (
                <tr
                  key={fila.id}
                  onClick={() => onSeleccionar(fila.id)}
                  className="cursor-pointer group"
                >
                  <td className="text-sm">
                    <span className={`block font-semibold leading-tight group-hover:text-[#1A4FA0]
                      ${seleccionado === fila.id ? 'text-[#1A4FA0]' : 'text-[#1A2B47]'}`}>
                      {fila.nombre}
                    </span>
                    <span className="block text-[11px] text-[#6B7EA8]">{fila.area || 'Sin área'}</span>
                  </td>
                  {fila.meses.map(m => (
                    <td
                      key={m.mes}
                      title={`${m.etiqueta}: ${m.semaforo === 'futuro' ? 'aún no llega'
                        : m.valor === null ? 'sin reportar' : formatValor(m.valor, fila.unidad)}`}
                      className={`h-7 text-center text-[10px] font-bold tabular-nums border rounded ${CELDA[m.semaforo]}`}
                    >
                      {m.semaforo !== 'futuro' && (
                        <>
                          <span aria-hidden="true" className="opacity-80">{GLIFO[m.semaforo]}</span>{' '}
                          {m.valor === null ? '' : formatValor(m.valor, '')}
                        </>
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="flex flex-wrap gap-3 mt-3 text-xs text-[#42557A]">
        {['verde', 'amarillo', 'rojo', 'sin_datos'].map(e => (
          <span key={e} className="inline-flex items-center gap-1.5">
            <Chip estado={e} />
          </span>
        ))}
        <span className="inline-flex items-center gap-1.5 text-[#6B7EA8]">
          <span className="inline-block w-4 h-4 rounded border border-dotted border-[#C3CFE2]" aria-hidden="true" />
          Mes que aún no llega
        </span>
      </div>
    </section>
  )
}

/** La tendencia del indicador elegido, con la gráfica que ya usa el módulo. */
function Tendencia({ fila, mes, onVer }) {
  const serie = fila.meses.map(m => ({
    mes: m.mes,
    etiqueta: m.etiqueta,
    valor: m.semaforo === 'futuro' ? null : m.valor,
    semaforo: m.semaforo,
  }))
  const actual = fila.meses.find(m => m.mes === mes)

  return (
    <section className="bg-white rounded-xl border border-[#D6E0F0] p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-3 mb-3">
        <div>
          <h3 className="font-bold text-[#0D2B5E]">{fila.nombre}</h3>
          <p className="text-xs text-[#6B7EA8]">
            {fila.area || 'Sin área'}
            {fila.meta !== null && ` · meta ${formatValor(fila.meta, fila.unidad)}`}
            {fila.direccion === 'arriba' ? ' · más alto es mejor' : ' · más bajo es mejor'}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-2xl font-bold tabular-nums text-[#0D2B5E]">
            {formatValor(actual?.valor ?? null, fila.unidad)}
          </span>
          <button
            onClick={() => onVer?.(fila.id)}
            className="text-sm font-semibold text-[#1A4FA0] hover:underline"
          >
            Ver detalle →
          </button>
        </div>
      </div>

      <GraficaTendencia
        serie={serie}
        unidad={fila.unidad}
        meta={fila.meta}
        mesActual={mes}
      />
    </section>
  )
}
