/**
 * La portada gerencial: el estado de la empresa en una pantalla.
 *
 * Responde tres preguntas y nada más: ¿está completa la lectura del mes?,
 * ¿qué se salió de meta o empeoró?, ¿qué área está peor. El mes, el alcance
 * y el buscador viven arriba, en `BarraContexto`, y los cinco conteos en
 * `KpisPeriodo`: los dos gobiernan las tres pestañas, así que cambiarse de
 * pestaña ya no cambia lo que se está mirando.
 *
 * La matriz del año se fue a su propia pestaña. Son casi novecientas celdas
 * y empujaban fuera de pantalla justamente lo que alguien viene a ver aquí.
 *
 * Todo llega calculado del servidor —conteos, movimientos, cumplimiento por
 * área—, que es lo mismo que alimenta el tablero. Si aquí se recalculara
 * algo, tarde o temprano las dos pantallas mostrarían números distintos del
 * mismo mes.
 *
 * Es una vista de LECTURA: registrar y editar siguen viviendo en el tablero.
 */
import { IconoAlerta, IconoCerrar, IconoReloj } from '../../../core/components/Iconos.jsx'
import { SEMAFOROS, coincideBusqueda, formatValor } from '../constants'

export default function ComoVamos({
  datos, periodo, filtro, onFiltro, busqueda, onVerIndicador,
}) {
  const { resumen, movimientos, por_area: porArea, matriz, pendientes } = datos

  // El filtro sale de los KPI de arriba: de «hay 3 en rojo» a «estos son».
  const delFiltro = filtro
    ? matriz.filter(f => estadoDelMes(f, periodo.mes) === filtro && coincideBusqueda(f, busqueda))
    : []

  return (
    <div className="space-y-4">
      <LecturaIncompleta
        pendientes={pendientes}
        medidos={resumen.verde + resumen.amarillo + resumen.rojo}
        total={resumen.total}
        cumplimiento={resumen.cumplimiento_pct}
        onVer={onVerIndicador}
      />

      {filtro && (
        <ListaFiltrada
          estado={filtro}
          indicadores={delFiltro}
          onCerrar={() => onFiltro(null)}
          onVer={onVerIndicador}
        />
      )}

      <div className="grid grid-cols-1 lg:grid-cols-[1.15fr_1fr] gap-4">
        <RequiereAtencion
          movimientos={movimientos.filter(m => coincideBusqueda(m, busqueda))}
          onVer={onVerIndicador}
        />
        <PorArea areas={porArea} />
      </div>
    </div>
  )
}

/** El semáforo del mes que se está viendo, leído de la matriz ya calculada. */
function estadoDelMes(fila, mes) {
  const punto = fila.meses.find(m => m.mes === mes)
  return punto ? punto.semaforo : 'sin_datos'
}

/**
 * Cuánto de la lectura del mes falta, y de quién es.
 *
 * Va arriba de todo y no como una nota al pie porque **cambia cómo se lee el
 * número principal**: un 92,9% calculado sobre 14 de 73 indicadores no es el
 * cumplimiento de la empresa, es el de los que alcanzaron a reportar. Sin
 * decirlo, la cifra promete más de lo que sabe.
 *
 * Los responsables van agrupados con cuántos le faltan a cada uno: un aviso
 * que dice «faltan 59» no se atiende, y uno que dice «a Hoover le faltan 6»
 * sí tiene a quién preguntarle.
 */
function LecturaIncompleta({ pendientes, medidos, total, cumplimiento, onVer }) {
  if (!pendientes || pendientes.length === 0) return null

  const porPersona = agruparPorResponsable(pendientes)

  return (
    <section className="bg-superficie border border-borde border-l-[3px] border-l-ambar
                        rounded-xl shadow-sm px-4 py-3.5">
      <div className="flex flex-wrap items-start gap-3">
        <span className="w-8 h-8 rounded-full bg-alerta-bg text-alerta grid place-items-center shrink-0"
              aria-hidden="true">
          <IconoReloj tam={16} />
        </span>
        <div className="min-w-0">
          <h2 className="text-sm font-semibold text-texto">
            La lectura de este mes está incompleta
          </h2>
          <p className="text-xs text-texto-3 mt-0.5 cifra">
            {pendientes.length} de {total} sin registrar
            {cumplimiento !== null && medidos > 0 && (
              <> · el {cumplimiento}% se calcula solo sobre los {medidos} que sí se midieron</>
            )}
          </p>
        </div>
      </div>

      <ul className="flex flex-wrap gap-1.5 mt-3">
        {porPersona.map(({ responsable, fichas }) => (
          <li key={responsable}>
            <details className="group">
              <summary className="list-none cursor-pointer inline-flex items-center gap-1.5
                                  px-2.5 py-1 rounded-md bg-superficie-2 border border-borde
                                  text-[11.5px] text-texto-2 hover:border-borde-fuerte transition">
                <span className="w-5 h-5 rounded-full bg-acento-suave text-acento grid place-items-center
                                 text-[9.5px] font-semibold shrink-0" aria-hidden="true">
                  {iniciales(responsable)}
                </span>
                {responsable}
                <span className="cifra font-semibold text-texto">{fichas.length}</span>
              </summary>
              <ul className="mt-1.5 ml-1 space-y-0.5">
                {fichas.map(f => (
                  <li key={f.id}>
                    <button
                      type="button"
                      onClick={() => onVer?.(f.id)}
                      className="text-[11.5px] text-acento hover:underline text-left"
                    >
                      {f.nombre}
                    </button>
                  </li>
                ))}
              </ul>
            </details>
          </li>
        ))}
      </ul>
    </section>
  )
}

