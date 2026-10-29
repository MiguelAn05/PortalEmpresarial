import { useQuery } from "@tanstack/react-query"
import { listarPlantillasRevision } from "../api"
import { problemaRevisores } from "../revision.js"

/**
 * Qué cadena de revisión y quién firma cada paso.
 *
 * La plantilla dice QUÉ pasos hay («Contador», «Revisora Fiscal»); aquí se
 * elige QUIÉN. Lo usan el formulario de tarea nueva y el panel del documento,
 * para que activar el flujo y cambiar quién firma se vean igual.
 *
 * `valor` es `{ plantilla_id, revisores: [id, …] }`, en el orden de los pasos:
 * exactamente lo que viaja al servidor.
 */
export default function SelectorRevisores({ valor, onChange, usuarios = [], asignadoId = null }) {
  const { data: plantillas = [], isLoading } = useQuery({
    queryKey: ["mp-plantillas-revision"],
    queryFn: listarPlantillasRevision,
    staleTime: 5 * 60_000,
  })

  const plantilla = plantillas.find(p => p.id === valor.plantilla_id) || null
  const problema = plantilla ? problemaRevisores(plantilla, valor.revisores, asignadoId) : null

  const elegirPlantilla = (id) => {
    const p = plantillas.find(x => x.id === Number(id))
    onChange({ plantilla_id: p?.id ?? null, revisores: p ? p.pasos.map(() => null) : [] })
  }
  const elegirRevisor = (i, id) => {
    const revisores = [...valor.revisores]
    revisores[i] = id ? Number(id) : null
    onChange({ ...valor, revisores })
  }

  if (isLoading) return <p className="text-xs text-texto-3">Cargando cadenas de revisión…</p>
  if (plantillas.length === 0) {
    return <p className="text-xs text-texto-3">No hay cadenas de revisión activas. Pídele a un administrador que cree una.</p>
  }

  return (
    <div className="space-y-3">
      <div>
        <label className="block text-xs font-semibold text-texto-2 uppercase mb-1">Cadena de revisión</label>
        <select
          value={valor.plantilla_id ?? ""}
          onChange={(e) => elegirPlantilla(e.target.value)}
          className="w-full rounded-lg border border-borde px-3 py-2 text-sm"
        >
          <option value="">Elige una…</option>
          {plantillas.map(p => <option key={p.id} value={p.id}>{p.nombre}</option>)}
        </select>
        {plantilla?.descripcion && <p className="text-xs text-texto-3 mt-1">{plantilla.descripcion}</p>}
      </div>

      {plantilla && (
        <ol className="space-y-2">
          {plantilla.pasos.map((paso, i) => (
            <li key={paso.orden} className="flex items-center gap-3">
              <span className="w-6 h-6 rounded-full bg-superficie-2 border border-borde text-xs font-bold text-texto-2 flex items-center justify-center cifra">
                {i + 1}
              </span>
              <span className="w-32 text-sm font-semibold text-texto">{paso.nombre}</span>
              <select
                value={valor.revisores[i] ?? ""}
                onChange={(e) => elegirRevisor(i, e.target.value)}
                aria-label={`Quién firma como ${paso.nombre}`}
                className="flex-1 rounded-lg border border-borde px-3 py-2 text-sm"
              >
                <option value="">Elige quién firma…</option>
                {usuarios.map(u => (
                  <option key={u.id} value={u.id} disabled={u.id === asignadoId}>
                    {u.nombre}{u.id === asignadoId ? ' (tiene la tarea)' : ''}
                  </option>
                ))}
              </select>
            </li>
          ))}
        </ol>
      )}

      {problema && <p className="text-xs text-alerta">{problema}</p>}
    </div>
  )
}
