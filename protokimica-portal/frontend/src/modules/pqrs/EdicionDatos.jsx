import { useRef, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import api from '../../core/api.js'
import { useCierreSeguro } from '../../core/components/cierreSeguro.jsx'
import {
  IconoCerrar, IconoClip, IconoEditar, IconoPapelera, IconoRecibo,
} from '../../core/components/Iconos.jsx'
import { mensajeDeError } from '../../core/errores.js'
import {
  DEPARTAMENTOS, LIMITES_DATOS, aplicaProducto, cambiosDeDatos,
  datosEditables,
} from './constants.js'

const inputCls = 'w-full px-3 py-2 rounded-lg border border-borde text-sm text-texto placeholder-texto-3 bg-white focus:outline-none focus:ring-2 focus:ring-acento'
const labelCls = 'block text-xs font-semibold text-texto-2 uppercase tracking-wide mb-1'

/** El botón pequeño que va en la cabecera de cada tarjeta corregible. */
export function BotonEditar({ onClick, etiqueta }) {
  return (
    <button
      onClick={onClick}
      aria-label={etiqueta}
      className="inline-flex items-center gap-1 text-xs font-semibold text-acento hover:bg-acento-suave px-2 py-1 rounded-lg transition-colors duration-150"
    >
      <IconoEditar tam={14} /> Editar
    </button>
  )
}

function Campo({ nombre, etiqueta, form, onChange, tipo = 'text', placeholder, autoFocus }) {
  return (
    <div>
      <label htmlFor={`editar-${nombre}`} className={labelCls}>{etiqueta}</label>
      <input
        id={`editar-${nombre}`}
        name={nombre}
        type={tipo}
        value={form[nombre]}
        onChange={onChange}
        maxLength={LIMITES_DATOS[nombre]}
        placeholder={placeholder}
        autoFocus={autoFocus}
        className={inputCls}
      />
    </div>
  )
}

/** Un select que conserva el valor actual aunque no esté en la lista. */
function Lista({ nombre, etiqueta, form, onChange, opciones }) {
  const actual = form[nombre]
  const todas = actual && !opciones.includes(actual) ? [...opciones, actual] : opciones
  return (
    <div>
      <label htmlFor={`editar-${nombre}`} className={labelCls}>{etiqueta}</label>
      <select id={`editar-${nombre}`} name={nombre} value={actual} onChange={onChange} className={inputCls}>
        <option value="">Sin definir</option>
        {todas.map(o => <option key={o} value={o}>{o}</option>)}
      </select>
    </div>
  )
}

/**
 * Corregir los datos del cliente y de la factura.
 *
 * Un solo formulario para las dos tarjetas: quien descubre que el correo está
 * mal casi siempre está revisando todo lo demás a la vez, y dos guardados
 * serían dos eventos en el historial para una sola revisión.
 *
 * Tipo, producto, canal y descripción no están aquí — cada uno tiene su
 * propio camino y se dice en el pie para que nadie los busque.
 */
export function ModalEditarDatos({ pqrs, onCerrar, onGuardado }) {
  const [form, setForm] = useState(() => datosEditables(pqrs))
  const [error, setError] = useState('')

  const cambios = cambiosDeDatos(pqrs, form)
  const cuantos = Object.keys(cambios).length
  const { intentarCerrar, dialogoDescarte } = useCierreSeguro({
    hayCambios: cuantos > 0, onCerrar,
  })

  const guardar = useMutation({
    mutationFn: () => api.patch(`/pqrs/${pqrs.id}/datos`, cambios),
    onSuccess: () => { onGuardado(); onCerrar() },
    onError: (err) => setError(mensajeDeError(err, 'No se pudieron guardar los datos.')),
  })

  const alCambiar = (e) => { setForm({ ...form, [e.target.name]: e.target.value }); setError('') }
  const nombreVacio = !form.cliente_nombre.trim()
  const props = { form, onChange: alCambiar }

  return (
    <div className="fixed inset-0 bg-texto/40 flex items-center justify-center z-50 p-4" onClick={intentarCerrar}>
      <div
        onClick={(e) => e.stopPropagation()}
        className="bg-white rounded-xl shadow-lg w-full max-w-2xl"
        role="dialog"
        aria-labelledby="editar-datos-titulo"
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-borde">
          <div>
            <h2 id="editar-datos-titulo" className="font-bold text-acento-fuerte text-lg">Corregir datos</h2>
            <p className="cifra text-xs text-texto-2 mt-0.5">{pqrs.codigo_seguimiento || `PQRS #${pqrs.id}`}</p>
          </div>
          <button onClick={intentarCerrar} aria-label="Cerrar" className="w-8 h-8 flex items-center justify-center rounded-lg text-texto-3 hover:bg-superficie-2 hover:text-texto transition-colors duration-150">
            <IconoCerrar tam={16} />
          </button>
        </div>

        <div className="p-6 space-y-6 max-h-[70vh] overflow-y-auto">
          <section>
            <p className="text-xs font-bold text-acento-fuerte uppercase tracking-wide mb-3">Datos del cliente</p>
            <div className="grid sm:grid-cols-2 gap-3">
              <Campo nombre="empresa" etiqueta="Empresa / persona" placeholder="Nombre de la empresa o de la persona" autoFocus {...props} />
              <Campo nombre="nit_cedula" etiqueta="NIT / cédula" {...props} />
              <div className="sm:col-span-2">
                <Campo nombre="cliente_nombre" etiqueta="Nombre del contacto *" {...props} />
                {nombreVacio && (
                  <p className="text-xs text-negativo mt-1">El contacto no puede quedar vacío: es a quien se le escribe.</p>
                )}
              </div>
              <Campo nombre="cliente_email" etiqueta="Correo" tipo="email" placeholder="cliente@empresa.com" {...props} />
              <Campo nombre="cliente_telefono" etiqueta="Teléfono" {...props} />
              <Campo nombre="ciudad" etiqueta="Ciudad" {...props} />
              <Lista nombre="departamento" etiqueta="Departamento" opciones={DEPARTAMENTOS} {...props} />
            </div>
          </section>

          {aplicaProducto(pqrs) && (
            <section>
              <p className="text-xs font-bold text-acento-fuerte uppercase tracking-wide mb-3">Factura</p>
              <div className="grid sm:grid-cols-2 gap-3">
                <Campo nombre="factura_numero" etiqueta="N.° de factura" {...props} />
              </div>
            </section>
          )}

          <p className="text-xs text-texto-2 bg-superficie-2 rounded-lg px-3 py-2">
            Cada corrección queda en el historial con el dato anterior, tu nombre y la fecha.
            El tipo se corrige en su propia tarjeta, y el lote y las cantidades en cada
            producto; el canal y la descripción no se cambian porque son lo que el cliente radicó.
          </p>

          {error && <p role="alert" className="text-sm text-negativo">{error}</p>}
        </div>

        <div className="px-6 py-4 border-t border-borde flex items-center justify-between gap-3">
          <span className="cifra text-xs text-texto-2">
            {cuantos === 0 ? 'Sin cambios' : `${cuantos} ${cuantos === 1 ? 'dato cambiado' : 'datos cambiados'}`}
          </span>
          <div className="flex gap-3">
            <button onClick={intentarCerrar} className="px-4 py-2 rounded-lg border border-borde text-sm font-semibold text-texto-2 hover:bg-fondo transition">
              Cancelar
            </button>
            <button
              onClick={() => guardar.mutate()}
              disabled={cuantos === 0 || nombreVacio || guardar.isPending}
              className="px-4 py-2 rounded-lg bg-acento-fuerte hover:bg-acento text-white text-sm font-bold transition disabled:opacity-50"
            >
              {guardar.isPending ? 'Guardando...' : 'Guardar cambios'}
            </button>
          </div>
        </div>
      </div>
      {dialogoDescarte}
    </div>
  )
}

// ── Adjuntos del cliente ────────────────────────────────────────────

// Topes ATADOS a `pqrs/service.py` (MAX_TAMANIO_MB, MAX_TAMANIO_VIDEO_MB y
// sus extensiones). Se revisan antes de subir para no esperar 20 MB de
// subida y enterarse al final de que no pasaba.
const TIPOS_ADJUNTO = {
  producto: { etiqueta: 'Foto del producto', acepta: '.jpg,.jpeg,.png,.webp,.pdf', maxMb: 10 },
  factura:  { etiqueta: 'Factura',           acepta: '.jpg,.jpeg,.png,.webp,.pdf', maxMb: 10 },
  video:    { etiqueta: 'Video de evidencia', acepta: '.mp4,.mov,.webm',           maxMb: 20 },
}
const COLUMNA = { producto: 'adjunto_producto', factura: 'adjunto_factura', video: 'adjunto_video' }

const esImagen = (ruta) => /\.(jpg|jpeg|png|webp)$/i.test(ruta || '')

function Vista({ campo, ruta }) {
  if (campo === 'video') {
    return <video src={ruta} controls className="w-full rounded-lg border border-borde max-h-52" />
  }
  if (esImagen(ruta)) {
    return (
      <a href={ruta} target="_blank" rel="noreferrer">
        <img
          src={ruta}
          alt={TIPOS_ADJUNTO[campo].etiqueta}
          className="w-full rounded-lg border border-borde object-cover max-h-40 hover:opacity-90 transition cursor-pointer"
          onError={(e) => { e.target.style.display = 'none' }}
        />
      </a>
    )
  }
  return (
    <a href={ruta} target="_blank" rel="noreferrer" className="flex items-center gap-2 p-3 bg-fondo rounded-lg hover:bg-borde transition">
      <IconoRecibo tam={20} className="text-texto-2" />
      <span className="text-sm font-medium text-acento underline">Ver archivo adjunto</span>
    </a>
  )
}

/**
 * Un adjunto: se ve, se cambia o se quita.
 *
 * Cambiar sube en cuanto se elige el archivo — un paso de «ahora guarda»
 * aparte es el que se olvida. Quitar sí pregunta, en la misma tarjeta y no
 * en un modal: es una decisión pequeña y se toma mirando el archivo.
 */
function Adjunto({ pqrs, campo, puedeEditar, onCambio }) {
  const ruta = pqrs[COLUMNA[campo]]
  const config = TIPOS_ADJUNTO[campo]
  const [confirmando, setConfirmando] = useState(false)
  const [error, setError] = useState('')
  const entrada = useRef(null)

  const subir = useMutation({
    mutationFn: (archivo) => {
      const datos = new FormData()
      datos.append('archivo', archivo)
      return api.put(`/pqrs/${pqrs.id}/adjuntos/${campo}`, datos)
    },
    onSuccess: () => { setError(''); onCambio() },
    onError: (err) => setError(mensajeDeError(err, 'No se pudo subir el archivo.')),
    onSettled: () => { if (entrada.current) entrada.current.value = '' },
  })

  const quitar = useMutation({
    mutationFn: () => api.delete(`/pqrs/${pqrs.id}/adjuntos/${campo}`),
    onSuccess: () => { setConfirmando(false); setError(''); onCambio() },
    onError: (err) => setError(mensajeDeError(err, 'No se pudo quitar el archivo.')),
  })

  const alElegir = (e) => {
    const archivo = e.target.files?.[0]
    if (!archivo) return
    if (archivo.size > config.maxMb * 1024 * 1024) {
      setError(`El archivo pesa más de ${config.maxMb} MB. Elige uno más liviano.`)
      e.target.value = ''
      return
    }
    subir.mutate(archivo)
  }

  const ocupado = subir.isPending || quitar.isPending

  return (
    <div>
      <div className="flex items-center justify-between gap-2 mb-2">
        <span className="text-xs text-texto-2 font-semibold uppercase tracking-wide">{config.etiqueta}</span>
        {puedeEditar && !confirmando && (
          <div className="flex items-center gap-1">
            <label
              className={`inline-flex items-center gap-1 text-xs font-semibold text-acento px-2 py-1 rounded-lg transition-colors duration-150 ${
                ocupado ? 'opacity-50 cursor-wait' : 'hover:bg-acento-suave cursor-pointer'}`}
            >
              <IconoClip tam={13} />
              {subir.isPending ? 'Subiendo…' : ruta ? 'Cambiar' : 'Adjuntar'}
              <input
                ref={entrada}
                type="file"
                accept={config.acepta}
                onChange={alElegir}
                disabled={ocupado}
                className="sr-only"
              />
            </label>
            {ruta && (
              <button
                onClick={() => setConfirmando(true)}
                disabled={ocupado}
                className="inline-flex items-center gap-1 text-xs font-semibold text-texto-2 hover:text-negativo hover:bg-negativo-bg px-2 py-1 rounded-lg transition-colors duration-150 disabled:opacity-50"
              >
                <IconoPapelera tam={13} /> Quitar
              </button>
            )}
          </div>
        )}
      </div>

      {ruta ? (
        <Vista campo={campo} ruta={ruta} />
      ) : (
        <p className="text-xs text-texto-3 border border-dashed border-borde rounded-lg px-3 py-3 text-center">
          Sin archivo
        </p>
      )}

      {confirmando && (
        <div className="mt-2 rounded-lg border border-negativo/25 bg-negativo-bg p-3">
          <p className="text-sm text-texto">¿Quitar «{config.etiqueta.toLowerCase()}» de esta PQRS?</p>
          <p className="text-xs text-texto-2 mt-0.5">
            Queda anotado en el historial y el archivo se conserva en el servidor por si fue un error.
          </p>
          <div className="flex gap-2 mt-2">
            <button
              onClick={() => setConfirmando(false)}
              className="flex-1 border border-borde bg-white hover:bg-superficie-2 text-texto-2 text-xs font-semibold py-1.5 rounded-lg transition"
            >
              Cancelar
            </button>
            <button
              onClick={() => quitar.mutate()}
              disabled={quitar.isPending}
              autoFocus
              className="flex-1 bg-negativo-vivo hover:bg-negativo text-white text-xs font-bold py-1.5 rounded-lg transition disabled:opacity-50"
            >
              {quitar.isPending ? 'Quitando…' : 'Sí, quitar'}
            </button>
          </div>
        </div>
      )}

      {error && <p role="alert" className="text-xs text-negativo mt-2">{error}</p>}
    </div>
  )
}

/**
 * Los archivos que adjuntó el cliente.
 *
 * Para quien puede editar se muestran también los espacios vacíos: si solo
 * aparecieran los llenos, no habría dónde poner la factura que el cliente
 * olvidó adjuntar y mandó después por WhatsApp.
 */
export function PanelAdjuntos({ pqrs, puedeEditar, onCambio }) {
  const campos = [
    ...(aplicaProducto(pqrs) ? ['producto', 'factura'] : []),
    ...(pqrs.tipo !== 'felicitacion' ? ['video'] : []),
  ].filter(c => puedeEditar || pqrs[COLUMNA[c]])
  // Un adjunto viejo en un tipo que ya no lo pide se sigue mostrando.
  for (const c of Object.keys(COLUMNA)) {
    if (pqrs[COLUMNA[c]] && !campos.includes(c)) campos.push(c)
  }

  if (campos.length === 0) return null

  return (
    <div className="bg-white rounded-xl border border-borde p-5 shadow-sm">
      <h3 className="font-semibold text-acento-fuerte mb-4 text-sm">Evidencias adjuntas</h3>
      <div className="space-y-4">
        {campos.map(campo => (
          <Adjunto key={campo} pqrs={pqrs} campo={campo} puedeEditar={puedeEditar} onCambio={onCambio} />
        ))}
      </div>
    </div>
  )
}
