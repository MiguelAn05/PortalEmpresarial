import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { GraficaTendencia, ChipSemaforo } from "./Graficas"
import FormMedicion from "./FormMedicion"
import {
  obtenerIndicador, listarHistorial, recalcularIndicador,
} from "../api"
import {
  MESES, formatValor, formatVariacion, tonoVariacion, TIPOS_CAPTURA,
} from "../constants"

/**
 * Detalle de un indicador: el valor del periodo, contra qué se compara, la
 * tendencia del año, los acumulados y quién ha tocado el número.
 */
export default function IndicadorDetalle({ indicadorId, anio, mes, editable, onEditar, onCerrar }) {
  const queryClient = useQueryClient()
  const [registrando, setRegistrando] = useState(false)

  const { data: ficha, isLoading } = useQuery({
    queryKey: ["ind-detalle", indicadorId, anio, mes],
    queryFn: () => obtenerIndicador(indicadorId, { anio, mes }),
  })

  const { data: historial = [] } = useQuery({
    queryKey: ["ind-historial", indicadorId],
    queryFn: () => listarHistorial(indicadorId),
  })

  const invalidar = () => {
    queryClient.invalidateQueries({ queryKey: ["ind-detalle", indicadorId] })
    queryClient.invalidateQueries({ queryKey: ["ind-historial", indicadorId] })
    queryClient.invalidateQueries({ queryKey: ["ind-tablero"] })
  }

  const mutRecalcular = useMutation({
    mutationFn: () => recalcularIndicador(indicadorId, anio, mes),
    onSuccess: invalidar,
  })

  return (
    <div className="fixed inset-0 bg-[#0D2B5E]/40 backdrop-blur-sm flex items-center justify-center p-4 z-50" onClick={onCerrar}>
      <div className="bg-white rounded-2xl w-full max-w-3xl max-h-[92vh] overflow-y-auto shadow-xl" onClick={(e) => e.stopPropagation()}>
        {isLoading || !ficha ? (
          <div className="p-16 text-center text-sm text-[#9BACC8]">Cargando indicador...</div>
        ) : (
          <>
            <div className="bg-gradient-to-r from-[#0D2B5E] to-[#1A4FA0] rounded-t-2xl p-6 text-white sticky top-0 z-10">
              <button onClick={onCerrar} className="absolute top-4 right-4 text-white/70 hover:text-white text-xl leading-none">✕</button>
              <p className="text-xs uppercase tracking-wide text-white/70 mb-1">
                {ficha.area || 'Sin área'}
                {ficha.responsable_nombre && ` · ${ficha.responsable_nombre}`}
              </p>
              <h2 className="text-xl font-bold pr-8">{ficha.nombre}</h2>
              {ficha.descripcion && <p className="text-sm text-white/80 mt-1">{ficha.descripcion}</p>}
            </div>

            <div className="p-6 space-y-6">
              {/* Cifra del periodo */}
              <div className="flex flex-wrap items-end justify-between gap-4">
                <div>
                  <p className="text-xs font-semibold text-[#6B7EA8] uppercase tracking-wide">
                    {MESES[mes - 1]} {anio}
                  </p>
                  <div className="flex items-center gap-3 mt-1">
                    <p className="text-4xl font-bold text-[#0D2B5E] leading-none">
                      {formatValor(ficha.valor, ficha.unidad)}
                    </p>
                    <ChipSemaforo estado={ficha.semaforo} />
                  </div>
                  {ficha.numerador !== null && ficha.denominador !== null && (
                    <p className="text-xs text-[#6B7EA8] mt-1.5">
                      {ficha.numerador} de {ficha.denominador}
                    </p>
                  )}
                </div>

                <div className="flex gap-2">
                  {editable && (
                    <button
                      onClick={() => onEditar(ficha)}
                      className="border border-[#D6E0F0] hover:bg-gray-50 text-[#0D2B5E] text-sm font-semibold px-4 py-2.5 rounded-xl transition"
                    >
                      Editar ficha
                    </button>
                  )}
                  {editable && ficha.es_automatico && (
                    <button
                      onClick={() => mutRecalcular.mutate()}
                      disabled={mutRecalcular.isPending}
                      className="border border-[#D6E0F0] hover:bg-gray-50 text-[#0D2B5E] text-sm font-semibold px-4 py-2.5 rounded-xl transition disabled:opacity-40"
                    >
                      {mutRecalcular.isPending ? 'Recalculando...' : '⚡ Recalcular'}
                    </button>
                  )}
                  {editable && !ficha.es_automatico && (
                    <button
                      onClick={() => setRegistrando(true)}
                      className="bg-[#1A4FA0] hover:bg-[#0D2B5E] text-white text-sm font-semibold px-4 py-2.5 rounded-xl transition"
                    >
                      {ficha.valor === null ? 'Registrar valor' : 'Corregir valor'}
                    </button>
                  )}
                </div>
              </div>

              {/* Comparaciones */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-[#EDF2F7] border border-[#EDF2F7] rounded-xl overflow-hidden">
                <Comparacion titulo="Mes anterior" valor={ficha.valor_mes_anterior}
                  variacion={ficha.variacion_mes} unidad={ficha.unidad} direccion={ficha.direccion} />
                <Comparacion titulo={`Mismo mes ${anio - 1}`} valor={ficha.valor_anio_anterior}
                  variacion={ficha.variacion_anio} unidad={ficha.unidad} direccion={ficha.direccion} />
                <Acumulado titulo={`Trimestre ${ficha.trimestre}`} acc={ficha.acumulado_trimestre}
                  unidad={ficha.unidad} modo={ficha.modo_acumulado} />
                <Acumulado titulo="Año corrido" acc={ficha.acumulado_anio}
                  unidad={ficha.unidad} modo={ficha.modo_acumulado} />
              </div>

              {/* Tendencia */}
              <div>
                <h3 className="text-sm font-bold text-[#0D2B5E] mb-3">Tendencia {anio}</h3>
                <GraficaTendencia serie={ficha.serie} unidad={ficha.unidad}
                  meta={ficha.meta} mesActual={mes} />
              </div>

              {/* Ficha técnica */}
              <div className="bg-[#F7F9FC] rounded-xl p-4 grid grid-cols-1 md:grid-cols-2 gap-4">
                {ficha.tipo_captura === 'razon' && (
                  <Campo titulo="Cómo se divide"
                    valor={`(${ficha.etiqueta_numerador || 'lo logrado'} ÷ ${ficha.etiqueta_denominador || 'el total'})`} />
                )}
                <Campo titulo="Fórmula" valor={ficha.formula_texto} />
                <Campo titulo="Cómo se captura" valor={TIPOS_CAPTURA[ficha.tipo_captura]?.label} />
                <Campo titulo="Meta"
                  valor={ficha.meta !== null
                    ? `${formatValor(ficha.meta, ficha.unidad)} · ${ficha.direccion === 'arriba' ? 'mejor cuando sube' : 'mejor cuando baja'}`
                    : null} />
                <Campo titulo="Umbrales del semáforo"
                  valor={ficha.umbral_verde !== null
                    ? `Cumple ${ficha.direccion === 'arriba' ? '≥' : '≤'} ${formatValor(ficha.umbral_verde, ficha.unidad)} · Alerta ${ficha.direccion === 'arriba' ? '≥' : '≤'} ${formatValor(ficha.umbral_amarillo, ficha.unidad)}`
                    : null} />
                {ficha.observacion && <Campo titulo="Observación del periodo" valor={ficha.observacion} />}
                {ficha.evidencia && (
                  <div>
                    <p className="text-[11px] font-semibold text-[#9BACC8] uppercase tracking-wide mb-1">Evidencia</p>
                    <a href={ficha.evidencia} target="_blank" rel="noreferrer"
                      className="text-sm text-[#1A4FA0] font-semibold underline">
                      📎 Ver soporte adjunto
                    </a>
                  </div>
                )}
              </div>

              {ficha.registrado_por && (
                <p className="text-[11px] text-[#9BACC8]">
                  Último registro por {ficha.registrado_por}
                </p>
              )}

              {/* Historial de correcciones */}
              <div className="border-t border-[#EDF2F7] pt-5">
                <h3 className="text-sm font-bold text-[#0D2B5E] mb-3">Correcciones al valor</h3>
                {historial.length === 0 ? (
                  <p className="text-xs text-[#9BACC8]">
                    Ningún valor de este indicador se ha corregido después de registrarse.
                  </p>
                ) : (
                  <div className="space-y-3">
                    {historial.map(h => (
                      <div key={h.id} className="border-l-2 border-[#D6E0F0] pl-4 py-1">
                        <div className="flex justify-between items-baseline gap-3">
                          <span className="text-sm font-semibold text-[#1A2B47]">
                            {MESES[h.mes - 1]} {h.anio}
                          </span>
                          <span className="text-[11px] text-[#9BACC8]">
                            {h.usuario_nombre} · {new Date(h.fecha).toLocaleDateString('es-CO', {
                              day: '2-digit', month: 'short', year: 'numeric',
                            })}
                          </span>
                        </div>
                        <p className="text-sm flex flex-wrap items-baseline gap-x-1.5">
                          <span className="line-through text-[#9BACC8]">{formatValor(h.valor_anterior, ficha.unidad)}</span>
                          <span className="text-[#9BACC8]">→</span>
                          <span className="font-semibold text-[#1A2B47]">{formatValor(h.valor_nuevo, ficha.unidad)}</span>
                        </p>
                        {h.motivo && <p className="text-xs text-[#6B7EA8] mt-0.5">{h.motivo}</p>}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </>
        )}
      </div>

      {registrando && ficha && (
        <FormMedicion
          indicador={ficha} anio={anio} mes={mes}
          onCerrar={() => setRegistrando(false)}
          onGuardado={() => { setRegistrando(false); invalidar() }}
        />
      )}
    </div>
  )
}

function Comparacion({ titulo, valor, variacion, unidad, direccion }) {
  const texto = formatVariacion(variacion, unidad)
  return (
    <div className="bg-white px-4 py-3">
      <p className="text-[11px] font-semibold text-[#9BACC8] uppercase tracking-wide">{titulo}</p>
      <p className="text-base font-bold text-[#0D2B5E] mt-1">{formatValor(valor, unidad)}</p>
      {texto && (
        <p className={`text-[11px] font-semibold ${tonoVariacion(variacion, direccion)}`}>{texto}</p>
      )}
    </div>
  )
}

function Acumulado({ titulo, acc, unidad, modo }) {
  return (
    <div className="bg-white px-4 py-3">
      <p className="text-[11px] font-semibold text-[#9BACC8] uppercase tracking-wide">{titulo}</p>
      <p className="text-base font-bold text-[#0D2B5E] mt-1">{formatValor(acc.valor, unidad)}</p>
      <p className="text-[11px] text-[#9BACC8]">
        {acc.meses} mes{acc.meses === 1 ? '' : 'es'}
        {modo === 'razon' && acc.denominador
          ? ` · ${acc.numerador} de ${acc.denominador}`
          : acc.aproximado ? ' · promedio' : ''}
      </p>
    </div>
  )
}

function Campo({ titulo, valor }) {
  return (
    <div>
      <p className="text-[11px] font-semibold text-[#9BACC8] uppercase tracking-wide mb-1">{titulo}</p>
      <p className="text-sm text-[#1A2B47] whitespace-pre-line">
        {valor || <span className="text-[#C3CFE2] italic">Sin definir</span>}
      </p>
    </div>
  )
}
