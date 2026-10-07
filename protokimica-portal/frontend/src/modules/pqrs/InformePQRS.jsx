/**
 * Informe gerencial de PQRS: una hoja para leer en pantalla y descargar en PDF.
 *
 * Los números llegan contados del servidor (`GET /pqrs/informe`); aquí solo
 * se dibujan. El PDF es la hoja de imprimir del navegador («Guardar como
 * PDF»): no hace falta instalar nada en el servidor, y lo que se descarga es
 * exactamente lo que se ve. Lo que no es informe —el menú, los controles—
 * lleva `print:hidden`.
 *
 * Gráficas a mano, sin librería, como en el resto del portal: una serie, un
 * color; la cifra al lado de cada barra y el detalle al pasar el cursor.
 */
import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import api from '../../core/api.js'
import { LOGO, NOMBRE_EMPRESA } from '../../core/marca.js'
import { mensajeDeError } from '../../core/errores.js'
import { Atenuado, Esqueleto } from '../../core/components/Cargando.jsx'
import { IconoAlerta, IconoAlDia, IconoCalendario, IconoRecibo } from '../../core/components/Iconos.jsx'
import { formatFecha, formatFechaHora } from '../masterPlanner/constants.js'
import { conOtros, estadoATiempo, marcasEje, periodosRapidos, textoVariacion } from './informe.js'

const TONO_TEXTO = { positivo: 'text-positivo', alerta: 'text-alerta', negativo: 'text-negativo', neutro: 'text-texto-2' }
const TONO_PUNTO = { positivo: 'bg-positivo-vivo', alerta: 'bg-ambar', negativo: 'bg-negativo-vivo', neutro: 'bg-texto-3' }

// ── Piezas ──────────────────────────────────────────────────────────────

function Seccion({ titulo, nota, children, className = '' }) {
  return (
    <section className={`bg-white rounded-xl border border-borde p-5 evitar-corte print:shadow-none ${className}`}>
      <h3 className="font-semibold text-acento-fuerte text-sm">{titulo}</h3>
      {nota && <p className="text-xs text-texto-2 mt-0.5">{nota}</p>}
      <div className="mt-4">{children}</div>
    </section>
  )
}

function Tarjeta({ titulo, valor, detalle, tono }) {
  return (
    <div className="bg-white rounded-xl border border-borde p-4 evitar-corte">
      <div className="text-xs font-semibold text-texto-2 uppercase tracking-wide">{titulo}</div>
      <div className="text-3xl font-bold text-texto mt-1">{valor}</div>
      {detalle && (
        <div className={`text-xs mt-1 flex items-center gap-1.5 ${TONO_TEXTO[tono] || 'text-texto-2'}`}>
          {tono && tono !== 'neutro' && <span className={`w-2 h-2 rounded-full flex-shrink-0 ${TONO_PUNTO[tono]}`} />}
          <span>{detalle}</span>
        </div>
      )}
    </div>
  )
}

/**
 * Barras horizontales de UNA serie. La barra más larga ocupa todo el ancho;
 * la cifra y el porcentaje van al final de cada una, y al pasar el cursor se
 * dice sobre qué total es el porcentaje.
 */
function Barras({ filas, sobre = 'del total', vacio = 'Sin datos en el periodo.', max = 8 }) {
  const visibles = conOtros(filas, max)
  if (!visibles.length) return <p className="text-sm text-texto-2">{vacio}</p>
  const mayor = Math.max(...visibles.map(f => f.n), 1)
  return (
    <ul className="space-y-2.5">
      {visibles.map(f => (
        <li key={f.clave} className="group relative grid grid-cols-[minmax(0,11rem)_1fr_auto] items-center gap-3 text-sm">
          <span className="truncate text-texto" title={f.etiqueta}>{f.etiqueta}</span>
          <span className="h-2.5 rounded-full bg-superficie-2 overflow-hidden">
            <span
              className="block h-full rounded-full bg-acento group-hover:bg-acento-fuerte transition-colors"
              style={{ width: `${(f.n / mayor) * 100}%` }}
            />
          </span>
          <span className="cifra text-texto font-semibold text-right min-w-[5.5rem]">
            {f.n} <span className="text-texto-2 font-normal">· {f.pct ?? 0}%</span>
          </span>
          <span role="tooltip" className="pointer-events-none absolute left-1/3 -top-8 z-10 hidden group-hover:block print:hidden
                                          whitespace-nowrap rounded-md bg-texto text-white text-xs px-2 py-1 shadow-md">
            {f.etiqueta}: {f.n} PQRS · {f.pct ?? 0}% {sobre}
          </span>
        </li>
      ))}
    </ul>
  )
}

