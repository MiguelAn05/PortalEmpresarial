import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import Boton from '../../../core/components/Boton.jsx'
import { Atenuado, EsqueletoFilas } from '../../../core/components/Cargando.jsx'
import { IconoAlerta, IconoFicha } from '../../../core/components/Iconos.jsx'
import { Estado } from '../../../core/components/Informe.jsx'
import { mensajeDeError } from '../../../core/errores.js'
import { descargarDocumento, listarDocumentos } from '../api.js'
import { TIPOS_DOCUMENTO } from '../constants.js'
import { formatoFechaSubida } from '../resumen.js'
import GenerarDocumento from './GenerarDocumento.jsx'
import LoteDocumentos from './LoteDocumentos.jsx'

/**
 * La pestaña «Documentos generados»: el historial de certificados de análisis
 * y fichas que el portal produjo, con su PDF tal como se generó. Quien tiene
 * la capacidad (`puede`) genera uno nuevo o un lote; los demás consultan y
 * bajan.
 */
export default function DocumentosGenerados({ puede, filtros, cambiar, esperado }) {
  const { dq, dtipo } = filtros
  const [generando, setGenerando] = useState(false)
  const [lote, setLote] = useState(false)
  const [bajando, setBajando] = useState(null)
  const [errorPdf, setErrorPdf] = useState(null)

  const { data, isLoading, isError, error, isFetching } = useQuery({
    queryKey: ['fichas-seguridad', 'documentos', esperado, dtipo],
    queryFn: () => listarDocumentos({ q: esperado || undefined, tipo: dtipo || undefined }),
    placeholderData: (anterior) => anterior,
  })
  const documentos = data?.documentos ?? []
  const hayFiltros = dq || dtipo

  const bajar = async (d) => {
    setBajando(d.id)
    setErrorPdf(null)
    try { await descargarDocumento(d) }
    catch (err) { setErrorPdf(mensajeDeError(err, 'No se pudo bajar el PDF. Intenta de nuevo.')) }
    finally { setBajando(null) }
  }

  return (
    <section className="bg-superficie rounded-xl border border-borde p-5 space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <div>
          <h2 className="font-semibold text-acento-fuerte text-sm">Documentos generados</h2>
          <p className="text-xs text-texto-2" aria-live="polite">
            {data ? `${data.total} ${data.total === 1 ? 'documento' : 'documentos'}` : 'Cargando…'}
            {data && data.total > documentos.length ? ` (se muestran los ${documentos.length} más recientes: afina la búsqueda)` : ''}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2 ml-auto">
          <input type="search" value={dq} placeholder="Producto, código, proveedor o lote" aria-label="Buscar documento"
                 onChange={(e) => cambiar({ dq: e.target.value })}
                 className="px-3 py-1.5 rounded-lg border border-borde text-sm w-64 bg-superficie" />
          <select value={dtipo} onChange={(e) => cambiar({ dtipo: e.target.value })} aria-label="Tipo de documento"
                  className="px-2 py-1.5 rounded-lg border border-borde text-sm bg-superficie">
            <option value="">Todos los tipos</option>
            {TIPOS_DOCUMENTO.map(t => <option key={t.clave} value={t.clave}>{t.label}</option>)}
          </select>
          {hayFiltros && <Boton tam="sm" tono="fantasma" onClick={() => cambiar({ dq: '', dtipo: '' })}>Quitar filtros</Boton>}
          {puede && (
            <>
              <Boton tam="sm" onClick={() => setLote(true)}>Carga en lote</Boton>
              <Boton tam="sm" tono="primario" icono={IconoFicha} onClick={() => setGenerando(true)}>Nuevo documento</Boton>
            </>
          )}
        </div>
      </div>

      {isError && (
        <div role="alert" className="flex items-center gap-2 bg-negativo-bg text-negativo text-sm rounded-xl p-4">
          <IconoAlerta tam={16} /> {mensajeDeError(error, 'No se pudo cargar el historial. Intenta de nuevo.')}
        </div>
      )}
      {errorPdf && (
        <div role="alert" className="flex items-center gap-2 bg-negativo-bg text-negativo text-sm rounded-xl p-4">
          <IconoAlerta tam={16} /> {errorPdf}
        </div>
      )}

      {isLoading && !data && <EsqueletoFilas filas={5} />}

      {data && (
        <Atenuado cargando={isFetching}>
          {documentos.length === 0 ? (
            <div className="p-10 text-center">
              <p className="text-sm font-semibold text-texto">
                {hayFiltros ? 'Ningún documento coincide con lo que buscas.' : 'Todavía no se ha generado ningún documento.'}
              </p>
              <p className="text-xs text-texto-2 mt-1">
                {hayFiltros ? 'Prueba con otra palabra o quita los filtros.'
                  : puede ? 'Genera el primero con «Nuevo documento».' : 'Cuando los generen, los verás aquí.'}
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-texto-2 border-b border-borde">
                    <th scope="col" className="py-2 pr-4 font-semibold">Producto</th>
                    <th scope="col" className="py-2 pr-4 font-semibold">Tipo</th>
                    <th scope="col" className="py-2 pr-4 font-semibold">Proveedor</th>
                    <th scope="col" className="py-2 pr-4 font-semibold">Lote / versión</th>
                    <th scope="col" className="py-2 pr-4 font-semibold">Generado</th>
                    <th scope="col" className="py-2 font-semibold"><span className="sr-only">Acciones</span></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-borde">
                  {documentos.map(d => (
                    <tr key={d.id}>
                      <td className="py-2.5 pr-4">
                        <span className="font-semibold text-texto">{d.producto}</span>
                        {d.codigo_producto && <span className="block text-xs text-texto-3">{d.codigo_producto}</span>}
                      </td>
                      <td className="py-2.5 pr-4">
                        <Estado tono="neutro">{TIPOS_DOCUMENTO.find(t => t.clave === d.tipo)?.formato ?? d.tipo}</Estado>
                      </td>
                      <td className="py-2.5 pr-4">{d.proveedor || '—'}</td>
                      <td className="py-2.5 pr-4 cifra">{d.lote || '—'}</td>
                      <td className="py-2.5 pr-4 text-xs text-texto-2">
                        <span className="cifra">{formatoFechaSubida(d.generado_en)}</span>
                        {d.generado_por_nombre && <span className="block text-texto-3">{d.generado_por_nombre}</span>}
                      </td>
                      <td className="py-2.5 text-right">
                        <Boton tam="sm" cargando={bajando === d.id} textoCargando="Bajando…" onClick={() => bajar(d)}>
                          Descargar PDF
                        </Boton>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Atenuado>
      )}

      {generando && <GenerarDocumento onCerrar={() => setGenerando(false)} onGenerado={() => setGenerando(false)} />}
      {lote && <LoteDocumentos onCerrar={() => setLote(false)} />}
    </section>
  )
}
