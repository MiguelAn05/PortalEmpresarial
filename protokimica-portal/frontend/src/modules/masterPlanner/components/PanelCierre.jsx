import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { listarCierres, retomarProyecto } from "../api"
import { formatFecha, formatMoneda } from "../constants"

/**
 * El acta de cierre de un proyecto terminado o cancelado.
 *
 * Muestra los números tal como se congelaron el día del cierre, no los
 * actuales: es lo que hace que el acta sirva para rendir cuentas.
 *
 * Si el proyecto se retomó, las actas anteriores siguen visibles marcadas
 * como anuladas — el rastro de que estuvo cancelado y por qué es justo lo
 * que alguien busca cuando pregunta si este proyecto no se había caído.
 */
export default function PanelCierre({ proyecto, puedeCerrar }) {
  const queryClient = useQueryClient()

  const { data: actas = [], isLoading } = useQuery({
    queryKey: ["mp-cierres", proyecto.id],
    queryFn: () => listarCierres(proyecto.id),
  })

  const mutRetomar = useMutation({
    mutationFn: () => retomarProyecto(proyecto.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["mp-proyecto", proyecto.id] })
      queryClient.invalidateQueries({ queryKey: ["mp-cierres", proyecto.id] })
      queryClient.invalidateQueries({ queryKey: ["mp-proyectos"] })
    },
  })

  if (isLoading) {
    return <p className="text-sm text-[#9BACC8] py-8 text-center">Cargando...</p>
  }

  if (actas.length === 0) {
    return (
      <div className="bg-white rounded-2xl border border-dashed border-[#D6E0F0] p-12 text-center">
        <p className="text-[#6B7EA8]">Este proyecto sigue abierto.</p>
        <p className="text-sm text-[#9BACC8] mt-1">
          Cuando termine o se cancele, aquí queda su acta.
        </p>
      </div>
    )
  }

  const vigente = actas.find(a => a.vigente)
  const anuladas = actas.filter(a => !a.vigente)

  return (
    <div className="space-y-4">
      {vigente && (
        <Acta acta={vigente} destacada>
          {puedeCerrar && (
            <button
              onClick={() => mutRetomar.mutate()}
              disabled={mutRetomar.isPending}
              className="border border-[#D6E0F0] hover:bg-gray-50 text-[#0D2B5E] text-sm font-semibold px-4 py-2 rounded-xl transition disabled:opacity-50"
            >
              {mutRetomar.isPending ? 'Retomando...' : 'Retomar proyecto'}
            </button>
          )}
        </Acta>
      )}

      {anuladas.length > 0 && (
        <div>
          <h3 className="text-xs font-bold text-[#6B7EA8] uppercase tracking-wide mb-2">
            Cierres anteriores
          </h3>
          <div className="space-y-3">
            {anuladas.map(a => <Acta key={a.id} acta={a} />)}
          </div>
        </div>
      )}
    </div>
  )
}

function Acta({ acta, destacada = false, children }) {
  const cancelado = acta.tipo === 'cancelado'
  const borde = !acta.vigente
    ? 'border-t-[#C3CFE2]'
    : cancelado ? 'border-t-[#D93B3B]' : 'border-t-[#2E9E6B]'

  return (
    <section className={`bg-white rounded-xl border border-[#D6E0F0] border-t-4 ${borde} p-5 ${acta.vigente ? '' : 'opacity-75'}`}>
      <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="font-bold text-[#0D2B5E]">
              {cancelado ? 'Proyecto cancelado' : 'Proyecto finalizado'}
            </h3>
            {!acta.vigente && (
              <span className="text-[11px] font-semibold text-[#6B7EA8] bg-[#F7F9FC] border border-[#D6E0F0] rounded-full px-2 py-0.5">
                Anulado — el proyecto se retomó
              </span>
            )}
          </div>
          <p className="text-xs text-[#6B7EA8] mt-0.5">
            {acta.cerrado_por_nombre || 'Alguien'} · {formatFecha(acta.cerrado_en)}
            {!acta.vigente && acta.anulado_por_nombre && (
              <> · retomado por {acta.anulado_por_nombre} el {formatFecha(acta.anulado_en)}</>
            )}
          </p>
        </div>
        {children}
      </div>

      {cancelado ? (
        <Bloque titulo="Motivo de la cancelación" texto={acta.motivo} />
      ) : (
        <Bloque titulo="Entregables" texto={acta.entregables} />
      )}

      {acta.observaciones && <Bloque titulo="Observaciones" texto={acta.observaciones} />}

      {acta.evidencia && (
        <p className="mt-3">
          <a href={`/uploads/${acta.evidencia.split('/').pop()}`}
             target="_blank" rel="noopener noreferrer"
             className="text-sm font-semibold text-[#1A4FA0] hover:underline">
            📎 Ver evidencia adjunta
          </a>
        </p>
      )}

      {/* Los números del día del cierre, no los de hoy */}
      {destacada && (
        <div className="mt-4 pt-4 border-t border-[#EDF2F7]">
          <h4 className="text-[11px] font-bold text-[#9BACC8] uppercase tracking-wide mb-3">
            Cómo quedó el proyecto al cerrarlo
          </h4>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <Cifra titulo="Tareas"
                   valor={`${acta.resumen.tareas_completadas} / ${acta.resumen.tareas_total}`}
                   nota="completadas" />
            <Cifra titulo="Duración"
                   valor={acta.resumen.dias_de_duracion !== null ? `${acta.resumen.dias_de_duracion} d` : '—'}
                   nota="desde el inicio" />
            <Cifra titulo="Planeado" valor={formatMoneda(acta.resumen.presupuesto_planeado)} />
            <Cifra titulo="Aprobado" valor={formatMoneda(acta.resumen.presupuesto_aprobado)} />
            <Cifra titulo="Pagado" valor={formatMoneda(acta.resumen.presupuesto_pagado)} />
          </div>
          <p className="text-[11px] text-[#9BACC8] mt-3">
            Cifras congeladas el día del cierre: no cambian aunque después se ajuste algo.
          </p>
        </div>
      )}
    </section>
  )
}

function Bloque({ titulo, texto }) {
  if (!texto) return null
  return (
    <div className="mt-3">
      <div className="text-[11px] font-semibold text-[#9BACC8] uppercase tracking-wide">{titulo}</div>
      <p className="text-sm text-[#1A2B47] mt-0.5 whitespace-pre-wrap">{texto}</p>
    </div>
  )
}

function Cifra({ titulo, valor, nota }) {
  return (
    <div>
      <div className="text-[11px] font-semibold text-[#9BACC8] uppercase tracking-wide">{titulo}</div>
      <div className="text-base font-bold text-[#0D2B5E] tabular-nums leading-tight mt-0.5">{valor}</div>
      {nota && <div className="text-[11px] text-[#9BACC8]">{nota}</div>}
    </div>
  )
}
