/**
 * Aviso antes de perder lo escrito al cerrar un formulario.
 *
 * El `stopPropagation` no es decorativo: este diálogo se dibuja dentro del
 * modal que está protegiendo, y ese modal cierra al hacer clic en su fondo.
 * Sin frenar el clic aquí, pulsar "Seguir editando" llegaba también al fondo,
 * que volvía a abrir el aviso al instante — se veía como si el botón no
 * funcionara y solo "Descartar" cerraba.
 */
export default function ConfirmarDescarte({ onSeguir, onDescartar }) {
  return (
    <div
      className="fixed inset-0 bg-[#0D2B5E]/50 backdrop-blur-sm flex items-center justify-center p-4 z-[70]"
      onClick={(e) => e.stopPropagation()}
    >
      <div className="bg-white rounded-2xl w-full max-w-sm shadow-xl overflow-hidden">
        <div className="px-6 py-5">
          <h3 className="text-base font-bold text-[#0D2B5E]">Tienes datos sin guardar</h3>
          <p className="text-sm text-[#6B7EA8] mt-1.5">
            Si cierras ahora se pierde lo que llevas escrito. ¿Qué quieres hacer?
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
            autoFocus
            className="flex-1 bg-[#1A4FA0] hover:bg-[#0D2B5E] text-white text-sm font-semibold py-2.5 rounded-lg transition"
          >
            Seguir editando
          </button>
        </div>
      </div>
    </div>
  )
}
