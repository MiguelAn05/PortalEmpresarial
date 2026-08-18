import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { obtenerPanel, listarPlantillas } from "./api"
import { ESCALA_MAX, NIVELES, formatNota, nivelCalificacion, urlPublica } from "./constants"
import FormPlantilla from "./components/FormPlantilla"
import { useAuth } from "../../core/AuthContext"
import { puedeEditar } from "../masterPlanner/constants"
import { IconoEstrella } from '../../core/components/Iconos.jsx'

/**
 * Encuestas: todas las respuestas del portal en un solo lugar.
 *
 * Junta la encuesta de satisfacción de PQRS —que vive en su propia tabla
 * desde antes de este módulo— con las que se crean aquí. Para quien consulta
 * son todas encuestas; de qué tabla salen es problema del backend.
 *
 * Los promedios, el ranking y la distribución llegan calculados del servidor.
 */
export default function Encuestas() {
  const { user } = useAuth()
  const editable = puedeEditar(user)

  const [pestana, setPestana] = useState('respuestas')
  const [origen, setOrigen] = useState('')
  const [editando, setEditando] = useState(null)   // null | 'nueva' | plantilla

  const { data: panel, isLoading } = useQuery({
    queryKey: ["enc-panel", origen],
    queryFn: () => obtenerPanel(origen ? { origen } : {}),
  })

  const { data: plantillas = [] } = useQuery({
    queryKey: ["enc-plantillas"],
    queryFn: listarPlantillas,
  })

  return (
    <div className="max-w-[1400px] mx-auto px-6 py-8 space-y-6">
      <div className="flex flex-wrap justify-between items-start gap-4">
        <div>
          <h1 className="text-3xl font-bold text-acento-fuerte">Encuestas</h1>
          <p className="text-texto-2 mt-2">
            Lo que opinan los clientes, venga de una PQRS o de un punto de venta.
          </p>
        </div>
        {editable && pestana === 'encuestas' && (
          <button
            onClick={() => setEditando('nueva')}
            className="bg-ambar hover:bg-ambar-claro text-acento-fuerte font-semibold px-5 py-2.5 rounded-xl shadow-sm transition"
          >
            + Nueva encuesta
          </button>
        )}
      </div>

      <div className="flex gap-1 border-b border-borde" role="tablist">
        {[['respuestas', 'Respuestas'], ['encuestas', 'Encuestas']].map(([id, label]) => (
          <button
            key={id}
            role="tab"
            aria-selected={pestana === id}
            onClick={() => setPestana(id)}
            className={`px-4 py-2.5 text-sm font-semibold border-b-2 -mb-px transition ${
              pestana === id
                ? 'border-acento text-acento'
                : 'border-transparent text-texto-2 hover:text-acento'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {pestana === 'respuestas' && (
        isLoading ? (
          <div className="text-center py-16 text-texto-3 text-sm">Cargando respuestas...</div>
        ) : panel && (
          <PanelRespuestas panel={panel} origen={origen} onOrigen={setOrigen} />
        )
      )}

      {pestana === 'encuestas' && (
        <ListaPlantillas
          plantillas={plantillas}
          editable={editable}
          onEditar={setEditando}
        />
      )}

      {editando && (
        <FormPlantilla
          plantilla={editando === 'nueva' ? null : editando}
          onCerrar={() => setEditando(null)}
        />
      )}
    </div>
  )
}

function PanelRespuestas({ panel, origen, onOrigen }) {
  const { resumen, por_sujeto: porSujeto, origenes, respuestas } = panel
  const nivel = nivelCalificacion(resumen.promedio)

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <label className="text-xs font-semibold text-texto-2 uppercase">Encuesta</label>
        <select
          value={origen}
          onChange={(e) => onOrigen(e.target.value)}
          className="rounded-lg border border-borde px-3 py-2 text-sm bg-white"
        >
          <option value="">Todas</option>
          {origenes.map(o => <option key={o.clave} value={o.clave}>{o.nombre}</option>)}
        </select>
      </div>

      {/* Resumen. El promedio solo no basta: dos promedios iguales pueden
          esconder repartos muy distintos, por eso van los detractores. */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl border border-borde border-t-4 border-t-acento p-4">
          <div className="text-xs font-semibold text-texto-2 uppercase tracking-wide">Calificación</div>
          <div className={`text-3xl font-bold mt-1 tabular-nums ${NIVELES[nivel].texto}`}>
            {formatNota(resumen.promedio)}
            <span className="text-base font-semibold text-texto-3"> / {resumen.escala_max}</span>
          </div>
          <div className="text-[11px] mt-0.5">
            <span className="inline-flex items-center gap-1">
              <span className="w-2 h-2 rounded-full inline-block" style={{ background: NIVELES[nivel].punto }} aria-hidden="true" />
              <span className="text-texto-2">{NIVELES[nivel].label}</span>
            </span>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-borde border-t-4 border-t-acento-fuerte p-4">
          <div className="text-xs font-semibold text-texto-2 uppercase tracking-wide">Respuestas</div>
          <div className="text-3xl font-bold mt-1 text-acento-fuerte tabular-nums">{resumen.total}</div>
          <div className="text-[11px] text-texto-3 mt-0.5">{resumen.calificadas} con calificación</div>
        </div>

        <div className="bg-white rounded-xl border border-borde border-t-4 border-t-negativo-vivo p-4">
          <div className="text-xs font-semibold text-texto-2 uppercase tracking-wide">Insatisfechos</div>
          <div className="text-3xl font-bold mt-1 text-negativo-vivo tabular-nums">{resumen.detractores}</div>
          <div className="text-[11px] text-texto-3 mt-0.5">
            {resumen.detractores_pct !== null ? `${resumen.detractores_pct}% calificó 1 o 2` : 'sin calificaciones'}
          </div>
        </div>

        <div className="bg-white rounded-xl border border-borde border-t-4 border-t-ambar p-4">
          <div className="text-xs font-semibold text-texto-2 uppercase tracking-wide">Comentarios</div>
          <div className="text-3xl font-bold mt-1 text-acento-fuerte tabular-nums">{resumen.con_comentario}</div>
          <div className="text-[11px] text-texto-3 mt-0.5">para leer</div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Distribucion resumen={resumen} />
        {porSujeto.length > 0 && <Ranking filas={porSujeto} />}
      </div>

      <ListaRespuestas respuestas={respuestas} hayMas={panel.hay_mas} />
    </div>
  )
}

/**
 * Cómo se reparten las notas. Una sola serie, un color, sin leyenda.
 *
 * Importa tanto como el promedio: un 3.0 parejo y un 3.0 de mitad cincos y
 * mitad unos son problemas distintos y el promedio los muestra iguales.
 */
function Distribucion({ resumen }) {
  const maximo = Math.max(1, ...Object.values(resumen.distribucion))

  return (
    <section className="bg-white rounded-xl border border-borde p-5">
      <h3 className="font-bold text-acento-fuerte">Cómo se reparten las notas</h3>
      <p className="text-xs text-texto-2 mb-3">
        Dos promedios iguales pueden esconder repartos muy distintos.
      </p>
      <div className="space-y-2">
        {[...Array(ESCALA_MAX)].map((_, i) => {
          const nota = ESCALA_MAX - i
          const cuantos = resumen.distribucion[nota] || 0
          const pct = (cuantos / maximo) * 100
          return (
            <div key={nota} className="grid grid-cols-[2.5rem_1fr_2.5rem] gap-2 items-center">
              <span className="cifra inline-flex items-center gap-1 text-xs text-texto-2 justify-end">{nota}<IconoEstrella tam={11} relleno className="text-ambar" /></span>
              <span className="h-4 bg-superficie-2 rounded overflow-hidden">
                <span className="block h-full bg-acento rounded" style={{ width: `${pct}%` }} />
              </span>
              <span className="text-xs font-bold tabular-nums text-right text-texto">{cuantos}</span>
            </div>
          )
        })}
      </div>
    </section>
  )
}

/** Peor calificado primero: un ranking sirve para actuar sobre la cola. */
function Ranking({ filas }) {
  return (
    <section className="bg-white rounded-xl border border-borde p-5">
      <h3 className="font-bold text-acento-fuerte">Calificación por persona o punto</h3>
      <p className="text-xs text-texto-2 mb-3">
        De menor a mayor: lo que necesita atención va arriba.
      </p>
      <ul className="divide-y divide-borde">
        {filas.map(f => {
          const nivel = nivelCalificacion(f.promedio)
          return (
            <li key={f.sujeto} className="flex items-center justify-between gap-3 py-2">
              <span className="text-sm text-texto truncate">{f.sujeto}</span>
              <span className="flex items-center gap-2 shrink-0">
                <span className="text-[11px] text-texto-3 tabular-nums">
                  {f.respuestas} resp.
                </span>
                <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-xs font-bold tabular-nums ${NIVELES[nivel].chip}`}>
                  {formatNota(f.promedio)} · {NIVELES[nivel].label}
                </span>
              </span>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

function ListaRespuestas({ respuestas, hayMas }) {
  const [abierta, setAbierta] = useState(null)

  if (respuestas.length === 0) {
    return (
      <div className="bg-white rounded-2xl border border-dashed border-borde p-16 text-center">
        <p className="text-texto-2">Todavía no hay respuestas en este filtro.</p>
      </div>
    )
  }

  return (
    <section className="bg-white rounded-xl border border-borde overflow-hidden">
      <div className="px-5 py-4 border-b border-borde">
        <h3 className="font-bold text-acento-fuerte">Respuestas</h3>
        <p className="text-xs text-texto-2">De la más reciente a la más antigua.</p>
      </div>

      <ul className="divide-y divide-borde">
        {respuestas.map(r => {
          const nivel = nivelCalificacion(r.calificacion)
          const abierto = abierta === r.id
          return (
            <li key={r.id}>
              <button
                onClick={() => setAbierta(abierto ? null : r.id)}
                aria-expanded={abierto}
                className="w-full px-5 py-3 flex items-start justify-between gap-4 text-left hover:bg-superficie-2 transition"
              >
                <span className="min-w-0">
                  <span className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-semibold text-texto">
                      {r.sujeto || r.origen_nombre}
                    </span>
                    <span className="text-[11px] text-texto-2 bg-superficie-2 border border-borde rounded-full px-2">
                      {r.origen_nombre}
                    </span>
                    {r.referencia && (
                      <span className="text-[11px] text-texto-3">{r.referencia}</span>
                    )}
                  </span>
                  {r.comentario && (
                    <span className={`block text-sm text-texto-2 mt-1 ${abierto ? '' : 'truncate'}`}>
                      «{r.comentario}»
                    </span>
                  )}
                </span>
                <span className="flex items-center gap-2 shrink-0">
                  {r.calificacion !== null && (
                    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-xs font-bold tabular-nums ${NIVELES[nivel].chip}`}>
                      {formatNota(r.calificacion)} · {NIVELES[nivel].label}
                    </span>
                  )}
                  <span className="text-[11px] text-texto-3 tabular-nums">
                    {r.respondida_en ? new Date(r.respondida_en).toLocaleDateString('es-CO') : '—'}
                  </span>
                </span>
              </button>

              {abierto && (
                <div className="px-5 pb-4 -mt-1">
                  <dl className="bg-superficie-2 border border-borde rounded-lg p-3 space-y-1.5">
                    {r.items.map((item, i) => (
                      <div key={i} className="grid grid-cols-[1fr_auto] gap-3">
                        <dt className="text-xs text-texto-2">{item.pregunta}</dt>
                        <dd className="text-xs font-semibold text-texto text-right">{item.valor}</dd>
                      </div>
                    ))}
                  </dl>
                </div>
              )}
            </li>
          )
        })}
      </ul>

      {hayMas && (
        <p className="px-5 py-3 text-xs text-texto-2 border-t border-borde">
          Se muestran las 200 más recientes. Usa el filtro de encuesta para acotar.
        </p>
      )}
    </section>
  )
}

function ListaPlantillas({ plantillas, editable, onEditar }) {
  const [copiado, setCopiado] = useState(null)

  if (plantillas.length === 0) {
    return (
      <div className="bg-white rounded-2xl border border-dashed border-borde p-16 text-center">
        <p className="text-texto-2 mb-2">Todavía no has creado ninguna encuesta.</p>
        <p className="text-sm text-texto-3">
          La de satisfacción de PQRS no aparece aquí: esa la crea el módulo de PQRS
          automáticamente al cerrar cada caso.
        </p>
      </div>
    )
  }

  const copiar = (slug) => {
    navigator.clipboard?.writeText(urlPublica(slug))
    setCopiado(slug)
    setTimeout(() => setCopiado(null), 2000)
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
      {plantillas.map(p => (
        <div key={p.id} className="bg-white rounded-xl border border-borde p-5 flex flex-col gap-3">
          <div>
            <div className="flex items-start justify-between gap-2">
              <h3 className="font-bold text-acento-fuerte">{p.nombre}</h3>
              {!p.activa && (
                <span className="text-[11px] font-semibold text-texto-2 bg-superficie-2 border border-borde rounded-full px-2 py-0.5 shrink-0">
                  Inactiva
                </span>
              )}
            </div>
            {p.descripcion && <p className="text-sm text-texto-2 mt-1">{p.descripcion}</p>}
          </div>

          <div className="text-xs text-texto-2 flex gap-3">
            <span>{p.preguntas.length} pregunta{p.preguntas.length === 1 ? '' : 's'}</span>
            <span>·</span>
            <span className="font-semibold text-texto tabular-nums">
              {p.total_respuestas} respuesta{p.total_respuestas === 1 ? '' : 's'}
            </span>
          </div>

          {/* El enlace es lo que se imprime en el QR del punto de venta */}
          <div className="bg-superficie-2 border border-borde rounded-lg px-3 py-2 flex items-center gap-2">
            <code className="text-[11px] text-texto-2 truncate flex-1">{urlPublica(p.slug)}</code>
            <button
              onClick={() => copiar(p.slug)}
              className="text-[11px] font-semibold text-acento hover:underline shrink-0"
            >
              {copiado === p.slug ? '¡Copiado!' : 'Copiar'}
            </button>
          </div>

          {editable && (
            <button
              onClick={() => onEditar(p)}
              className="text-sm font-semibold text-acento hover:underline text-left"
            >
              Editar
            </button>
          )}
        </div>
      ))}
    </div>
  )
}
