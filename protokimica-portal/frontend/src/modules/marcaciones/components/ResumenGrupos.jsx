import { Seccion } from '../../../core/components/Informe.jsx'

/**
 * Una fila por área o por líder con lo que importa de un vistazo. Pulsarla
 * filtra la lista de abajo por ese grupo; volver a pulsarla lo quita.
 */
function Tabla({ filas, clave, rotulo, activo, onElegir }) {
  if (!filas.length) return <p className="text-sm text-texto-2">Sin datos para este día.</p>
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-xs text-texto-2 uppercase tracking-wide text-left border-b border-borde">
          <th className="py-2 font-semibold">{rotulo}</th>
          <th className="py-2 font-semibold text-right" title="Personas esperadas ese día">Pers.</th>
          <th className="py-2 font-semibold text-right">Adentro</th>
          <th className="py-2 font-semibold text-right">Ausentes</th>
          <th className="py-2 font-semibold text-right">Novedades</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-borde">
        {filas.map(f => {
          const nombre = f[clave]
          const marcada = activo === nombre
          return (
            <tr key={nombre}>
              <td className="py-1.5">
                <button type="button" onClick={() => onElegir(marcada ? '' : nombre)} aria-pressed={marcada}
                        title={marcada ? 'Quitar el filtro' : 'Ver solo este grupo'}
                        className={`text-left rounded px-1.5 py-0.5 -mx-1.5 transition ${
                          marcada ? 'bg-acento-suave text-acento-fuerte font-semibold' : 'text-texto hover:bg-superficie-2'}`}>
                  {nombre}
                </button>
                {f.areas && <div className="text-[11px] text-texto-3 truncate max-w-[16rem]">{f.areas.join(', ')}</div>}
              </td>
              <td className="py-1.5 text-right cifra">{f.personas}</td>
              <td className="py-1.5 text-right cifra">{f.adentro + f.en_descanso}</td>
              <td className="py-1.5 text-right cifra">
                {f.ausente ? <span className="text-negativo font-semibold">{f.ausente}</span> : <span className="text-texto-3">0</span>}
              </td>
              <td className="py-1.5 text-right cifra">
                {f.total_novedades
                  ? <span className="inline-flex items-center gap-1.5 text-negativo font-semibold">
                      <span className="w-2 h-2 rounded-full bg-negativo-vivo" aria-hidden="true" />{f.total_novedades}
                    </span>
                  : <span className="text-texto-3">0</span>}
              </td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

export default function ResumenGrupos({ resumen, area, lider, onArea, onLider, verLideres }) {
  return (
    <div className={`grid gap-5 ${verLideres ? 'lg:grid-cols-2' : ''}`}>
      <Seccion titulo="Por área" nota="Pulsa un área para ver solo su gente.">
        <Tabla filas={resumen.por_area} clave="area" rotulo="Área" activo={area} onElegir={onArea} />
      </Seccion>
      {verLideres && (
        <Seccion titulo="Por líder" nota="Lo que ve cada líder en las áreas que responde.">
          <Tabla filas={resumen.por_lider} clave="lider" rotulo="Líder" activo={lider} onElegir={onLider} />
        </Seccion>
      )}
    </div>
  )
}
