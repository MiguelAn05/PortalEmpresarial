import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { useAuth } from '../../core/AuthContext.jsx'
import { RUTA_DE_MODULO } from '../../core/modulos.js'
import {
  IconoAdmin, IconoAlDia, IconoAlerta, IconoChevron, IconoDinero,
  IconoEncuestas, IconoIndicadores, IconoPQRS, IconoProyectos,
  IconoRecargar,
} from '../../core/components/Iconos.jsx'
import { formatMoneda } from '../masterPlanner/constants.js'
import GraficaEjecucion from './components/GraficaEjecucion.jsx'
import { obtenerInicio } from './api.js'
import {
  montoCorto, ordenTarjetas, plazoRelativo, primerNombre, saludo, tonoPendientes,
} from './resumen.js'

const ROLES = {
  admin: 'Administrador',
  gerencia: 'Gerencia',
  lider: 'Líder de área',
  agente: 'Agente',
  lectura: 'Solo lectura',
}

const ACCESOS = {
  pqrs: { Icono: IconoPQRS, titulo: 'PQRS', nota: 'Radicar, responder y cerrar solicitudes' },
  master_planner: { Icono: IconoProyectos, titulo: 'Master Planner', nota: 'Proyectos, tareas y presupuesto' },
  indicadores: { Icono: IconoIndicadores, titulo: 'Indicadores', nota: 'Registrar el mes y ver cómo vamos' },
  encuestas: { Icono: IconoEncuestas, titulo: 'Encuestas', nota: 'Satisfacción del cliente' },
  admin: { Icono: IconoAdmin, titulo: 'Administración', nota: 'Usuarios, áreas y configuración' },
}

const MESES = [
  'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
  'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
]

// Un tono es un estado, y cada estado tiene su borde, su texto y su fondo.
// Están juntos aquí para que nadie combine el rojo de uno con el verde de otro.
const TONOS = {
  positivo: { borde: 'bg-positivo-vivo', texto: 'text-positivo', chip: 'bg-positivo-bg text-positivo' },
  alerta: { borde: 'bg-ambar', texto: 'text-ambar-texto', chip: 'bg-alerta-bg text-alerta' },
  negativo: { borde: 'bg-negativo-vivo', texto: 'text-negativo', chip: 'bg-negativo-bg text-negativo' },
  neutro: { borde: 'bg-borde-fuerte', texto: 'text-texto-2', chip: 'bg-superficie-2 text-texto-3' },
}

// ── Piezas ────────────────────────────────────────────────────

/**
 * La tarjeta base. `destacada` sube un nivel de elevación de forma
 * permanente: así se declara cuál es la pieza principal de la pantalla sin
 * pintarla de otro color.
 */
function Tarjeta({ titulo, icono, extra, tono, destacada = false, children, className = '' }) {
  return (
    <section
      className={`relative overflow-hidden bg-superficie rounded-xl border border-borde
        ${destacada ? 'shadow-md' : 'shadow-sm'} ${className}`}
    >
      {tono && (
        <span
          className={`absolute inset-x-0 top-0 h-[3px] ${TONOS[tono].borde}`}
          aria-hidden="true"
        />
      )}
      {titulo && (
        <header className="flex items-center justify-between gap-3 px-5 py-4 border-b border-borde">
          <h2 className="flex items-center gap-2 text-[15px] font-semibold text-texto min-w-0">
            {icono}
            <span className="truncate">{titulo}</span>
          </h2>
          {extra}
        </header>
      )}
      <div className="p-5">{children}</div>
    </section>
  )
}

