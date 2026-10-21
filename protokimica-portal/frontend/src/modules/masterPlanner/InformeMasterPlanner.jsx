/**
 * Informe gerencial de Master Planner: una hoja para leer en pantalla y
 * descargar en PDF, como el de PQRS.
 *
 * Es UN informe de empresa con el área como filtro (no uno por área): los
 * proyectos cruzan áreas y la comparación entre ellas es justamente lo que
 * se viene a ver. Los números llegan contados de `GET /master-planner/informe`
 * —porcentajes y diferencias incluidos—; aquí solo se dibujan.
 *
 * El informe separa lo que PASÓ en el periodo (compromisos, entregas,
 * aplazamientos, cierres, pagos) de lo que es FOTO DE HOY (salud, avance,
 * lo pendiente de pago): el avance de un mes ya pasado no está guardado, y
 * cada sección dice cuál de las dos es.
 *
 * El periodo y el área van en la URL: un enlace copiado abre el mismo informe.
 */
import { useMemo } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import api from '../../core/api.js'
import { LOGO, NOMBRE_EMPRESA } from '../../core/marca.js'
import { mensajeDeError } from '../../core/errores.js'
import { useFiltrosEnUrl } from '../../core/useFiltrosEnUrl.js'
import { Atenuado, Esqueleto } from '../../core/components/Cargando.jsx'
import { BarraPartida, Estado, Seccion, Tarjeta, Tendencia } from '../../core/components/Informe.jsx'
import { IconoAlerta, IconoAlDia, IconoCalendario, IconoRecibo } from '../../core/components/Iconos.jsx'
import { formatFecha, formatFechaHora, formatMoneda } from './constants.js'
import {
  TONO_SALUD, estadoCumplimiento, informeVacio, periodosInforme, textoAntes, textoBase,
  textoPuntos, tramosCompromisos,
} from './informe.js'

const enlaceProyecto = (id) => `/master-planner?proyecto=${id}`

function NombreProyecto({ id, nombre }) {
  return (
    <Link to={enlaceProyecto(id)} className="font-semibold text-acento-fuerte hover:underline">
      {nombre}
    </Link>
  )
}

function Cumplimiento({ c }) {
  if (!c || !c.juzgadas) return <span className="text-texto-3">—</span>
  const e = estadoCumplimiento(c.pct)
  return (
    <span title={textoBase(c)}>
      <Estado tono={e.tono}><span className="cifra font-semibold">{c.pct}%</span></Estado>
      <span className="text-texto-3 text-xs cifra"> · {c.a_tiempo}/{c.juzgadas}</span>
    </span>
  )
}

const Th = ({ children, derecha }) => (
  <th className={`py-2 font-semibold ${derecha ? 'text-right' : ''}`}>{children}</th>
)

// ── Secciones ───────────────────────────────────────────────────────────

