import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { TarjetasKPI } from "../components/KPICards"
import HistorialPanel from "../components/HistorialPanel"
import { obtenerResumen, listarHistorialGeneral } from "../api"
import { SALUD, TONOS, lecturaAvancePlazo, formatFecha, formatMoneda } from "../constants"

/**
 * Vista para gerencia: los números primero. Todo llega ya calculado del
 * endpoint /resumen — el frontend no recalcula nada, solo lo presenta.
 */
export default function ResumenView({ onAbrirProyecto }) {
  const [area, setArea] = useState("")

  const { data, isLoading, isError } = useQuery({
    queryKey: ["mp-resumen", area],
    queryFn: () => obtenerResumen(area ? { area } : {}),
  })

  const { data: actividad = [] } = useQuery({
    queryKey: ["mp-historial-general"],
    queryFn: () => listarHistorialGeneral({ limite: 25 }),
  })

  if (isLoading) return <div className="text-center py-16 text-[#9BACC8] text-sm">Cargando resumen...</div>
  if (isError || !data) {
    return <div className="text-center py-16 text-red-500 text-sm">No se pudo cargar el resumen.</div>
  }

  const { kpis, presupuesto, presupuesto_por_area, proyectos, cumplimiento_por_area, carga_por_persona } = data

  return (
    <div className="space-y-6">
      {/* Filtro de área: afecta a todo lo de abajo */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <label className="text-xs font-semibold text-[#6B7EA8] uppercase">Área</label>
          <select
            value={area} onChange={(e) => setArea(e.target.value)}
            className="rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm bg-white min-w-[180px]"
          >
            <option value="">Todas las áreas</option>
            {data.areas_disponibles.map(a => <option key={a} value={a}>{a}</option>)}
          </select>
          {area && (
            <button onClick={() => setArea("")} className="text-xs font-semibold text-[#1A4FA0] hover:underline">
              Quitar filtro
            </button>
          )}
        </div>
        <p className="text-xs text-[#9BACC8]">
          Solo proyectos activos. Los archivados no entran en ningún número.
        </p>
      </div>

      <TarjetasKPI tarjetas={[
        { label: 'Proyectos', value: kpis.proyectos_total, color: 'border-t-[#0D2B5E]',
          nota: `${kpis.proyectos_en_ejecucion} en ejecución` },
        { label: 'Tareas abiertas', value: kpis.tareas_abiertas, color: 'border-t-[#1A4FA0]',
          nota: kpis.tareas_sin_asignar > 0 ? `${kpis.tareas_sin_asignar} sin asignar` : null },
        { label: 'Alta prioridad', value: kpis.tareas_alta_prioridad, color: 'border-t-[#F5A800]' },
        { label: 'Vencidas', value: kpis.tareas_vencidas, color: 'border-t-[#D93B3B]',
          alerta: kpis.tareas_vencidas > 0 },
        { label: 'Proyectos en riesgo', value: kpis.proyectos_en_riesgo, color: 'border-t-[#D93B3B]',
          alerta: kpis.proyectos_en_riesgo > 0 },
      ]} />

      <Presupuesto total={presupuesto} porArea={presupuesto_por_area} />

      <EstadoProyectos proyectos={proyectos} onAbrirProyecto={onAbrirProyecto} />

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <Cumplimiento areas={cumplimiento_por_area} global={kpis} />
        <Carga personas={carga_por_persona} sinAsignar={kpis.tareas_sin_asignar} />
      </div>

      <Panel titulo="Actividad reciente"
        subtitulo="Últimos cambios registrados en proyectos y tareas.">
        <div className="p-5">
          <HistorialPanel entradas={actividad} mostrarEntidad />
        </div>
      </Panel>
    </div>
  )
}

function Panel({ titulo, subtitulo, children, accion }) {
  return (
    <div className="bg-white rounded-2xl border border-[#D6E0F0] shadow-sm overflow-hidden">
      <div className="flex flex-wrap justify-between items-center gap-2 px-5 py-4 border-b border-[#D6E0F0]">
        <div>
          <h3 className="text-sm font-bold text-[#0D2B5E]">{titulo}</h3>
          {subtitulo && <p className="text-xs text-[#9BACC8] mt-0.5">{subtitulo}</p>}
        </div>
        {accion}
      </div>
      {children}
    </div>
  )
}

function Presupuesto({ total, porArea }) {
  const sobreEjecutado = total.ejecutado > total.planeado

  return (
    <Panel
      titulo="Presupuesto"
      subtitulo="Planeado contra realmente ejecutado. El detalle por ítem está dentro de cada proyecto."
    >
      <div className="grid grid-cols-1 md:grid-cols-4 gap-px bg-[#EDF2F7] border-b border-[#D6E0F0]">
        <Cifra titulo="Planeado" valor={formatMoneda(total.planeado)} />
        <Cifra titulo="Ejecutado" valor={formatMoneda(total.ejecutado)} />
        <Cifra
          titulo="Disponible" valor={formatMoneda(total.disponible)}
          alerta={total.disponible < 0}
        />
        <Cifra
          titulo="% de ejecución" valor={`${total.ejecucion_pct}%`}
          alerta={sobreEjecutado}
        />
      </div>

      {porArea.length === 0 ? (
        <p className="px-5 py-10 text-center text-sm text-[#9BACC8]">
          Ningún proyecto tiene presupuesto cargado todavía.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full">
            <thead className="bg-[#F7F9FC] border-b border-[#D6E0F0]">
              <tr className="text-xs uppercase tracking-wider text-[#6B7EA8]">
                <th className="text-left px-5 py-3">Área</th>
                <th className="text-right px-5 py-3">Planeado</th>
                <th className="text-right px-5 py-3">Ejecutado</th>
                <th className="text-right px-5 py-3">Disponible</th>
                <th className="text-left px-5 py-3 w-56">% ejecutado</th>
              </tr>
            </thead>
            <tbody>
              {porArea.map(a => (
                <tr key={a.area} className="border-b border-[#EDF2F7] last:border-b-0">
                  <td className="px-5 py-3">
                    <p className="text-sm font-semibold text-[#0D2B5E]">{a.area}</p>
                    <p className="text-[11px] text-[#9BACC8]">
                      {a.proyectos} proyecto{a.proyectos === 1 ? '' : 's'} · {a.participacion_pct}% del total
                    </p>
                  </td>
                  <td className="px-5 py-3 text-right text-sm whitespace-nowrap">{formatMoneda(a.planeado)}</td>
                  <td className="px-5 py-3 text-right text-sm whitespace-nowrap">{formatMoneda(a.ejecutado)}</td>
                  <td className={`px-5 py-3 text-right text-sm whitespace-nowrap font-semibold ${
                    a.disponible < 0 ? 'text-red-600' : 'text-[#1A2B47]'
                  }`}>
                    {formatMoneda(a.disponible)}
                  </td>
                  <td className="px-5 py-3">
                    <BarraEjecucion pct={a.ejecucion_pct} sobrepasado={a.sobrepasado} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  )
}

function Cifra({ titulo, valor, alerta }) {
  return (
    <div className="bg-white px-5 py-4">
      <p className="text-xs font-semibold text-[#6B7EA8] uppercase tracking-wide">{titulo}</p>
      <p className={`text-xl font-bold mt-1 ${alerta ? 'text-[#D93B3B]' : 'text-[#0D2B5E]'}`}>{valor}</p>
    </div>
  )
}

function BarraEjecucion({ pct, sobrepasado }) {
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-gray-200 rounded-full h-2 min-w-[80px]">
        <div
          className="h-2 rounded-full transition-all"
          style={{
            // Por encima de 100% la barra se queda llena y el aviso lo da el color.
            width: `${Math.min(pct, 100)}%`,
            background: sobrepasado ? '#EF4444' : pct >= 80 ? '#F59E0B' : '#22C55E',
          }}
        />
      </div>
      <span className={`text-xs font-semibold w-14 text-right ${sobrepasado ? 'text-red-600' : 'text-[#6B7EA8]'}`}>
        {pct}%{sobrepasado && ' ⚠'}
      </span>
    </div>
  )
}

function EstadoProyectos({ proyectos, onAbrirProyecto }) {
  if (proyectos.length === 0) {
    return (
      <Panel titulo="Estado de los proyectos">
        <p className="px-5 py-10 text-center text-sm text-[#9BACC8]">No hay proyectos activos.</p>
      </Panel>
    )
  }

  return (
    <Panel
      titulo="Estado de los proyectos"
      subtitulo="Ordenados por riesgo. La barra es el avance real; la marca vertical (│) es dónde debería ir hoy según el tiempo transcurrido."
    >
      <div className="overflow-x-auto">
        <table className="min-w-full">
          <thead className="bg-[#F7F9FC] border-b border-[#D6E0F0]">
            <tr className="text-xs uppercase tracking-wider text-[#6B7EA8]">
              <th className="text-left px-5 py-3">Proyecto</th>
              <th className="text-left px-5 py-3">Semáforo</th>
              <th className="text-left px-5 py-3 w-48">Avance vs. plazo</th>
              <th className="text-right px-5 py-3">Entrega</th>
              <th className="text-right px-5 py-3">Replanificado</th>
              <th className="text-right px-5 py-3">Presupuesto</th>
            </tr>
          </thead>
          <tbody>
            {proyectos.map(p => {
              const salud = SALUD[p.salud] || SALUD.sin_datos
              return (
                <tr
                  key={p.id}
                  onClick={() => onAbrirProyecto(p.id)}
                  className="border-b border-[#EDF2F7] last:border-b-0 hover:bg-[#F9FBFD] transition cursor-pointer"
                >
                  <td className="px-5 py-3">
                    <p className="text-sm font-semibold text-[#0D2B5E]">{p.nombre}</p>
                    <p className="text-[11px] text-[#9BACC8]">
                      {p.area}
                      {p.lider_nombre && ` · ${p.lider_nombre}`}
                      {p.tareas_vencidas > 0 && (
                        <span className="text-red-600 font-semibold"> · {p.tareas_vencidas} tarea(s) vencida(s)</span>
                      )}
                    </p>
                  </td>
                  <td className="px-5 py-3">
                    <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold ${salud.color}`}>
                      <span className={`w-2 h-2 rounded-full ${salud.punto}`} />
                      {salud.label}
                    </span>
                  </td>
                  <td className="px-5 py-3">
                    <AvanceVsPlazo avance={p.avance_pct} plazo={p.plazo_consumido_pct} />
                  </td>
                  <td className="px-5 py-3 text-right text-sm whitespace-nowrap">
                    {formatFecha(p.fecha_fin_estimada, { day: '2-digit', month: 'short', year: 'numeric' })}
                  </td>
                  <td className="px-5 py-3 text-right whitespace-nowrap">
                    {p.replanificaciones === 0 ? (
                      <span className="text-xs text-[#C3CFE2]">—</span>
                    ) : (
                      <div>
                        <p className="text-sm font-semibold text-[#1A2B47]">
                          {p.replanificaciones} {p.replanificaciones === 1 ? 'vez' : 'veces'}
                        </p>
                        {p.dias_aplazados > 0 && (
                          <p className="text-[11px] text-red-600 font-semibold">+{p.dias_aplazados} días</p>
                        )}
                      </div>
                    )}
                  </td>
                  <td className="px-5 py-3 text-right whitespace-nowrap">
                    {!p.presupuesto_visible ? (
                      <span className="text-xs text-[#C3CFE2]" title="El presupuesto de un proyecto de otra área es privado">
                        Sin acceso
                      </span>
                    ) : p.planeado === 0 ? (
                      <span className="text-xs text-[#C3CFE2]">Sin presupuesto</span>
                    ) : (
                      <div>
                        <p className="text-sm font-semibold text-[#1A2B47]">{formatMoneda(p.planeado)}</p>
                        <p className={`text-[11px] font-semibold ${
                          p.ejecucion_pct > 100 ? 'text-red-600' : 'text-[#9BACC8]'
                        }`}>
                          {p.ejecucion_pct}% ejecutado
                        </p>
                      </div>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </Panel>
  )
}

/**
 * La barra es el avance real; la marca vertical es dónde debería ir según el
 * tiempo transcurrido. Debajo va el veredicto en palabras, porque comparar
 * dos porcentajes de cabeza no es evidente para nadie.
 */
function AvanceVsPlazo({ avance, plazo }) {
  const lectura = lecturaAvancePlazo(avance, plazo)

  if (plazo === null || plazo === undefined) {
    return (
      <div>
        <div className="bg-gray-200 rounded-full h-2.5">
          <div className="h-2.5 rounded-full bg-gray-400" style={{ width: `${Math.min(avance, 100)}%` }} />
        </div>
        <p className="text-[11px] text-[#9BACC8] mt-1">
          {avance}% de avance · sin fechas para comparar
        </p>
      </div>
    )
  }

  return (
    <div title={lectura.detalle}>
      <div className="relative bg-gray-200 rounded-full h-2.5">
        <div
          className="h-2.5 rounded-full transition-all"
          style={{
            width: `${Math.min(avance, 100)}%`,
            background: lectura.tono === 'bueno' ? '#22C55E' : lectura.tono === 'regular' ? '#F59E0B' : '#EF4444',
          }}
        />
        <div
          className="absolute top-[-3px] w-0.5 h-[16px] bg-[#0D2B5E]"
          style={{ left: `${Math.min(plazo, 100)}%` }}
          title={`Marca del plazo: hoy debería ir por el ${Math.round(plazo)}%`}
        />
      </div>
      <p className={`text-[11px] font-semibold mt-1 ${TONOS[lectura.tono]}`}>{lectura.texto}</p>
      <p className="text-[11px] text-[#9BACC8]">{lectura.detalle}</p>
    </div>
  )
}

function Cumplimiento({ areas, global }) {
  return (
    <Panel
      titulo="Cumplimiento de fechas"
      subtitulo="Solo cuenta las tareas cerradas que tenían fecha comprometida."
      accion={
        <div className="text-right">
          <p className="text-2xl font-bold text-[#0D2B5E]">{global.cumplimiento_pct}%</p>
          <p className="text-[11px] text-[#9BACC8]">{global.tareas_medibles} tarea(s) medible(s)</p>
        </div>
      }
    >
      {global.tareas_medibles === 0 ? (
        <p className="px-5 py-8 text-center text-sm text-[#9BACC8]">
          Todavía no hay tareas cerradas con fecha comprometida. El porcentaje aparece
          a medida que se vayan completando tareas que tenían fecha de fin.
        </p>
      ) : (
        <div className="divide-y divide-[#EDF2F7]">
          {areas.filter(a => a.medibles > 0 || a.abiertas > 0).map(a => (
            <div key={a.area} className="px-5 py-3">
              <div className="flex justify-between items-baseline mb-1.5">
                <span className="text-sm font-semibold text-[#0D2B5E]">{a.area}</span>
                <span className="text-xs text-[#6B7EA8]">
                  {a.medibles > 0 ? `${a.cumplimiento_pct}% a tiempo` : 'sin datos aún'}
                </span>
              </div>
              {a.medibles > 0 && (
                <div className="flex h-2 rounded-full overflow-hidden bg-gray-200 mb-1.5">
                  <div className="bg-green-500" style={{ width: `${a.cumplimiento_pct}%` }} />
                  <div className="bg-red-400 flex-1" />
                </div>
              )}
              <p className="text-[11px] text-[#9BACC8]">
                {a.a_tiempo} a tiempo · {a.tarde} tarde · {a.abiertas} abiertas
                {a.vencidas > 0 && <span className="text-red-600 font-semibold"> · {a.vencidas} vencidas</span>}
              </p>
            </div>
          ))}
        </div>
      )}
    </Panel>
  )
}

function Carga({ personas, sinAsignar }) {
  return (
    <Panel
      titulo="Carga por responsable"
      subtitulo="Tareas abiertas de cada persona, con lo vencido primero."
    >
      {personas.length === 0 ? (
        <p className="px-5 py-8 text-center text-sm text-[#9BACC8]">
          No hay tareas abiertas asignadas a nadie.
        </p>
      ) : (
        <div className="divide-y divide-[#EDF2F7]">
          {personas.map(p => (
            <div key={p.usuario_id} className="px-5 py-3 flex items-center justify-between gap-4">
              <div className="min-w-0">
                <p className="text-sm font-semibold text-[#0D2B5E] truncate">{p.nombre}</p>
                <p className="text-[11px] text-[#9BACC8]">
                  {p.area || 'Sin área'}
                  {p.alta_prioridad > 0 && ` · ${p.alta_prioridad} de alta prioridad`}
                </p>
              </div>
              <div className="flex gap-2 shrink-0">
                <Contador valor={p.activas} etiqueta="activas" />
                {p.por_vencer > 0 && <Contador valor={p.por_vencer} etiqueta="por vencer" tono="amber" />}
                {p.vencidas > 0 && <Contador valor={p.vencidas} etiqueta="vencidas" tono="red" />}
              </div>
            </div>
          ))}
        </div>
      )}
      {sinAsignar > 0 && (
        <div className="px-5 py-3 bg-[#FFF8E6] border-t border-[#F5E3B0] text-xs text-[#8A6D1F] font-medium">
          ⚠ {sinAsignar} tarea{sinAsignar === 1 ? '' : 's'} abierta{sinAsignar === 1 ? '' : 's'} sin responsable asignado.
        </div>
      )}
    </Panel>
  )
}

function Contador({ valor, etiqueta, tono }) {
  const estilos = {
    amber: 'bg-amber-50 border-amber-200 text-amber-700',
    red: 'bg-red-50 border-red-200 text-red-700',
  }[tono] || 'bg-[#F7F9FC] border-[#D6E0F0] text-[#0D2B5E]'

  return (
    <div className={`border rounded-lg px-2.5 py-1 text-center min-w-[64px] ${estilos}`}>
      <p className="text-base font-bold leading-tight">{valor}</p>
      <p className="text-[10px] uppercase tracking-wide leading-tight">{etiqueta}</p>
    </div>
  )
}