/** Punto + texto. El punto no sustituye la palabra: la acompaña. */
function Chip({ tono = 'neutro', children }) {
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-md
      text-[11.5px] font-semibold whitespace-nowrap ${TONOS[tono].chip}`}>
      <span className="w-1.5 h-1.5 rounded-full bg-current flex-shrink-0" aria-hidden="true" />
      {children}
    </span>
  )
}

function Barra({ pct, tono = 'acento' }) {
  const relleno = tono === 'acento' ? 'bg-acento' : TONOS[tono].borde
  return (
    <span className="block h-1.5 rounded-full bg-superficie-2 overflow-hidden">
      <span
        className={`block h-full rounded-full ${relleno}`}
        style={{ width: `${Math.max(0, Math.min(100, pct || 0))}%` }}
      />
    </span>
  )
}

/**
 * Tarjeta de cifra. El contexto no es opcional: un número sin meta, sin
 * comparación y sin estado obliga a preguntar «¿eso es bueno?».
 */
function TarjetaCifra({ etiqueta, valor, Icono, exacto, children }) {
  return (
    <article
      title={exacto}
      className="bg-superficie rounded-xl border border-borde shadow-sm p-5
        transition-shadow duration-150 ease-suave hover:shadow-md"
    >
      <div className="flex items-center justify-between gap-2 mb-3">
        <span className="etiqueta truncate">{etiqueta}</span>
        {Icono && <Icono tam={16} className="text-texto-3" />}
      </div>
      <div className="cifra text-[30px] leading-none font-semibold tracking-tight text-texto">
        {valor}
      </div>
      <div className="mt-3 flex flex-col gap-2 text-xs text-texto-3">{children}</div>
    </article>
  )
}

/** El plazo, siempre con palabras: el color solo no se lee en voz alta. */
function Plazo({ fecha }) {
  const { texto, vencido, urgente } = plazoRelativo(fecha)
  const tono = vencido ? 'negativo' : urgente ? 'alerta' : 'neutro'
  return <Chip tono={tono}>{texto}</Chip>
}

function Fila({ to, titulo, detalle, derecha }) {
  return (
    <Link
      to={to}
      className="group flex items-center gap-3 py-2.5 px-3 -mx-3 rounded-lg
        hover:bg-superficie-2 transition-colors duration-150 ease-suave"
    >
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-medium text-texto truncate">{titulo}</span>
        {detalle && <span className="block text-xs text-texto-3 truncate">{detalle}</span>}
      </span>
      {derecha}
      <IconoChevron
        tam={14}
        className="text-texto-3 opacity-0 group-hover:opacity-100 transition-opacity"
      />
    </Link>
  )
}

function Grupo({ titulo, children }) {
  return (
    <div>
      <div className="etiqueta mb-1">{titulo}</div>
      <div className="divide-y divide-borde">{children}</div>
    </div>
  )
}

function VerTodas({ to, children }) {
  return (
    <Link
      to={to}
      className="inline-flex items-center gap-1 mt-2 text-xs font-medium text-acento
        hover:underline"
    >
      {children}
      <IconoChevron tam={12} />
    </Link>
  )
}

// ── Las cuatro tarjetas ───────────────────────────────────────

/**
 * Lo primero que se ve: qué le toca a esta persona hoy.
 *
 * Va elevada y con borde de color arriba porque es la única pregunta que
 * responde esta pantalla para quien no es gerencia. El conteo por gravedad
 * va en chips, no en un texto corrido: «1 vencida» pesa distinto que «4».
 */
function Pendientes({ inicio }) {
  const { tono, titulo } = tonoPendientes(inicio)
  const { mis_tareas: tareas, mis_pqrs: pqrs, indicadores_por_registrar: indicadores } = inicio
  const vacio = inicio.total_pendiente === 0
  const estaSemana = Math.max(0, (inicio.total_pendiente || 0) - (inicio.total_urgente || 0))

  return (
    <Tarjeta
      tono={tono}
      destacada
      titulo={titulo}
      icono={
        vacio
          ? <IconoAlDia tam={18} className={TONOS[tono].texto} />
          : <IconoAlerta tam={18} className={TONOS[tono].texto} />
      }
      extra={
        !vacio && (
          <span className="flex items-center gap-2 flex-shrink-0">
            {inicio.total_urgente > 0 && (
              <Chip tono="negativo">
                {inicio.total_urgente} {inicio.total_urgente === 1 ? 'vencida' : 'vencidas'}
              </Chip>
            )}
            {estaSemana > 0 && <Chip tono="alerta">{estaSemana} esta semana</Chip>}
          </span>
        )
      }
    >
      {vacio ? (
        <div className="flex items-start gap-3">
          <IconoAlDia tam={20} className="text-positivo mt-0.5" />
          <p className="text-sm text-texto-2">
            No tienes tareas ni PQRS con plazo esta semana. Lo que sigue lo
            encuentras en cada módulo.
          </p>
        </div>
      ) : (
        <div className="space-y-5">
          {tareas.lista.length > 0 && (
            <Grupo titulo={`Mis tareas · ${tareas.abiertas} abiertas`}>
              {tareas.lista.map(t => (
                <Fila
                  key={t.id}
                  to={`/master-planner?tarea=${t.id}`}
                  titulo={t.titulo}
                  detalle={t.proyecto}
                  derecha={<Plazo fecha={t.fecha_fin} />}
                />
              ))}
              {tareas.abiertas > tareas.lista.length && (
                <VerTodas to="/master-planner">Ver mis {tareas.abiertas} tareas</VerTodas>
              )}
            </Grupo>
          )}

          {pqrs.lista.length > 0 && (
            <Grupo titulo={`Mis PQRS · ${pqrs.abiertas} sin cerrar`}>
              {pqrs.lista.map(p => (
                <Fila
                  key={p.id}
                  to={`/pqrs/${p.id}`}
                  titulo={`${p.codigo} — ${p.tipo}`}
                  detalle={p.cliente}
                  derecha={<Plazo fecha={p.fecha_limite_sla} />}
                />
              ))}
              {pqrs.abiertas > pqrs.lista.length && (
                <VerTodas to="/pqrs">Ver mis {pqrs.abiertas} PQRS</VerTodas>
              )}
            </Grupo>
          )}

          {indicadores.length > 0 && (
            <Grupo titulo="Indicadores sin registrar">
              {indicadores.map(i => (
                <Fila
                  key={i.id}
                  to={`/indicadores?indicador=${i.id}`}
                  titulo={i.nombre}
                  derecha={<Chip tono="alerta">falta {MESES[i.mes - 1]} {i.anio}</Chip>}
                />
              ))}
            </Grupo>
          )}
        </div>
      )}
    </Tarjeta>
  )
}

function Accesos({ modulos }) {
  const visibles = modulos.filter(m => m !== 'inicio' && ACCESOS[m])
  if (visibles.length === 0) return null

  return (
    <Tarjeta titulo="Accesos rápidos">
      <div className="grid gap-2 sm:grid-cols-2">
        {visibles.map(m => {
          const { Icono, titulo, nota } = ACCESOS[m]
          return (
            <Link
              key={m}
              to={RUTA_DE_MODULO[m]}
              className="group flex items-start gap-3 p-3 rounded-lg border border-borde
                hover:border-borde-fuerte hover:shadow-sm hover:-translate-y-px
                transition-all duration-150 ease-suave"
            >
              <span className="w-8 h-8 rounded-lg bg-superficie-2 text-texto-2
                flex items-center justify-center flex-shrink-0
                group-hover:bg-acento-suave group-hover:text-acento
                transition-colors duration-150 ease-suave">
                <Icono tam={17} />
              </span>
              <span className="min-w-0">
                <span className="block text-sm font-semibold text-texto">{titulo}</span>
                <span className="block text-xs text-texto-3">{nota}</span>
              </span>
            </Link>
          )
        })}
      </div>
    </Tarjeta>
  )
}

function MiArea({ area }) {
  const vencidas = area.tareas_vencidas_equipo

  return (
    <Tarjeta
      titulo={`Mi área · ${area.area}`}
      extra={<span className="text-xs text-texto-3 flex-shrink-0">{area.personas} personas</span>}
    >
      {/* Tres cifras en fila, separadas por línea: es un bloque, no tres
          tarjetas sueltas dentro de otra tarjeta. */}
      <div className="grid grid-cols-3 divide-x divide-borde -mx-1 mb-5">
        {[
          { etiqueta: 'Proyectos', valor: area.total_proyectos },
          { etiqueta: 'Tareas abiertas', valor: area.tareas_abiertas_equipo },
          {
            etiqueta: 'Vencidas',
            valor: vencidas,
            alerta: vencidas > 0,
          },
        ].map(({ etiqueta, valor, alerta }) => (
          <div key={etiqueta} className="px-3 first:pl-1">
            <div className="etiqueta truncate">{etiqueta}</div>
            <div className={`cifra text-2xl font-semibold mt-1 leading-none
              ${alerta ? 'text-negativo' : 'text-texto'}`}>
              {valor}
            </div>
          </div>
        ))}
      </div>

      {area.proyectos.length === 0 ? (
        <div className="flex items-start gap-3 py-2">
          <IconoProyectos tam={20} className="text-texto-3 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-texto">Tu área no tiene proyectos activos</p>
            <p className="text-xs text-texto-3 mt-0.5">
              Crea el primero en Master Planner para verlo aquí.
            </p>
            <VerTodas to="/master-planner">Ir a Master Planner</VerTodas>
          </div>
        </div>
      ) : (
        <>
          <div className="etiqueta mb-1">Los que menos han avanzado</div>
          <div className="divide-y divide-borde">
            {area.proyectos.map(p => {
              const pct = Math.round(p.avance_pct || 0)
              return (
                <Fila
                  key={p.id}
                  to={`/master-planner?proyecto=${p.id}`}
                  titulo={p.nombre}
                  derecha={
                    <span className="flex items-center gap-2 flex-shrink-0">
                      <span className="w-20 hidden sm:block">
                        <Barra pct={pct} tono={pct < 25 ? 'alerta' : 'acento'} />
                      </span>
                      <span className="cifra text-xs text-texto-2 w-9 text-right">{pct}%</span>
                    </span>
                  }
                />
              )
            })}
          </div>
        </>
      )}
    </Tarjeta>
  )
}

/** Los números de la empresa, en grilla horizontal. Cada uno con su contexto. */
/** Una fila de la tabla de proyectos: nombre, cuándo vence y cómo va. */
function FilaProyecto({ proyecto }) {
  const pct = Math.round(proyecto.avance_pct || 0)
  const { texto, vencido, urgente } = plazoRelativo(proyecto.fecha_fin)

  return (
    <Link
      to={`/master-planner?proyecto=${proyecto.id}`}
      className="group flex items-center gap-3 px-5 py-2.5 hover:bg-superficie-2
        transition-colors duration-150 ease-suave"
    >
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-medium text-texto truncate">
          {proyecto.nombre}
        </span>
        <span className={`block text-xs truncate ${
          vencido ? 'text-negativo font-medium' : urgente ? 'text-alerta' : 'text-texto-3'
        }`}>
          {proyecto.fecha_fin ? texto : 'Sin fecha de entrega'}
        </span>
      </span>
      {/* Barra y cifra juntas: la barra se compara de un vistazo, la cifra se
          lee en voz alta. Una sola de las dos deja a alguien preguntando. */}
      <span className="hidden sm:block w-16 flex-shrink-0">
        <Barra pct={pct} tono={pct < 25 ? 'alerta' : 'acento'} />
      </span>
      <span className="cifra text-xs font-semibold text-texto w-9 text-right flex-shrink-0">
        {pct}%
      </span>
    </Link>
  )
}

/**
 * La portada de gerencia: cuatro cifras, la ejecución del presupuesto mes a
 * mes y qué proyectos están al frente.
 *
 * Cada cifra lleva su contexto pegado —contra el mes pasado, contra la meta o
 * el estado en palabras— porque un número solo obliga a preguntar «¿eso es
 * bueno?», y quien abre esto quiere responderse en tres segundos.
 */
function Empresa({ empresa, area }) {
  const {
    proyectos_activos: activos, proyectos_nuevos_mes: nuevos, proyectos = [],
    pqrs_abiertas: pqrs, pqrs_cerradas_mes: cerradas,
    presupuesto_pagado: pagado, presupuesto_aprobado: aprobado,
    pagado_pct_aprobado: pctAprobado, serie_presupuesto: serie = [],
    indicadores_en_rojo: rojos, indicadores_medidos: medidos,
    indicadores_rojo_anterior: rojosAntes, periodo_indicadores: periodo,
    periodo_anterior: periodoAntes,
  } = empresa

  // El delta se dice en palabras además del color: una flecha sola no se lee
  // en voz alta ni sobrevive a una impresión en blanco y negro.
  const deltaIndicadores = (rojos !== null && rojosAntes !== undefined && rojosAntes !== null)
    ? rojos - rojosAntes
    : null

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-[15px] font-semibold text-texto">Cómo va la empresa</h2>
        <Link
          to="/indicadores"
          className="inline-flex items-center gap-1 text-xs font-medium text-acento hover:underline"
        >
          Ver el detalle
          <IconoChevron tam={12} />
        </Link>
      </div>

      <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 xl:grid-cols-4">
        <TarjetaCifra etiqueta="Proyectos activos" valor={activos} Icono={IconoProyectos}>
          {nuevos > 0
            ? <span>{nuevos} {nuevos === 1 ? 'nuevo' : 'nuevos'} este mes</span>
            : area
              ? <span>{area.total_proyectos} de {area.area}</span>
              : <span>ninguno nuevo este mes</span>}
        </TarjetaCifra>

        <TarjetaCifra etiqueta="PQRS sin cerrar" valor={pqrs} Icono={IconoPQRS}>
          {pqrs > 0
            ? <Chip tono="alerta">Esperan respuesta</Chip>
            : <Chip tono="positivo">Ninguna pendiente</Chip>}
          {cerradas > 0 && (
            <span className="cifra">{cerradas} cerradas este mes</span>
          )}
        </TarjetaCifra>

        <TarjetaCifra
          etiqueta="Presupuesto pagado"
          valor={montoCorto(pagado)}
          Icono={IconoDinero}
          exacto={formatMoneda(pagado)}
        >
          {/* Se mide sobre lo APROBADO, no sobre lo planeado: lo planeado
              puede no aprobarse nunca, y la deuda real es lo aprobado. */}
          {pctAprobado === null || pctAprobado === undefined ? (
            <span>nada aprobado todavía</span>
          ) : (
            <>
              <Barra pct={pctAprobado} />
              <span className="cifra">
                {pctAprobado}% de {montoCorto(aprobado)} aprobados
              </span>
            </>
          )}
        </TarjetaCifra>

        {rojos !== null && (
          <TarjetaCifra etiqueta="Indicadores en rojo" valor={rojos} Icono={IconoIndicadores}>
            {rojos > 0
              ? <Chip tono="negativo">Bajo la meta en {periodo}</Chip>
              : <Chip tono="positivo">Ninguno bajo la meta</Chip>}
            <span className="cifra">
              {medidos > 0 ? `de ${medidos} medidos` : 'sin mediciones este mes'}
              {deltaIndicadores !== null && deltaIndicadores !== 0 && periodoAntes && (
                <span className={deltaIndicadores < 0 ? 'text-positivo' : 'text-negativo'}>
                  {' · '}
                  {deltaIndicadores < 0 ? 'bajó' : 'subió'} {Math.abs(deltaIndicadores)} vs {periodoAntes}
                </span>
              )}
            </span>
          </TarjetaCifra>
        )}
      </div>

      {/* La gráfica pesa más que la tabla porque responde la pregunta cara
          (¿se está ejecutando lo aprobado?); la tabla acompaña. */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-start">
        <section className="lg:col-span-7 bg-superficie rounded-xl border border-borde shadow-sm">
          <header className="flex items-center justify-between gap-3 px-5 py-4 border-b border-borde">
            <h3 className="text-sm font-semibold text-texto">
              Ejecución presupuestal por mes
            </h3>
            <Link
              to="/master-planner"
              className="inline-flex items-center gap-1 text-xs font-medium text-acento
                hover:underline flex-shrink-0"
            >
              Ver el detalle
              <IconoChevron tam={12} />
            </Link>
          </header>
          <div className="py-4">
            <GraficaEjecucion serie={serie} />
          </div>
        </section>

        <section className="lg:col-span-5 bg-superficie rounded-xl border border-borde
          shadow-sm overflow-hidden">
          <header className="flex items-center justify-between gap-3 px-5 py-4 border-b border-borde">
            <h3 className="text-sm font-semibold text-texto">Proyectos al frente</h3>
            <span className="etiqueta flex-shrink-0">Avance</span>
          </header>

          {proyectos.length === 0 ? (
            <div className="flex items-start gap-3 px-5 py-6">
              <IconoProyectos tam={20} className="text-texto-3 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-texto">No hay proyectos activos</p>
                <p className="text-xs text-texto-3 mt-0.5">
                  Los que estén en planeación o en ejecución aparecen aquí, y
                  arriba el que vence primero.
                </p>
              </div>
            </div>
          ) : (
            <div className="divide-y divide-borde">
              {proyectos.map(p => <FilaProyecto key={p.id} proyecto={p} />)}
            </div>
          )}
        </section>
      </div>
    </div>
  )
}


// ── Carga y error ─────────────────────────────────────────────

/** El esqueleto tiene la forma de lo que viene, no es un «Cargando…». */
function Esqueleto() {
  return (
    <div className="max-w-6xl mx-auto space-y-6" aria-busy="true" aria-label="Cargando el inicio">
      <div>
        <div className="esqueleto h-7 w-56" />
        <div className="esqueleto h-4 w-40 mt-2" />
      </div>
      <div className="bg-superficie rounded-xl border border-borde shadow-md p-5 space-y-3">
        <div className="esqueleto h-5 w-64" />
        {[0, 1, 2].map(i => <div key={i} className="esqueleto h-10 w-full" />)}
      </div>
      <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 xl:grid-cols-4">
        {[0, 1, 2, 3].map(i => (
          <div key={i} className="bg-superficie rounded-xl border border-borde shadow-sm p-5">
            <div className="esqueleto h-3 w-24" />
            <div className="esqueleto h-8 w-20 mt-3" />
            <div className="esqueleto h-3 w-28 mt-3" />
          </div>
        ))}
      </div>
    </div>
  )
}

function ErrorInicio({ onReintentar }) {
  return (
    <div className="max-w-6xl mx-auto">
      <Tarjeta tono="negativo">
        <div className="flex items-start gap-3">
          <IconoAlerta tam={20} className="text-negativo mt-0.5" />
          <div className="min-w-0">
            <h2 className="text-[15px] font-semibold text-texto">
              No se pudo cargar el inicio
            </h2>
            <p className="text-sm text-texto-2 mt-1">
              Vuelve a intentarlo. Si sigue igual, entra directo al módulo que
              necesites desde el menú de la izquierda y avísale a un administrador.
            </p>
            <button
              onClick={onReintentar}
              className="inline-flex items-center gap-2 mt-3 h-9 px-4 rounded-lg
                bg-acento-fuerte text-white text-[13px] font-semibold
                hover:bg-acento transition-colors duration-150 ease-suave"
            >
              <IconoRecargar tam={15} />
              Reintentar
            </button>
          </div>
        </div>
      </Tarjeta>
    </div>
  )
}

// ── La página ─────────────────────────────────────────────────

export default function Inicio() {
  const { user } = useAuth()
  const { data: inicio, isLoading, isError, refetch } = useQuery({
    queryKey: ['inicio'],
    queryFn: obtenerInicio,
  })

  if (isLoading) return <Esqueleto />
  if (isError || !inicio) return <ErrorInicio onReintentar={() => refetch()} />

  // Cada bloque dice cuánto ancho ocupa. «Mi área» y «Accesos» quedan
  // pegados en los dos órdenes posibles, así que comparten fila.
  const tarjetas = {
    pendientes: {
      ancho: 'lg:col-span-12',
      nodo: <Pendientes inicio={inicio} />,
    },
    empresa: inicio.empresa && {
      ancho: 'lg:col-span-12',
      nodo: <Empresa empresa={inicio.empresa} area={inicio.mi_area} />,
    },
    area: inicio.mi_area && {
      ancho: 'lg:col-span-6',
      nodo: <MiArea area={inicio.mi_area} />,
    },
    accesos: {
      ancho: 'lg:col-span-6',
      nodo: <Accesos modulos={inicio.modulos} />,
    },
  }

  return (
    <div className="max-w-6xl mx-auto">
      <header className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 mb-6">
        <h1 className="text-2xl font-semibold text-texto">
          {saludo()}, {primerNombre(inicio.usuario.nombre)}
        </h1>
        <p className="text-[13px] text-texto-3">
          {ROLES[inicio.usuario.rol] ?? inicio.usuario.rol}
          {inicio.usuario.area && ` · ${inicio.usuario.area}`}
        </p>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {ordenTarjetas(user)
          .map(nombre => [nombre, tarjetas[nombre]])
          .filter(([, tarjeta]) => tarjeta)
          .map(([nombre, { ancho, nodo }]) => (
            <div key={nombre} className={`col-span-1 ${ancho}`}>{nodo}</div>
          ))}
      </div>
    </div>
  )
}
