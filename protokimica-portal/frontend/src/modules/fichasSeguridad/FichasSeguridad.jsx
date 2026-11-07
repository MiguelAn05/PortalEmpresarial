/**
 * Fichas de seguridad: las fichas de datos de seguridad (FDS) de los productos.
 *
 * Cada producto tiene UNA ficha con todas sus versiones; la lista muestra la
 * vigente y de ahí se baja el PDF. Quién es la vigente, cuántas versiones hay y
 * qué ficha coincide con lo que se busca lo calcula el servidor
 * (`GET /fichas-seguridad`, con la búsqueda sin tildes); aquí solo se dibuja.
 *
 * Los filtros viven en la URL (`useFiltrosEnUrl`), incluida la ficha abierta:
 * un enlace con la ficha de un producto se puede mandar por chat.
 */
import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useAuth } from '../../core/useAuth.js'
import { useFiltrosEnUrl } from '../../core/useFiltrosEnUrl.js'
import { mensajeDeError } from '../../core/errores.js'
import Boton from '../../core/components/Boton.jsx'
import { Atenuado, EsqueletoFilas } from '../../core/components/Cargando.jsx'
import { IconoAlerta, IconoFicha } from '../../core/components/Iconos.jsx'
import { Estado } from '../../core/components/Informe.jsx'
import { abrirPdf, listarFichas } from './api.js'
import { ESPERA_BUSQUEDA_MS, ESTADOS_LISTA, FILTROS_FICHAS, VISTAS } from './constants.js'
import { formatoFechaEmision, puedeGestionarFichas } from './resumen.js'
import DetalleFicha from './components/DetalleFicha.jsx'
import FormFicha from './components/FormFicha.jsx'
import DocumentosGenerados from './components/DocumentosGenerados.jsx'

/** El valor, pero solo después de que dejó de cambiar: una petición por pausa al escribir, no por letra. */
function useConEspera(valor, ms) {
  const [esperado, setEsperado] = useState(valor)
  useEffect(() => {
    const t = setTimeout(() => setEsperado(valor), ms)
    return () => clearTimeout(t)
  }, [valor, ms])
  return esperado
}

