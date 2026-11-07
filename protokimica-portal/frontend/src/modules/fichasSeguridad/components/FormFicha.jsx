import { useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import Boton from '../../../core/components/Boton.jsx'
import { useCierreSeguro } from '../../../core/components/cierreSeguro.jsx'
import { tieneDatos } from '../../../core/components/tieneDatos.js'
import { IconoAlerta, IconoClip } from '../../../core/components/Iconos.jsx'
import { mensajeDeError } from '../../../core/errores.js'
import { crearFicha, editarFicha, editarVersion, subirVersion } from '../api.js'
import { MAX_CODIGO, MAX_MB, MAX_NOMBRE, MAX_OBSERVACIONES, MAX_VERSION } from '../constants.js'
import { formatoTamano, hoyISO, validarArchivo, validarCampos, versionSugerida } from '../resumen.js'

const TITULOS = {
  crear: 'Nueva ficha de seguridad',
  version: 'Subir una versión nueva',
  editar: 'Corregir la ficha',
  corregir_version: 'Corregir los datos de la versión',
}

const ENTRADA = 'w-full px-3 py-2 rounded-lg border border-borde text-sm bg-superficie'

function valoresIniciales(modo, ficha, version) {
  if (modo === 'corregir_version') {
    return { version: version.version, fecha_emision: version.fecha_emision ?? '', observaciones: version.observaciones ?? '' }
  }
  if (modo === 'editar') return { nombre_producto: ficha.nombre_producto, codigo_producto: ficha.codigo_producto ?? '' }
  if (modo === 'version') return { version: versionSugerida(ficha.versiones), fecha_emision: '', observaciones: '' }
  return { nombre_producto: '', codigo_producto: '', version: '', fecha_emision: '', observaciones: '' }
}

function Campo({ id, etiqueta, ayuda, children }) {
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-semibold text-texto mb-1">{etiqueta}</label>
      {children}
      {ayuda && <p className="text-xs text-texto-3 mt-1">{ayuda}</p>}
    </div>
  )
}

/**
 * Tres formularios en uno, porque comparten casi todo: una ficha nueva
 * (`crear`: producto + su primera versión), una versión nueva de una ficha
 * (`version`), corregir el nombre y el código (`editar`) o corregir el número,
 * la fecha y las observaciones de una versión ya subida (`corregir_version`,
 * sin tocar el PDF: otro documento es otra versión). El servidor repite
 * cada validación; esto solo evita el viaje cuando el error ya se ve.
 */
