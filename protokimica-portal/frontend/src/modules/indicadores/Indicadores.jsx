import { useCallback, useMemo, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import TarjetaIndicador from "./components/TarjetaIndicador"
import BarraContexto from "./components/BarraContexto"
import KpisPeriodo from "./components/KpisPeriodo"
import ComoVamos from "./components/ComoVamos"
import ElAno from "./components/ElAno"
import IndicadorDetalle from "./components/IndicadorDetalle"
import { useAbrirDesdeUrl } from "../../core/abrirDesdeUrl.js"
import FormIndicador from "./components/FormIndicador"
import GestionOmpEnAreas from "./components/GestionOmpEnAreas"
import { ChipSemaforo } from "./components/Graficas"
import Boton from "../../core/components/Boton.jsx"
import {
  Atenuado, EsqueletoKPIs, EsqueletoTarjetas,
} from "../../core/components/Cargando.jsx"
import { IconoOjo, IconoRecargar } from "../../core/components/Iconos.jsx"
import { obtenerComoVamos, obtenerTablero, recalcularPeriodo } from "./api"
import { listarUsuariosAsignables } from "../masterPlanner/api"
import { puedeEditar } from "../masterPlanner/constants"
import { useAuth } from "../../core/AuthContext"
import {
  PESTANAS, coincideBusqueda, periodoPorDefecto, periodoAnterior,
  periodoSiguiente, pestanaInicial,
} from "./constants"

/**
 * Indicadores: tres vistas del mismo mes, con un solo contexto.
 *
 * El módulo hace tres cosas y antes las apretaba en dos pestañas que además
 * no compartían estado:
 *
 *   Cómo vamos  — leer el estado de la empresa (gerencial)
 *   Tablero     — registrar y consultar indicador por indicador (operativo)
 *   El año      — la matriz de doce meses, que no cabe en ninguna de las dos
 *
 * **El contexto vive arriba de las pestañas y las gobierna a las tres**: el
 * mes, el alcance, el área y la búsqueda. Antes el mes estaba fuera pero el
 * interruptor empresa/área vivía dentro de una pestaña, así que cambiar de
 * pestaña cambiaba en silencio qué parte de la empresa se estaba mirando.
 *
 * Los cinco conteos también son únicos. Estaban duplicados —una copia en
 * cada pestaña, con rótulos distintos para lo mismo— y dos versiones del
 * mismo número en una pantalla acaban discutiéndose entre sí.
 *
 * Todo el cálculo (semáforo, acumulados, comparaciones, el delta contra el
 * mes pasado) llega resuelto del servidor: aquí solo se presenta.
 */
export default function Indicadores() {
  const queryClient = useQueryClient()
  const { user } = useAuth()
  const editable = puedeEditar(user)

  const [pestana, setPestana] = useState(() => pestanaInicial(user))
  const [periodo, setPeriodo] = useState(periodoPorDefecto)
  const [alcance, setAlcance] = useState('empresa')
  const [area, setArea] = useState("")
  const [busqueda, setBusqueda] = useState("")
  const [filtro, setFiltro] = useState(null)        // semáforo elegido en los KPI
  const [abierto, setAbierto] = useState(null)      // id del indicador en detalle
  const [editando, setEditando] = useState(null)    // null | 'nuevo' | indicador

  // `/indicadores?indicador=7` abre esa ficha directo — así entra quien viene
  // del inicio, que ya sabe cuál le falta por registrar.
  const abrirIndicadorDeUrl = useCallback((id) => {
    setAbierto(id)
    setPestana('tablero')   // al cerrar queda donde se registra
  }, [])
  const { limpiar: limpiarIndicadorDeUrl } = useAbrirDesdeUrl("indicador", abrirIndicadorDeUrl)

  const cerrarIndicador = () => {
    setAbierto(null)
    limpiarIndicadorDeUrl()
  }

  // Una sola consulta alimenta el contexto, los KPI, «Cómo vamos» y «El año».
  // El tablero pide lo suyo aparte porque necesita la ficha completa de cada
  // indicador, que es bastante más de lo que la matriz usa.
  const { data, isLoading, isError, isFetching } = useQuery({
    queryKey: ["ind-como-vamos", periodo.anio, periodo.mes, alcance, area],
    queryFn: () => obtenerComoVamos({
      anio: periodo.anio, mes: periodo.mes, alcance, ...(area && { area }),
    }),
    // Al cambiar de mes se conserva lo anterior mientras llega lo nuevo:
    // reemplazarlo por un esqueleto obliga a esperar para volver a ver algo
    // que ya se estaba leyendo, y hace saltar la página en cada flecha.
    placeholderData: (previa) => previa,
  })

  const { data: tablero, isFetching: cargandoTablero } = useQuery({
    queryKey: ["ind-tablero", periodo.anio, periodo.mes, alcance, area],
    queryFn: () => obtenerTablero({
      anio: periodo.anio, mes: periodo.mes, ...(area && { area }),
    }),
    enabled: pestana === 'tablero',
    placeholderData: (previa) => previa,
  })

  const { data: usuarios = [] } = useQuery({
    queryKey: ["mp-usuarios"],
    queryFn: listarUsuariosAsignables,
  })

  const mutRecalcular = useMutation({
    mutationFn: () => recalcularPeriodo(periodo.anio, periodo.mes),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["ind-tablero"] })
      .then(() => queryClient.invalidateQueries({ queryKey: ["ind-como-vamos"] })),
  })

  const porDefecto = periodoPorDefecto()
  const esUltimoCerrado = periodo.anio === porDefecto.anio && periodo.mes === porDefecto.mes
  const hoy = new Date()
  const esFuturo = periodo.anio > hoy.getFullYear()
    || (periodo.anio === hoy.getFullYear() && periodo.mes >= hoy.getMonth() + 1)

  const moverPeriodo = (hacia) => setPeriodo(
    hacia === 'anterior'
      ? periodoAnterior(periodo.anio, periodo.mes)
      : periodoSiguiente(periodo.anio, periodo.mes),
  )

  // Qué se está mirando, dicho en voz alta: una lista acotada que no avisa
  // que lo está se lee como «en la empresa solo hay estos».
  const resumenAlcance = useMemo(() => {
    if (!data) return null
    const responsables = new Set(
      data.matriz.map(f => f.responsable_nombre).filter(Boolean),
    ).size
    const cuantos = data.matriz.length
    return `${cuantos} indicador${cuantos === 1 ? '' : 'es'} · ${responsables} responsable${responsables === 1 ? '' : 's'}`
  }, [data])

  return (
    <div className="max-w-[1400px] mx-auto space-y-4">

      <header className="flex flex-wrap justify-between items-start gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-acento-fuerte">Indicadores</h1>
          <p className="text-sm text-texto-2 mt-1">Seguimiento de metas, mes a mes.</p>
        </div>
        <div className="flex gap-2 items-center">
          {!editable && (
            <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-texto-2
                             bg-superficie-2 border border-borde rounded-lg px-3 h-9">
              <IconoOjo tam={14} />Modo consulta
            </span>
          )}
          {editable && (
            <>
              <GestionOmpEnAreas />
              <Boton
                onClick={() => mutRecalcular.mutate()}
                cargando={mutRecalcular.isPending}
                textoCargando="Recalculando…"
                icono={IconoRecargar}
                title="Vuelve a calcular todos los indicadores automáticos de este periodo"
              >
                Recalcular automáticos
              </Boton>
              <Boton tono="marca" onClick={() => setEditando('nuevo')}>
                Nuevo indicador
              </Boton>
            </>
          )}
        </div>
      </header>

      <BarraContexto
        periodo={{ ...periodo, esUltimoCerrado }}
        onPeriodo={moverPeriodo}
        onUltimoCerrado={() => setPeriodo(periodoPorDefecto())}
        area={area}
        onArea={setArea}
        areasDisponibles={data?.areas_disponibles || []}
        alcance={alcance}
        onAlcance={setAlcance}
        puedeCambiarAlcance={data?.alcance?.puede_cambiar}
        areaPropia={data?.alcance?.area}
        busqueda={busqueda}
        onBusqueda={setBusqueda}
        resumenAlcance={resumenAlcance}
      />

      <nav className="flex gap-6 border-b border-borde" role="tablist">
        {PESTANAS.map(({ clave, texto }) => (
          <button
            key={clave}
            role="tab"
            aria-selected={pestana === clave}
            onClick={() => setPestana(clave)}
            className={`pb-2.5 -mb-px text-sm border-b-2 transition ${
              pestana === clave
                ? 'border-acento text-texto font-semibold'
                : 'border-transparent text-texto-3 font-medium hover:text-texto-2'
            }`}
          >
            {texto}
            {clave === 'tablero' && data && (
              <span className="ml-2 px-1.5 py-0.5 rounded-full bg-superficie-2 text-texto-3
                               text-[10.5px] font-semibold cifra">
                {data.resumen.total}
              </span>
            )}
          </button>
        ))}
      </nav>

      {esFuturo && (
        <p className="bg-alerta-bg border border-ambar/30 text-alerta text-sm rounded-xl px-4 py-3">
          Este mes todavía no ha cerrado. Lo que veas está incompleto.
        </p>
      )}

      {isError ? (
        <p className="text-center py-16 text-negativo text-sm">
          No se pudieron cargar los indicadores. Revisa tu conexión y vuelve a intentar.
        </p>
      ) : isLoading || !data ? (
        <EsqueletoKPIs />
      ) : (
        <Atenuado cargando={isFetching}>
          <div className="space-y-4">
            <KpisPeriodo resumen={data.resumen} filtro={filtro} onFiltro={setFiltro} />

            {pestana === 'como-vamos' && (
              <ComoVamos
                datos={data}
                periodo={periodo}
                filtro={filtro}
                onFiltro={setFiltro}
                busqueda={busqueda}
                onVerIndicador={(id) => { setPestana('tablero'); setAbierto(id) }}
              />
            )}

            {pestana === 'el-ano' && (
              <ElAno
                matriz={data.matriz}
                anio={periodo.anio}
                busqueda={busqueda}
                onVerIndicador={(id) => { setPestana('tablero'); setAbierto(id) }}
              />
            )}

            {pestana === 'tablero' && (
              <Tablero
                tablero={tablero}
                cargando={cargandoTablero && !tablero}
                area={area}
                busqueda={busqueda}
                filtro={filtro}
                editable={editable}
                onAbrir={setAbierto}
                onCrear={() => setEditando('nuevo')}
              />
            )}
          </div>
        </Atenuado>
      )}

      {abierto && (
        <IndicadorDetalle
          indicadorId={abierto} anio={periodo.anio} mes={periodo.mes}
          editable={editable}
          onEditar={(ficha) => setEditando(ficha)}
          onCerrar={cerrarIndicador}
        />
      )}

      {editando && (
        <FormIndicador
          indicador={editando === 'nuevo' ? null : editando}
          usuarios={usuarios}
          onCerrar={() => setEditando(null)}
          onGuardado={() => setEditando(null)}
        />
      )}
    </div>
  )
}

