import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import TarjetaIndicador from "./components/TarjetaIndicador"
import ComoVamos from "./components/ComoVamos"
import IndicadorDetalle from "./components/IndicadorDetalle"
import FormIndicador from "./components/FormIndicador"
import { BarrasPorArea, ChipSemaforo } from "./components/Graficas"
import { obtenerTablero, recalcularPeriodo } from "./api"
import { listarUsuariosAsignables } from "../masterPlanner/api"
import { puedeEditar } from "../masterPlanner/constants"
import { useAuth } from "../../core/AuthContext"
import { MESES, periodoPorDefecto, periodoAnterior, periodoSiguiente, pestanaInicial } from "./constants"

/**
 * Tablero de indicadores. Todo el cálculo (semáforo, acumulados,
 * comparaciones) llega resuelto del servidor: aquí solo se presenta.
 */
export default function Indicadores() {
  const queryClient = useQueryClient()
  const { user } = useAuth()
  const editable = puedeEditar(user)

  const [pestana, setPestana] = useState(() => pestanaInicial(user))
  const [periodo, setPeriodo] = useState(periodoPorDefecto)
  const [area, setArea] = useState("")
  const [abierto, setAbierto] = useState(null)      // id del indicador en detalle
  const [editando, setEditando] = useState(null)    // null | 'nuevo' | indicador

  const { data: tablero, isLoading, isError } = useQuery({
    queryKey: ["ind-tablero", periodo.anio, periodo.mes, area],
    queryFn: () => obtenerTablero({ anio: periodo.anio, mes: periodo.mes, ...(area && { area }) }),
  })

  const { data: usuarios = [] } = useQuery({
    queryKey: ["mp-usuarios"],
    queryFn: listarUsuariosAsignables,
  })

  const mutRecalcular = useMutation({
    mutationFn: () => recalcularPeriodo(periodo.anio, periodo.mes),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["ind-tablero"] }),
  })

  const hoy = new Date()
  const esFuturo = periodo.anio > hoy.getFullYear()
    || (periodo.anio === hoy.getFullYear() && periodo.mes >= hoy.getMonth() + 1)

  return (
    <div className="max-w-[1400px] mx-auto px-6 py-8 space-y-6">
      <div className="flex flex-wrap justify-between items-start gap-4">
        <div>
          <h1 className="text-3xl font-bold text-[#0D2B5E]">Indicadores</h1>
          <p className="text-[#6B7EA8] mt-2">
            Cómo vamos contra lo que nos comprometimos, mes a mes.
          </p>
        </div>
        <div className="flex gap-3 items-center">
          {!editable && (
            <span className="text-xs font-semibold text-[#6B7EA8] bg-[#F7F9FC] border border-[#D6E0F0] rounded-lg px-3 py-2">
              👁 Modo consulta
            </span>
          )}
          {editable && (
            <>
              <button
                onClick={() => mutRecalcular.mutate()}
                disabled={mutRecalcular.isPending}
                title="Vuelve a calcular todos los indicadores automáticos de este periodo"
                className="bg-white border border-[#D6E0F0] hover:bg-gray-50 text-[#0D2B5E] font-semibold px-5 py-3 rounded-xl shadow-sm transition disabled:opacity-40"
              >
                {mutRecalcular.isPending ? 'Recalculando...' : '⚡ Recalcular automáticos'}
              </button>
              <button
                onClick={() => setEditando('nuevo')}
                className="bg-[#F5A800] hover:bg-[#FFC840] text-[#0D2B5E] font-semibold px-6 py-3 rounded-xl shadow-sm transition"
              >
                + Nuevo indicador
              </button>
            </>
          )}
        </div>
      </div>

      {/* Periodo y área */}
      <div className="bg-white rounded-2xl border border-[#D6E0F0] p-4 shadow-sm flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <button onClick={() => setPeriodo(periodoAnterior(periodo.anio, periodo.mes))}
            aria-label="Mes anterior"
            className="w-9 h-9 rounded-lg border border-[#D6E0F0] hover:bg-[#F7F9FC] text-[#6B7EA8]">‹</button>
          <span className="text-base font-bold text-[#0D2B5E] min-w-[160px] text-center">
            {MESES[periodo.mes - 1]} {periodo.anio}
          </span>
          <button onClick={() => setPeriodo(periodoSiguiente(periodo.anio, periodo.mes))}
            aria-label="Mes siguiente"
            className="w-9 h-9 rounded-lg border border-[#D6E0F0] hover:bg-[#F7F9FC] text-[#6B7EA8]">›</button>
          <button onClick={() => setPeriodo(periodoPorDefecto())}
            className="ml-2 text-xs font-semibold text-[#1A4FA0] hover:underline">
            Último mes cerrado
          </button>
        </div>

        <div className="flex items-center gap-3">
          <select value={area} onChange={(e) => setArea(e.target.value)}
            className="rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm bg-white min-w-[170px]">
            <option value="">Todas las áreas</option>
            {(tablero?.areas_disponibles || []).map(a => <option key={a} value={a}>{a}</option>)}
          </select>
        </div>
      </div>

      {/* Dos usos del mismo módulo: leer el estado, o registrar y consultar. */}
      <div className="flex gap-1 border-b border-[#D6E0F0]" role="tablist">
        {[['como-vamos', 'Cómo vamos'], ['tablero', 'Tablero']].map(([id, label]) => (
          <button
            key={id}
            role="tab"
            aria-selected={pestana === id}
            onClick={() => setPestana(id)}
            className={`px-4 py-2.5 text-sm font-semibold border-b-2 -mb-px transition ${
              pestana === id
                ? 'border-[#1A4FA0] text-[#1A4FA0]'
                : 'border-transparent text-[#6B7EA8] hover:text-[#1A4FA0]'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {esFuturo && (
        <div className="bg-amber-50 border border-amber-200 text-amber-800 text-sm rounded-xl px-4 py-3">
          Este mes todavía no ha cerrado. Los valores que veas están incompletos.
        </div>
      )}

      {pestana === 'como-vamos' && (
        <ComoVamos
          periodo={periodo}
          onVerIndicador={(id) => { setPestana('tablero'); setAbierto(id) }}
        />
      )}

      {pestana === 'tablero' && <>

      {isError && (
        <div className="text-center py-16 text-red-500 text-sm">No se pudo cargar el tablero.</div>
      )}

      {isLoading ? (
        <div className="text-center py-16 text-[#9BACC8] text-sm">Cargando indicadores...</div>
      ) : tablero && (
        <>
          {/* Resumen del periodo */}
          <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-4">
            <Tarjeta label="Cumplimiento"
              value={tablero.resumen.cumplimiento_pct !== null ? `${tablero.resumen.cumplimiento_pct}%` : '—'}
              color="border-t-[#0D2B5E]"
              nota={tablero.resumen.cumplimiento_pct !== null
                ? `${tablero.resumen.verde} de ${tablero.resumen.verde + tablero.resumen.amarillo + tablero.resumen.rojo} con meta`
                : 'Sin indicadores con meta'} />
            <Tarjeta label="Cumplen" value={tablero.resumen.verde} color="border-t-[#2E9E6B]" />
            <Tarjeta label="En alerta" value={tablero.resumen.amarillo} color="border-t-[#F5A800]" />
            <Tarjeta label="No cumplen" value={tablero.resumen.rojo} color="border-t-[#D93B3B]"
              alerta={tablero.resumen.rojo > 0} />
            <Tarjeta label="Falta registrar" value={tablero.resumen.pendientes_registro}
              color="border-t-[#9BACC8]"
              nota={tablero.resumen.sin_datos > 0 ? `${tablero.resumen.sin_datos} sin dato` : null} />
          </div>

          {tablero.pendientes.length > 0 && editable && (
            <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3">
              <p className="text-sm font-semibold text-amber-900 mb-1.5">
                Falta registrar {tablero.pendientes.length} indicador{tablero.pendientes.length === 1 ? '' : 'es'} de este mes
              </p>
              <div className="flex flex-wrap gap-2">
                {tablero.pendientes.map(p => (
                  <button key={p.id} onClick={() => setAbierto(p.id)}
                    className="text-xs bg-white border border-amber-200 rounded-full px-3 py-1 hover:border-amber-400 text-amber-900">
                    {p.nombre}
                    {p.responsable_nombre && <span className="text-amber-700/70"> · {p.responsable_nombre}</span>}
                  </button>
                ))}
              </div>
            </div>
          )}

          {tablero.indicadores.length === 0 ? (
            <div className="bg-white rounded-2xl border border-dashed border-[#D6E0F0] p-16 text-center">
              <p className="text-[#6B7EA8] mb-4">
                {area ? 'Esta área no tiene indicadores configurados.' : 'Todavía no hay indicadores configurados.'}
              </p>
              {editable && !area && (
                <button onClick={() => setEditando('nuevo')}
                  className="bg-[#F5A800] hover:bg-[#FFC840] text-[#0D2B5E] font-semibold px-6 py-3 rounded-xl shadow-sm transition">
                  + Crear el primer indicador
                </button>
              )}
            </div>
          ) : (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                {tablero.indicadores.map(ficha => (
                  <TarjetaIndicador key={ficha.id} ficha={ficha} onAbrir={(f) => setAbierto(f.id)} />
                ))}
              </div>

              {tablero.por_area.length > 1 && (
                <div className="bg-white rounded-2xl border border-[#D6E0F0] shadow-sm overflow-hidden">
                  <div className="px-5 py-4 border-b border-[#D6E0F0]">
                    <h3 className="text-sm font-bold text-[#0D2B5E]">Cumplimiento por área</h3>
                    <p className="text-xs text-[#9BACC8] mt-0.5">
                      Porcentaje de indicadores del área que cumplen su meta este mes.
                    </p>
                  </div>
                  <div className="p-5">
                    <BarrasPorArea areas={tablero.por_area} />
                  </div>
                </div>
              )}
            </>
          )}
        </>
      )}

      </>}

      {abierto && (
        <IndicadorDetalle
          indicadorId={abierto} anio={periodo.anio} mes={periodo.mes}
          editable={editable}
          onEditar={(ficha) => setEditando(ficha)}
          onCerrar={() => setAbierto(null)}
        />
      )}

      {editando && (
        <FormIndicador
          indicador={editando === 'nuevo' ? null : editando}
          usuarios={usuarios}
          onCerrar={() => setEditando(null)}
          onGuardado={() => setEditando(null)}
        />
      )}
    </div>
  )
}

/** Misma tarjeta de resumen que usan PQRS y Master Planner. */
function Tarjeta({ label, value, color, nota, alerta }) {
  return (
    <div className={`bg-white rounded-xl border border-[#D6E0F0] border-t-4 ${color} p-4`}>
      <div className="text-xs font-semibold text-[#6B7EA8] uppercase tracking-wide">{label}</div>
      <div className={`text-3xl font-bold mt-1 ${alerta ? 'text-[#D93B3B]' : 'text-[#0D2B5E]'}`}>{value}</div>
      {nota && <div className="text-[11px] text-[#9BACC8] mt-0.5">{nota}</div>}
    </div>
  )
}

export { ChipSemaforo }
