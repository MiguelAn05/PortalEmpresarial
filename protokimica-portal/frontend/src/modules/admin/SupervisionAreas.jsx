import { useState } from 'react'
import { AREAS } from '../../core/areas.js'
import { IconoCerrar, IconoPersonas } from '../../core/components/Iconos.jsx'

/**
 * Qué áreas supervisa una persona, además de la suya.
 *
 * Un director responde por varias áreas —Dirección Técnica mira IDI y
 * Salvak— y el portal filtra por área exacta: sin esto no vería nada de su
 * gente. Es de **una sola vía**: se marca hacia abajo, y el equipo de esas
 * áreas sigue viendo solo la suya.
 *
 * El botón dice cuántas supervisa en vez de esconderlo en un menú: con
 * cuarenta usuarios, saber de un vistazo quién mira qué es la mitad del
 * trabajo de administrar esto.
 */
export default function SupervisionAreas({ usuario, onGuardar, guardando }) {
  const actuales = usuario.areas_supervisadas ?? []
  const [abierto, setAbierto] = useState(false)
  const [marcadas, setMarcadas] = useState(actuales)

  const abrir = () => { setMarcadas(usuario.areas_supervisadas ?? []); setAbierto(true) }
  const alternar = (area) => setMarcadas(
    marcadas.includes(area) ? marcadas.filter(a => a !== area) : [...marcadas, area],
  )

  const cambio = JSON.stringify([...marcadas].sort()) !== JSON.stringify([...actuales].sort())

  return (
    <>
      <button
        onClick={abrir}
        title={actuales.length
          ? `Supervisa: ${actuales.join(', ')}`
          : 'No supervisa otras áreas'}
        className={`inline-flex items-center gap-1 text-xs font-semibold px-2 py-1.5 rounded-lg border transition-colors duration-150 flex-shrink-0 ${
          actuales.length
            ? 'border-acento/40 bg-acento-suave text-acento'
            : 'border-borde bg-white text-texto-3 hover:text-texto-2'
        }`}
      >
        <IconoPersonas tam={14} />
        {actuales.length ? `Supervisa ${actuales.length}` : 'Supervisa'}
      </button>

      {abierto && (
        <div className="fixed inset-0 bg-acento-fuerte/40 flex items-center justify-center p-4 z-[60]"
             onClick={() => setAbierto(false)}>
          <div onClick={(e) => e.stopPropagation()}
               className="bg-white rounded-xl shadow-lg w-full max-w-md overflow-hidden">
            <div className="flex items-start justify-between gap-2 px-6 py-4 border-b border-borde">
              <div>
                <h3 className="text-base font-bold text-acento-fuerte">Áreas que supervisa</h3>
                <p className="text-xs text-texto-2 mt-0.5">{usuario.nombre}</p>
              </div>
              <button onClick={() => setAbierto(false)} aria-label="Cerrar"
                className="text-texto-3 hover:text-texto">
                <IconoCerrar tam={16} />
              </button>
            </div>

            <div className="px-6 py-4">
              <p className="text-xs text-texto-2 mb-3">
                Verá los indicadores, las oportunidades de mejora y los proyectos de
                estas áreas, además de los de la suya. Ellos no ven los de él.
              </p>
              {/* Con dos docenas de áreas, lo marcado se pierde en la lista:
                  arriba se dice de una vez qué queda supervisando. */}
              <p className="text-xs bg-superficie-2 rounded-lg px-3 py-2 mb-3">
                {marcadas.length
                  ? <>Supervisará: <strong className="text-texto">{marcadas.join(" · ")}</strong></>
                  : <span className="text-texto-3">No supervisa otras áreas.</span>}
              </p>
              <div className="max-h-64 overflow-y-auto space-y-1">
                {AREAS.map(area => {
                  const esLaSuya = area === usuario.area
                  return (
                    <label key={area}
                      className={`flex items-center gap-2 text-sm rounded-lg px-2 py-1.5 ${
                        esLaSuya ? 'text-texto-3' : 'text-texto hover:bg-superficie-2 cursor-pointer'
                      }`}>
                      <input
                        type="checkbox"
                        checked={esLaSuya || marcadas.includes(area)}
                        disabled={esLaSuya}
                        onChange={() => alternar(area)}
                        className="rounded border-borde accent-acento"
                      />
                      {area}
                      {esLaSuya && <span className="text-xs text-texto-3">· es su área</span>}
                    </label>
                  )
                })}
              </div>
            </div>

            <div className="flex gap-2 px-6 py-4 bg-superficie-2 border-t border-borde">
              <button onClick={() => setAbierto(false)}
                className="flex-1 border border-borde bg-white hover:bg-superficie-2 text-sm font-semibold text-acento-fuerte py-2.5 rounded-lg transition">
                Cancelar
              </button>
              <button
                onClick={() => { onGuardar(marcadas); setAbierto(false) }}
                disabled={!cambio || guardando}
                className="flex-1 bg-acento hover:bg-acento-fuerte disabled:opacity-40 text-white text-sm font-semibold py-2.5 rounded-lg transition"
              >
                {guardando ? 'Guardando…' : 'Guardar'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
