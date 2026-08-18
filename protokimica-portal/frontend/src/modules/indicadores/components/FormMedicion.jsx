import { useState } from "react"
import { useMutation } from "@tanstack/react-query"
import { registrarMedicion } from "../api"
import { MESES, formatValor } from "../constants"
import { useCierreSeguro } from "../../../core/components/cierreSeguro"
import { tieneDatos } from "../../../core/components/tieneDatos"
import { IconoClip } from '../../../core/components/Iconos.jsx'

/**
 * Registro del valor de un mes. En los indicadores de razón se piden los dos
 * números y el porcentaje se calcula en vivo: quien registra ve al instante
 * qué va a quedar guardado, sin tener que hacer la cuenta aparte.
 */
export default function FormMedicion({ indicador, anio, mes, onCerrar, onGuardado }) {
  const esCorreccion = indicador.valor !== null
  const [form, setForm] = useState({
    valor: indicador.valor ?? "",
    numerador: indicador.numerador ?? "",
    denominador: indicador.denominador ?? "",
    observacion: indicador.observacion ?? "",
    motivo: "",
  })
  const [evidencia, setEvidencia] = useState(null)
  const [error, setError] = useState(null)

  const esRazon = indicador.tipo_captura === "razon"

  const inicial = {
    valor: indicador.valor ?? "",
    numerador: indicador.numerador ?? "",
    denominador: indicador.denominador ?? "",
    observacion: indicador.observacion ?? "",
    motivo: "",
  }
  const hayCambios = tieneDatos(form, inicial) || evidencia !== null
  const { intentarCerrar, dialogoDescarte } = useCierreSeguro({ hayCambios, onCerrar })

  const set = (campo) => (e) => setForm({ ...form, [campo]: e.target.value })

  // Vista previa del resultado, con la misma cuenta que hará el servidor.
  const previa = (() => {
    if (!esRazon) return null
    const n = Number(form.numerador), d = Number(form.denominador)
    if (form.numerador === "" || form.denominador === "" || !d || isNaN(n) || isNaN(d)) return null
    const bruto = n / d
    return indicador.unidad === "porcentaje" ? bruto * 100 : bruto
  })()

  // Solo tiene sentido avisar en indicadores de porcentaje: en una razon
  // (satisfaccion de 1 a 5, por ejemplo) pasar de 1 es normal.
  const sospechaInvertido =
    indicador.unidad === 'porcentaje' && previa !== null && previa > 100

  const invertir = () => setForm({
    ...form, numerador: form.denominador, denominador: form.numerador,
  })

  const mut = useMutation({
    mutationFn: () => {
      const fd = new FormData()
      fd.append("anio", anio)
      fd.append("mes", mes)
      if (esRazon) {
        fd.append("numerador", form.numerador)
        fd.append("denominador", form.denominador)
      } else {
        fd.append("valor", form.valor)
      }
      if (form.observacion) fd.append("observacion", form.observacion)
      if (form.motivo) fd.append("motivo", form.motivo)
      if (evidencia) fd.append("evidencia", evidencia)
      return registrarMedicion(indicador.id, fd)
    },
    onSuccess: onGuardado,
    onError: (e) => setError(e?.response?.data?.detail || "No se pudo guardar el valor."),
  })

  const completo = esRazon
    ? form.numerador !== "" && form.denominador !== "" && Number(form.denominador) !== 0
    : form.valor !== ""

  return (
    <div className="fixed inset-0 bg-acento-fuerte/50 backdrop-blur-sm flex items-center justify-center p-4 z-[60]" onClick={intentarCerrar}>
      <div className="bg-white rounded-2xl w-full max-w-md shadow-xl overflow-hidden" onClick={(e) => e.stopPropagation()}>
        <div className="px-6 py-4 border-b border-borde">
          <h3 className="text-base font-bold text-acento-fuerte">
            {esCorreccion ? 'Corregir' : 'Registrar'} · {MESES[mes - 1]} {anio}
          </h3>
          <p className="text-xs text-texto-2 mt-0.5">{indicador.nombre}</p>
        </div>

        <div className="px-6 py-4 space-y-4">
          {error && (
            <p className="bg-negativo-bg border border-negativo/25 text-negativo text-sm rounded-lg px-3 py-2">{error}</p>
          )}

          {esRazon ? (
            <>
              <div className="grid grid-cols-[1fr_auto_1fr] gap-2 items-end">
                <div>
                  <label className="block text-xs font-semibold text-positivo uppercase mb-1">
                    {indicador.etiqueta_numerador || 'Lo que se logró'}
                  </label>
                  <input type="number" value={form.numerador} onChange={set('numerador')}
                    autoFocus
                    className="w-full rounded-lg border border-borde px-3 py-2 text-sm" />
                </div>
                <div className="text-xl text-texto-3 pb-2">÷</div>
                <div>
                  <label className="block text-xs font-semibold text-texto-2 uppercase mb-1">
                    {indicador.etiqueta_denominador || 'De un total de'}
                  </label>
                  <input type="number" value={form.denominador} onChange={set('denominador')}
                    className="w-full rounded-lg border border-borde px-3 py-2 text-sm" />
                </div>
              </div>

              <div className="bg-superficie-2 rounded-lg px-4 py-3 text-center">
                <p className="text-[11px] font-semibold text-texto-2 uppercase tracking-wide">Quedará registrado</p>
                <p className="text-2xl font-bold text-acento-fuerte mt-0.5">
                  {previa !== null ? formatValor(Math.round(previa * 100) / 100, indicador.unidad) : '—'}
                </p>
              </div>

              {/* Un porcentaje por encima de 100 casi siempre significa que
                  los dos números se escribieron al revés. Se avisa antes de
                  guardar, no se bloquea: hay casos legítimos (sobrecumplir
                  una meta de ventas, por ejemplo). */}
              {sospechaInvertido && (
                <p className="text-xs text-alerta bg-alerta-bg border border-ambar/30 rounded-lg px-3 py-2">
                  El resultado da más de 100%. ¿Seguro que no están al revés?
                  Arriba va <strong>{indicador.etiqueta_numerador || 'lo que se logró'}</strong>{' '}
                  ({Math.min(Number(form.numerador), Number(form.denominador))}) y abajo{' '}
                  <strong>{indicador.etiqueta_denominador || 'el total'}</strong>{' '}
                  ({Math.max(Number(form.numerador), Number(form.denominador))}).
                  <button type="button" onClick={invertir}
                    className="block mt-1.5 font-semibold text-acento hover:underline">
                    Intercambiar los dos números
                  </button>
                </p>
              )}

              <p className="text-[11px] text-texto-3">
                Se guardan los dos números, no solo el resultado: es lo que permite que
                el acumulado del trimestre y del año salga correcto.
              </p>
            </>
          ) : (
            <div>
              <label className="block text-xs font-semibold text-texto-2 uppercase mb-1">
                Valor del mes
              </label>
              <input type="number" step="any" value={form.valor} onChange={set('valor')}
                autoFocus
                className="w-full rounded-lg border border-borde px-3 py-2 text-sm" />
            </div>
          )}

          <div>
            <label className="block text-xs font-semibold text-texto-2 uppercase mb-1">
              Observación (opcional)
            </label>
            <textarea value={form.observacion} onChange={set('observacion')} rows={2}
              placeholder="Contexto del resultado, si hace falta"
              className="w-full rounded-lg border border-borde px-3 py-2 text-sm resize-none" />
          </div>

          <div>
            <label className="block text-xs font-semibold text-texto-2 uppercase mb-1">
              Evidencia {indicador.requiere_evidencia && <span className="text-negativo">· obligatoria</span>}
            </label>
            <input type="file" accept=".jpg,.jpeg,.png,.webp,.pdf"
              onChange={(e) => setEvidencia(e.target.files?.[0] || null)}
              className="w-full text-xs text-texto-2 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-acento-suave file:text-acento hover:file:bg-borde" />
            {evidencia && <p className="flex items-center gap-1.5 text-xs text-texto-2 mt-1"><IconoClip tam={12} /> {evidencia.name}</p>}
          </div>

          {/* El motivo solo aplica cuando se está cambiando un número ya publicado. */}
          {esCorreccion && (
            <div>
              <label className="block text-xs font-semibold text-texto-2 uppercase mb-1">
                ¿Por qué se corrige?
              </label>
              <input value={form.motivo} onChange={set('motivo')}
                placeholder="Queda en el historial junto al cambio"
                className="w-full rounded-lg border border-borde px-3 py-2 text-sm" />
            </div>
          )}
        </div>

        <div className="flex gap-2 px-6 py-4 bg-superficie-2 border-t border-borde">
          <button onClick={intentarCerrar}
            className="flex-1 border border-borde bg-white hover:bg-superficie-2 text-sm font-semibold text-acento-fuerte py-2.5 rounded-lg transition">
            Cancelar
          </button>
          <button onClick={() => { setError(null); mut.mutate() }}
            disabled={!completo || mut.isPending}
            className="flex-1 bg-acento hover:bg-acento-fuerte disabled:opacity-40 text-white text-sm font-semibold py-2.5 rounded-lg transition">
            {mut.isPending ? 'Guardando...' : 'Guardar'}
          </button>
        </div>
      </div>

      {dialogoDescarte}
    </div>
  )
}
