import { etiquetaCampo, valorHistorial, diasDesplazados } from "../constants"

/**
 * Confirmación antes de guardar. Muestra exactamente qué va a cambiar, con
 * el valor de antes y el de después, en vez de un "¿seguro?" genérico: si
 * el pop-up no dice nada útil, la gente aprende a darle Aceptar sin leer.
 *
 * `cambios` es una lista de { campo, antes, despues } ya calculada por quien
 * lo invoca — así el modal no necesita saber de dónde salen los datos.
 */
export default function ConfirmarCambios({
  titulo = "¿Guardar los cambios?",
  cambios = [],
  nota,
  textoConfirmar = "Guardar",
  guardando = false,
  onConfirmar,
  onCancelar,
}) {
  return (
    <div
      className="fixed inset-0 bg-[#0D2B5E]/50 backdrop-blur-sm flex items-center justify-center p-4 z-[60]"
      onClick={onCancelar}
    >
      <div
        className="bg-white rounded-2xl w-full max-w-md shadow-xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-6 py-4 border-b border-[#EDF2F7]">
          <h3 className="text-base font-bold text-[#0D2B5E]">{titulo}</h3>
        </div>

        <div className="px-6 py-4 max-h-[50vh] overflow-y-auto">
          {cambios.length === 0 ? (
            <p className="text-sm text-[#6B7EA8]">No hay cambios por guardar.</p>
          ) : (
            <ul className="space-y-2.5">
              {cambios.map((c, i) => <LineaCambio key={`${c.campo}-${i}`} cambio={c} />)}
            </ul>
          )}

          <p className="text-xs text-[#9BACC8] mt-4 pt-3 border-t border-[#EDF2F7]">
            {nota || 'Queda registrado en el historial con tu nombre y la fecha.'}
          </p>
        </div>

        <div className="flex gap-2 px-6 py-4 bg-[#F7F9FC] border-t border-[#EDF2F7]">
          <button
            onClick={onCancelar}
            className="flex-1 border border-[#D6E0F0] bg-white hover:bg-gray-50 text-sm font-semibold text-[#0D2B5E] py-2.5 rounded-lg transition"
          >
            Cancelar
          </button>
          <button
            onClick={onConfirmar}
            disabled={guardando || cambios.length === 0}
            className="flex-1 bg-[#1A4FA0] hover:bg-[#0D2B5E] disabled:opacity-40 text-white text-sm font-semibold py-2.5 rounded-lg transition"
          >
            {guardando ? 'Guardando...' : textoConfirmar}
          </button>
        </div>
      </div>
    </div>
  )
}

function LineaCambio({ cambio }) {
  const { campo, antes, despues } = cambio
  const dias = diasDesplazados({ campo, valor_anterior: antes, valor_nuevo: despues })

  return (
    <li className="text-sm">
      <p className="text-xs font-semibold text-[#6B7EA8] uppercase tracking-wide">
        {etiquetaCampo(campo)}
      </p>
      <p className="flex flex-wrap items-baseline gap-x-1.5 mt-0.5">
        <span className="line-through text-[#9BACC8]">{valorHistorial(campo, antes)}</span>
        <span className="text-[#9BACC8]">→</span>
        <span className="font-semibold text-[#1A2B47]">{valorHistorial(campo, despues)}</span>
      </p>
      {dias !== null && dias !== 0 && (
        <span className={`inline-block mt-1 text-[11px] font-semibold rounded-full px-2 py-0.5 ${
          dias > 0 ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'
        }`}>
          {dias > 0
            ? `se aplaza ${dias} día${dias === 1 ? '' : 's'}`
            : `se adelanta ${Math.abs(dias)} día${Math.abs(dias) === 1 ? '' : 's'}`}
        </span>
      )}
    </li>
  )
}

/**
 * Aviso al cerrar un formulario con cambios pendientes. Es el otro lado de
 * la moneda: confirmar antes de guardar y avisar antes de perder.
 */
export function ConfirmarDescarte({ onSeguir, onDescartar }) {
  return (
    <div className="fixed inset-0 bg-[#0D2B5E]/50 backdrop-blur-sm flex items-center justify-center p-4 z-[60]">
      <div className="bg-white rounded-2xl w-full max-w-sm shadow-xl overflow-hidden">
        <div className="px-6 py-5">
          <h3 className="text-base font-bold text-[#0D2B5E]">Tienes cambios sin guardar</h3>
          <p className="text-sm text-[#6B7EA8] mt-1.5">
            Si cierras ahora se pierden. ¿Qué quieres hacer?
          </p>
        </div>
        <div className="flex gap-2 px-6 py-4 bg-[#F7F9FC] border-t border-[#EDF2F7]">
          <button
            onClick={onDescartar}
            className="flex-1 border border-[#D6E0F0] bg-white hover:bg-red-50 hover:border-red-200 hover:text-red-700 text-sm font-semibold text-[#0D2B5E] py-2.5 rounded-lg transition"
          >
            Descartar
          </button>
          <button
            onClick={onSeguir}
            className="flex-1 bg-[#1A4FA0] hover:bg-[#0D2B5E] text-white text-sm font-semibold py-2.5 rounded-lg transition"
          >
            Seguir editando
          </button>
        </div>
      </div>
    </div>
  )
}