function TablaAreas({ filas }) {
  if (!filas.length) return <p className="text-sm text-texto-2">Ninguna área con proyectos o compromisos en el periodo.</p>
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-xs text-texto-2 uppercase tracking-wide text-left border-b border-borde">
            <Th>Área</Th>
            <Th derecha>Proyectos</Th>
            <Th derecha>Avance</Th>
            <Th derecha>En riesgo</Th>
            <Th derecha>Compromisos</Th>
            <Th derecha>Fechas movidas</Th>
            <Th derecha>Actividades</Th>
            <Th derecha>Cerrados</Th>
          </tr>
        </thead>
        <tbody className="divide-y divide-borde">
          {filas.map(f => (
            <tr key={f.area}>
              <td className="py-2 text-texto font-semibold">{f.area}</td>
              <td className="py-2 text-right cifra" title="Responsable + participa">
                {f.proyectos_responsable}
                {f.proyectos_participa > 0 && <span className="text-texto-3"> + {f.proyectos_participa}</span>}
              </td>
              <td className="py-2 text-right cifra">{f.avance_promedio == null ? '—' : `${f.avance_promedio}%`}</td>
              <td className="py-2 text-right cifra">
                {f.en_riesgo ? <Estado tono="negativo">{f.en_riesgo}</Estado> : <span className="text-texto-3">0</span>}
              </td>
              <td className="py-2 text-right"><Cumplimiento c={f.compromisos} /></td>
              <td className="py-2 text-right cifra">{f.aplazamientos || <span className="text-texto-3">0</span>}</td>
              <td className="py-2 text-right cifra">
                {f.actividades_pct == null ? <span className="text-texto-3">—</span> : (
                  <Estado tono={estadoCumplimiento(f.actividades_pct).tono}>{f.actividades_pct}%</Estado>
                )}
              </td>
              <td className="py-2 text-right cifra">
                {f.finalizados}
                {f.cancelados > 0 && <span className="text-texto-3"> · {f.cancelados} cancel.</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function ListaRiesgo({ filas }) {
  if (!filas.length) {
    return <Estado tono="positivo">Ningún proyecto activo en riesgo.</Estado>
  }
  return (
    <ul className="divide-y divide-borde">
      {filas.map(p => (
        <li key={p.id} className="py-3 first:pt-0 last:pb-0 evitar-corte">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <NombreProyecto id={p.id} nombre={p.nombre} />
            <span className="text-sm">
              <Estado tono={TONO_SALUD[p.salud]}>{p.salud === 'rojo' ? 'Riesgo alto' : 'Atención'}</Estado>
              <span className="cifra text-texto-2"> · {p.avance_pct}% de avance</span>
            </span>
          </div>
          <p className="text-xs text-texto-2 mt-0.5">
            {p.area}{p.lider_nombre ? ` · Lidera ${p.lider_nombre}` : ' · Sin líder'}
            {p.fecha_fin_estimada && ` · Entrega ${formatFecha(p.fecha_fin_estimada)}`}
          </p>
          {p.motivos.length > 0 && (
            <ul className="mt-1.5 text-sm text-texto list-disc pl-5 space-y-0.5">
              {p.motivos.map(m => <li key={m}>{m}</li>)}
            </ul>
          )}
        </li>
      ))}
    </ul>
  )
}

function ListaCierres({ filas }) {
  if (!filas.length) return <p className="text-sm text-texto-2">Ningún proyecto se cerró en el periodo.</p>
  return (
    <ul className="divide-y divide-borde">
      {filas.map(c => (
        <li key={c.id} className="py-3 first:pt-0 last:pb-0 evitar-corte">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <NombreProyecto id={c.id} nombre={c.nombre} />
            <span className="text-sm">
              {c.tipo === 'finalizado'
                ? <Estado tono="positivo">Finalizado</Estado>
                : <Estado tono="neutro">Cancelado</Estado>}
              <span className="text-texto-2"> · {formatFecha(c.fecha)}</span>
            </span>
          </div>
          <p className="text-xs text-texto-2 mt-0.5">
            {c.area}{c.lider_nombre && ` · ${c.lider_nombre}`}
            {c.tareas_total != null && ` · ${c.tareas_completadas ?? 0} de ${c.tareas_total} tareas`}
            {c.dias_de_duracion != null && ` · ${c.dias_de_duracion} días`}
            {c.en_plazo === true && ' · En plazo'}
            {c.en_plazo === false && ' · Después de la fecha prevista'}
          </p>
          {c.texto && (
            <p className="text-sm text-texto mt-1 whitespace-pre-line">
              <span className="text-texto-2">{c.tipo === 'finalizado' ? 'Entregó: ' : 'Motivo: '}</span>{c.texto}
            </p>
          )}
        </li>
      ))}
    </ul>
  )
}

function Aplazamientos({ a, etiquetaAnterior }) {
  const total = a.tareas + a.proyectos
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 text-sm">
        <div>
          <div className="text-2xl font-bold cifra text-texto">{a.tareas}</div>
          <div className="text-xs text-texto-2">
            {a.tareas === 1 ? 'vez se movió la fecha de una tarea' : 'veces se movió la fecha de una tarea'}
            {a.tareas > 0 && ` (${a.tareas_distintas} tareas, ${a.dias_tareas} días en total)`}
          </div>
        </div>
        <div>
          <div className="text-2xl font-bold cifra text-texto">{a.proyectos}</div>
          <div className="text-xs text-texto-2">
            {a.proyectos === 1 ? 'vez se movió la entrega de un proyecto' : 'veces se movió la entrega de un proyecto'}
            {a.proyectos > 0 && ` (${a.dias_proyectos} días en total)`}
          </div>
        </div>
      </div>
      <p className="text-xs text-texto-2">{textoAntes(a.total_anterior, etiquetaAnterior)} · total {total}</p>
      {a.mas_aplazados.length > 0 && (
        <ul className="divide-y divide-borde text-sm">
          {a.mas_aplazados.map(p => (
            <li key={p.id} className="py-1.5 flex justify-between gap-3">
              <span className="truncate"><NombreProyecto id={p.id} nombre={p.nombre} /> <span className="text-texto-3 text-xs">{p.area}</span></span>
              <span className="cifra text-texto-2 whitespace-nowrap">{p.veces} {p.veces === 1 ? 'vez' : 'veces'} · {p.dias} días</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function Quietos({ filas }) {
  if (!filas.length) return <Estado tono="positivo">Todos los proyectos activos tuvieron movimiento.</Estado>
  return (
    <ul className="divide-y divide-borde text-sm">
      {filas.map(p => (
        <li key={p.id} className="py-1.5 flex justify-between gap-3">
          <span className="truncate">
            <NombreProyecto id={p.id} nombre={p.nombre} />
            <span className="text-texto-3 text-xs"> {p.area}{p.lider_nombre && ` · ${p.lider_nombre}`}</span>
          </span>
          <span className="cifra text-texto-2 whitespace-nowrap">
            {p.dias_sin_movimiento == null ? '—' : `${p.dias_sin_movimiento} días sin movimiento`}
          </span>
        </li>
      ))}
    </ul>
  )
}

function Actividades({ act, etiquetaAnterior }) {
  if (!act.esperados) {
    return <p className="text-sm text-texto-2">No había actividades programadas en el periodo.</p>
  }
  const e = estadoCumplimiento(act.pct)
  const puntos = textoPuntos(act.variacion_puntos, etiquetaAnterior)
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="text-3xl font-bold cifra text-texto">{act.pct}%</span>
        <Estado tono={e.tono}>{e.etiqueta}</Estado>
        <span className="text-xs text-texto-2 cifra">{act.cumplidos} de {act.esperados} veces registradas</span>
        {puntos && <span className="text-xs"><Estado tono={puntos.tono}>{puntos.texto}</Estado></span>}
      </div>
      {act.menos_cumplidas.length > 0 && (
        <>
          <p className="text-xs font-semibold text-texto-2 uppercase tracking-wide">Las que menos se registraron</p>
          <ul className="divide-y divide-borde text-sm">
            {act.menos_cumplidas.map(a => (
              <li key={a.id} className="py-1.5 flex justify-between gap-3">
                <span className="truncate">
                  <span className="text-texto font-semibold">{a.titulo}</span>
                  <span className="text-texto-3 text-xs"> {a.area}{a.asignado_nombre && ` · ${a.asignado_nombre}`} · {a.frecuencia}</span>
                </span>
                <span className="cifra whitespace-nowrap">
                  <Estado tono={estadoCumplimiento(a.pct).tono}>{a.pct}%</Estado>
                  <span className="text-texto-3 text-xs"> · {a.cumplidos}/{a.esperados}</span>
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}

function Presupuesto({ p, etiquetaAnterior }) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 print:grid-cols-4">
        <Tarjeta titulo="Pagado en el periodo" valor={formatMoneda(p.pagado_periodo)}
                 detalle={`${p.pagos_periodo} pagos · antes ${formatMoneda(p.pagado_anterior)}`} />
        <Tarjeta titulo="Aprobado en el periodo" valor={formatMoneda(p.aprobado_periodo)} />
        <Tarjeta titulo="Pendiente de pago hoy" valor={formatMoneda(p.pendiente_pago)}
                 detalle="Aprobado que aún no sale" />
        <Tarjeta titulo="Por aprobar hoy" valor={formatMoneda(p.por_aprobar)}
                 detalle={p.items_por_aprobar ? `${p.items_por_aprobar} ítems esperando` : 'Nada esperando'}
                 tono={p.items_por_aprobar ? 'alerta' : 'positivo'} />
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-xs text-texto-2 uppercase tracking-wide text-left border-b border-borde">
              <Th>Área responsable</Th>
              <Th derecha>Planeado</Th>
              <Th derecha>Aprobado</Th>
              <Th derecha>Pagado</Th>
              <Th derecha>% pagado</Th>
              <Th derecha>Pagado en el periodo</Th>
            </tr>
          </thead>
          <tbody className="divide-y divide-borde">
            {p.por_area.map(f => (
              <tr key={f.area}>
                <td className="py-2 text-texto font-semibold">{f.area}</td>
                <td className="py-2 text-right cifra">{formatMoneda(f.planeado)}</td>
                <td className="py-2 text-right cifra">{formatMoneda(f.aprobado)}</td>
                <td className="py-2 text-right cifra">{formatMoneda(f.pagado)}</td>
                <td className="py-2 text-right cifra">{f.pagado_pct == null ? '—' : `${f.pagado_pct}%`}</td>
                <td className="py-2 text-right cifra">{formatMoneda(f.pagado_periodo)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t-2 border-borde font-semibold">
              <td className="py-2">Total</td>
              <td className="py-2 text-right cifra">{formatMoneda(p.planeado)}</td>
              <td className="py-2 text-right cifra">{formatMoneda(p.aprobado)}</td>
              <td className="py-2 text-right cifra">{formatMoneda(p.pagado)}</td>
              <td className="py-2 text-right cifra">{p.pagado_pct == null ? '—' : `${p.pagado_pct}%`}</td>
              <td className="py-2 text-right cifra">{formatMoneda(p.pagado_periodo)}</td>
            </tr>
          </tfoot>
        </table>
      </div>
      <p className="text-xs text-texto-2">
        Planeado, aprobado y pagado son de los proyectos vivos hoy; lo «del periodo» incluye también los ya
        cerrados. El % pagado es sobre lo aprobado, que es lo que de verdad se debe.
        {etiquetaAnterior && ` «Antes» es ${etiquetaAnterior.toLowerCase()}.`}
      </p>
    </div>
  )
}

function Personas({ filas }) {
  if (!filas.length) return <p className="text-sm text-texto-2">Nadie tenía compromisos ni tareas abiertas.</p>
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-xs text-texto-2 uppercase tracking-wide text-left border-b border-borde">
            <Th>Persona</Th>
            <Th derecha>Compromisos del periodo</Th>
            <Th derecha>Vencidas hoy</Th>
            <Th derecha>Abiertas</Th>
            <Th derecha>Horas estimadas</Th>
            <Th derecha>Fechas movidas</Th>
          </tr>
        </thead>
        <tbody className="divide-y divide-borde">
          {filas.map(f => (
            <tr key={f.usuario_id}>
              <td className="py-2">
                <span className="text-texto font-semibold">{f.nombre}</span>
                <span className="text-texto-3 text-xs"> {f.area || 'Sin área'}</span>
              </td>
              <td className="py-2 text-right"><Cumplimiento c={f.compromisos} /></td>
              <td className="py-2 text-right cifra">
                {f.vencidas_hoy ? <Estado tono="negativo">{f.vencidas_hoy}</Estado> : <span className="text-texto-3">0</span>}
              </td>
              <td className="py-2 text-right cifra">{f.abiertas}</td>
              <td className="py-2 text-right cifra" title={f.sin_estimar ? `${f.sin_estimar} tareas sin estimar` : undefined}>
                {f.horas_abiertas == null ? '—' : `${f.horas_abiertas} h`}
                {f.sin_estimar > 0 && f.horas_abiertas != null && <span className="text-texto-3"> +{f.sin_estimar}?</span>}
              </td>
              <td className="py-2 text-right cifra">{f.aplazamientos || <span className="text-texto-3">0</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ── La hoja ─────────────────────────────────────────────────────────────

function Hoja({ inf }) {
  const r = inf.resumen
  const c = inf.cumplimiento
  const e = inf.entregas
  const anterior = inf.periodo.anterior.etiqueta
  const estado = estadoCumplimiento(c.pct)
  const puntos = textoPuntos(c.variacion_puntos, anterior)
  const riesgo = inf.salud.filter(s => s.clave === 'rojo' || s.clave === 'amarillo')
  const enRiesgo = riesgo.reduce((s, x) => s + x.n, 0)
  const alcance = inf.alcance.area ? `${inf.alcance.descripcion} · Área: ${inf.alcance.area}` : inf.alcance.descripcion

  return (
    <div className="space-y-5">
      <div className="bg-white rounded-xl border border-borde p-5 flex items-center justify-between gap-4 evitar-corte">
        <div>
          <div className="text-xs font-semibold text-texto-2 uppercase tracking-wide">Informe de Master Planner</div>
          <h2 className="text-2xl font-bold text-acento-fuerte mt-0.5">{inf.periodo.etiqueta}</h2>
          <p className="text-xs text-texto-2 mt-1">
            {alcance} · Del {formatFecha(inf.periodo.desde)} al {formatFecha(inf.periodo.hasta)} ·
            Generado el {formatFechaHora(inf.periodo.generado)}
          </p>
          <p className="text-xs text-texto-2 mt-0.5">
            Se compara con {anterior.toLowerCase()}. Lo marcado «hoy» es el estado al generar el informe.
          </p>
        </div>
        <img src={LOGO} alt={NOMBRE_EMPRESA} className="h-10 w-auto object-contain flex-shrink-0" />
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 print:grid-cols-5">
        <Tarjeta titulo="Compromisos a tiempo" valor={c.pct == null ? '—' : `${c.pct}%`}
                 detalle={puntos ? `${textoBase(c)} · ${puntos.texto}` : `${estado.etiqueta} · ${textoBase(c)}`}
                 tono={c.pct == null ? 'neutro' : estado.tono} />
        <Tarjeta titulo="Tareas entregadas" valor={e.total}
                 detalle={e.con_fecha ? `${e.pct}% a tiempo · antes ${e.total_anterior}` : `Antes ${e.total_anterior}`} />
        <Tarjeta titulo="Proyectos activos hoy" valor={r.proyectos_activos}
                 detalle={r.avance_promedio == null ? 'Sin proyectos activos' : `Avance promedio ${r.avance_promedio}%`} />
        <Tarjeta titulo="En riesgo hoy" valor={enRiesgo}
                 detalle={enRiesgo ? riesgo.map(x => `${x.n} ${x.etiqueta.toLowerCase()}`).join(' · ') : 'Ninguno'}
                 tono={enRiesgo ? 'negativo' : 'positivo'} />
        <Tarjeta titulo="Finalizados" valor={r.finalizados}
                 detalle={`${r.cancelados} cancelados · antes ${r.finalizados_anterior}`} />
      </div>

      <div className="grid lg:grid-cols-2 gap-5 print:grid-cols-2">
        <Seccion titulo="Compromisos del periodo"
                 nota="Tareas cuya fecha de entrega cae en el periodo. Lo que vence más adelante no se juzga todavía.">
          <BarraPartida tramos={tramosCompromisos(c)} unidad="tareas" vacio="Ninguna tarea vencía en el periodo." />
          {c.aplazadas > 0 && (
            <p className="text-xs text-texto-2 mt-3">
              {c.aplazadas} de {c.total} se movieron de fecha al menos una vez: se miden contra la fecha vigente.
            </p>
          )}
        </Seccion>
        <Seccion titulo="Salud de los proyectos · hoy"
                 nota="Avance contra el tiempo que ya pasó. Vencido sin terminar es riesgo alto.">
          <BarraPartida tramos={inf.salud.map(s => ({ ...s, tono: TONO_SALUD[s.clave] }))}
                        unidad="proyectos" vacio="No hay proyectos activos." />
          <p className="text-xs text-texto-2 mt-3 cifra">
            {r.nuevos} nuevos en el periodo (antes {r.nuevos_anterior}) · {r.con_movimiento} con movimiento ·{' '}
            {r.quietos} sin movimiento
          </p>
        </Seccion>
      </div>

      <Seccion titulo="Tareas entregadas en el periodo"
               nota={`${e.total} entregadas, ${e.creadas} creadas. El % a tiempo es el mismo del indicador «Cumplimiento de fechas».`}>
        <Tendencia tendencia={inf.tendencia_entregas} unidad="tareas entregadas" />
      </Seccion>

      <Seccion titulo="Por área"
               nota="Proyectos: responsable + donde participa. Avance y riesgo son de hoy; compromisos, fechas movidas, actividades y cerrados, del periodo.">
        <TablaAreas filas={inf.por_area} />
      </Seccion>

      <Seccion titulo="Proyectos en riesgo · hoy" nota="Cada uno con el motivo. Clic en el nombre para abrirlo.">
        <ListaRiesgo filas={inf.en_riesgo} />
      </Seccion>

      <div className="grid lg:grid-cols-2 gap-5 print:grid-cols-2">
        <Seccion titulo="Fechas que se movieron" nota="Del historial: solo cuenta mover una fecha que ya existía.">
          <Aplazamientos a={inf.aplazamientos} etiquetaAnterior={anterior} />
        </Seccion>
        <Seccion titulo="Proyectos sin movimiento"
                 nota="Activos que no tuvieron ningún cambio, avance ni tarea entregada en el periodo.">
          <Quietos filas={inf.quietos} />
        </Seccion>
      </div>

      <Seccion titulo="Proyectos cerrados en el periodo"
               nota={`${r.finalizados} finalizados (${r.finalizados_en_plazo} en plazo) y ${r.cancelados} cancelados. Se cuentan aparte: uno se cumplió, el otro se abandonó.`}>
        <ListaCierres filas={inf.cierres} />
      </Seccion>

      <Seccion titulo="Actividades diarias" nota="Lo que se repite: veces registradas sobre las que tocaban, hasta ayer.">
        <Actividades act={inf.actividades} etiquetaAnterior={anterior} />
      </Seccion>

      {inf.presupuesto && (
        <Seccion titulo="Presupuesto"
                 nota={inf.presupuesto.proyectos_sin_acceso
                   ? `De ${inf.presupuesto.proyectos} proyectos. No incluye ${inf.presupuesto.proyectos_sin_acceso} cuyo presupuesto no está a tu cargo.`
                   : `De ${inf.presupuesto.proyectos} proyectos.`}>
          <Presupuesto p={inf.presupuesto} etiquetaAnterior={anterior} />
        </Seccion>
      )}

      {inf.personas && (
        <Seccion titulo="Por persona"
                 nota="Compromisos del periodo y carga abierta hoy. Las horas son la estimación de quien planeó, no lo trabajado.">
          <Personas filas={inf.personas} />
        </Seccion>
      )}

      <p className="text-center text-xs text-texto-3 pt-2">
        {NOMBRE_EMPRESA} · Portal de gestión · Informe generado el {formatFechaHora(inf.periodo.generado)}
      </p>
    </div>
  )
}

// ── Pantalla ────────────────────────────────────────────────────────────

export default function InformeMasterPlanner() {
  const navigate = useNavigate()
  const rapidos = useMemo(() => periodosInforme(), [])
  // Vacío es «este mes»: así la URL limpia abre el informe del mes en curso
  // y no queda una fecha de hoy pegada en un enlace que se abre mañana.
  const [filtros, cambiar] = useFiltrosEnUrl({ desde: '', hasta: '', area: '' })
  const periodo = {
    desde: filtros.desde || rapidos[0].desde,
    hasta: filtros.hasta || rapidos[0].hasta,
  }
  const params = { ...periodo, ...(filtros.area ? { area: filtros.area } : {}) }

  const { data: inf, isLoading, isError, error, isFetching } = useQuery({
    queryKey: ['mp-informe', params],
    queryFn: () => api.get('/master-planner/informe', { params }).then(r => r.data),
    placeholderData: (anterior) => anterior,
  })

  const elegirRapido = (p) => cambiar(p.clave === 'mes' ? { desde: '', hasta: '' } : { desde: p.desde, hasta: p.hasta })
  const activo = rapidos.find(p => p.desde === periodo.desde && p.hasta === periodo.hasta)?.clave

  return (
    <div className="max-w-5xl mx-auto">
      <div className="print:hidden">
        <button onClick={() => navigate('/master-planner')}
                className="flex items-center gap-2 text-sm text-texto-2 hover:text-acento-fuerte mb-5 transition">
          ← Volver a Master Planner
        </button>

        <div className="flex flex-wrap items-start justify-between gap-4 mb-4">
          <div>
            <h1 className="text-xl font-bold text-acento-fuerte">Informe de Master Planner</h1>
            <p className="text-sm text-texto-2 mt-1">
              Qué se comprometió y qué se cumplió, qué se movió, qué se cerró y cómo va cada área. Se descarga en PDF tal como se ve.
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

        <div className="bg-white rounded-xl border border-borde p-3 mb-5 flex flex-wrap items-center gap-2">
          <IconoCalendario tam={16} className="text-texto-2 ml-1" />
          {rapidos.map(p => (
            <button key={p.clave} onClick={() => elegirRapido(p)}
                    className={`px-3 py-1.5 rounded-lg text-sm font-semibold transition ${
                      activo === p.clave ? 'bg-acento-suave text-acento-fuerte' : 'text-texto-2 hover:bg-superficie-2'
                    }`}>
              {p.etiqueta}
            </button>
          ))}
          <span className="mx-1 h-5 w-px bg-borde" />
          <label className="text-xs text-texto-2" htmlFor="mp-informe-desde">Desde</label>
          <input id="mp-informe-desde" type="date" value={periodo.desde} max={periodo.hasta}
                 onChange={e => cambiar({ desde: e.target.value, hasta: periodo.hasta })}
                 className="px-2 py-1.5 rounded-lg border border-borde text-sm" />
          <label className="text-xs text-texto-2" htmlFor="mp-informe-hasta">Hasta</label>
          <input id="mp-informe-hasta" type="date" value={periodo.hasta} min={periodo.desde}
                 onChange={e => cambiar({ desde: periodo.desde, hasta: e.target.value })}
                 className="px-2 py-1.5 rounded-lg border border-borde text-sm" />
          {/* El área elige DENTRO de lo que cada quien ve: el servidor no abre nada más. */}
          {inf?.alcance.areas_disponibles.length > 0 && (
            <>
              <span className="mx-1 h-5 w-px bg-borde" />
              <label className="text-xs text-texto-2" htmlFor="mp-informe-area">Área</label>
              <select id="mp-informe-area" value={filtros.area} onChange={e => cambiar({ area: e.target.value })}
                      className="px-2 py-1.5 rounded-lg border border-borde text-sm">
                <option value="">Todas</option>
                {inf.alcance.areas_disponibles.map(a => <option key={a} value={a}>{a}</option>)}
              </select>
            </>
          )}
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
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
            {[0, 1, 2, 3, 4].map(i => <Esqueleto key={i} alto="h-28" className="rounded-xl" />)}
          </div>
          <div className="grid lg:grid-cols-2 gap-5">
            <Esqueleto alto="h-40" className="rounded-xl" />
            <Esqueleto alto="h-40" className="rounded-xl" />
          </div>
          <Esqueleto alto="h-56" className="rounded-xl" />
        </div>
      )}

      {inf && (
        <Atenuado cargando={isFetching}>
          {informeVacio(inf) ? (
            <div className="bg-white rounded-xl border border-borde p-10 text-center">
              <IconoAlDia tam={26} className="mx-auto mb-3 text-positivo" />
              <p className="text-sm font-semibold text-texto">
                No hay proyectos, compromisos ni actividades en {inf.periodo.etiqueta.toLowerCase()}.
              </p>
              <p className="text-xs text-texto-2 mt-1">Prueba con otro periodo{inf.alcance.area ? ' o con todas las áreas' : ''}.</p>
            </div>
          ) : (
            <Hoja inf={inf} />
          )}
        </Atenuado>
      )}
    </div>
  )
}
