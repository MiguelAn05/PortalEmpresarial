import { useState } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { cerrarProyecto } from "../api"
import { formatMoneda } from "../constants"
import { useCierreSeguro } from "../../../core/components/cierreSeguro"

/**
 * Cerrar un proyecto: finalizarlo o cancelarlo.
 *
 * Las dos son la misma operación con distinto significado, por eso viven en
 * el mismo modal: quien llega aquí ya decidió que el proyecto para, y lo que
 * falta es decir si terminó o se abandona.
 *
 * Antes de confirmar se muestra el resumen de lo que va a quedar en el acta,
 * porque esos números se congelan: es lo que dirá el acta dentro de dos años
 * aunque después alguien corrija un pago.
 */
export default function CierreProyectoModal({ proyecto, onCerrar }) {
  const queryClient = useQueryClient()

  const [tipo, setTipo] = useState('finalizado')
  const [entregables, setEntregables] = useState('')
  const [motivo, setMotivo] = useState('')
  const [observaciones, setObservaciones] = useState('')
  const [evidencia, setEvidencia] = useState(null)
  const [error, setError] = useState('')

  const sucio = Boolean(entregables || motivo || observaciones || evidencia)
  const { intentarCerrar, dialogoDescarte } = useCierreSeguro({
    hayCambios: sucio, onCerrar,
  })

  const mutacion = useMutation({
    mutationFn: () => {
      const datos = new FormData()
      datos.append('tipo', tipo)
      datos.append('entregables', entregables)
      datos.append('motivo', motivo)
      datos.append('observaciones', observaciones)
      if (evidencia) datos.append('evidencia', evidencia)
      return cerrarProyecto(proyecto.id, datos)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["mp-proyecto", proyecto.id] })
      queryClient.invalidateQueries({ queryKey: ["mp-proyectos"] })
      queryClient.invalidateQueries({ queryKey: ["mp-resumen"] })
      onCerrar()
    },
    onError: (e) => setError(e.response?.data?.detail || 'No se pudo cerrar el proyecto.'),
  })

  const confirmar = (e) => {
    e.preventDefault()
    setError('')
    if (tipo === 'cancelado' && !motivo.trim()) {
      setError('Explica por qué se cancela: es lo único que va a quedar para entender la decisión.')
      return
    }
    mutacion.mutate()
  }

  const cancelando = tipo === 'cancelado'

  return (
    <div className="fixed inset-0 bg-black/40 flex items-start justify-center p-4 z-50 overflow-y-auto"
         onClick={intentarCerrar}>
      <form
        onSubmit={confirmar}
        onClick={(e) => e.stopPropagation()}
        className="bg-white rounded-2xl w-full max-w-2xl my-8 shadow-xl"
      >
        <div className="px-6 py-4 border-b border-[#D6E0F0]">
          <h2 className="text-xl font-bold text-[#0D2B5E]">Cerrar proyecto</h2>
          <p className="text-sm text-[#6B7EA8] mt-0.5">{proyecto.nombre}</p>
        </div>

        <div className="p-6 space-y-5">
          {/* La decisión primero: todo lo demás depende de ella */}
          <div className="grid grid-cols-2 gap-3">
            <button
              type="button"
              onClick={() => { setTipo('finalizado'); setError('') }}
              aria-pressed={tipo === 'finalizado'}
              className={`text-left p-4 rounded-xl border-2 transition ${
                tipo === 'finalizado'
                  ? 'border-[#2E9E6B] bg-green-50'
                  : 'border-[#D6E0F0] hover:border-[#2E9E6B]'
              }`}
            >
              <span className="block font-bold text-[#0D2B5E]">✓ Finalizar</span>
              <span className="block text-xs text-[#6B7EA8] mt-1">
                El proyecto cumplió su objetivo.
              </span>
            </button>

            <button
              type="button"
              onClick={() => { setTipo('cancelado'); setError('') }}
              aria-pressed={tipo === 'cancelado'}
              className={`text-left p-4 rounded-xl border-2 transition ${
                cancelando
                  ? 'border-[#D93B3B] bg-red-50'
                  : 'border-[#D6E0F0] hover:border-[#D93B3B]'
              }`}
            >
              <span className="block font-bold text-[#0D2B5E]">✕ Cancelar</span>
              <span className="block text-xs text-[#6B7EA8] mt-1">
                Se abandona sin completarse.
              </span>
            </button>
          </div>

          {error && (
            <div role="alert" className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3">
              {error}
            </div>
          )}

          {cancelando ? (
            <div>
              <label className="block text-xs font-semibold text-[#6B7EA8] uppercase mb-1">
                ¿Por qué se cancela? <span className="text-[#D93B3B]">*</span>
              </label>
              <textarea
                value={motivo} onChange={(e) => setMotivo(e.target.value)} rows={3}
                placeholder="El proveedor incumplió y no hay presupuesto para reemplazarlo este año"
                className="w-full rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm"
              />
              <p className="text-[11px] text-[#9BACC8] mt-1">
                Dentro de un año, esto es lo único que va a explicar la decisión.
              </p>
            </div>
          ) : (
            <div>
              <label className="block text-xs font-semibold text-[#6B7EA8] uppercase mb-1">
                Entregables
              </label>
              <textarea
                value={entregables} onChange={(e) => setEntregables(e.target.value)} rows={3}
                placeholder="Manual de operación, capacitación al personal, equipos instalados..."
                className="w-full rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm"
              />
              <p className="text-[11px] text-[#9BACC8] mt-1">
                Qué quedó del proyecto, para quien lo consulte después.
              </p>
            </div>
          )}

          <div>
            <label className="block text-xs font-semibold text-[#6B7EA8] uppercase mb-1">
              Observaciones <span className="normal-case font-normal">(opcional)</span>
            </label>
            <textarea
              value={observaciones} onChange={(e) => setObservaciones(e.target.value)} rows={2}
              placeholder="Lecciones aprendidas, pendientes que quedaron..."
              className="w-full rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-[#6B7EA8] uppercase mb-1">
              Evidencia <span className="normal-case font-normal">(opcional)</span>
            </label>
            <input
              type="file" accept="image/*,.pdf,.doc,.docx,.xls,.xlsx"
              onChange={(e) => setEvidencia(e.target.files[0] || null)}
              className="text-xs text-[#6B7EA8]"
            />
            <p className="text-[11px] text-[#9BACC8] mt-1">
              Acta de reunión, correo de aprobación, informe final...
            </p>
          </div>

          {/* Lo que se congela en el acta */}
          <div className="bg-[#F7F9FC] border border-[#D6E0F0] rounded-xl p-4">
            <h3 className="text-xs font-bold text-[#6B7EA8] uppercase tracking-wide mb-3">
              Así queda el proyecto
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <Cifra titulo="Tareas"
                     valor={`${proyecto.tareas_completadas} / ${proyecto.total_tareas}`}
                     nota="completadas" />
              <Cifra titulo="Avance" valor={`${proyecto.avance_pct}%`} />
              <Cifra titulo="Presupuesto" valor={formatMoneda(proyecto.presupuesto_total)}
                     nota="planeado" />
              <Cifra titulo="Pagado" valor={formatMoneda(proyecto.presupuesto_pagado)}
                     nota={`${proyecto.pagado_pct}% de lo aprobado`} />
            </div>
            <p className="text-[11px] text-[#9BACC8] mt-3">
              Estos números quedan guardados tal como están hoy. El acta seguirá
              mostrándolos aunque después se corrija algo.
            </p>
          </div>

          <div className="bg-amber-50 border border-amber-200 text-amber-800 text-sm rounded-lg px-4 py-3">
            El proyecto sale de las vistas del día a día, pero <b>no se borra nada</b>:
            sus tareas, presupuesto e historial quedan intactos y siempre puedes retomarlo.
          </div>
        </div>

        <div className="px-6 py-4 border-t border-[#D6E0F0] flex justify-end gap-3">
          <button type="button" onClick={onCerrar}
            className="px-4 py-2 text-sm font-semibold text-[#6B7EA8] hover:text-[#0D2B5E]">
            Volver
          </button>
          <button type="submit" disabled={mutacion.isPending}
            className={`text-white font-semibold px-5 py-2 rounded-xl text-sm transition disabled:opacity-50 ${
              cancelando ? 'bg-[#D93B3B] hover:bg-[#B32E2E]' : 'bg-[#2E9E6B] hover:bg-[#248056]'
            }`}>
            {mutacion.isPending
              ? 'Guardando...'
              : cancelando ? 'Cancelar proyecto' : 'Finalizar proyecto'}
          </button>
        </div>
      </form>

      {dialogoDescarte}
    </div>
  )
}

function Cifra({ titulo, valor, nota }) {
  return (
    <div>
      <div className="text-[11px] font-semibold text-[#9BACC8] uppercase tracking-wide">{titulo}</div>
      <div className="text-lg font-bold text-[#0D2B5E] tabular-nums leading-tight mt-0.5">{valor}</div>
      {nota && <div className="text-[11px] text-[#9BACC8]">{nota}</div>}
    </div>
  )
}
