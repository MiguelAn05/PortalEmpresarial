import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useAuth } from '../../core/AuthContext.jsx'
import { AREAS } from '../../core/areas.js'
import {
  IconoAlerta, IconoBuscar, IconoIdea, IconoPersonas, IconoReloj,
} from '../../core/components/Iconos.jsx'
import TarjetasKPI from '../../core/components/TarjetasKPI.jsx'
import { listarOportunidades } from './api.js'
import { CICLO, ESTADOS, esEstadoTerminal, estadoDelPlazo } from './constants.js'
import DetalleOportunidad from './components/DetalleOportunidad.jsx'
import FormOportunidad from './components/FormOportunidad.jsx'

/**
 * Oportunidades de Mejora.
 *
 * La pantalla se ordena por lo que está sin terminar: una OMP cerrada ya no
 * pide nada a nadie, así que las abiertas mandan y las cerradas quedan
 * detrás de un filtro. Es la diferencia entre un tablero de trabajo y un
 * archivo.
 */

const TONOS = {
  positivo: 'bg-positivo-bg text-positivo',
  alerta: 'bg-alerta-bg text-alerta',
  negativo: 'bg-negativo-bg text-negativo',
  info: 'bg-info-bg text-info',
  neutro: 'bg-superficie-2 text-texto-2',
}

const PLAZOS = {
  vencida: { texto: 'Vencida', tono: 'negativo' },
  por_vencer: { texto: 'Vence pronto', tono: 'alerta' },
}