/**
 * La pestaña operativa: una tarjeta por indicador, para registrar y abrir.
 *
 * Responde al buscador y al semáforo elegido arriba, igual que las otras
 * dos. Un filtro que solo funciona en una pestaña obliga a recordar dónde
 * sirve, y se acaba usando en la que no.
 */
function Tablero({ tablero, cargando, area, busqueda, filtro, editable, onAbrir, onCrear }) {
  const visibles = useMemo(() => {
    const fichas = tablero?.indicadores ?? []
    return fichas
      .filter(f => coincideBusqueda(f, busqueda))
      .filter(f => !filtro || f.semaforo === filtro)
  }, [tablero, busqueda, filtro])

  if (cargando) return <EsqueletoTarjetas />
  if (!tablero) return null

  if (tablero.indicadores.length === 0) {
    return (
      <div className="bg-superficie rounded-xl border border-dashed border-borde p-16 text-center">
        <p className="text-sm text-texto-2 mb-4">
          {area
            ? 'Esta área no tiene indicadores configurados.'
            : 'Todavía no hay indicadores configurados.'}
        </p>
        {editable && !area && (
          <Boton tono="marca" tam="lg" onClick={onCrear}>Crear el primer indicador</Boton>
        )}
      </div>
    )
  }

  if (visibles.length === 0) {
    return (
      <div className="bg-superficie rounded-xl border border-dashed border-borde p-16 text-center">
        <p className="text-sm text-texto-2">
          Ningún indicador coincide con lo que estás filtrando.
        </p>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
      {visibles.map(ficha => (
        <TarjetaIndicador key={ficha.id} ficha={ficha} onAbrir={(f) => onAbrir(f.id)} />
      ))}
    </div>
  )
}

export { ChipSemaforo }
