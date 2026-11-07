import { useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import Boton from '../../../core/components/Boton.jsx'
import { useCierreSeguro } from '../../../core/components/cierreSeguro.jsx'
import { tieneDatos } from '../../../core/components/tieneDatos.js'
import { IconoAlerta, IconoClip } from '../../../core/components/Iconos.jsx'
import { mensajeDeError } from '../../../core/errores.js'
import { abrirVistaPrevia, descargarDocumento, extraerDocumento, generarDocumento } from '../api.js'
import { MAX_PARAMETROS, MAX_SECCION, MAX_TEXTO, TIPOS_DOCUMENTO } from '../constants.js'
import {
  datosParaFormulario, datosVacios, formatoTamano, parametroVacio, validarArchivoLectura, validarDocumento,
} from '../resumen.js'

const ENTRADA = 'w-full px-3 py-2 rounded-lg border border-borde text-sm bg-superficie'
const CELDA = 'w-full px-2 py-1.5 rounded-md border border-borde text-xs bg-superficie'

function Campo({ id, etiqueta, children, ancho = '' }) {
  return (
    <div className={ancho}>
      <label htmlFor={id} className="block text-sm font-semibold text-texto mb-1">{etiqueta}</label>
      {children}
    </div>
  )
}

/**
 * Generar un documento oficial a partir del de un proveedor. Tres pasos, en
 * este orden porque la lectura solo PROPONE: elegir (tipo y archivo, o llenar a
 * mano) → revisar y corregir lo leído → generar. Si viene `inicial` (el
 * lote ya leyó el archivo) arranca directo en la revisión.
 *
 * Lo que no se pudo leer se señala arriba, y NADA bloquea generar salvo
 * que falte el producto: igual que en el servidor, que es quien decide.
 */
export default function GenerarDocumento({ inicial, onCerrar, onGenerado }) {
  const queryClient = useQueryClient()
  const [tipo, setTipo] = useState(inicial?.tipo ?? TIPOS_DOCUMENTO[0].clave)
  const [paso, setPaso] = useState(inicial ? 'revisar' : 'elegir')
  const [archivo, setArchivo] = useState(null)
  const [datos, setDatos] = useState(inicial?.datos ?? null)
  const [original] = useState(inicial?.datos ?? null)
  const [faltantes, setFaltantes] = useState(inicial?.faltantes ?? [])
  const [avisos, setAvisos] = useState(inicial?.avisos ?? [])
  const [error, setError] = useState(null)
  const [mirando, setMirando] = useState(false)
  const entradaArchivo = useRef(null)

  const hayCambios = paso === 'revisar' && tieneDatos(datos, original ?? datosVacios(tipo))
  const { intentarCerrar, dialogoDescarte } = useCierreSeguro({ hayCambios, onCerrar })

  const leer = useMutation({
    mutationFn: () => extraerDocumento(tipo, archivo),
    onSuccess: (r) => {
      setDatos(datosParaFormulario(tipo, r.datos))
      setFaltantes(r.faltantes ?? [])
      setAvisos(r.avisos ?? [])
      setError(null)
      setPaso('revisar')
    },
    onError: (err) => setError(mensajeDeError(err, 'No se pudo leer el documento. Intenta de nuevo o llénalo a mano.')),
  })

  const generar = useMutation({
    mutationFn: async () => {
      const documento = await generarDocumento(tipo, datos)
      try { await descargarDocumento(documento) } catch { /* ya quedó en el historial: se baja desde ahí */ }
      return documento
    },
    onSuccess: (documento) => {
      queryClient.invalidateQueries({ queryKey: ['fichas-seguridad'] })
      onGenerado(documento)
    },
    onError: (err) => setError(mensajeDeError(err, 'No se pudo generar el documento. Intenta de nuevo.')),
  })

  const elegirArchivo = (e) => {
    const f = e.target.files?.[0] ?? null
    setArchivo(f)
    setError(f ? validarArchivoLectura(f) : null)
  }
  const quitarArchivo = () => {
    setArchivo(null)
    if (entradaArchivo.current) entradaArchivo.current.value = ''
  }
  const llenarAMano = () => { setDatos(datosVacios(tipo)); setFaltantes([]); setAvisos([]); setError(null); setPaso('revisar') }
  const leerArchivo = () => {
    const problema = validarArchivoLectura(archivo)
    if (problema) { setError(problema); return }
    setError(null)
    leer.mutate()
  }

  const poner = (campo) => (e) => setDatos({ ...datos, [campo]: e.target.value })
  const ponerParametro = (i, campo, valor) =>
    setDatos({ ...datos, parametros: datos.parametros.map((p, j) => (j === i ? { ...p, [campo]: valor } : p)) })
  const ponerSeccion = (i, valor) =>
    setDatos({ ...datos, secciones: datos.secciones.map((s, j) => (j === i ? { ...s, contenido: valor } : s)) })

  const verPrevia = async () => {
    const problema = validarDocumento(datos)
    if (problema) { setError(problema); return }
    setMirando(true)
    setError(null)
    try { await abrirVistaPrevia(tipo, datos) }
    catch (err) { setError(mensajeDeError(err, 'No se pudo armar la vista previa. Intenta de nuevo.')) }
    finally { setMirando(false) }
  }
  const enviar = (e) => {
    e.preventDefault()
    const problema = validarDocumento(datos)
    if (problema) { setError(problema); return }
    setError(null)
    generar.mutate()
  }

  const info = TIPOS_DOCUMENTO.find(t => t.clave === tipo)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4" onClick={intentarCerrar}>
      <form role="dialog" aria-modal="true" aria-label="Generar documento" noValidate onSubmit={enviar}
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-3xl max-h-[92vh] overflow-y-auto bg-superficie rounded-2xl shadow-xl p-5 space-y-4">
        <div>
          <h2 className="text-lg font-bold text-acento-fuerte">
            {paso === 'elegir' ? 'Nuevo documento' : `${info.label} (${info.formato})`}
          </h2>
          {paso === 'revisar' && (
            <p className="text-xs text-texto-2 mt-0.5">
              Revisa lo que leyó la lectura automática y corrige lo que haga falta: tú firmas lo que sale.
            </p>
          )}
        </div>

        {paso === 'elegir' && (
          <>
            <Campo id="doc-tipo" etiqueta="Qué documento quieres generar">
              <select id="doc-tipo" value={tipo} onChange={(e) => setTipo(e.target.value)} className={ENTRADA}>
                {TIPOS_DOCUMENTO.map(t => <option key={t.clave} value={t.clave}>{t.label} ({t.formato})</option>)}
              </select>
              <p className="text-xs text-texto-3 mt-1">{info.ayuda}</p>
            </Campo>

            <div>
              <span className="block text-sm font-semibold text-texto mb-1">Documento del proveedor</span>
              <input ref={entradaArchivo} type="file" className="sr-only" aria-label="Documento del proveedor"
                     accept="application/pdf,.pdf"
                     onChange={elegirArchivo} />
              {archivo ? (
                <div className="flex items-center gap-2 text-sm">
                  <IconoClip tam={16} className="text-texto-3" />
                  <span className="truncate text-texto">{archivo.name}</span>
                  <span className="text-xs text-texto-3 flex-shrink-0">{formatoTamano(archivo.size)}</span>
                  <Boton tam="sm" tono="fantasma" onClick={() => entradaArchivo.current?.click()}>Cambiar</Boton>
                  <Boton tam="sm" tono="fantasma" onClick={quitarArchivo}>Quitar</Boton>
                </div>
              ) : (
                <Boton tam="sm" icono={IconoClip} onClick={() => entradaArchivo.current?.click()}>Elegir PDF</Boton>
              )}
              <p className="text-xs text-texto-3 mt-1">
                Un PDF con texto, hasta 20 MB. El documento no se guarda ni sale del servidor; la lectura no traduce,
                así que revisa lo que trae antes de generar.
              </p>
            </div>
          </>
        )}

        {paso === 'revisar' && datos && (
          <>
            {avisos.length > 0 && (
              <div role="status" className="bg-superficie-2 border border-borde text-texto-2 text-sm rounded-xl p-3 space-y-1">
                {avisos.map(a => <p key={a}>{a}</p>)}
              </div>
            )}
            {faltantes.length > 0 && (
              <div role="status" className="bg-alerta-bg text-alerta text-sm rounded-xl p-3">
                <p className="font-semibold">La lectura no pudo leer:</p>
                <ul className="list-disc pl-5 mt-1">{faltantes.map(f => <li key={f}>{f}</li>)}</ul>
                <p className="mt-1 text-xs">Complétalo a mano si lo necesitas; puedes generar el documento aunque queden vacíos.</p>
              </div>
            )}

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Campo id="doc-producto" etiqueta="Producto">
                <input id="doc-producto" className={ENTRADA} maxLength={200} value={datos.producto} onChange={poner('producto')} autoFocus />
              </Campo>
              <Campo id="doc-codigo" etiqueta="Código (opcional)">
                <input id="doc-codigo" className={ENTRADA} maxLength={40} value={datos.codigo_producto} onChange={poner('codigo_producto')} />
              </Campo>
              <Campo id="doc-proveedor" etiqueta="Proveedor">
                <input id="doc-proveedor" className={ENTRADA} maxLength={200} value={datos.proveedor} onChange={poner('proveedor')} />
              </Campo>
              {tipo === 'certificado_analisis' ? (
                <>
                  <Campo id="doc-lote-pk" etiqueta="Lote Protokimica">
                    <input id="doc-lote-pk" className={ENTRADA} maxLength={100} value={datos.lote_protokimica} onChange={poner('lote_protokimica')} />
                  </Campo>
                  <Campo id="doc-lote-fab" etiqueta="Lote del fabricante">
                    <input id="doc-lote-fab" className={ENTRADA} maxLength={100} value={datos.lote_fabricante} onChange={poner('lote_fabricante')} />
                  </Campo>
                  <Campo id="doc-fab" etiqueta="Fecha de fabricación">
                    <input id="doc-fab" className={ENTRADA} maxLength={40} value={datos.fecha_fabricacion} onChange={poner('fecha_fabricacion')} />
                  </Campo>
                  <Campo id="doc-venc" etiqueta="Fecha de vencimiento">
                    <input id="doc-venc" className={ENTRADA} maxLength={40} value={datos.fecha_vencimiento} onChange={poner('fecha_vencimiento')} />
                  </Campo>
                </>
              ) : (
                <>
                  <Campo id="doc-version" etiqueta="Versión">
                    <input id="doc-version" className={ENTRADA} maxLength={20} value={datos.version} onChange={poner('version')} />
                  </Campo>
                  <Campo id="doc-emision" etiqueta="Fecha de emisión">
                    <input id="doc-emision" className={ENTRADA} maxLength={40} value={datos.fecha_emision} onChange={poner('fecha_emision')} />
                  </Campo>
                </>
              )}
            </div>

            {tipo === 'certificado_analisis' ? (
              <section aria-label="Parámetros">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="font-semibold text-acento-fuerte text-sm">Parámetros ({datos.parametros.length})</h3>
                  <Boton tam="sm" disabled={datos.parametros.length >= MAX_PARAMETROS}
                         onClick={() => setDatos({ ...datos, parametros: [...datos.parametros, parametroVacio()] })}>
                    Agregar parámetro
                  </Boton>
                </div>
                {datos.parametros.length === 0 ? (
                  <p className="text-xs text-texto-3">Sin parámetros. Agrégalos con el botón, o genera el documento sin tabla.</p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="text-left text-texto-2">
                          {['Parámetro', 'Unidad', 'Requisito', 'Método', 'Resultado'].map(h => <th key={h} scope="col" className="pb-1 pr-2 font-semibold">{h}</th>)}
                          <th scope="col" className="pb-1"><span className="sr-only">Quitar</span></th>
                        </tr>
                      </thead>
                      <tbody>
                        {datos.parametros.map((p, i) => (
                          <tr key={i}>
                            {['nombre', 'unidad', 'requisito', 'metodo', 'resultado'].map(c => (
                              <td key={c} className="pr-2 pb-1.5">
                                <input className={CELDA} maxLength={MAX_TEXTO} aria-label={`${c} ${i + 1}`}
                                       value={p[c]} onChange={(e) => ponerParametro(i, c, e.target.value)} />
                              </td>
                            ))}
                            <td className="pb-1.5">
                              <Boton tam="sm" tono="fantasma" onClick={() => setDatos({ ...datos, parametros: datos.parametros.filter((_, j) => j !== i) })}>
                                Quitar
                              </Boton>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>
            ) : (
              <section aria-label="Secciones" className="space-y-3">
                <h3 className="font-semibold text-acento-fuerte text-sm">Secciones de la ficha</h3>
                {datos.secciones.map((s, i) => (
                  <Campo key={s.numero} id={`doc-sec-${s.numero}`} etiqueta={`${s.numero}. ${s.titulo}`}>
                    <textarea id={`doc-sec-${s.numero}`} rows={3} className={ENTRADA} maxLength={MAX_SECCION}
                              value={s.contenido} onChange={(e) => ponerSeccion(i, e.target.value)} />
                  </Campo>
                ))}
              </section>
            )}
          </>
        )}

        {error && (
          <div role="alert" className="flex items-start gap-2 bg-negativo-bg text-negativo text-sm rounded-xl p-3">
            <IconoAlerta tam={16} className="mt-0.5" /> <span>{error}</span>
          </div>
        )}

        <div className="flex flex-wrap justify-end gap-2 pt-1">
          <Boton tono="fantasma" onClick={intentarCerrar}>Cancelar</Boton>
          {paso === 'elegir' ? (
            <>
              <Boton onClick={llenarAMano}>Llenar a mano</Boton>
              <Boton tono="primario" cargando={leer.isPending} textoCargando="Leyendo el documento…" onClick={leerArchivo}>
                Leer documento
              </Boton>
            </>
          ) : (
            <>
              {!inicial && <Boton tono="fantasma" onClick={() => { setPaso('elegir'); setError(null) }}>Volver</Boton>}
              <Boton cargando={mirando} textoCargando="Armando…" onClick={verPrevia}>Vista previa</Boton>
              <Boton type="submit" tono="primario" cargando={generar.isPending} textoCargando="Generando…">
                Generar y descargar
              </Boton>
            </>
          )}
        </div>
      </form>
      {dialogoDescarte}
    </div>
  )
}