export default function FichasSeguridad() {
  const { user } = useAuth()
  const puede = puedeGestionarFichas(user)
  const [filtros, cambiar, limpiar] = useFiltrosEnUrl(FILTROS_FICHAS)
  const { buscar, estado, ficha, vista } = filtros
  const documentosEsperado = useConEspera(filtros.dq.trim(), ESPERA_BUSQUEDA_MS)
  const [creando, setCreando] = useState(false)
  const [abriendo, setAbriendo] = useState(null)
  const [errorPdf, setErrorPdf] = useState(null)

  const busqueda = useConEspera(buscar.trim(), ESPERA_BUSQUEDA_MS)
  const { data, isLoading, isError, error, isFetching } = useQuery({
    queryKey: ['fichas-seguridad', 'lista', busqueda, estado],
    queryFn: () => listarFichas({ q: busqueda || undefined, estado }),
    placeholderData: (anterior) => anterior,
  })

  const fichas = data?.fichas ?? []
  const hayFiltros = buscar || estado !== FILTROS_FICHAS.estado

  const abrir = async (version) => {
    setAbriendo(version.id)
    setErrorPdf(null)
    try { await abrirPdf(version) }
    catch (err) { setErrorPdf(mensajeDeError(err, 'No se pudo abrir el PDF. Intenta de nuevo.')) }
    finally { setAbriendo(null) }
  }

  return (
    <div className="max-w-[1400px] mx-auto px-6 py-8 space-y-6">
      <div className="flex flex-wrap justify-between items-start gap-4">
        <div>
          <h1 className="text-3xl font-bold text-acento-fuerte">Fichas de seguridad</h1>
          <p className="text-texto-2 mt-2">
            Las fichas de datos de seguridad (FDS) de los productos, con su versión vigente y el historial de cambios,
            y los certificados de análisis y fichas que el portal genera a partir de los documentos de los proveedores.
          </p>
        </div>
        {puede && vista === 'fichas' && (
          <Boton tono="primario" icono={IconoFicha} onClick={() => setCreando(true)}>Nueva ficha</Boton>
        )}
      </div>

      <div role="tablist" aria-label="Secciones del módulo" className="flex gap-1 border-b border-borde">
        {VISTAS.map(t => (
          <button key={t.clave} type="button" role="tab" aria-selected={vista === t.clave}
                  onClick={() => cambiar({ vista: t.clave })}
                  className={`px-4 py-2 text-sm font-semibold border-b-2 -mb-px ${vista === t.clave
                    ? 'border-acento text-acento-fuerte' : 'border-transparent text-texto-2 hover:text-acento-fuerte'}`}>
            {t.label}
          </button>
        ))}
      </div>

      {vista === 'documentos' && (
        <DocumentosGenerados puede={puede} filtros={filtros} cambiar={cambiar} esperado={documentosEsperado} />
      )}

      {vista === 'fichas' && (
      <section className="bg-superficie rounded-xl border border-borde p-5 space-y-4">
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <h2 className="font-semibold text-acento-fuerte text-sm">Fichas</h2>
            <p className="text-xs text-texto-2" aria-live="polite">
              {data ? `${data.total} ${data.total === 1 ? 'ficha' : 'fichas'}` : 'Cargando…'}
              {'. Pulsa un producto para ver sus versiones.'}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2 ml-auto">
            <input type="search" value={buscar} placeholder="Buscar por producto o código" aria-label="Buscar ficha"
                   onChange={(e) => cambiar({ buscar: e.target.value })}
                   className="px-3 py-1.5 rounded-lg border border-borde text-sm w-64 bg-superficie" />
            <select value={estado} onChange={(e) => cambiar({ estado: e.target.value })} aria-label="Estado de la ficha"
                    className="px-2 py-1.5 rounded-lg border border-borde text-sm bg-superficie">
              {ESTADOS_LISTA.map(e => <option key={e.clave} value={e.clave}>{e.label}</option>)}
            </select>
            {hayFiltros && <Boton tam="sm" tono="fantasma" onClick={() => limpiar()}>Quitar filtros</Boton>}
          </div>
        </div>

        {isError && (
          <div role="alert" className="flex items-center gap-2 bg-negativo-bg text-negativo text-sm rounded-xl p-4">
            <IconoAlerta tam={16} /> {mensajeDeError(error, 'No se pudieron cargar las fichas. Intenta de nuevo.')}
          </div>
        )}
        {errorPdf && (
          <div role="alert" className="flex items-center gap-2 bg-negativo-bg text-negativo text-sm rounded-xl p-4">
            <IconoAlerta tam={16} /> {errorPdf}
          </div>
        )}

        {isLoading && !data && <EsqueletoFilas filas={6} />}

        {data && (
          <Atenuado cargando={isFetching}>
            {fichas.length === 0 ? (
              <div className="p-10 text-center">
                <p className="text-sm font-semibold text-texto">
                  {hayFiltros ? 'Ninguna ficha coincide con lo que buscas.' : 'Todavía no hay fichas de seguridad.'}
                </p>
                <p className="text-xs text-texto-2 mt-1">
                  {hayFiltros
                    ? 'Prueba con otra palabra o quita los filtros: la búsqueda ignora tildes y mayúsculas.'
                    : puede
                      ? 'Sube la primera con «Nueva ficha».'
                      : 'Cuando las suban, las verás aquí. Si necesitas subirlas, pide la capacidad a un administrador.'}
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-texto-2 border-b border-borde">
                      <th scope="col" className="py-2 pr-4 font-semibold">Producto</th>
                      <th scope="col" className="py-2 pr-4 font-semibold">Versión vigente</th>
                      <th scope="col" className="py-2 pr-4 font-semibold">Emitida</th>
                      <th scope="col" className="py-2 pr-4 font-semibold">Versiones</th>
                      <th scope="col" className="py-2 pr-4 font-semibold">Estado</th>
                      <th scope="col" className="py-2 font-semibold"><span className="sr-only">Acciones</span></th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-borde">
                    {fichas.map(f => (
                      <tr key={f.id}>
                        <td className="py-2.5 pr-4">
                          <button type="button" onClick={() => cambiar({ ficha: String(f.id) })}
                                  className="text-left font-semibold text-acento hover:underline">
                            {f.nombre_producto}
                          </button>
                          {f.codigo_producto && <span className="block text-xs text-texto-3">{f.codigo_producto}</span>}
                        </td>
                        <td className="py-2.5 pr-4 cifra">{f.vigente ? f.vigente.version : '—'}</td>
                        <td className="py-2.5 pr-4 cifra">{formatoFechaEmision(f.vigente?.fecha_emision)}</td>
                        <td className="py-2.5 pr-4 cifra">{f.total_versiones}</td>
                        <td className="py-2.5 pr-4">
                          <Estado tono={f.activa ? 'positivo' : 'neutro'}>{f.activa ? 'Activa' : 'Desactivada'}</Estado>
                        </td>
                        <td className="py-2.5 text-right">
                          {f.vigente ? (
                            <Boton tam="sm" cargando={abriendo === f.vigente.id} textoCargando="Abriendo…"
                                   onClick={() => abrir(f.vigente)}>
                              Abrir PDF
                            </Boton>
                          ) : <span className="text-xs text-texto-3">Sin versión vigente</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Atenuado>
        )}
      </section>
      )}

      {vista === 'fichas' && ficha && (
        <DetalleFicha fichaId={Number(ficha)} puede={puede} onCerrar={() => cambiar({ ficha: '' })} />
      )}
      {creando && (
        <FormFicha modo="crear" onCerrar={() => setCreando(false)}
                   onGuardado={(nueva) => { setCreando(false); cambiar({ ficha: String(nueva.id) }) }} />
      )}
    </div>
  )
}