/** Columnas de la tendencia: una serie, eje con tres marcas y detalle al pasar el cursor. */
function Tendencia({ tendencia }) {
  const puntos = tendencia?.puntos || []
  const mayor = Math.max(...puntos.map(p => p.n), 0)
  const marcas = marcasEje(mayor)
  const tope = marcas[marcas.length - 1] || 1
  // En un mes, rotular cada cinco días; por meses, todos.
  const rotular = (i) => tendencia?.escala === 'mes' || i === 0 || (i + 1) % 5 === 0
  if (!puntos.length) return null
  return (
    <div className="flex gap-2">
      <div className="relative w-6 h-40 text-[11px] text-texto-3 cifra">
        {marcas.map(m => (
          <span key={m} className="absolute right-0 -translate-y-1/2" style={{ bottom: `${(m / tope) * 100}%` }}>{m}</span>
        ))}
      </div>
      <div className="flex-1 min-w-0">
        <div className="relative h-40">
          {marcas.map(m => (
            <div key={m} className="absolute inset-x-0 border-t border-borde" style={{ bottom: `${(m / tope) * 100}%` }} />
          ))}
          <div className="absolute inset-0 flex items-end gap-[2px]">
            {puntos.map(p => (
              <div key={p.clave} className="group relative flex-1 h-full flex items-end">
                <div
                  className="w-full rounded-t bg-acento group-hover:bg-acento-fuerte transition-colors"
                  style={{ height: `${(p.n / tope) * 100}%` }}
                />
                <span role="tooltip" className="pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 mb-1 z-10 hidden group-hover:block print:hidden
                                                whitespace-nowrap rounded-md bg-texto text-white text-xs px-2 py-1 shadow-md">
                  {tendencia.escala === 'dia' ? `Día ${p.etiqueta}` : p.etiqueta}: {p.n} PQRS
                </span>
              </div>
            ))}
          </div>
        </div>
        <div className="flex gap-[2px] mt-1.5 text-[11px] text-texto-3 cifra">
          {puntos.map((p, i) => (
            <span key={p.clave} className="flex-1 text-center">{rotular(i) ? p.etiqueta : ''}</span>
          ))}
        </div>
      </div>
    </div>
  )
}

