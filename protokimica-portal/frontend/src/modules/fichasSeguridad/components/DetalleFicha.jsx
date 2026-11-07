import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import Boton from '../../../core/components/Boton.jsx'
import { EsqueletoFilas } from '../../../core/components/Cargando.jsx'
import { IconoAlerta, IconoFicha } from '../../../core/components/Iconos.jsx'
import { Estado } from '../../../core/components/Informe.jsx'
import { mensajeDeError } from '../../../core/errores.js'
import { abrirPdf, editarFicha, eliminarFicha, hacerVigente, obtenerFicha } from '../api.js'
import { formatoFechaEmision, formatoFechaSubida, formatoTamano } from '../resumen.js'
import FormFicha from './FormFicha.jsx'

/**
 * Una ficha con todas sus versiones. La vigente va marcada con palabra y punto
 * y las anteriores se conservan: lo que se entregó a un cliente hace un año
 * tiene que poder consultarse. Todo lo que escribe (subir, volver vigente,
 * corregir, desactivar, borrar) solo se ofrece si `puede`; el servidor lo
 * vuelve a comprobar.
 */
export default function DetalleFicha({ fichaId, puede, onCerrar }) {
  const queryClient = useQueryClient()
  const [formulario, setFormulario] = useState(null)   // 'version' | 'editar' | 'corregir_version' | null
  const [versionACorregir, setVersionACorregir] = useState(null)
  const [error, setError] = useState(null)
  const [abriendo, setAbriendo] = useState(null)
  const [avisoBorrado, setAvisoBorrado] = useState(null)

  const { data: ficha, isLoading, isError, error: errorCarga } = useQuery({
    queryKey: ['fichas-seguridad', 'detalle', fichaId],
    queryFn: () => obtenerFicha(fichaId),
  })

  // Escape cierra el detalle, pero no mientras hay un formulario encima: ese
  // ya tiene su propia protección contra perder lo escrito.
  useEffect(() => {
    if (formulario) return undefined
    const alTeclear = (e) => { if (e.key === 'Escape') onCerrar() }
    window.addEventListener('keydown', alTeclear)
    return () => window.removeEventListener('keydown', alTeclear)
  }, [formulario, onCerrar])

  const refrescar = () => queryClient.invalidateQueries({ queryKey: ['fichas-seguridad'] })
  const fallo = (texto) => (err) => setError(mensajeDeError(err, texto))

  const cambiarEstado = useMutation({
    mutationFn: () => editarFicha(fichaId, { activa: !ficha.activa }),
    onSuccess: () => { setError(null); refrescar() },
    onError: fallo('No se pudo cambiar el estado de la ficha. Intenta de nuevo.'),
  })

  const volverVigente = useMutation({
    mutationFn: (version) => hacerVigente(version.id),
    onSuccess: () => { setError(null); refrescar() },
    onError: fallo('No se pudo dejar esa versión como vigente. Intenta de nuevo.'),
  })

  // Sin confirmar, el servidor responde 409 explicando cuánto se perdería: ese
  // texto es el que se le muestra a la persona, tal cual.
  const borrar = useMutation({
    mutationFn: (confirmado) => eliminarFicha(fichaId, confirmado),
    onSuccess: () => { refrescar(); onCerrar() },
    onError: (err) => {
      if (err?.response?.status === 409) { setError(null); setAvisoBorrado(mensajeDeError(err, '')) }
      else setError(mensajeDeError(err, 'No se pudo borrar la ficha. Intenta de nuevo.'))
    },
  })

  const abrir = async (version) => {
    setAbriendo(version.id)
    setError(null)
    try { await abrirPdf(version) }
    catch (err) { setError(mensajeDeError(err, 'No se pudo abrir el PDF. Intenta de nuevo.')) }
    finally { setAbriendo(null) }
  }

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/30 p-4" onClick={onCerrar}>
      <div role="dialog" aria-modal="true" aria-label={ficha ? `Ficha de ${ficha.nombre_producto}` : 'Ficha de seguridad'}
           onClick={(e) => e.stopPropagation()}
           className="w-full max-w-2xl max-h-[90vh] overflow-y-auto bg-superficie rounded-2xl shadow-xl p-5 space-y-4">
        {isLoading && <EsqueletoFilas filas={4} />}
        {isError && (
          <div role="alert" className="flex items-center gap-2 bg-negativo-bg text-negativo text-sm rounded-xl p-4">
            <IconoAlerta tam={16} /> {mensajeDeError(errorCarga, 'No se pudo abrir la ficha. Intenta de nuevo.')}
          </div>
        )}

        {ficha && (
          <>
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <h2 className="text-lg font-bold text-acento-fuerte break-words">{ficha.nombre_producto}</h2>
                <p className="text-xs text-texto-2 mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-1">
                  <span>{ficha.codigo_producto ? `Código ${ficha.codigo_producto}` : 'Sin código de producto'}</span>
                  <Estado tono={ficha.activa ? 'positivo' : 'neutro'}>{ficha.activa ? 'Activa' : 'Desactivada'}</Estado>
                </p>
              </div>
              <button type="button" onClick={onCerrar} className="text-sm text-texto-2 hover:text-acento-fuerte">Cerrar</button>
            </div>

            {puede && (
              <div className="flex flex-wrap gap-2">
                {ficha.activa && (
                  <Boton tam="sm" tono="primario" icono={IconoFicha} onClick={() => setFormulario('version')}>
                    Subir versión nueva
                  </Boton>
                )}
                <Boton tam="sm" onClick={() => setFormulario('editar')}>Corregir nombre o código</Boton>
                <Boton tam="sm" cargando={cambiarEstado.isPending} onClick={() => cambiarEstado.mutate()}>
                  {ficha.activa ? 'Desactivar' : 'Reactivar'}
                </Boton>
              </div>
            )}

            {error && (
              <div role="alert" className="flex items-start gap-2 bg-negativo-bg text-negativo text-sm rounded-xl p-3">
                <IconoAlerta tam={16} className="mt-0.5" /> <span>{error}</span>
              </div>
            )}

            <section aria-label="Versiones">
              <h3 className="font-semibold text-acento-fuerte text-sm mb-2">
                Versiones ({ficha.total_versiones})
              </h3>
              <ul className="divide-y divide-borde border border-borde rounded-xl">
                {ficha.versiones.map(v => (
                  <li key={v.id} className="p-3 flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0 space-y-0.5">
                      <p className="text-sm text-texto flex flex-wrap items-center gap-x-3 gap-y-1">
                        <span className="font-semibold">Versión {v.version}</span>
                        <Estado tono={v.vigente ? 'positivo' : 'neutro'}>{v.vigente ? 'Vigente' : 'Anterior'}</Estado>
                      </p>
                      <p className="text-xs text-texto-2">
                        Emitida el <span className="cifra">{formatoFechaEmision(v.fecha_emision)}</span>
                        {' · '}{formatoTamano(v.tamano)}
                      </p>
                      <p className="text-xs text-texto-3">
                        Subida{v.subida_por_nombre ? ` por ${v.subida_por_nombre}` : ''} el {formatoFechaSubida(v.subida_en)}
                      </p>
                      {v.observaciones && <p className="text-xs text-texto-2 pt-1">{v.observaciones}</p>}
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Boton tam="sm" cargando={abriendo === v.id} textoCargando="Abriendo…" onClick={() => abrir(v)}>
                        Abrir PDF
                      </Boton>
                      {puede && (
                        <Boton tam="sm" tono="fantasma"
                               onClick={() => { setVersionACorregir(v); setFormulario('corregir_version') }}>
                          Corregir datos
                        </Boton>
                      )}
                      {puede && !v.vigente && (
                        <Boton tam="sm" tono="fantasma" cargando={volverVigente.isPending && volverVigente.variables?.id === v.id}
                               onClick={() => volverVigente.mutate(v)}>
                          Dejar como vigente
                        </Boton>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            </section>

            {puede && (
              <div className="pt-1 border-t border-borde">
                {avisoBorrado ? (
                  <div role="alert" className="mt-3 bg-alerta-bg text-alerta text-sm rounded-xl p-4 space-y-3">
                    <p>{avisoBorrado}</p>
                    <div className="flex flex-wrap gap-2">
                      {ficha.activa && (
                        <Boton tam="sm" tono="primario" cargando={cambiarEstado.isPending}
                               onClick={() => { setAvisoBorrado(null); cambiarEstado.mutate() }}>
                          Mejor desactivarla
                        </Boton>
                      )}
                      <Boton tam="sm" tono="peligro" cargando={borrar.isPending} textoCargando="Borrando…"
                             onClick={() => borrar.mutate(true)}>
                        Sí, borrar todo
                      </Boton>
                      <Boton tam="sm" tono="fantasma" onClick={() => setAvisoBorrado(null)}>Cancelar</Boton>
                    </div>
                  </div>
                ) : (
                  <Boton tam="sm" tono="fantasma" className="mt-3 text-negativo" cargando={borrar.isPending}
                         onClick={() => borrar.mutate(false)}>
                    Eliminar ficha…
                  </Boton>
                )}
              </div>
            )}
          </>
        )}
      </div>

      {formulario && ficha && (
        <FormFicha modo={formulario} ficha={ficha} version={versionACorregir}
                   onCerrar={() => { setFormulario(null); setVersionACorregir(null) }}
                   onGuardado={() => { setFormulario(null); setVersionACorregir(null); setError(null) }} />
      )}
    </div>
  )
}
