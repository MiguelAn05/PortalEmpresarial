import { useRef, useState } from 'react'
import Boton from '../../../core/components/Boton.jsx'
import { IconoAlerta, IconoClip } from '../../../core/components/Iconos.jsx'
import { Estado } from '../../../core/components/Informe.jsx'
import { mensajeDeError } from '../../../core/errores.js'
import { extraerDocumento } from '../api.js'
import { CONCURRENCIA_LOTE, MAX_LOTE, TIPOS_DOCUMENTO } from '../constants.js'
import {
  datosParaFormulario, ordenarLote, procesarConConcurrencia, recortarLote, validarArchivoLectura,
} from '../resumen.js'
import GenerarDocumento from './GenerarDocumento.jsx'

const ESTADOS = {
  leyendo: { texto: 'Leyendo…', tono: 'neutro' },
  listo: { texto: 'Por revisar', tono: 'alerta' },
  error: { texto: 'Con error', tono: 'negativo' },
  generado: { texto: 'Generado', tono: 'positivo' },
}

/**
 * Hasta 10 documentos de proveedor a la vez, leídos de a 3. Un archivo que
 * falla se marca solo y el resto del lote sigue. Cada uno se REVISA y se
 * genera por separado (la lectura propone; nadie firma sin mirar), y los ya
 * generados bajan al final de la lista.
 */
export default function LoteDocumentos({ onCerrar }) {
  const [tipo, setTipo] = useState(TIPOS_DOCUMENTO[0].clave)
  const [items, setItems] = useState([])
  const [aviso, setAviso] = useState(null)
  const [procesando, setProcesando] = useState(false)
  const [revisando, setRevisando] = useState(null)
  const entrada = useRef(null)

  const actualizar = (id, cambio) => setItems(lista => lista.map(x => (x.id === id ? { ...x, ...cambio } : x)))

  const elegir = async (e) => {
    const { archivos, sobran } = recortarLote(e.target.files)
    if (entrada.current) entrada.current.value = ''
    if (archivos.length === 0) return
    setAviso(sobran > 0 ? `Solo se leen ${MAX_LOTE} documentos por lote: quedaron fuera ${sobran}. Procésalos en otro lote.` : null)
    const nuevos = archivos.map((archivo, i) => ({
      id: `${Date.now()}-${i}`, archivo, tipo, estado: 'leyendo', datos: null, faltantes: [], avisos: [], error: null,
    }))
    setItems(nuevos)
    setProcesando(true)
    await procesarConConcurrencia(nuevos, CONCURRENCIA_LOTE, async (item) => {
      const problema = validarArchivoLectura(item.archivo)
      if (problema) throw new Error(problema)
      const r = await extraerDocumento(item.tipo, item.archivo)
      actualizar(item.id, {
        estado: 'listo', datos: datosParaFormulario(item.tipo, r.datos), faltantes: r.faltantes ?? [], avisos: r.avisos ?? [],
      })
    }, (i, resultado) => {
      if (!resultado.ok) {
        actualizar(nuevos[i].id, {
          estado: 'error', error: mensajeDeError(resultado.error, 'No se pudo leer. Revisa el archivo o genéralo a mano.'),
        })
      }
    })
    setProcesando(false)
  }

  const pendientes = items.filter(x => x.estado !== 'generado').length

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4" onClick={onCerrar}>
      <div role="dialog" aria-modal="true" aria-label="Carga en lote" onClick={(e) => e.stopPropagation()}
           className="w-full max-w-2xl max-h-[90vh] overflow-y-auto bg-superficie rounded-2xl shadow-xl p-5 space-y-4">
        <div>
          <h2 className="text-lg font-bold text-acento-fuerte">Carga en lote</h2>
          <p className="text-xs text-texto-2 mt-0.5">
            Hasta {MAX_LOTE} documentos del mismo tipo, leídos de a {CONCURRENCIA_LOTE}. Si uno falla, los demás siguen.
            Cada uno se revisa y se genera por separado.
          </p>
        </div>

        {items.length === 0 && (
          <div className="space-y-3">
            <select value={tipo} onChange={(e) => setTipo(e.target.value)} aria-label="Tipo de documento"
                    className="w-full px-3 py-2 rounded-lg border border-borde text-sm bg-superficie">
              {TIPOS_DOCUMENTO.map(t => <option key={t.clave} value={t.clave}>{t.label} ({t.formato})</option>)}
            </select>
            <input ref={entrada} type="file" multiple className="sr-only" aria-label="Documentos del proveedor"
                   accept="application/pdf,.pdf" onChange={elegir} />
            <Boton icono={IconoClip} onClick={() => entrada.current?.click()}>Elegir documentos</Boton>
          </div>
        )}

        {aviso && (
          <div role="status" className="bg-alerta-bg text-alerta text-sm rounded-xl p-3">{aviso}</div>
        )}

        {items.length > 0 && (
          <ul className="divide-y divide-borde border border-borde rounded-xl">
            {ordenarLote(items).map(item => (
              <li key={item.id} className="p-3 flex flex-wrap items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-sm text-texto truncate">{item.datos?.producto || item.archivo.name}</p>
                  {item.datos?.producto && <p className="text-xs text-texto-3 truncate">{item.archivo.name}</p>}
                  {item.error && (
                    <p className="text-xs text-negativo flex items-start gap-1 mt-1">
                      <IconoAlerta tam={14} className="mt-0.5" /> {item.error}
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <Estado tono={ESTADOS[item.estado].tono}>{ESTADOS[item.estado].texto}</Estado>
                  {item.estado === 'listo' && <Boton tam="sm" tono="primario" onClick={() => setRevisando(item)}>Revisar</Boton>}
                </div>
              </li>
            ))}
          </ul>
        )}

        <div className="flex justify-end gap-2">
          <Boton tono={pendientes === 0 && items.length > 0 ? 'primario' : 'fantasma'} disabled={procesando} onClick={onCerrar}>
            {items.length === 0 ? 'Cancelar' : 'Finalizar lote'}
          </Boton>
        </div>
      </div>

      {revisando && (
        <GenerarDocumento inicial={{ tipo: revisando.tipo, datos: revisando.datos, faltantes: revisando.faltantes, avisos: revisando.avisos }}
                          onCerrar={() => setRevisando(null)}
                          onGenerado={() => { actualizar(revisando.id, { estado: 'generado' }); setRevisando(null) }} />
      )}
    </div>
  )
}
