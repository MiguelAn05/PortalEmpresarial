/**
 * Informe de Marcaciones: una hoja para leer en pantalla, descargar en PDF
 * (la hoja de imprimir del navegador, como PQRS y Master Planner) y bajar en
 * CSV para Excel. Los números llegan contados del servidor
 * (`GET /marcaciones/informe`); aquí solo se dibujan. Lo que se descarga es
 * lo que quien lo pide puede ver: el servidor recorta por rol y área.
 */
import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { LOGO, NOMBRE_EMPRESA } from '../../core/marca.js'
import { mensajeDeError } from '../../core/errores.js'
import Boton from '../../core/components/Boton.jsx'
import { Atenuado, Esqueleto } from '../../core/components/Cargando.jsx'
import { IconoAlerta, IconoAlDia, IconoCalendario, IconoRecibo } from '../../core/components/Iconos.jsx'
import { Barras, Seccion, Tarjeta } from '../../core/components/Informe.jsx'
import { formatFecha, formatFechaHora } from '../masterPlanner/constants.js'
import { descargarCsv, obtenerDia, obtenerInforme } from './api.js'
import { NOVEDADES } from './constants.js'
import { filasDeNovedades, periodosRapidos } from './resumen.js'
import { Novedades } from './components/piezas.jsx'

