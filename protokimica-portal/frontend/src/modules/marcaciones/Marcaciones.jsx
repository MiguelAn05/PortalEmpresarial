/**
 * Marcaciones: qué pasa AHORA con las marcaciones del reloj biométrico.
 *
 * El tablero se vuelve a pedir cada 30 s mientras se mira hoy. Los números
 * —quién está adentro, quién llegó tarde, quién es ausente— llegan calculados
 * del servidor (`GET /marcaciones/dia`); aquí solo se filtran y se dibujan.
 * Qué personas aparecen lo decide el servidor según el rol y el área de quien
 * mira: un líder ve la suya y un agente, solo lo propio.
 *
 * Los filtros viven en la URL (`useFiltrosEnUrl`), así que un enlace con
 * «Ausentes» o con una persona abierta se puede mandar por chat.
 */
import { useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { mensajeDeError } from '../../core/errores.js'
import { useFiltrosEnUrl } from '../../core/useFiltrosEnUrl.js'
import TarjetasKPI from '../../core/components/TarjetasKPI.jsx'
import Boton from '../../core/components/Boton.jsx'
import { Atenuado, EsqueletoKPIs, EsqueletoFilas } from '../../core/components/Cargando.jsx'
import { IconoAlerta, IconoRecibo } from '../../core/components/Iconos.jsx'
import { Barras, Seccion } from '../../core/components/Informe.jsx'
import { formatFecha, isoDeHoy } from '../masterPlanner/constants.js'
import { obtenerDia } from './api.js'
import { FILTROS_MARCACIONES, NOVEDADES, SEGUNDOS_ACTUALIZACION, VISTAS } from './constants.js'
import { avisoDeAtraso, contarPorVista, filasDeNovedades, filtrarPersonas, moverDia } from './resumen.js'
import ResumenGrupos from './components/ResumenGrupos.jsx'
import TablaPersonas from './components/TablaPersonas.jsx'
import DetallePersona from './components/DetallePersona.jsx'

export default function Marcaciones() {
  const navigate = useNavigate()
  const [filtros, cambiar, limpiar] = useFiltrosEnUrl(FILTROS_MARCACIONES)
  const { fecha, area, lider, vista, buscar, persona } = filtros
  const hoy = isoDeHoy()
  const dia = fecha || hoy
  const miraHoy = dia === hoy

  const { data, isLoading, isError, error, isFetching, dataUpdatedAt } = useQuery({
    queryKey: ['marcaciones', 'dia', dia],
    queryFn: () => obtenerDia({ fecha: dia }),
    // En vivo solo hoy: un día pasado ya no cambia.
    refetchInterval: miraHoy ? SEGUNDOS_ACTUALIZACION * 1000 : false,
    placeholderData: (anterior) => anterior,
  })

  const personas = useMemo(() => data?.personas ?? [], [data])
  const visibles = useMemo(
    () => filtrarPersonas(personas, { vista, area, lider, buscar }, data?.resumen.por_lider ?? []),
    [personas, vista, area, lider, buscar, data],
  )
  const cuantas = useMemo(() => contarPorVista(personas), [personas])
  const aviso = avisoDeAtraso(data?.estado, data?.es_hoy)
  const t = data?.resumen.totales
  const hayFiltros = area || lider || vista !== 'todos' || buscar

  // Una tarjeta y el desplegable de vista usan la misma función: pulsar la
  // tarjeta activa quita el filtro.
  const elegirVista = (clave) => cambiar({ vista: vista === clave ? 'todos' : clave })

  const tarjetas = t && [
    { label: 'En la empresa', value: t.adentro, nota: `${t.personas} esperadas`, punto: 'positivo',
      onClick: () => elegirVista('adentro'), activa: vista === 'adentro' },
    { label: 'En descanso', value: t.en_descanso, nota: 'break o almuerzo', punto: 'alerta',
      onClick: () => elegirVista('en_descanso'), activa: vista === 'en_descanso' },
    { label: 'Ya salieron', value: t.salio, nota: t.pendiente ? `${t.pendiente} aún sin marcar` : 'todos marcaron', punto: 'neutro',
      onClick: () => elegirVista('salio'), activa: vista === 'salio' },
    { label: 'Ausentes', value: t.ausente, alerta: t.ausente > 0,
      nota: t.ausente ? 'sin marcar pasado su turno' : 'ninguno por ahora', punto: t.ausente ? 'negativo' : 'positivo',
      onClick: () => elegirVista('ausente'), activa: vista === 'ausente' },
    { label: 'Con novedades', value: t.con_novedad, alerta: t.con_novedad > 0,
      nota: t.con_novedad ? `${t.total_novedades} novedades en total` : 'sin novedades', punto: t.con_novedad ? 'negativo' : 'positivo',
      onClick: () => elegirVista('novedades'), activa: vista === 'novedades' },
  ]

  return (
    <div className="max-w-[1400px] mx-auto px-6 py-8 space-y-6">
      <div className="flex flex-wrap justify-between items-start gap-4">
        <div>
          <h1 className="text-3xl font-bold text-acento-fuerte">Marcaciones</h1>
          <p className="text-texto-2 mt-2">
            Lo que marca el reloj biométrico: quién está, quién llegó tarde y quién no ha venido.
          </p>
        </div>
        <Boton tono="primario" icono={IconoRecibo} onClick={() => navigate('/marcaciones/informe')}>
          Informes y descargas
        </Boton>
      </div>

      {/* Fecha */}
      <div className="flex flex-wrap items-center gap-2">
        <Boton tam="sm" onClick={() => cambiar({ fecha: moverDia(dia, -1) })} aria-label="Día anterior">←</Boton>
        <input type="date" value={dia} max={hoy} aria-label="Fecha"
               onChange={(e) => cambiar({ fecha: e.target.value === hoy ? '' : e.target.value })}
               className="px-2 py-1.5 rounded-lg border border-borde text-sm bg-white" />
        <Boton tam="sm" disabled={miraHoy} onClick={() => cambiar({ fecha: moverDia(dia, 1) === hoy ? '' : moverDia(dia, 1) })} aria-label="Día siguiente">→</Boton>
        {!miraHoy && <Boton tam="sm" tono="fantasma" onClick={() => cambiar({ fecha: '' })}>Volver a hoy</Boton>}
        <span className="text-sm font-semibold text-texto ml-2">{formatFecha(dia, { weekday: 'long', day: 'numeric', month: 'long' })}</span>
        {data?.festivo && <span className="text-xs text-alerta bg-alerta-bg rounded-md px-2 py-0.5">Festivo: {data.festivo}</span>}
        {data && miraHoy && (
          <span className="text-xs text-texto-3 ml-auto" aria-live="polite">
            {isFetching ? 'Actualizando…' : `Actualizado a las ${new Date(dataUpdatedAt).toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })}`}
            {' · se renueva solo'}
          </span>
        )}
      </div>

      {aviso && (
        <div role="alert" className="flex items-start gap-2 bg-alerta-bg text-alerta text-sm rounded-xl p-4">
          <IconoAlerta tam={16} className="mt-0.5" /> <span>{aviso}</span>
        </div>
      )}
      {isError && (
        <div role="alert" className="flex items-center gap-2 bg-negativo-bg text-negativo text-sm rounded-xl p-4">
          <IconoAlerta tam={16} /> {mensajeDeError(error, 'No se pudieron cargar las marcaciones. Intenta de nuevo.')}
        </div>
      )}

      {isLoading && !data && (
        <div className="space-y-5"><EsqueletoKPIs cuantas={5} principal={false} /><EsqueletoFilas filas={6} /></div>
      )}

      {data && (
        <Atenuado cargando={isFetching && !miraHoy}>
          <div className="space-y-6">
            {data.futuro ? (
              <p className="bg-white rounded-xl border border-borde p-10 text-center text-sm text-texto-2">Ese día todavía no llega.</p>
            ) : personas.length === 0 ? (
              <div className="bg-white rounded-xl border border-borde p-10 text-center">
                <p className="text-sm font-semibold text-texto">No hay marcaciones ni turnos para mostrar este día.</p>
                <p className="text-xs text-texto-2 mt-1">
                  {data.alcance.tipo === 'propio'
                    ? 'Solo ves tus marcaciones. Si debería haber alguna, pide a Gestión Humana que revise que tu correo esté en la malla.'
                    : 'Puede ser un festivo, un domingo o que la malla aún no se ha cargado.'}
                </p>
              </div>
            ) : (
              <>
                <TarjetasKPI tarjetas={tarjetas} />

                {data.alcance.tipo !== 'propio' && (
                  <ResumenGrupos resumen={data.resumen} area={area} lider={lider}
                                 verLideres
                                 onArea={(a) => cambiar({ area: a })} onLider={(l) => cambiar({ lider: l })} />
                )}

                {t.total_novedades > 0 && (
                  <Seccion titulo="Novedades del día" nota="Cuántas hay de cada tipo.">
                    <Barras unidad="novedades" filas={filasDeNovedades(t, NOVEDADES)} sobre="de las novedades" />
                  </Seccion>
                )}

                <section className="bg-white rounded-xl border border-borde p-5 space-y-4">
                  <div className="flex flex-wrap items-end gap-3">
                    <div>
                      <h3 className="font-semibold text-acento-fuerte text-sm">Personas</h3>
                      <p className="text-xs text-texto-2">{visibles.length} de {personas.length}. Pulsa un nombre para ver sus días.</p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2 ml-auto">
                      <input type="search" value={buscar} placeholder="Buscar por nombre o código" aria-label="Buscar persona"
                             onChange={(e) => cambiar({ buscar: e.target.value })}
                             className="px-3 py-1.5 rounded-lg border border-borde text-sm w-56" />
                      <select value={vista} onChange={(e) => cambiar({ vista: e.target.value })} aria-label="Vista"
                              className="px-2 py-1.5 rounded-lg border border-borde text-sm bg-white">
                        {VISTAS.map(v => <option key={v.clave} value={v.clave}>{v.label} ({cuantas[v.clave]})</option>)}
                      </select>
                      {data.alcance.tipo !== 'propio' && (
                        <select value={area} onChange={(e) => cambiar({ area: e.target.value })} aria-label="Área"
                                className="px-2 py-1.5 rounded-lg border border-borde text-sm bg-white">
                          <option value="">Todas las áreas</option>
                          {data.resumen.por_area.map(a => <option key={a.area} value={a.area}>{a.area}</option>)}
                        </select>
                      )}
                      {hayFiltros && <Boton tam="sm" tono="fantasma" onClick={() => limpiar()}>Quitar filtros</Boton>}
                    </div>
                  </div>
                  <TablaPersonas personas={visibles} onAbrir={(c) => cambiar({ persona: c })} />
                </section>
              </>
            )}
          </div>
        </Atenuado>
      )}

      {persona && <DetallePersona empCode={persona} onCerrar={() => cambiar({ persona: '' })} />}
    </div>
  )
}
