import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { crearGestionOmpEnAreas, obtenerGestionOmp } from "../api"
import { mensajeDeError } from "../../../core/errores.js"

/**
 * Crear «Gestión de OMP» en las áreas que no lo tienen.
 *
 * Quién puede hacerlo lo decide el servidor: si la consulta responde 403, el
 * botón simplemente no aparece. Y si ya todas lo tienen, tampoco: un botón
 * que no haría nada solo genera la pregunta de para qué está.
 *
 * Antes de crear se dice en qué áreas: son varios indicadores de golpe, y
 * nadie debería enterarse de cuáles después de pulsar.
 */
export default function GestionOmpEnAreas() {
  const queryClient = useQueryClient()
  const [confirmando, setConfirmando] = useState(false)
  const [error, setError] = useState(null)

  const { data } = useQuery({
    queryKey: ["ind-gestion-omp"],
    queryFn: obtenerGestionOmp,
    retry: false,
  })

  const crear = useMutation({
    mutationFn: crearGestionOmpEnAreas,
    onSuccess: () => {
      setConfirmando(false)
      queryClient.invalidateQueries({ queryKey: ["ind-gestion-omp"] })
      queryClient.invalidateQueries({ queryKey: ["ind-tablero"] })
    },
    onError: (e) => setError(mensajeDeError(e, "No se pudieron crear los indicadores.")),
  })

  const faltantes = data?.faltantes ?? []
  if (faltantes.length === 0) return null

  return (
    <>
      <button
        onClick={() => { setError(null); setConfirmando(true) }}
        title="Crea el indicador Gestión de OMP en las áreas que todavía no lo tienen"
        className="bg-white border border-borde hover:bg-superficie-2 text-acento-fuerte font-semibold px-5 py-3 rounded-xl shadow-sm transition"
      >
        Gestión de OMP en las áreas
      </button>

      {confirmando && (
        <div className="fixed inset-0 bg-acento-fuerte/40 flex items-center justify-center p-4 z-50"
             onClick={() => setConfirmando(false)}>
          <div onClick={(e) => e.stopPropagation()}
               className="bg-white rounded-xl shadow-lg w-full max-w-lg overflow-hidden">
            <div className="px-6 py-4 border-b border-borde">
              <h3 className="text-base font-bold text-acento-fuerte">Crear «Gestión de OMP»</h3>
              <p className="text-xs text-texto-2 mt-0.5">
                Se crea en <span className="cifra font-semibold">{faltantes.length}</span>{" "}
                {faltantes.length === 1 ? "área que no lo tiene" : "áreas que no lo tienen"}.
              </p>
            </div>

            <div className="px-6 py-4 space-y-3 text-sm">
              <p className="text-texto">
                Mide cada mes qué parte de las OMP del área estuvo <strong>al día</strong>:
              </p>
              <ul className="text-texto-2 space-y-1 list-disc pl-5">
                <li>sin acciones vencidas, contando la fecha que se comprometió primero;</li>
                <li>con algún avance en el mes: seguimiento, cambio de etapa o acción cumplida;</li>
                <li>sin pasarse de su fecha estimada de solución.</li>
              </ul>
              <p className="text-texto-2">
                Se calcula solo y queda con meta de 80 %, que cada área puede ajustar en su ficha.
              </p>
              <div className="bg-superficie-2 rounded-lg px-3 py-2 max-h-32 overflow-y-auto">
                <p className="text-xs text-texto-2">{faltantes.join(" · ")}</p>
              </div>
              {error && <p role="alert" className="text-sm text-negativo">{error}</p>}
            </div>

            <div className="flex gap-2 px-6 py-4 bg-superficie-2 border-t border-borde">
              <button onClick={() => setConfirmando(false)}
                className="flex-1 border border-borde bg-white hover:bg-superficie-2 text-sm font-semibold text-acento-fuerte py-2.5 rounded-lg transition">
                Cancelar
              </button>
              <button onClick={() => crear.mutate()} disabled={crear.isPending}
                className="flex-1 bg-acento hover:bg-acento-fuerte disabled:opacity-40 text-white text-sm font-semibold py-2.5 rounded-lg transition">
                {crear.isPending ? "Creando…" : `Crear en ${faltantes.length} ${faltantes.length === 1 ? "área" : "áreas"}`}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
