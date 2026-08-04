import { useEffect, useState } from "react"
import ConfirmarDescarte from "./ConfirmarDescarte"

/**
 * Evita que un clic accidental fuera de un modal borre lo que la persona
 * llevaba escrito.
 *
 * La regla: si el formulario está vacío, cerrar es inofensivo y se cierra sin
 * preguntar. Si ya hay algo escrito, se pide confirmación. Bloquear el cierre
 * siempre sería igual de molesto que perderlo todo — el aviso solo aparece
 * cuando de verdad hay algo que perder.
 *
 * Uso:
 *   const { intentarCerrar, dialogoDescarte } = useCierreSeguro({ hayCambios, onCerrar })
 *   <div onClick={intentarCerrar}>            // fondo
 *     <button onClick={intentarCerrar}>✕</button>
 *     ...
 *   </div>
 *   {dialogoDescarte}
 */
export function useCierreSeguro({ hayCambios, onCerrar }) {
  const [preguntando, setPreguntando] = useState(false)

  const intentarCerrar = () => {
    if (hayCambios) setPreguntando(true)
    else onCerrar()
  }

  // Escape hace lo mismo que el clic fuera: es la otra forma de cerrar sin
  // querer, y tiene que estar igual de protegida.
  useEffect(() => {
    const alPulsar = (e) => {
      if (e.key !== 'Escape') return
      if (hayCambios) setPreguntando(true)
      else onCerrar()
    }
    document.addEventListener('keydown', alPulsar)
    return () => document.removeEventListener('keydown', alPulsar)
  }, [hayCambios, onCerrar])

  const dialogoDescarte = preguntando ? (
    <ConfirmarDescarte
      onSeguir={() => setPreguntando(false)}
      onDescartar={() => { setPreguntando(false); onCerrar() }}
    />
  ) : null

  return { intentarCerrar, dialogoDescarte, preguntando }
}
