import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { mensajeDeError } from '../../../core/errores.js'
import { Esqueleto } from '../../../core/components/Cargando.jsx'
import { formatFecha } from '../../masterPlanner/constants.js'
import { ESTADOS_MARCA } from '../constants.js'
import { obtenerPersona } from '../api.js'
import { Presencia } from './piezas.jsx'
import NovedadesDia from './NovedadesDia.jsx'

/**
 * El detalle de una persona: sus últimos 14 días, con cada marcación y las
 * novedades. Es un panel encima de la lista; Escape o el fondo lo cierran.
 */
export default function DetallePersona({ empCode, onCerrar }) {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['marcaciones', 'persona', empCode],
    queryFn: () => obtenerPersona(empCode),
  })

  useEffect(() => {
    const alTeclear = (e) => { if (e.key === 'Escape') onCerrar() }
    window.addEventListener('keydown', alTeclear)
    return () => window.removeEventListener('keydown', alTeclear)
  }, [onCerrar])

  const t = data?.totales
  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-black/30 print:hidden" onClick={onCerrar}>
      <aside role="dialog" aria-modal="true" aria-label="Detalle de marcaciones"
             onClick={(e) => e.stopPropagation()}
             className="w-full max-w-xl h-full overflow-y-auto bg-superficie shadow-xl p-5 space-y-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-xl font-bold text-acento-fuerte">{data?.persona.nombre ?? 'Cargando…'}</h2>
            {data && <p className="text-xs text-texto-2 mt-0.5">{data.persona.area || 'Sin área'} · código {data.persona.emp_code}</p>}
          </div>
          <button type="button" onClick={onCerrar} className="text-sm text-texto-2 hover:text-acento-fuerte">Cerrar</button>
        </div>

        {isError && <p role="alert" className="text-sm text-negativo">{mensajeDeError(error, 'No se pudo cargar a esta persona.')}</p>}
        {isLoading && <div className="space-y-2">{[0, 1, 2].map(i => <Esqueleto key={i} alto="h-16" className="rounded-xl" />)}</div>}

        {data && (
          <>
            <p className="text-xs text-texto-2">
              Del {formatFecha(data.desde)} al {formatFecha(data.hasta)}:{' '}
              <span className="cifra">{t.con_novedad}</span> días con novedad, <span className="cifra">{t.total_novedades}</span> novedades en total.
            </p>
            <ul className="space-y-3">
              {data.dias.length === 0 && <li className="text-sm text-texto-2">Sin días con turno ni marcaciones en este rango.</li>}
              {data.dias.map(d => (
                <li key={d.fecha} className="rounded-xl border border-borde p-3">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-semibold text-texto text-sm">{formatFecha(d.fecha, { weekday: 'short', day: '2-digit', month: 'short' })}</span>
                    <Presencia clave={d.presencia} />
                  </div>
                  <div className="text-xs text-texto-2 mt-1">
                    Turno <span className="cifra">{d.turno || d.turno_opciones || '—'}</span>
                    {d.motivo && <> · {d.motivo}</>}
                  </div>
                  {d.marcas.length > 0 && (
                    <ol className="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-xs text-texto">
                      {d.marcas.map((m, i) => (
                        <li key={i}><span className="cifra font-semibold">{m.hora}</span> <span className="text-texto-2">{ESTADOS_MARCA[m.estado] ?? m.estado}</span></li>
                      ))}
                    </ol>
                  )}
                  {d.novedades.length > 0 && (
                    <div className="mt-2">
                      <NovedadesDia empCode={data.persona.emp_code} fecha={d.fecha} novedades={d.novedades} puede={data.puede_justificar} />
                    </div>
                  )}
                </li>
              ))}
            </ul>
          </>
        )}
      </aside>
    </div>
  )
}