function Chip({ tono = 'neutro', children }) {
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-md
      text-[11.5px] font-semibold whitespace-nowrap ${TONOS[tono]}`}>
      <span className="w-1.5 h-1.5 rounded-full bg-current flex-shrink-0" aria-hidden="true" />
      {children}
    </span>
  )
}

function Fila({ omp, onAbrir }) {
  const estado = ESTADOS[omp.estado] ?? ESTADOS.abierta
  const plazo = PLAZOS[estadoDelPlazo(omp)]

  return (
    <button
      onClick={() => onAbrir(omp.id)}
      className="w-full text-left flex items-center gap-3 px-5 py-3 hover:bg-superficie-2
        transition-colors duration-150 ease-suave"
    >
      <span className="min-w-0 flex-1">
        <span className="flex items-center gap-2 flex-wrap">
          <span className="cifra text-xs font-semibold text-texto-3">{omp.codigo}</span>
          <span className="text-sm font-medium text-texto">{omp.titulo}</span>
        </span>
        <span className="block text-xs text-texto-3 mt-0.5 truncate">
          {omp.area || 'Toda la empresa'}
          {omp.autor_nombre && ` · la abrió ${omp.autor_nombre}`}
          {omp.indicador_nombre && ` · ${omp.indicador_nombre}`}
        </span>
      </span>

      {plazo && <Chip tono={plazo.tono}>{plazo.texto}</Chip>}

      {/* El avance del plan, cuando ya hay plan que mostrar. */}
      {omp.total_acciones > 0 && (
        <span className="cifra hidden sm:block text-xs text-texto-2 w-14 text-right flex-shrink-0">
          {omp.acciones_completadas}/{omp.total_acciones}
        </span>
      )}

      <Chip tono={estado.tono}>{estado.label}</Chip>
    </button>
  )
}

export default function Mejora() {
  const { user } = useAuth()
  const [filtros, setFiltros] = useState({ estado: '', area: '', texto: '' })
  const [verCerradas, setVerCerradas] = useState(false)
  const [abierta, setAbierta] = useState(null)
  const [creando, setCreando] = useState(false)

  // Elegir un estado terminal en el filtro manda sobre el interruptor: si
  // alguien pide ver las descartadas, es que quiere verlas. Antes las dos
  // condiciones se anulaban y el filtro devolvía vacío.
  const soloAbiertas = !verCerradas && !esEstadoTerminal(filtros.estado)

  const { data: oportunidades = [], isLoading, isError } = useQuery({
    queryKey: ['omp', { soloAbiertas }],
    queryFn: () => listarOportunidades(soloAbiertas ? { abiertas: true } : {}),
  })

  const puedeCrear = user?.rol === 'admin' || user?.rol === 'lider'

  const visibles = oportunidades.filter(o => (
    (!filtros.estado || o.estado === filtros.estado)
    && (!filtros.area || o.area === filtros.area)
    && (!filtros.texto || `${o.codigo} ${o.titulo} ${o.indicador_nombre || ''}`
      .toLowerCase().includes(filtros.texto.toLowerCase()))
  ))

  const cuenta = (estados) => oportunidades.filter(o => estados.includes(o.estado)).length
  const vencidas = oportunidades.filter(o => estadoDelPlazo(o) === 'vencida').length

  return (
    <div className="max-w-[1400px] mx-auto space-y-6">
      <div className="flex flex-wrap justify-between items-start gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-texto">Oportunidades de mejora</h1>
          <p className="text-sm text-texto-2 mt-1">
            Acciones implementadas para llevar el indicador a su meta, y resultados obtenidos.
          </p>
        </div>
        {puedeCrear && (
          <button
            onClick={() => setCreando(true)}
            className="bg-acento-fuerte hover:bg-acento text-white font-semibold
              px-5 py-2.5 rounded-lg text-sm shadow-xs
              transition-colors duration-150 ease-suave"
          >
            Abrir oportunidad
          </button>
        )}
      </div>

      <TarjetasKPI tarjetas={[
        {
          label: 'Sin terminar', value: cuenta(['abierta', 'analisis', 'ejecucion', 'verificacion']),
          nota: 'en algún punto del ciclo',
        },
        {
          label: 'Sin causa raíz', value: cuenta(['abierta']),
          nota: cuenta(['abierta']) > 0 ? 'falta analizarlas' : 'todas analizadas',
        },
        {
          label: 'Por verificar', value: cuenta(['verificacion']),
          nota: cuenta(['verificacion']) > 0 ? 'esperan comprobación' : 'ninguna pendiente',
        },
        {
          label: 'Vencidas', value: vencidas, alerta: vencidas > 0,
          nota: vencidas > 0 ? 'pasaron su fecha límite' : 'ninguna fuera de plazo',
        },
      ]} />

      {/* Filtros en una sola fila, encima de la lista. */}
      <div className="bg-superficie rounded-xl border border-borde shadow-sm p-4
        flex flex-wrap items-end gap-3">
        <div className="flex-1 min-w-[200px]">
          <label className="etiqueta block mb-1">Buscar</label>
          <div className="relative">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-texto-3">
              <IconoBuscar tam={15} />
            </span>
            <input
              value={filtros.texto}
              onChange={(e) => setFiltros({ ...filtros, texto: e.target.value })}
              placeholder="Código, título o indicador…"
              className="w-full pl-9 pr-3 py-2 rounded-lg border border-borde-fuerte text-sm
                text-texto placeholder-texto-3 focus:outline-none focus:border-acento"
            />
          </div>
        </div>

        <div>
          <label className="etiqueta block mb-1">Estado</label>
          <select
            value={filtros.estado}
            onChange={(e) => setFiltros({ ...filtros, estado: e.target.value })}
            className="rounded-lg border border-borde-fuerte px-3 py-2 text-sm bg-superficie"
          >
            <option value="">Todos</option>
            {[...CICLO, 'descartada'].map(e => (
              <option key={e} value={e}>{ESTADOS[e].label}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="etiqueta block mb-1">Área</label>
          <select
            value={filtros.area}
            onChange={(e) => setFiltros({ ...filtros, area: e.target.value })}
            className="rounded-lg border border-borde-fuerte px-3 py-2 text-sm bg-superficie"
          >
            <option value="">Todas</option>
            {AREAS.map(a => <option key={a} value={a}>{a}</option>)}
          </select>
        </div>

        <label className="flex items-center gap-2 text-sm text-texto-2 py-2">
          <input
            type="checkbox"
            checked={verCerradas}
            onChange={(e) => setVerCerradas(e.target.checked)}
            className="rounded border-borde-fuerte"
          />
          Ver también las cerradas
        </label>
      </div>

      <section className="bg-superficie rounded-xl border border-borde shadow-sm overflow-hidden">
        {isLoading && (
          <p className="px-5 py-10 text-center text-sm text-texto-2">Cargando…</p>
        )}

        {isError && (
          <div className="flex items-start gap-3 px-5 py-8">
            <IconoAlerta tam={20} className="text-negativo mt-0.5" />
            <div>
              <p className="text-sm font-medium text-texto">No se pudieron cargar</p>
              <p className="text-xs text-texto-3 mt-0.5">
                Vuelve a cargar la página; si sigue igual, avísale a un administrador.
              </p>
            </div>
          </div>
        )}

        {!isLoading && !isError && visibles.length === 0 && (
          <div className="flex flex-col items-center text-center px-5 py-12">
            <IconoIdea tam={24} className="text-texto-3 mb-3" />
            <p className="text-sm font-medium text-texto">
              {oportunidades.length === 0
                ? 'Todavía no hay oportunidades de mejora'
                : 'Ninguna coincide con el filtro'}
            </p>
            <p className="text-xs text-texto-3 mt-1 max-w-sm">
              {oportunidades.length === 0
                ? 'Se abren desde un indicador que no cumplió su meta, o desde aquí cuando el origen es otro.'
                : 'Prueba quitando el estado o el área.'}
            </p>
          </div>
        )}

        {visibles.length > 0 && (
          <div className="divide-y divide-borde">
            {visibles.map(omp => (
              <Fila key={omp.id} omp={omp} onAbrir={setAbierta} />
            ))}
          </div>
        )}
      </section>

      {/* Quién la abrió y para cuándo son las dos columnas del Excel que
          usan hoy; se ven en la lista sin tener que entrar a cada una. */}
      {visibles.length > 0 && (
        <p className="flex items-center gap-2 text-xs text-texto-3">
          <IconoPersonas tam={14} />
          {visibles.length} {visibles.length === 1 ? 'oportunidad' : 'oportunidades'}
          {!verCerradas && ' sin terminar'}
          <IconoReloj tam={14} className="ml-2" />
          El plazo se mide contra la fecha límite de cada una.
        </p>
      )}

      {abierta && (
        <DetalleOportunidad ompId={abierta} onCerrar={() => setAbierta(null)} />
      )}

      {creando && (
        <FormOportunidad
          onCerrar={() => setCreando(false)}
          onCreada={(id) => { setCreando(false); setAbierta(id) }}
        />
      )}
    </div>
  )
}
