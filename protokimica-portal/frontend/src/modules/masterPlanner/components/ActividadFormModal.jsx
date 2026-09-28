/**
 * Crear una actividad diaria.
 *
 * **Tres campos: qué, quién y cada cuánto.** Es a propósito: una actividad
 * diaria es corta y repetitiva, y pedirle siete campos a algo que se escribe
 * una vez y se marca todos los días es cómo se consigue que nadie la cree.
 * El área se hereda del responsable en el servidor, que es quien la sabe.
 *
 * Lo que NO tiene, y tampoco por descuido: proyecto (no pertenece a
 * ninguno), fecha de entrega (no termina) y avance (o se hizo ese día o no).
 */
import { useState } from "react"
import { useMutation } from "@tanstack/react-query"
import { crearActividad } from "../api"
import { DIAS_ISO, FRECUENCIAS, MAX_TITULO_ACTIVIDAD } from "../constants"
import { useCierreSeguro } from "../../../core/components/cierreSeguro"
import { mensajeDeError } from "../../../core/errores.js"
import { IconoCerrar } from "../../../core/components/Iconos.jsx"

export default function ActividadFormModal({ usuarios = [], onClose, onCreada }) {
  const [titulo, setTitulo] = useState("")
  const [asignadoA, setAsignadoA] = useState("")
  const [frecuencia, setFrecuencia] = useState("diaria")
  const [dias, setDias] = useState([])
  const [diaMes, setDiaMes] = useState("")
  const [soloHabiles, setSoloHabiles] = useState(true)
  const [error, setError] = useState("")

  const hayCambios = Boolean(titulo.trim())
  const { intentarCerrar, dialogoDescarte } = useCierreSeguro({ hayCambios, onCerrar: onClose })

  const alternarDia = (n) =>
    setDias(dias.includes(n) ? dias.filter(d => d !== n) : [...dias, n].sort())

  const mutCrear = useMutation({
    mutationFn: () => crearActividad({
      titulo: titulo.trim(),
      asignado_a: asignadoA ? Number(asignadoA) : null,
      frecuencia,
      dias_semana: frecuencia === "semanal" ? dias : [],
      dia_mes: frecuencia === "mensual" && diaMes ? Number(diaMes) : null,
      solo_dias_habiles: soloHabiles,
    }),
    onSuccess: () => { onCreada?.(); onClose() },
    onError: (err) => setError(mensajeDeError(err, 'No se pudo crear la actividad.')),
  })

  // Lo que el servidor va a exigir, comprobado aquí para que el error no
  // ocurra en vez de explicarlo después.
  const listo = titulo.trim().length >= 3
    && (frecuencia !== "semanal" || dias.length > 0)
    && (frecuencia !== "mensual" || Boolean(diaMes))

  const campo = "w-full rounded-lg border border-borde px-3 py-2 text-sm"

  return (
    <>
      <div
        className="fixed inset-0 bg-acento-fuerte/40 backdrop-blur-sm flex items-center
          justify-center p-4 z-50"
        onClick={intentarCerrar}
      >
        <div
          onClick={(e) => e.stopPropagation()}
          className="bg-white rounded-2xl w-full max-w-md max-h-[90vh] overflow-y-auto shadow-xl"
        >
          <div className="bg-gradient-to-r from-acento-fuerte to-acento rounded-t-2xl p-6 text-white sticky top-0">
            <button
              onClick={intentarCerrar} aria-label="Cerrar"
              className="absolute top-4 right-4 text-white/70 hover:text-white"
            >
              <IconoCerrar tam={18} />
            </button>
            <h2 className="text-lg font-bold">Nueva actividad diaria</h2>
            <p className="text-xs text-white/70 mt-1">
              Actividades que se repiten y no pertenecen a un proyecto.
            </p>
          </div>

          <div className="p-6 space-y-4">
            <div>
              <label className="block text-xs font-semibold text-texto-2 uppercase mb-1">
                Nombre de la actividad 
              </label>
              <input
                value={titulo} onChange={(e) => setTitulo(e.target.value)}
                maxLength={MAX_TITULO_ACTIVIDAD} autoFocus className={campo}
                placeholder="Ej: Revisar el correo del área"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-texto-2 uppercase mb-1">
                Responsable
              </label>
              <select value={asignadoA} onChange={(e) => setAsignadoA(e.target.value)} className={campo}>
                <option value="">Yo</option>
                {usuarios.map(u => <option key={u.id} value={u.id}>{u.nombre}</option>)}
              </select>
              <p className="text-xs text-texto-3 mt-1">
                Solo tú o alguien de tu área. El área se toma de esa persona.
              </p>
            </div>

            <div>
              <label className="block text-xs font-semibold text-texto-2 uppercase mb-1">
                Cada cuánto
              </label>
              <select value={frecuencia} onChange={(e) => setFrecuencia(e.target.value)} className={campo}>
                {Object.entries(FRECUENCIAS).map(([v, label]) => (
                  <option key={v} value={v}>{label}</option>
                ))}
              </select>
            </div>

            {frecuencia === "diaria" && (
              <label className="flex items-start gap-2 text-sm text-texto-2">
                <input
                  type="checkbox" checked={soloHabiles}
                  onChange={(e) => setSoloHabiles(e.target.checked)}
                  className="rounded border-borde-fuerte mt-0.5"
                />
                <span>
                  Solo días hábiles
                  <span className="block text-xs text-texto-3">
                    Sin fines de semana ni festivos. El portal ya sabe cuáles son.
                  </span>
                </span>
              </label>
            )}

            {frecuencia === "semanal" && (
              <div>
                <span className="block text-xs font-semibold text-texto-2 uppercase mb-1.5">
                  Qué días
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {Object.entries(DIAS_ISO).map(([n, nombre]) => (
                    <button
                      key={n} type="button"
                      onClick={() => alternarDia(Number(n))}
                      aria-pressed={dias.includes(Number(n))}
                      className={`px-3 py-1.5 rounded-lg text-xs font-semibold border
                        transition-colors duration-150 ${
                        dias.includes(Number(n))
                          ? 'bg-acento text-white border-acento'
                          : 'bg-white text-texto-2 border-borde hover:border-acento'
                      }`}
                    >
                      {nombre.slice(0, 3)}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {frecuencia === "mensual" && (
              <div>
                <label className="block text-xs font-semibold text-texto-2 uppercase mb-1">
                  Qué día del mes
                </label>
                <input
                  type="number" min="1" max="31" value={diaMes}
                  onChange={(e) => setDiaMes(e.target.value)}
                  className={`${campo} cifra`} placeholder="Ej: 5"
                />
                <p className="text-xs text-texto-3 mt-1">
                  Si pones 31, en los meses de 30 se espera el último día.
                </p>
              </div>
            )}

            {error && (
              <p role="alert" className="text-sm text-negativo bg-negativo-bg
                border border-negativo/25 rounded-lg px-3 py-2">
                {error}
              </p>
            )}

            <button
              onClick={() => mutCrear.mutate()}
              disabled={!listo || mutCrear.isPending}
              className="w-full bg-acento hover:bg-acento-fuerte disabled:opacity-40
                text-white font-semibold py-2.5 rounded-lg transition"
            >
              {mutCrear.isPending ? 'Creando…' : 'Crear actividad'}
            </button>
          </div>
        </div>
      </div>
      {dialogoDescarte}
    </>
  )
}