/**
 * Quién debe registrar qué.
 *
 * Los que no tienen responsable van en su propio grupo y NUNCA se descartan:
 * un indicador que nadie reclama es el que con más seguridad no se va a
 * registrar, y esconderlo lo vuelve invisible justo por eso.
 */
function agruparPorResponsable(pendientes) {
  const mapa = new Map()
  for (const ficha of pendientes) {
    const clave = ficha.responsable_nombre || 'Sin responsable'
    if (!mapa.has(clave)) mapa.set(clave, [])
    mapa.get(clave).push(ficha)
  }
  return [...mapa.entries()]
    .map(([responsable, fichas]) => ({ responsable, fichas }))
    // Quien más debe, primero; «Sin responsable» al final, que no es persona.
    .sort((a, b) => {
      if (a.responsable === 'Sin responsable') return 1
      if (b.responsable === 'Sin responsable') return -1
      return b.fichas.length - a.fichas.length
    })
}

function iniciales(nombre) {
  if (nombre === 'Sin responsable') return '—'
  return nombre.split(/\s+/).slice(0, 2).map(p => p[0]).join('').toUpperCase()
}

/**
 * Lo que se salió de meta o empeoró contra el mes pasado.
 *
 * Es la sección que hace corto el tablero: nadie necesita revisar setenta
 * indicadores, necesita ver los tres que se movieron. Lo que sigue igual no
 * ocupa espacio. El orden —lo que empeoró primero, y dentro de eso lo más
 * grave— lo decide el servidor.
 */
function RequiereAtencion({ movimientos, onVer }) {
  const VISIBLES = 6
  const mostrados = movimientos.slice(0, VISIBLES)

  return (
    <section className="bg-superficie rounded-xl border border-borde shadow-sm overflow-hidden">
      <header className="px-5 py-3.5 border-b border-borde">
        <h2 className="text-sm font-semibold text-texto">Requiere atención</h2>
        <p className="text-xs text-texto-3 mt-0.5">
          Lo que cambió de estado contra el mes pasado. Lo demás sigue igual.
        </p>
      </header>

      {movimientos.length === 0 ? (
        <p className="px-5 py-8 text-sm text-texto-2 text-center">
          Ningún indicador cambió de estado este mes.
        </p>
      ) : (
        <ul className="divide-y divide-borde">
          {mostrados.map(m => (
            <li key={m.id}>
              <button
                type="button"
                onClick={() => onVer?.(m.id)}
                className="w-full flex items-center gap-3 px-5 py-2.5 text-left
                           hover:bg-superficie-2 transition"
              >
                <span className="min-w-0 flex-1">
                  <span className="block text-[13px] font-medium text-texto leading-snug">
                    {m.nombre}
                  </span>
                  <span className="block text-[11.5px] text-texto-3 mt-0.5 truncate">
                    {m.area || 'Sin área'}
                  </span>
                </span>

                <span className="text-right shrink-0">
                  <span className="block text-[13px] font-semibold text-texto cifra">
                    {formatValor(m.valor, m.unidad)}
                  </span>
                  <span className="block text-[11px] text-texto-3 cifra">
                    desde {formatValor(m.valor_anterior, m.unidad)}
                  </span>
                </span>

                <Chip estado={m.semaforo} empeoro={m.empeoro} />
              </button>
            </li>
          ))}
        </ul>
      )}

      {movimientos.length > VISIBLES && (
        <p className="px-5 py-2.5 border-t border-borde text-[11.5px] text-texto-3">
          Y {movimientos.length - VISIBLES} más. Están todos en la pestaña «Tablero».
        </p>
      )}
    </section>
  )
}

/**
 * El estado, con forma además de color.
 *
 * El ámbar de la marca no alcanza el contraste mínimo sobre blanco, así que
 * el color nunca va solo: cada chip lleva su palabra y su icono, que es lo
 * único que sobrevive a una fotocopia en gris.
 */