function TablaTiempos({ filas }) {
  if (!filas?.length) {
    return <p className="text-sm text-texto-2">Todavía no hay tramos terminados en el periodo: se cuentan desde que el caso sale del área.</p>
  }
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-xs text-texto-2 uppercase tracking-wide text-left border-b border-borde">
          <th className="py-2 font-semibold">Área</th>
          <th className="py-2 font-semibold text-right">Veces que la tuvo</th>
          <th className="py-2 font-semibold text-right">Promedio</th>
          <th className="py-2 font-semibold text-right">Pasadas de 3 días</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-borde">
        {filas.map(f => (
          <tr key={f.area}>
            <td className="py-2 text-texto">{f.area}</td>
            <td className="py-2 text-right cifra">{f.tramos}</td>
            <td className="py-2 text-right cifra">{f.promedio_dias} días hábiles</td>
            <td className="py-2 text-right cifra">
              {f.excedidos ? (
                <span className="inline-flex items-center gap-1.5 text-negativo font-semibold">
                  <span className="w-2 h-2 rounded-full bg-negativo-vivo" />{f.excedidos} ({f.pct_excedidos}%)
                </span>
              ) : (
                <span className="inline-flex items-center gap-1.5 text-positivo">
                  <span className="w-2 h-2 rounded-full bg-positivo-vivo" />Ninguna
                </span>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

// ── La hoja ─────────────────────────────────────────────────────────────

function Hoja({ inf, alcance }) {
  const r = inf.resumen
  const variacion = textoVariacion(r, inf.periodo.anterior.etiqueta)
  const aTiempo = estadoATiempo(r.pct_a_tiempo)

  return (
    <div className="space-y-5">
      {/* Encabezado: es lo primero que se lee en el PDF. */}
      <div className="bg-white rounded-xl border border-borde p-5 flex items-center justify-between gap-4 evitar-corte">
        <div>
          <div className="text-xs font-semibold text-texto-2 uppercase tracking-wide">Informe de PQRS</div>
          <h2 className="text-2xl font-bold text-acento-fuerte mt-0.5">{inf.periodo.etiqueta}</h2>
          <p className="text-xs text-texto-2 mt-1">
            {alcance} · Radicadas entre el {formatFecha(inf.periodo.desde)} y el {formatFecha(inf.periodo.hasta)} ·
            Generado el {formatFechaHora(inf.periodo.generado)}
          </p>
        </div>
        <img src={LOGO} alt={NOMBRE_EMPRESA} className="h-10 w-auto object-contain flex-shrink-0" />
      </div>

      {/* Lo que se pregunta primero */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 print:grid-cols-4">
        <Tarjeta titulo="Radicadas" valor={r.total}
                 detalle={variacion?.texto || 'Sin periodo anterior para comparar'} tono={variacion?.tono} />
        <Tarjeta titulo="Respondidas a tiempo" valor={r.pct_a_tiempo == null ? '—' : `${r.pct_a_tiempo}%`}
                 detalle={r.con_plazo ? `${aTiempo.etiqueta} · ${r.a_tiempo} de ${r.con_plazo}` : aTiempo.etiqueta}
                 tono={aTiempo.tono} />
        <Tarjeta titulo="Tiempo de respuesta" valor={r.dias_respuesta_promedio == null ? '—' : r.dias_respuesta_promedio}
                 detalle={r.dias_respuesta_promedio == null ? 'Ninguna respondida todavía' : 'días hábiles en promedio'} />
        <Tarjeta titulo="Abiertas hoy" valor={r.abiertas}
                 detalle={r.vencidas ? `${r.vencidas} con el plazo legal vencido` : 'Ninguna vencida'}
                 tono={r.vencidas ? 'negativo' : 'positivo'} />
      </div>

      <Seccion titulo="Cómo entraron en el periodo"
               nota={inf.tendencia.escala === 'dia' ? 'PQRS radicadas por día.' : 'PQRS radicadas por mes.'}>
        <Tendencia tendencia={inf.tendencia} />
      </Seccion>

      <div className="grid lg:grid-cols-2 gap-5 print:grid-cols-2">
        <Seccion titulo="Por tipo"><Barras filas={inf.por_tipo} /></Seccion>
        <Seccion titulo="Estado actual"><Barras filas={inf.por_estado} /></Seccion>
      </div>

      <Seccion
        titulo="Asociado a: por qué llegan"
        nota={r.total
          ? `Sobre las ${r.con_causa} que ya tienen causa (${r.pct_con_causa ?? 0}%).${r.sin_causa ? ` ${r.sin_causa} están sin clasificar.` : ''}`
          : null}
      >
        <div className="grid lg:grid-cols-2 gap-6 print:grid-cols-2">
          <div>
            <div className="text-xs font-semibold text-texto-2 uppercase tracking-wide mb-3">Causa</div>
            <Barras filas={inf.por_asociado} sobre="de las clasificadas"
                    vacio="Ninguna clasificada todavía. Se marca en «Causa de la PQRS»." />
          </div>
          <div>
            <div className="text-xs font-semibold text-texto-2 uppercase tracking-wide mb-3">Área causante</div>
            <Barras filas={inf.por_area_causante} sobre="de las que tienen área causante"
                    vacio="Ninguna tiene área causante todavía." />
          </div>
        </div>
      </Seccion>

      <div className="grid lg:grid-cols-2 gap-5 print:grid-cols-2">
        <Seccion titulo="Por dónde entran" nota="Canal de atención: punto de venta, venta institucional, WhatsApp…">
          <Barras filas={inf.por_canal} />
        </Seccion>
        <Seccion titulo="Quién la radica" nota="El cliente por el formulario web, o el área de quien la registró por dentro.">
          <Barras filas={inf.por_origen} />
        </Seccion>
      </div>

      <div className="grid lg:grid-cols-2 gap-5 print:grid-cols-2">
        <Seccion titulo="Productos con más PQRS"
                 nota={inf.productos_distintos ? `${inf.productos_distintos} productos distintos en el periodo.` : null}>
          <Barras filas={inf.top_productos} sobre="de los productos reportados"
                  vacio="Ninguna PQRS del periodo trae producto." />
        </Seccion>
        <Seccion titulo="Dónde están las abiertas" nota="Área que tiene cada PQRS abierta hoy.">
          <Barras filas={inf.por_area_actual} sobre="de las abiertas" vacio="No hay PQRS abiertas del periodo." />
        </Seccion>
      </div>

      <Seccion titulo="Cuánto se demora cada área"
               nota="Cada vez que un área tuvo un caso y lo soltó. La regla es máximo 3 días hábiles por área.">
        <TablaTiempos filas={inf.tiempo_por_area} />
      </Seccion>

      <p className="text-center text-xs text-texto-3 pt-2">
        {NOMBRE_EMPRESA} · Portal de gestión · Informe generado el {formatFechaHora(inf.periodo.generado)}
      </p>
    </div>
  )
}

// ── Pantalla ────────────────────────────────────────────────────────────

export default function InformePQRS() {
  const navigate = useNavigate()
  const rapidos = useMemo(() => periodosRapidos(), [])
  const [periodo, setPeriodo] = useState({ desde: rapidos[0].desde, hasta: rapidos[0].hasta })

  const { data: inf, isLoading, isError, error, isFetching } = useQuery({
    queryKey: ['pqrs', 'informe', periodo.desde, periodo.hasta],
    queryFn: () => api.get('/pqrs/informe', { params: periodo }).then(r => r.data),
    placeholderData: (anterior) => anterior,
    enabled: Boolean(periodo.desde && periodo.hasta),
  })

  const { data: visibilidad } = useQuery({
    queryKey: ['pqrs-visibilidad'],
    queryFn: () => api.get('/pqrs/visibilidad').then(r => r.data),
  })
  // Un informe acotado que no lo dice se lee como «la empresa entera».
  const alcance = visibilidad?.restringida
    ? `Solo ${visibilidad.puntos.map(p => p.canal).join(', ')}`
    : 'Toda la empresa'

  const activo = rapidos.find(p => p.desde === periodo.desde && p.hasta === periodo.hasta)?.clave

  return (
    <div className="max-w-5xl mx-auto">
      <div className="print:hidden">
        <button onClick={() => navigate('/pqrs')}
                className="flex items-center gap-2 text-sm text-texto-2 hover:text-acento-fuerte mb-5 transition">
          ← Volver a PQRS
        </button>

        <div className="flex flex-wrap items-start justify-between gap-4 mb-4">
          <div>
            <h1 className="text-xl font-bold text-acento-fuerte">Informe de PQRS</h1>
            <p className="text-sm text-texto-2 mt-1">
              Cuántas entraron, por qué, por dónde y cómo se respondieron. Se descarga en PDF tal como se ve.
            </p>
          </div>
          <button
            onClick={() => window.print()}
            disabled={!inf}
            className="flex items-center gap-2 bg-acento-fuerte hover:bg-acento text-white font-bold px-4 py-2.5 rounded-lg text-sm transition disabled:opacity-50"
          >
            <IconoRecibo tam={16} /> Descargar PDF
          </button>
        </div>

        {/* El periodo va en una sola fila, arriba de todo lo que filtra. */}
        <div className="bg-white rounded-xl border border-borde p-3 mb-5 flex flex-wrap items-center gap-2">
          <IconoCalendario tam={16} className="text-texto-2 ml-1" />
          {rapidos.map(p => (
            <button key={p.clave} onClick={() => setPeriodo({ desde: p.desde, hasta: p.hasta })}
                    className={`px-3 py-1.5 rounded-lg text-sm font-semibold transition ${
                      activo === p.clave ? 'bg-acento-suave text-acento-fuerte' : 'text-texto-2 hover:bg-superficie-2'
                    }`}>
              {p.etiqueta}
            </button>
          ))}
          <span className="mx-1 h-5 w-px bg-borde" />
          <label className="text-xs text-texto-2" htmlFor="informe-desde">Desde</label>
          <input id="informe-desde" type="date" value={periodo.desde} max={periodo.hasta}
                 onChange={e => setPeriodo(p => ({ ...p, desde: e.target.value }))}
                 className="px-2 py-1.5 rounded-lg border border-borde text-sm" />
          <label className="text-xs text-texto-2" htmlFor="informe-hasta">Hasta</label>
          <input id="informe-hasta" type="date" value={periodo.hasta} min={periodo.desde}
                 onChange={e => setPeriodo(p => ({ ...p, hasta: e.target.value }))}
                 className="px-2 py-1.5 rounded-lg border border-borde text-sm" />
        </div>
      </div>

      {isError && !inf && (
        <div role="alert" className="flex items-center gap-2 bg-negativo-bg text-negativo text-sm rounded-xl p-4">
          <IconoAlerta tam={16} /> {mensajeDeError(error, 'No se pudo generar el informe. Intenta de nuevo.')}
        </div>
      )}
      {isError && inf && (
        <p role="alert" className="text-sm text-negativo mb-3 print:hidden">
          {mensajeDeError(error, 'No se pudo cambiar el periodo.')} Se muestra el anterior.
        </p>
      )}

      {isLoading && !inf && (
        <div className="space-y-5">
          <Esqueleto alto="h-24" className="rounded-xl" />
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            {[0, 1, 2, 3].map(i => <Esqueleto key={i} alto="h-28" className="rounded-xl" />)}
          </div>
          <Esqueleto alto="h-56" className="rounded-xl" />
        </div>
      )}

      {inf && (
        <Atenuado cargando={isFetching}>
          {inf.resumen.total === 0 ? (
            <div className="bg-white rounded-xl border border-borde p-10 text-center">
              <IconoAlDia tam={26} className="mx-auto mb-3 text-positivo" />
              <p className="text-sm font-semibold text-texto">No entró ninguna PQRS en {inf.periodo.etiqueta.toLowerCase()}.</p>
              <p className="text-xs text-texto-2 mt-1">Prueba con otro periodo.</p>
            </div>
          ) : (
            <Hoja inf={inf} alcance={alcance} />
          )}
        </Atenuado>
      )}
    </div>
  )
}
