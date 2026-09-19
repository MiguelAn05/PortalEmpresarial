/**
 * El estado del mes en cinco cifras, con UNA claramente principal.
 *
 * Dos cosas cambiaron respecto de lo que había:
 *
 * 1. **Estaban duplicadas.** Cinco tarjetas en «Cómo vamos» y otras cinco
 *    casi iguales en el tablero, con rótulos distintos para lo mismo («Sin
 *    reportar» contra «Falta registrar»). Dos versiones del mismo mes en una
 *    pantalla acaban discutiéndose entre sí. Ahora son estas, una sola vez,
 *    arriba de las pestañas.
 *
 * 2. **Todas pesaban igual**: cinco tarjetas idénticas con un borde de color
 *    distinto cada una. Cinco colores a la vez no son jerarquía, son un
 *    tablero de bingo, y la pregunta que trae a alguien aquí —«¿cómo vamos?»—
 *    no tenía dónde mirarse. El cumplimiento ocupa ahora el doble de ancho,
 *    lleva su barra hacia la meta y su delta contra el mes pasado; el resto
 *    son conteos que filtran.
 *
 * El delta lo calcula el SERVIDOR (`resumen.delta_cumplimiento`). Restar dos
 * porcentajes aquí es fácil y por eso mismo es la clase de cuenta que un día
 * deja de coincidir con el reporte.
 */
import { IconoFlecha } from '../../../core/components/Iconos.jsx'
import { SEMAFOROS, leerDelta } from '../constants'

// Los conteos que se pueden usar como filtro, en orden de gravedad: lo que
// arde primero. «Sin registrar» va al final pero no es un incumplimiento —
// es un problema distinto y por eso no baja el cumplimiento.
const CONTEOS = [
  { clave: 'verde', rotulo: 'Cumplen' },
  { clave: 'amarillo', rotulo: 'En alerta' },
  { clave: 'rojo', rotulo: 'No cumplen' },
  { clave: 'sin_datos', rotulo: 'Sin registrar' },
]

export default function KpisPeriodo({ resumen, filtro, onFiltro }) {
  const juzgados = resumen.verde + resumen.amarillo + resumen.rojo
  const pct = resumen.cumplimiento_pct
  const delta = leerDelta(resumen.delta_cumplimiento, resumen.mes_anterior_nombre)

  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-[1.6fr_repeat(4,1fr)]">

      {/* El único elemento primario de la pantalla. */}
      <article className="bg-superficie rounded-xl border border-borde shadow-sm p-4 sm:p-5">
        <p className="etiqueta">Cumplimiento del mes</p>
        <p className="text-4xl font-semibold text-acento-fuerte mt-2 cifra leading-none">
          {pct !== null ? `${pct}%` : '—'}
        </p>

        {/* La barra nunca va sin su cifra, ni la cifra sin la barra: una
            sola de las dos obliga a estimar lo que la otra ya dice. */}
        <div className="h-1.5 rounded-full bg-superficie-2 overflow-hidden mt-3">
          <span
            className="block h-full rounded-full bg-positivo-vivo transition-[width] duration-300 ease-suave"
            style={{ width: `${pct ?? 0}%` }}
          />
        </div>

        <p className="text-xs text-texto-3 mt-2.5">
          {juzgados > 0
            ? <>{resumen.verde} de {juzgados} con meta</>
            : 'Todavía no hay indicadores con meta medidos'}
          {delta && (
            <>
              {' · '}
              <span className={`font-semibold ${delta.tono}`}>
                {delta.flecha && (
                  <IconoFlecha
                    tam={11}
                    className={`inline -mt-0.5 mr-0.5 ${
                      delta.flecha === 'sube' ? '-rotate-90' : 'rotate-90'
                    }`}
                  />
                )}
                {delta.texto}
              </span>
            </>
          )}
        </p>
      </article>

      {CONTEOS.map(({ clave, rotulo }) => {
        const activo = filtro === clave
        const cuantos = resumen[clave]
        return (
          <button
            key={clave}
            type="button"
            onClick={() => onFiltro(activo ? null : clave)}
            aria-pressed={activo}
            className={`bg-superficie rounded-xl border p-4 text-left shadow-sm
              transition duration-150 ease-suave hover:shadow-md hover:-translate-y-px
              ${activo ? 'border-acento ring-1 ring-acento' : 'border-borde'}`}
          >
            {/* El punto de color NUNCA va solo: el ámbar de la marca no llega
                al contraste mínimo sobre blanco, así que el rótulo es el que
                de verdad dice el estado. */}
            <p className="etiqueta flex items-center gap-2">
              <span
                className="w-1.5 h-1.5 rounded-full shrink-0"
                style={{ background: SEMAFOROS[clave].punto }}
                aria-hidden="true"
              />
              {rotulo}
            </p>
            <p className="text-2xl font-semibold text-texto mt-2 cifra leading-none">{cuantos}</p>
            <p className="text-[11px] text-texto-3 mt-2">
              {cuantos === 0
                ? SIN_NINGUNO[clave]
                : activo ? 'Ocultar la lista' : 'Ver cuáles'}
            </p>
          </button>
        )
      })}
    </div>
  )
}

/**
 * Un cero también necesita contexto.
 *
 * «No cumplen: 0» sin más obliga a preguntar si es buena noticia o si es que
 * nadie midió. Cada estado dice qué significa no tener ninguno.
 */
const SIN_NINGUNO = {
  verde: 'Ninguno en meta todavía',
  amarillo: 'Ninguno al límite',
  rojo: 'Ninguno fuera de meta',
  sin_datos: 'El mes está completo',
}