function Chip({ estado, empeoro }) {
  const cfg = SEMAFOROS[estado]
  const Icono = empeoro ? IconoCerrar : IconoAlerta

  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md border
                      text-[11px] font-semibold shrink-0 ${cfg.chip}`}>
      <Icono tam={11} />
      {empeoro ? 'Empeoró' : 'Mejoró'}
    </span>
  )
}

/**
 * Cumplimiento por área, en barra apilada.
 *
 * El porcentaje solo no basta: un área al 80% con algo en rojo pesa más que
 * una al 75% con todo en amarillo. La barra muestra la composición —cuánto
 * cumple, cuánto no, cuánto no se midió— y el número va al lado, nunca solo.
 *
 * Las áreas sin un solo dato se muestran con la barra vacía en vez de
 * esconderse: que un área no haya reportado nada es información.
 */
function PorArea({ areas }) {
  if (areas.length === 0) {
    return (
      <section className="bg-superficie rounded-xl border border-borde shadow-sm p-5">
        <h2 className="text-sm font-semibold text-texto">Cumplimiento por área</h2>
        <p className="text-sm text-texto-2 mt-3">
          Todavía no hay áreas con indicadores medidos este mes.
        </p>
      </section>
    )
  }

  const sinDatos = areas.filter(a => a.cumplimiento_pct === null).length

  return (
    <section className="bg-superficie rounded-xl border border-borde shadow-sm overflow-hidden">
      <header className="px-5 py-3.5 border-b border-borde">
        <h2 className="text-sm font-semibold text-texto">Cumplimiento por área</h2>
        <p className="text-xs text-texto-3 mt-0.5">
          Las áreas con algo en rojo van primero.
        </p>
      </header>

      <div className="py-2">
        {areas.map(a => {
          const juzgados = a.verde + a.amarillo + a.rojo
          const parte = (n) => (juzgados ? (n / juzgados) * 100 : 0)
          return (
            <div key={a.area}
                 className="grid grid-cols-[7.5rem_1fr_2.75rem] items-center gap-3 px-5 py-1.5">
              <span className="text-xs text-texto-2 text-right truncate" title={a.area}>
                {a.area}
              </span>
              <span className="h-[18px] rounded-md bg-superficie-2 overflow-hidden flex">
                <i className="h-full bg-positivo-vivo" style={{ width: `${parte(a.verde)}%` }} />
                <i className="h-full bg-ambar" style={{ width: `${parte(a.amarillo)}%` }} />
                <i className="h-full bg-negativo-vivo" style={{ width: `${parte(a.rojo)}%` }} />
              </span>
              <span className={`text-xs text-right cifra ${
                a.cumplimiento_pct === null ? 'text-texto-3' : 'font-semibold text-texto'
              }`}>
                {a.cumplimiento_pct === null ? '—' : `${Math.round(a.cumplimiento_pct)}%`}
              </span>
            </div>
          )
        })}
      </div>

      <div className="flex flex-wrap gap-x-4 gap-y-1 px-5 py-3 border-t border-borde
                      text-[11px] text-texto-3">
        {[['verde', 'bg-positivo-vivo'], ['amarillo', 'bg-ambar'], ['rojo', 'bg-negativo-vivo']].map(
          ([estado, fondo]) => (
            <span key={estado} className="inline-flex items-center gap-1.5">
              <i className={`inline-block w-2.5 h-2.5 rounded-sm ${fondo}`} aria-hidden="true" />
              {SEMAFOROS[estado].label}
            </span>
          ),
        )}
        {sinDatos > 0 && (
          <span className="ml-auto cifra">{sinDatos} sin datos este mes</span>
        )}
      </div>
    </section>
  )
}

/** De la cifra al detalle: «hay 3 en rojo» → «estos son». */
function ListaFiltrada({ estado, indicadores, onCerrar, onVer }) {
  const cfg = SEMAFOROS[estado]

  return (
    <section className="bg-superficie rounded-xl border border-borde shadow-sm overflow-hidden">
      <header className="flex items-center justify-between gap-3 px-5 py-3.5 border-b border-borde">
        <h2 className="text-sm font-semibold text-texto">{cfg.label} este mes</h2>
        <button
          type="button"
          onClick={onCerrar}
          className="text-xs font-semibold text-texto-2 hover:text-texto inline-flex items-center gap-1.5"
        >
          <IconoCerrar tam={13} /> Cerrar
        </button>
      </header>

      {indicadores.length === 0 ? (
        <p className="px-5 py-8 text-sm text-texto-2 text-center">
          Ninguno en este estado.
        </p>
      ) : (
        <ul className="divide-y divide-borde">
          {indicadores.map(ind => (
            <li key={ind.id}>
              <button
                type="button"
                onClick={() => onVer?.(ind.id)}
                className="w-full flex items-center justify-between gap-3 px-5 py-2.5
                           text-left hover:bg-superficie-2 transition"
              >
                <span className="min-w-0">
                  <span className="block text-[13px] font-medium text-texto">{ind.nombre}</span>
                  <span className="block text-[11.5px] text-texto-3">
                    {ind.area || 'Sin área'}
                    {ind.responsable_nombre && ` · ${ind.responsable_nombre}`}
                  </span>
                </span>
                <span className={`inline-flex items-center px-2 py-0.5 rounded-md border
                                  text-[11px] font-semibold shrink-0 ${cfg.chip}`}>
                  {cfg.label}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