function Hoja({ inf }) {
  const t = inf.totales
  const conNovedad = inf.filas.filter(f => f.novedades.length)
  const alcance = inf.filtros.area || (inf.alcance.tipo === 'todo' ? 'Toda la empresa' : inf.alcance.tipo === 'propio' ? 'Solo tus marcaciones' : inf.alcance.areas.join(', '))

  return (
    <div className="space-y-5">
      <div className="bg-white rounded-xl border border-borde p-5 flex items-center justify-between gap-4 evitar-corte">
        <div>
          <div className="text-xs font-semibold text-texto-2 uppercase tracking-wide">Informe de marcaciones</div>
          <h2 className="text-2xl font-bold text-acento-fuerte mt-0.5">
            {formatFecha(inf.desde)}{inf.desde !== inf.hasta && <> al {formatFecha(inf.hasta)}</>}
          </h2>
          <p className="text-xs text-texto-2 mt-1">{alcance} · Generado el {formatFechaHora(inf.generado)}</p>
        </div>
        <img src={LOGO} alt={NOMBRE_EMPRESA} className="h-10 w-auto object-contain flex-shrink-0" />
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 print:grid-cols-4">
        <Tarjeta titulo="Personas" valor={inf.por_persona.length} detalle={`${inf.filas.length} días-persona revisados`} />
        <Tarjeta titulo="Con novedades" valor={conNovedad.length} detalle={t.total_novedades ? `${t.total_novedades} novedades` : 'Sin novedades'}
                 tono={conNovedad.length ? 'negativo' : 'positivo'} />
        <Tarjeta titulo="Llegadas tarde" valor={t.novedades.llegada_tarde} tono={t.novedades.llegada_tarde ? 'alerta' : 'positivo'} />
        <Tarjeta titulo="Ausencias" valor={t.novedades.ausencia} tono={t.novedades.ausencia ? 'negativo' : 'positivo'} />
      </div>

      <div className="grid lg:grid-cols-2 gap-5 print:grid-cols-2">
        <Seccion titulo="Novedades por tipo">
          <Barras unidad="novedades" filas={filasDeNovedades(t, NOVEDADES)} sobre="de las novedades" vacio="Ninguna novedad en el periodo." />
        </Seccion>
        <Seccion titulo="Novedades por área">
          <Barras unidad="novedades" sobre="de las novedades" vacio="Ninguna novedad en el periodo."
                  filas={inf.por_area.filter(a => a.total_novedades).sort((a, b) => b.total_novedades - a.total_novedades)
                    .map(a => ({ clave: a.area, etiqueta: a.area, n: a.total_novedades, pct: t.total_novedades ? Math.round((a.total_novedades / t.total_novedades) * 1000) / 10 : 0 }))} />
        </Seccion>
      </div>

      <Seccion titulo="Por persona" nota="Quien más novedades tiene va primero.">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-xs text-texto-2 uppercase tracking-wide text-left border-b border-borde">
              <th className="py-2 font-semibold">Persona</th>
              <th className="py-2 font-semibold text-right">Días</th>
              <th className="py-2 font-semibold text-right">Tarde</th>
              <th className="py-2 font-semibold text-right">Sal. ant.</th>
              <th className="py-2 font-semibold text-right">Ausencias</th>
              <th className="py-2 font-semibold text-right">Almuerzo</th>
              <th className="py-2 font-semibold text-right">Break</th>
              <th className="py-2 font-semibold text-right">Total</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-borde">
            {inf.por_persona.map(p => (
              <tr key={p.emp_code}>
                <td className="py-1.5"><span className="text-texto">{p.nombre}</span> <span className="text-[11px] text-texto-3">{p.area}</span></td>
                <td className="py-1.5 text-right cifra">{p.dias}</td>
                <td className="py-1.5 text-right cifra">{p.llegada_tarde}</td>
                <td className="py-1.5 text-right cifra">{p.salida_anticipada}</td>
                <td className="py-1.5 text-right cifra">{p.ausencia}</td>
                <td className="py-1.5 text-right cifra">{p.exceso_almuerzo}</td>
                <td className="py-1.5 text-right cifra">{p.exceso_break}</td>
                <td className="py-1.5 text-right cifra font-semibold">{p.total_novedades || <span className="text-texto-3 font-normal">0</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Seccion>

      <Seccion titulo="Detalle de las novedades" nota="Cada día con novedad, con lo que pasó. El CSV trae además los días sin novedad.">
        {conNovedad.length === 0 ? (
          <p className="text-sm text-texto-2">Ninguna novedad en el periodo.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-texto-2 uppercase tracking-wide text-left border-b border-borde">
                <th className="py-2 font-semibold">Fecha</th>
                <th className="py-2 font-semibold">Persona</th>
                <th className="py-2 font-semibold">Novedad</th>
                <th className="py-2 font-semibold">Detalle</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-borde">
              {conNovedad.map(f => (
                <tr key={`${f.fecha}-${f.emp_code}`} className="align-top">
                  <td className="py-1.5 whitespace-nowrap cifra">{formatFecha(f.fecha, { day: '2-digit', month: 'short' })}</td>
                  <td className="py-1.5">{f.nombre}<div className="text-[11px] text-texto-3">{f.area}</div></td>
                  <td className="py-1.5"><Novedades lista={f.novedades} /></td>
                  <td className="py-1.5 text-xs text-texto-2">{f.novedades.map(n => n.detalle).join(' ')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Seccion>

      <p className="text-center text-xs text-texto-3 pt-2">
        {NOMBRE_EMPRESA} · Portal de gestión · Informe generado el {formatFechaHora(inf.generado)}
      </p>
    </div>
  )
}

export default function InformeMarcaciones() {
  const navigate = useNavigate()
  const rapidos = useMemo(() => periodosRapidos(), [])
  const [periodo, setPeriodo] = useState({ desde: rapidos[1].desde, hasta: rapidos[1].hasta })
  const [area, setArea] = useState('')
  const [soloNovedades, setSoloNovedades] = useState(false)
  const [bajando, setBajando] = useState(false)
  const [errorCsv, setErrorCsv] = useState('')

  const params = { ...periodo, ...(area ? { area } : {}) }
  const { data: inf, isLoading, isError, error, isFetching } = useQuery({
    queryKey: ['marcaciones', 'informe', params],
    queryFn: () => obtenerInforme(params),
    placeholderData: (anterior) => anterior,
    enabled: Boolean(periodo.desde && periodo.hasta),
  })
  // Solo para llenar el desplegable de áreas (la misma consulta que el tablero).
  const { data: hoy } = useQuery({ queryKey: ['marcaciones', 'dia', ''], queryFn: () => obtenerDia({}), staleTime: 60_000 })
  const areas = hoy?.resumen.por_area.map(a => a.area) ?? []
  const activo = rapidos.find(p => p.desde === periodo.desde && p.hasta === periodo.hasta)?.clave

  async function bajarCsv() {
    setBajando(true); setErrorCsv('')
    try { await descargarCsv({ ...params, ...(soloNovedades ? { solo_novedades: true } : {}) }) }
    catch (e) { setErrorCsv(mensajeDeError(e, 'No se pudo descargar el CSV.')) }
    finally { setBajando(false) }
  }

  return (
    <div className="max-w-5xl mx-auto">
      <div className="print:hidden">
        <button onClick={() => navigate('/marcaciones')}
                className="flex items-center gap-2 text-sm text-texto-2 hover:text-acento-fuerte mb-5 transition">
          ← Volver a Marcaciones
        </button>
        <div className="flex flex-wrap items-start justify-between gap-4 mb-4">
          <div>
            <h1 className="text-xl font-bold text-acento-fuerte">Informe de marcaciones</h1>
            <p className="text-sm text-texto-2 mt-1">
              Llegadas tarde, salidas anticipadas, ausencias y excesos de descanso. PDF tal como se ve, o CSV para Excel.
            </p>
          </div>
          <div className="flex gap-2">
            <Boton tono="secundario" icono={IconoRecibo} cargando={bajando} textoCargando="Descargando…" disabled={!inf} onClick={bajarCsv}>Descargar CSV</Boton>
            <Boton tono="primario" icono={IconoRecibo} disabled={!inf} onClick={() => window.print()}>Descargar PDF</Boton>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-borde p-3 mb-5 flex flex-wrap items-center gap-2">
          <IconoCalendario tam={16} className="text-texto-2 ml-1" />
          {rapidos.map(p => (
            <button key={p.clave} onClick={() => setPeriodo({ desde: p.desde, hasta: p.hasta })}
                    className={`px-3 py-1.5 rounded-lg text-sm font-semibold transition ${activo === p.clave ? 'bg-acento-suave text-acento-fuerte' : 'text-texto-2 hover:bg-superficie-2'}`}>
              {p.etiqueta}
            </button>
          ))}
          <span className="mx-1 h-5 w-px bg-borde" />
          <label className="text-xs text-texto-2" htmlFor="mar-desde">Desde</label>
          <input id="mar-desde" type="date" value={periodo.desde} max={periodo.hasta}
                 onChange={e => setPeriodo(p => ({ ...p, desde: e.target.value }))} className="px-2 py-1.5 rounded-lg border border-borde text-sm" />
          <label className="text-xs text-texto-2" htmlFor="mar-hasta">Hasta</label>
          <input id="mar-hasta" type="date" value={periodo.hasta} min={periodo.desde}
                 onChange={e => setPeriodo(p => ({ ...p, hasta: e.target.value }))} className="px-2 py-1.5 rounded-lg border border-borde text-sm" />
          {areas.length > 1 && (
            <select value={area} onChange={e => setArea(e.target.value)} aria-label="Área" className="px-2 py-1.5 rounded-lg border border-borde text-sm bg-white">
              <option value="">Todas las áreas</option>
              {areas.map(a => <option key={a} value={a}>{a}</option>)}
            </select>
          )}
          <label className="flex items-center gap-1.5 text-sm text-texto-2 ml-2">
            <input type="checkbox" checked={soloNovedades} onChange={e => setSoloNovedades(e.target.checked)} /> CSV solo con días con novedad
          </label>
        </div>
        {errorCsv && <p role="alert" className="text-sm text-negativo mb-3">{errorCsv}</p>}
      </div>

      {isError && !inf && (
        <div role="alert" className="flex items-center gap-2 bg-negativo-bg text-negativo text-sm rounded-xl p-4">
          <IconoAlerta tam={16} /> {mensajeDeError(error, 'No se pudo generar el informe. Intenta de nuevo.')}
        </div>
      )}
      {isError && inf && (
        <p role="alert" className="text-sm text-negativo mb-3 print:hidden">{mensajeDeError(error, 'No se pudo cambiar el periodo.')} Se muestra el anterior.</p>
      )}
      {isLoading && !inf && (
        <div className="space-y-5"><Esqueleto alto="h-24" className="rounded-xl" /><Esqueleto alto="h-56" className="rounded-xl" /></div>
      )}
      {inf && (
        <Atenuado cargando={isFetching}>
          {inf.por_persona.length === 0 ? (
            <div className="bg-white rounded-xl border border-borde p-10 text-center">
              <IconoAlDia tam={26} className="mx-auto mb-3 text-positivo" />
              <p className="text-sm font-semibold text-texto">No hay marcaciones ni turnos en este periodo.</p>
              <p className="text-xs text-texto-2 mt-1">Prueba con otro periodo o con otra área.</p>
            </div>
          ) : <Hoja inf={inf} />}
        </Atenuado>
      )}
    </div>
  )
}
