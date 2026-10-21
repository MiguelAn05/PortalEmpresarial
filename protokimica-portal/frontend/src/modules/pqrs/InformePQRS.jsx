/**
 * Informe gerencial de PQRS: una hoja para leer en pantalla y descargar en PDF.
 *
 * Los números llegan contados del servidor (`GET /pqrs/informe`); aquí solo
 * se dibujan. El PDF es la hoja de imprimir del navegador («Guardar como
 * PDF»): no hace falta instalar nada en el servidor, y lo que se descarga es
 * exactamente lo que se ve. Lo que no es informe —el menú, los controles—
 * lleva `print:hidden`.
 *
 * Las piezas de dibujo (tarjeta, barras, tendencia) son las de
 * `core/components/Informe.jsx`, compartidas con el informe de Master Planner.
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
import { Barras, Seccion, Tarjeta, Tendencia } from '../../core/components/Informe.jsx'
import { estadoATiempo, formatoPromedio, periodosRapidos, textoVariacion } from './informe.js'

// ── Piezas ──────────────────────────────────────────────────────────────

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
          {/* Cómo leer los «/día»: sin esto, alguien los divide por días corridos. */}
          <p className="text-xs text-texto-2 mt-0.5">
            Los promedios son por día hábil: <span className="cifra">{r.dias_habiles}</span> en el periodo, sin
            fines de semana ni festivos y sin contar los días que todavía no pasan.
          </p>
        </div>
        <img src={LOGO} alt={NOMBRE_EMPRESA} className="h-10 w-auto object-contain flex-shrink-0" />
      </div>

      {/* Lo que se pregunta primero */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 print:grid-cols-5">
        <Tarjeta titulo="Radicadas" valor={r.total}
                 detalle={variacion?.texto || 'Sin periodo anterior para comparar'} tono={variacion?.tono} />
        {/* El anterior se promedia con SUS días hábiles: comparar los totales
            de dos periodos con distintos festivos no compara lo mismo. */}
        <Tarjeta titulo="Por día hábil" valor={formatoPromedio(r.promedio_dia_habil)}
                 detalle={r.promedio_dia_habil_anterior == null
                   ? `En ${r.dias_habiles} días hábiles`
                   : `En ${r.dias_habiles} días hábiles · antes ${formatoPromedio(r.promedio_dia_habil_anterior)}`} />
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
        <Tendencia tendencia={inf.tendencia} unidad="PQRS" />
      </Seccion>

      <div className="grid lg:grid-cols-2 gap-5 print:grid-cols-2">
        <Seccion titulo="Por tipo"><Barras unidad="PQRS" filas={inf.por_tipo} /></Seccion>
        {/* La única que suma las anuladas: el resto del informe cuenta solo
            los casos reales, y sin decirlo aquí las cifras no cuadrarían. */}
        <Seccion titulo="Estado actual"
                 nota={r.anuladas
                   ? `Incluye ${r.anuladas === 1 ? '1 anulada' : `${r.anuladas} anuladas`} (duplicadas o por error), que no cuentan en las demás cifras.`
                   : null}>
          <Barras unidad="PQRS" filas={inf.por_estado} sobre="de todo lo que entró" />
        </Seccion>
      </div>

      {/* La causa y el área causante en recuadros aparte: son dos preguntas
          distintas —por qué llegan y de dónde salió el problema— y en uno
          solo se leían como una sola lista. */}
      <div className="grid lg:grid-cols-2 gap-5 print:grid-cols-2">
        <Seccion
          titulo="Asociado a: por qué llegan"
          nota={r.total
            ? `Sobre las ${r.con_causa} que ya tienen causa (${r.pct_con_causa ?? 0}%).${r.sin_causa ? ` ${r.sin_causa} están sin clasificar.` : ''}`
            : null}
        >
          <Barras unidad="PQRS" filas={inf.por_asociado} sobre="de las clasificadas"
                  vacio="Ninguna clasificada todavía. Se marca en «Causa de la PQRS»." />
        </Seccion>
        <Seccion titulo="Área causante: de dónde salió el problema"
                 nota="Puede no ser el área que gestionó la PQRS.">
          <Barras unidad="PQRS" filas={inf.por_area_causante} sobre="de las que tienen área causante"
                  vacio="Ninguna tiene área causante todavía." />
        </Seccion>
      </div>

      <div className="grid lg:grid-cols-2 gap-5 print:grid-cols-2">
        <Seccion titulo="Por dónde entran" nota="Canal de atención: punto de venta, venta institucional, WhatsApp…">
          <Barras unidad="PQRS" filas={inf.por_canal} />
        </Seccion>
        <Seccion titulo="Quién la radica" nota="El cliente por el formulario web, o el área de quien la registró por dentro.">
          <Barras unidad="PQRS" filas={inf.por_origen} />
        </Seccion>
      </div>

      <div className="grid lg:grid-cols-2 gap-5 print:grid-cols-2">
        <Seccion titulo="Productos con más PQRS"
                 nota={inf.productos_distintos ? `${inf.productos_distintos} productos distintos en el periodo.` : null}>
          <Barras unidad="PQRS" filas={inf.top_productos} sobre="de los productos reportados"
                  vacio="Ninguna PQRS del periodo trae producto." />
        </Seccion>
        <Seccion titulo="Dónde están las abiertas" nota="Área que tiene cada PQRS abierta hoy.">
          <Barras unidad="PQRS" filas={inf.por_area_actual} sobre="de las abiertas" vacio="No hay PQRS abiertas del periodo." />
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