export default function FormFicha({ modo, ficha, version, onCerrar, onGuardado }) {
  const queryClient = useQueryClient()
  const [inicial] = useState(() => valoresIniciales(modo, ficha, version))
  const [form, setForm] = useState(inicial)
  const [archivo, setArchivo] = useState(null)
  const [error, setError] = useState(null)
  const entradaArchivo = useRef(null)

  const pideArchivo = modo === 'crear' || modo === 'version'
  const hayCambios = tieneDatos(form, inicial) || Boolean(archivo)
  const { intentarCerrar, dialogoDescarte } = useCierreSeguro({ hayCambios, onCerrar })
  const set = (campo) => (e) => setForm({ ...form, [campo]: e.target.value })

  const guardar = useMutation({
    mutationFn: () => {
      if (modo === 'editar') {
        return editarFicha(ficha.id, { nombre_producto: form.nombre_producto, codigo_producto: form.codigo_producto })
      }
      if (modo === 'corregir_version') {
        return editarVersion(version.id, {
          version: form.version.trim(), fecha_emision: form.fecha_emision, observaciones: form.observaciones.trim(),
        })
      }
      return modo === 'version' ? subirVersion(ficha.id, form, archivo) : crearFicha(form, archivo)
    },
    onSuccess: (guardada) => {
      queryClient.invalidateQueries({ queryKey: ['fichas-seguridad'] })
      onGuardado(guardada)
    },
    onError: (err) => setError(mensajeDeError(err, 'No se pudo guardar la ficha. Intenta de nuevo.')),
  })

  const enviar = (e) => {
    e.preventDefault()
    const problema = validarCampos(form, modo) || (pideArchivo ? validarArchivo(archivo) : null)
    if (problema) { setError(problema); return }
    setError(null)
    guardar.mutate()
  }

  // El <input> se limpia al quitar: si no, volver a elegir el mismo archivo no
  // dispara `onChange`.
  const quitarArchivo = () => {
    setArchivo(null)
    if (entradaArchivo.current) entradaArchivo.current.value = ''
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4" onClick={intentarCerrar}>
      <form role="dialog" aria-modal="true" aria-label={TITULOS[modo]} noValidate
            onSubmit={enviar} onClick={(e) => e.stopPropagation()}
            className="w-full max-w-lg max-h-[90vh] overflow-y-auto bg-superficie rounded-2xl shadow-xl p-5 space-y-4">
        <div>
          <h2 className="text-lg font-bold text-acento-fuerte">{TITULOS[modo]}</h2>
          {modo !== 'crear' && (
            <p className="text-xs text-texto-2 mt-0.5">
              {ficha.nombre_producto}{modo === 'corregir_version' ? ` · versión ${version.version}` : ''}
            </p>
          )}
        </div>

        {(modo === 'crear' || modo === 'editar') && (
          <>
            <Campo id="fds-nombre" etiqueta="Producto">
              <input id="fds-nombre" type="text" value={form.nombre_producto} maxLength={MAX_NOMBRE}
                     onChange={set('nombre_producto')} className={ENTRADA} autoFocus />
            </Campo>
            <Campo id="fds-codigo" etiqueta="Código del producto (opcional)"
                   ayuda="El del ERP, si lo tiene. Ayuda a encontrar la ficha en el buscador.">
              <input id="fds-codigo" type="text" value={form.codigo_producto} maxLength={MAX_CODIGO}
                     onChange={set('codigo_producto')} className={ENTRADA} />
            </Campo>
          </>
        )}

        {modo !== 'editar' && (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Campo id="fds-version" etiqueta="Versión" ayuda="Como aparece en el encabezado de la ficha.">
                <input id="fds-version" type="text" value={form.version} maxLength={MAX_VERSION}
                       onChange={set('version')} className={ENTRADA} autoFocus={modo !== 'crear'} />
              </Campo>
              <Campo id="fds-fecha" etiqueta="Fecha de emisión" ayuda="La del encabezado, no la de hoy.">
                <input id="fds-fecha" type="date" value={form.fecha_emision} max={hoyISO()}
                       onChange={set('fecha_emision')} className={ENTRADA} />
              </Campo>
            </div>

            <Campo id="fds-observaciones" etiqueta="Observaciones (opcional)"
                   ayuda="Qué cambió respecto a la versión anterior.">
              <textarea id="fds-observaciones" rows={2} value={form.observaciones} maxLength={MAX_OBSERVACIONES}
                        onChange={set('observaciones')} className={ENTRADA} />
            </Campo>

            {modo === 'corregir_version' ? (
              <p className="text-xs text-texto-3">
                El PDF no se cambia aquí. Si el documento es otro, súbelo como versión nueva: así queda constancia de qué se entregó con cada una.
              </p>
            ) : (
            <div>
              <span className="block text-sm font-semibold text-texto mb-1">Archivo PDF</span>
              <input ref={entradaArchivo} id="fds-archivo" type="file" accept="application/pdf,.pdf" className="sr-only"
                     onChange={(e) => setArchivo(e.target.files?.[0] ?? null)} />
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
              <p className="text-xs text-texto-3 mt-1">Hasta {MAX_MB} MB. Se guarda fuera de lo público: solo se abre desde el portal.</p>
            </div>
            )}
          </>
        )}

        {error && (
          <div role="alert" className="flex items-start gap-2 bg-negativo-bg text-negativo text-sm rounded-xl p-3">
            <IconoAlerta tam={16} className="mt-0.5" /> <span>{error}</span>
          </div>
        )}

        <div className="flex justify-end gap-2 pt-1">
          <Boton tono="fantasma" onClick={intentarCerrar}>Cancelar</Boton>
          <Boton type="submit" tono="primario" cargando={guardar.isPending} textoCargando="Guardando…">
            {modo === 'crear' ? 'Guardar ficha' : modo === 'version' ? 'Subir versión' : 'Guardar cambios'}
          </Boton>
        </div>
      </form>
      {dialogoDescarte}
    </div>
  )
}
