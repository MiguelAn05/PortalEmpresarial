import { useMemo, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../../core/api.js'
import { AREAS } from '../../core/areas.js'
import { CANALES, canalesConPrefijo } from '../../core/canales.js'
import TarjetasKPI from '../../core/components/TarjetasKPI.jsx'
import {
  IconoBuscar, IconoCerrar, IconoClip, IconoEmpresa, IconoFiltro, IconoPapelera, IconoPQRS,
} from '../../core/components/Iconos.jsx'
import { mensajeDeError } from '../../core/errores.js'
import {
  AREA_SIN_ASIGNAR, DEPARTAMENTOS, LIMITES_RADICACION, MAX_PRODUCTOS, PRESENTACIONES,
  areasParaFiltrar, coincideAreaAsignada, contarPorFoco, cumpleFoco, estadoDelPlazo,
  faltaEnProductos, nombrePrincipal, productoVacio, productosParaEnviar,
} from './constants.js'

// Un estado se llama y se pinta igual en la lista, en el filtro y en el
// detalle. El color sube con la gravedad; no es un color por categoría.
const TIPOS = {
  peticion:     { label: 'Petición',     color: 'bg-superficie-2 text-texto-2' },
  queja:        { label: 'Queja',        color: 'bg-alerta-bg text-alerta'     },
  reclamo:      { label: 'Reclamo',      color: 'bg-negativo-bg text-negativo' },
  sugerencia:   { label: 'Sugerencia',   color: 'bg-info-bg text-info'         },
  felicitacion: { label: 'Felicitación', color: 'bg-positivo-bg text-positivo' },
}

const ESTADOS = {
  recibido:   { label: 'Recibido',   color: 'bg-superficie-2 text-texto-2' },
  asignado:   { label: 'Asignado',   color: 'bg-info-bg text-info'         },
  en_proceso: { label: 'En proceso', color: 'bg-alerta-bg text-alerta'     },
  resuelto:   { label: 'Resuelto',   color: 'bg-positivo-bg text-positivo' },
  cerrado:    { label: 'Cerrado',    color: 'bg-superficie-2 text-texto-2' },
}

const PRIORIDADES = {
  baja:    { label: 'Baja',    color: 'text-positivo' },
  media:   { label: 'Media',   color: 'text-texto-2'  },
  alta:    { label: 'Alta',    color: 'text-alerta'   },
  critica: { label: 'Crítica', color: 'text-negativo' },
}

// Sale de core/canales.js, gemelo de core/canales.py: se usa para filtrar
// por punto de venta a partir del prefijo del radicado.
const PUNTOS_VENTA = canalesConPrefijo()

// Compara el prefijo exacto del radicado (evita que "PVC" matchee "PVCR0010")
function coincidePuntoVenta(codigo, prefijo) {
  if (!codigo) return false
  return new RegExp(`^${prefijo}\\d+$`).test(codigo)
}

function Badge({ map, value }) {
  const item = map[value] || { label: value, color: 'bg-superficie-2 text-texto-2' }
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold ${item.color}`}>
      {item.label}
    </span>
  )
}

const TONO_PLAZO = {
  negativo: 'text-negativo font-semibold',
  alerta: 'text-alerta font-semibold',
  neutro: 'text-texto-2',
}

/**
 * Cuánto le queda de plazo, o una raya cuando ya no hay plazo que contar.
 *
 * Recibe la PQRS entera y no solo la fecha: **el estado es parte de la
 * cuenta.** Con la fecha sola, una PQRS cerrada hace meses seguía contra el
 * reloj del calendario y aparecía «Vencida» para siempre. La regla vive en
 * `estadoDelPlazo()` del `constants.js` del módulo, que es gemelo de la del
 * servidor y tiene prueba.
 */
function SLALabel({ pqrs }) {
  const plazo = estadoDelPlazo(pqrs)
  if (!plazo) return <span className="text-xs text-texto-3">—</span>

  return (
    <span className={`cifra text-xs ${TONO_PLAZO[plazo.tono]}`}>{plazo.texto}</span>
  )
}

const CANALES_ATENCION = CANALES
const CANALES_ATENCION_FELICITACION = CANALES

const AREAS_PQRS = AREAS

/**
 * Un archivo elegido antes de enviar: se ve cuál es y se puede quitar.
 *
 * El `<input type="file">` suelto no deja quitar lo elegido — solo elegir
 * otro —, así que quien adjuntaba la foto equivocada tenía que cerrar el
 * formulario y empezar de nuevo, o mandarla igual.
 */
function ArchivoElegido({ etiqueta, acepta, ayuda, archivo, onCambio }) {
  const entrada = useRef(null)
  const labelCls = 'block text-xs font-semibold text-texto-2 uppercase tracking-wide mb-1.5'

  const quitar = () => {
    onCambio(null)
    // Sin esto, volver a elegir el mismo archivo no dispara `onChange`.
    if (entrada.current) entrada.current.value = ''
  }

  return (
    <div>
      <span className={labelCls}>{etiqueta}</span>
      {archivo ? (
        <div className="flex items-center gap-2 rounded-lg border border-positivo/30 bg-positivo-bg px-3 py-2">
          <IconoClip tam={14} className="text-positivo" />
          <span className="text-xs text-texto truncate flex-1" title={archivo.name}>{archivo.name}</span>
          <span className="cifra text-xs text-texto-3">{(archivo.size / 1024 / 1024).toFixed(1)} MB</span>
          <button
            type="button"
            onClick={quitar}
            aria-label={`Quitar ${etiqueta.toLowerCase()}`}
            className="inline-flex items-center gap-1 text-xs font-semibold text-texto-2 hover:text-negativo px-1.5 py-0.5 rounded transition-colors duration-150"
          >
            <IconoPapelera tam={13} /> Quitar
          </button>
        </div>
      ) : (
        <input
          ref={entrada}
          type="file"
          accept={acepta}
          onChange={(e) => onCambio(e.target.files?.[0] || null)}
          className="w-full text-xs text-texto-2 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-acento-suave file:text-acento hover:file:bg-borde"
        />
      )}
      {ayuda && <p className="text-xs text-texto-3 mt-1">{ayuda}</p>}
    </div>
  )
}

// ── Modal para crear PQRS ──────────────────────────────────────────
// Mismos campos que el formulario público (/formulario), para que una
// PQRS registrada por un agente interno guarde exactamente la misma
// información que una radicada por el cliente.
// `canalInicial`: una sede registra casi siempre lo que pasó en su mostrador,
// así que arranca marcado. Si no, radicaría sin canal, el caso saldría
// `PK-…` y desaparecería de su propia lista al guardarlo.
function ModalCrear({ onClose, onCreated, canalInicial = '' }) {
  const FORM_VACIO = {
    tipo: 'queja',
    empresa: '',
    nit_cedula: '',
    cliente_nombre: '',
    cliente_email: '',
    cliente_telefono: '',
    ciudad: '',
    departamento: '',
    canal_atencion: canalInicial,
    factura_numero: '',
    area_responsable: '',
    descripcion: '',
  }
  const [form, setForm] = useState(FORM_VACIO)
  // Uno o varios productos, cada uno con su lote y cantidades.
  const [productos, setProductos] = useState(() => [productoVacio()])
  const [adjuntoProducto, setAdjuntoProducto] = useState(null)
  const [adjuntoFactura, setAdjuntoFactura]   = useState(null)
  const [adjuntoVideo, setAdjuntoVideo]       = useState(null)
  const [error, setError] = useState('')

  // Una felicitación no necesita producto/factura/lote — solo el canal
  // por el que llegó y un comentario opcional. Una queja tampoco, porque
  // es sobre el servicio (ej: "me atendieron mal"), no sobre un producto.
  // Mismo criterio que el formulario público.
  const esFelicitacion = form.tipo === 'felicitacion'
  const esQueja = form.tipo === 'queja'
  const mostrarProducto = !esFelicitacion && !esQueja

  const mutation = useMutation({
    mutationFn: () => {
      const formData = new FormData()
      Object.entries(form).forEach(([key, value]) => formData.append(key, value ?? ''))
      // Lo que está escondido no viaja: si alguien llenó un producto y luego
      // cambió el tipo a queja, ese producto no es parte de la queja.
      if (mostrarProducto) {
        formData.append('productos', JSON.stringify(productosParaEnviar(productos)))
        if (adjuntoProducto) formData.append('adjunto_producto', adjuntoProducto)
        if (adjuntoFactura)  formData.append('adjunto_factura', adjuntoFactura)
      }
      if (adjuntoVideo && !esFelicitacion) formData.append('adjunto_video', adjuntoVideo)
      return api.post('/pqrs', formData, { headers: { 'Content-Type': 'multipart/form-data' } })
    },
    onSuccess: () => { onCreated(); onClose() },
    onError: (err) => setError(mensajeDeError(err, 'Error al crear la PQRS')),
  })

  const handleChange = (e) => { setForm({ ...form, [e.target.name]: e.target.value }); setError('') }
  const cambiarProducto = (clave, e) => {
    const { name, value } = e.target
    setProductos(lista => lista.map(p => (p.clave === clave ? { ...p, [name]: value } : p)))
    setError('')
  }
  // Internamente no se exige producto (una PQRS por teléfono se escribe con
  // lo que el cliente sabe), pero sí que ninguna fila quede a medio llenar.
  const faltaProducto = mostrarProducto ? faltaEnProductos(productos) : null
  const filaIncompleta = Boolean(faltaProducto) && faltaProducto.startsWith('Producto')

  const inputCls = "w-full px-3 py-2.5 rounded-lg border border-borde text-sm text-texto placeholder-texto-3 focus:outline-none focus:ring-2 focus:ring-acento"
  const labelCls = "block text-xs font-semibold text-texto-2 uppercase tracking-wide mb-1.5"

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-2xl">
        <div className="flex items-center justify-between px-6 py-4 border-b border-borde">
          <div>
            <h2 className="font-bold text-acento-fuerte text-lg">Registrar PQRS</h2>
            <p className="text-xs text-texto-2 mt-0.5">Mismos datos que el formulario público del cliente.</p>
          </div>
          <button onClick={onClose} aria-label="Cerrar" className="w-8 h-8 flex items-center justify-center rounded-lg text-texto-3 hover:bg-superficie-2 hover:text-texto transition-colors duration-150"><IconoCerrar tam={16} /></button>
        </div>

        <div className="p-6 space-y-5 max-h-[70vh] overflow-y-auto">

          {/* Tipo y área */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={labelCls}>Tipo *</label>
              <select name="tipo" value={form.tipo} onChange={handleChange} className={inputCls}>
                <option value="peticion">Petición</option>
                <option value="queja">Queja</option>
                <option value="reclamo">Reclamo</option>
                <option value="sugerencia">Sugerencia</option>
                <option value="felicitacion">Felicitación</option>
              </select>
            </div>
            <div>
              <label className={labelCls}>Área responsable</label>
              <select name="area_responsable" value={form.area_responsable} onChange={handleChange} className={inputCls}>
                <option value="">Sin asignar</option>
                {AREAS_PQRS.map(a => <option key={a} value={a}>{a}</option>)}
              </select>
            </div>
          </div>

          {/* Cliente */}
          <div>
            <p className="text-xs font-bold text-acento-fuerte uppercase tracking-wide mb-2">Datos del cliente</p>
            <div className="grid grid-cols-2 gap-4 mb-3">
              <div>
                <label className={labelCls}>Empresa</label>
                <input name="empresa" maxLength={LIMITES_RADICACION.empresa} value={form.empresa} onChange={handleChange} placeholder="Ej: Industrias del Valle S.A.S" className={inputCls} />
              </div>
              <div>
                <label className={labelCls}>NIT / Cédula</label>
                <input name="nit_cedula" maxLength={LIMITES_RADICACION.nit_cedula} value={form.nit_cedula} onChange={handleChange} placeholder="Ej: 900123456-7" className={inputCls} />
              </div>
            </div>
            <div className="mb-3">
              <label className={labelCls}>Nombre del contacto *</label>
              <input name="cliente_nombre" maxLength={LIMITES_RADICACION.cliente_nombre} value={form.cliente_nombre} onChange={handleChange} placeholder="Nombre de quien contacta" required className={inputCls} />
            </div>
            <div className="grid grid-cols-2 gap-4 mb-3">
              <div>
                <label className={labelCls}>Correo</label>
                <input name="cliente_email" maxLength={LIMITES_RADICACION.cliente_email} type="email" value={form.cliente_email} onChange={handleChange} placeholder="cliente@empresa.com" className={inputCls} />
              </div>
              <div>
                <label className={labelCls}>Teléfono</label>
                <input name="cliente_telefono" maxLength={LIMITES_RADICACION.cliente_telefono} value={form.cliente_telefono} onChange={handleChange} placeholder="3001234567" className={inputCls} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className={labelCls}>Ciudad</label>
                <input name="ciudad" maxLength={LIMITES_RADICACION.ciudad} value={form.ciudad} onChange={handleChange} placeholder="Ej: Medellín" className={inputCls} />
              </div>
              <div>
                <label className={labelCls}>Departamento</label>
                <select name="departamento" value={form.departamento} onChange={handleChange} className={inputCls}>
                  <option value="">Selecciona...</option>
                  {DEPARTAMENTOS.map(d => <option key={d} value={d}>{d}</option>)}
                </select>
              </div>
            </div>
          </div>

          {/* Canal de atención — siempre visible, cambia de opciones según el tipo */}
          <div>
            <label className={labelCls}>Canal de atención</label>
            <select name="canal_atencion" value={form.canal_atencion} onChange={handleChange} className={inputCls}>
              <option value="">Selecciona...</option>
              {(esFelicitacion ? CANALES_ATENCION_FELICITACION : CANALES_ATENCION).map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>

          {/* Producto — no aplica a felicitaciones ni quejas */}
          {mostrarProducto && (
            <div>
              <p className="text-xs font-bold text-acento-fuerte uppercase tracking-wide mb-2">Productos</p>
              <div className="space-y-3">
                {productos.map((fila, i) => (
                  <div key={fila.clave} className="rounded-xl border border-borde p-4">
                    {productos.length > 1 && (
                      <div className="flex items-center justify-between mb-3">
                        <span className="text-sm font-semibold text-acento-fuerte">Producto {i + 1}</span>
                        <button
                          type="button"
                          onClick={() => setProductos(lista => lista.filter(p => p.clave !== fila.clave))}
                          className="inline-flex items-center gap-1 text-xs font-semibold text-texto-2 hover:text-negativo hover:bg-negativo-bg px-2 py-1 rounded-lg transition-colors duration-150"
                        >
                          <IconoPapelera tam={13} /> Quitar
                        </button>
                      </div>
                    )}
                    <div className="grid grid-cols-2 gap-3 mb-3">
                      <div>
                        <label className={labelCls}>Código</label>
                        <input name="producto_codigo" maxLength={LIMITES_RADICACION.producto_codigo} value={fila.producto_codigo} onChange={(e) => cambiarProducto(fila.clave, e)} placeholder="Ej: PK-001" className={inputCls} />
                      </div>
                      <div>
                        <label className={labelCls}>Nombre</label>
                        <input name="producto_nombre" maxLength={LIMITES_RADICACION.producto_nombre} value={fila.producto_nombre} onChange={(e) => cambiarProducto(fila.clave, e)} placeholder="Ej: Hipoclorito de Sodio 13%" className={inputCls} />
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-3 mb-3">
                      <div>
                        <label className={labelCls}>Presentación</label>
                        <div className="flex gap-2">
                          <select name="presentacion" value={fila.presentacion} onChange={(e) => cambiarProducto(fila.clave, e)} className={inputCls}>
                            <option value="">Selecciona...</option>
                            {PRESENTACIONES.map(p => <option key={p} value={p}>{p}</option>)}
                          </select>
                          <input
                            name="cantidad_presentacion" maxLength={LIMITES_RADICACION.cantidad_presentacion}
                            value={fila.cantidad_presentacion} onChange={(e) => cambiarProducto(fila.clave, e)}
                            disabled={!fila.presentacion} placeholder="Cant." aria-label="Cantidad de la presentación"
                            className={`${inputCls} w-20 disabled:bg-superficie-2 disabled:cursor-not-allowed`}
                          />
                        </div>
                      </div>
                      <div>
                        <label className={labelCls}>Lote</label>
                        <input name="lote" maxLength={LIMITES_RADICACION.lote} value={fila.lote} onChange={(e) => cambiarProducto(fila.clave, e)} placeholder="Ej: L240815" className={inputCls} />
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className={labelCls}>Cant. en factura</label>
                        <input name="cantidad_factura" maxLength={LIMITES_RADICACION.cantidad_factura} value={fila.cantidad_factura} onChange={(e) => cambiarProducto(fila.clave, e)} placeholder="Ej: 10" className={inputCls} />
                      </div>
                      <div>
                        <label className={labelCls}>Cant. en reclamo</label>
                        <input name="cantidad_reclamo" maxLength={LIMITES_RADICACION.cantidad_reclamo} value={fila.cantidad_reclamo} onChange={(e) => cambiarProducto(fila.clave, e)} placeholder="Ej: 3" className={inputCls} />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
              {productos.length < MAX_PRODUCTOS && (
                <button
                  type="button"
                  onClick={() => setProductos(lista => [...lista, productoVacio()])}
                  className="mt-3 w-full border-2 border-dashed border-borde-fuerte hover:border-acento hover:bg-acento-suave text-acento font-semibold py-2.5 rounded-xl text-sm transition"
                >
                  + Agregar otro producto
                </button>
              )}
              {filaIncompleta && <p role="alert" className="text-xs text-negativo mt-2">{faltaProducto}</p>}

              {/* La factura es de la compra, no de cada producto. */}
              <div className="mt-4">
                <label className={labelCls}>N° Factura</label>
                <input name="factura_numero" maxLength={LIMITES_RADICACION.factura_numero} value={form.factura_numero} onChange={handleChange} placeholder="Ej: FV-2026-1234" className={inputCls} />
              </div>
              <div className="grid grid-cols-2 gap-4 mt-3">
                <ArchivoElegido etiqueta="Foto del producto" acepta=".jpg,.jpeg,.png,.webp,.pdf" archivo={adjuntoProducto} onCambio={setAdjuntoProducto} />
                <ArchivoElegido etiqueta="Foto de la factura" acepta=".jpg,.jpeg,.png,.webp,.pdf" archivo={adjuntoFactura} onCambio={setAdjuntoFactura} />
              </div>
            </div>
          )}

          {/* Video de evidencia — opcional, aplica a todo menos felicitaciones */}
          {!esFelicitacion && (
            <ArchivoElegido
              etiqueta="Video de evidencia (opcional)"
              acepta=".mp4,.mov,.webm"
              ayuda="MP4, MOV o WEBM — máx. 20MB (~20-30 seg)"
              archivo={adjuntoVideo}
              onCambio={setAdjuntoVideo}
            />
          )}

          {/* Descripción / comentario */}
          <div>
            <label className={labelCls}>
              {esFelicitacion ? 'Comentario (opcional)' : 'Descripción *'}
            </label>
            <textarea
              name="descripcion"
              value={form.descripcion}
              onChange={handleChange}
              placeholder={esFelicitacion ? 'Cuéntanos qué le gustó al cliente...' : 'Describe detalladamente la situación...'}
              rows={4}
              required={!esFelicitacion}
              className={`${inputCls} resize-none`}
            />
          </div>

          {error && (
            <div className="bg-negativo-bg border border-negativo/25 rounded-lg px-4 py-3 text-sm text-negativo">
              {error}
            </div>
          )}
        </div>

        <div className="px-6 py-4 border-t border-borde flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg border border-borde text-sm font-semibold text-texto-2 hover:bg-fondo transition"
          >
            Cancelar
          </button>
          <button
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending || !form.cliente_nombre || (!esFelicitacion && !form.descripcion) || filaIncompleta}
            className="px-4 py-2 rounded-lg bg-ambar hover:bg-ambar-claro text-acento-fuerte text-sm font-bold transition disabled:opacity-50"
          >
            {mutation.isPending ? 'Creando...' : 'Crear PQRS'}
          </button>
        </div>
      </div>
    </div>
  )
}


// Cerrar manda la encuesta de inmediato: elegir "Cerrado" sin querer y
// guardar no debe tener el mismo costo que cualquier otro cambio de estado.
function ConfirmarCierre({ pqrs, guardando, onConfirmar, onCancelar }) {
  return (
    <div
      className="fixed inset-0 bg-texto/50 flex items-center justify-center z-[60] p-4"
      onClick={onCancelar}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="bg-white rounded-2xl shadow-lg w-full max-w-md"
      >
        <div className="px-6 py-4 border-b border-borde">
          <h3 className="text-base font-bold text-acento-fuerte">¿Cerrar esta PQRS?</h3>
          {pqrs.codigo_seguimiento && (
            <p className="cifra text-xs text-texto-3 mt-0.5">{pqrs.codigo_seguimiento}</p>
          )}
        </div>
        <div className="px-6 py-5">
          <div className="rounded-xl border border-borde bg-superficie-2 p-3">
            <p className="text-sm text-texto">
              Se le manda la encuesta de satisfacción al cliente de inmediato.
            </p>
            <p className="text-sm text-texto-2 mt-1">
              Si la cierras por error, puedes volver a abrirla desde aquí —
              pero el correo ya se habrá enviado.
            </p>
          </div>
        </div>
        <div className="flex justify-end gap-3 px-6 py-4 bg-superficie-2 border-t border-borde">
          <button
            onClick={onCancelar}
            className="px-4 py-2 rounded-lg border border-borde text-sm font-semibold text-texto-2 hover:bg-white transition"
          >
            Cancelar
          </button>
          <button
            onClick={onConfirmar}
            autoFocus
            disabled={guardando}
            className="px-4 py-2 rounded-lg bg-acento-fuerte hover:bg-acento text-white text-sm font-bold transition disabled:opacity-50"
          >
            {guardando ? 'Cerrando...' : 'Sí, cerrar'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Modal detalle / cambiar estado ─────────────────────────────────
function ModalDetalle({ pqrs, onClose, onUpdated }) {
  const [nuevoEstado, setNuevoEstado] = useState(pqrs.estado)
  const [comentario, setComentario] = useState('')
  const [solucion, setSolucion] = useState('')
  const [adjuntosSolucion, setAdjuntosSolucion] = useState([])
  const [error, setError] = useState('')
  const [confirmandoCierre, setConfirmandoCierre] = useState(false)

  // El endpoint recibe multipart, no JSON: mandarlo como objeto respondía 422
  // y el modal se quedaba sin guardar nada. Es la misma puerta que usa el
  // detalle, así el cambio queda igual desde los dos lados.
  const mutation = useMutation({
    mutationFn: () => {
      const datos = new FormData()
      datos.append('estado', nuevoEstado)
      if (comentario.trim()) datos.append('comentario', comentario.trim())
      if (nuevoEstado === 'resuelto') {
        datos.append('solucion', solucion.trim())
        adjuntosSolucion.forEach((archivo) => datos.append('adjuntos_solucion', archivo))
      }
      return api.patch(`/pqrs/${pqrs.id}/gestion`, datos)
    },
    onSuccess: () => { onUpdated(); onClose() },
    // Antes esto no tenía onError: si el servidor rechazaba el cambio (por
    // ejemplo, un 403 porque quien lo intenta no es de Servicio al Cliente),
    // el modal se quedaba tal cual, sin decir nada — y eso se lee igual que
    // "no me deja cambiar el estado".
    onError: (err) => setError(mensajeDeError(err, 'No se pudo guardar el cambio.')),
  })

  const esResuelto = nuevoEstado === 'resuelto'
  const listo = !esResuelto || solucion.trim() !== ''

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg">
        <div className="flex items-center justify-between px-6 py-4 border-b border-borde">
          <div>
            <h2 className="font-bold text-acento-fuerte text-lg">
              {pqrs.codigo_seguimiento || `PQRS #${pqrs.id}`}
            </h2>
            <p className="text-xs text-texto-2">{pqrs.cliente_nombre}</p>
          </div>
          <button onClick={onClose} aria-label="Cerrar" className="w-8 h-8 flex items-center justify-center rounded-lg text-texto-3 hover:bg-superficie-2 hover:text-texto transition-colors duration-150"><IconoCerrar tam={16} /></button>
        </div>

        <div className="p-6 space-y-4">
          <div className="flex gap-2 flex-wrap">
            <Badge map={TIPOS} value={pqrs.tipo} />
            <Badge map={ESTADOS} value={pqrs.estado} />
            <span className={`text-xs font-semibold ${PRIORIDADES[pqrs.prioridad]?.color}`}>
              ● {PRIORIDADES[pqrs.prioridad]?.label}
            </span>
          </div>

          <div className="bg-fondo rounded-lg p-4 text-sm text-texto">
            {pqrs.descripcion}
          </div>

          <div className="grid grid-cols-2 gap-3 text-sm">
            <div>
              <span className="text-xs text-texto-2 block">Área</span>
              <span className="font-medium">{pqrs.area_responsable || '—'}</span>
            </div>
            <div>
              <span className="text-xs text-texto-2 block">SLA</span>
              <SLALabel pqrs={pqrs} />
            </div>
            {pqrs.cliente_email && (
              <div>
                <span className="text-xs text-texto-2 block">Email cliente</span>
                <span className="font-medium">{pqrs.cliente_email}</span>
              </div>
            )}
            {pqrs.cliente_telefono && (
              <div>
                <span className="text-xs text-texto-2 block">Teléfono</span>
                <span className="font-medium">{pqrs.cliente_telefono}</span>
              </div>
            )}
          </div>

          <div className="border-t border-borde pt-4">
            <label className="block text-xs font-semibold text-texto-2 uppercase tracking-wide mb-2">
              Cambiar estado
            </label>
            <select
              value={nuevoEstado}
              onChange={(e) => setNuevoEstado(e.target.value)}
              className="w-full px-3 py-2.5 rounded-lg border border-borde text-sm text-texto focus:outline-none focus:ring-2 focus:ring-acento mb-3"
            >
              {Object.entries(ESTADOS).map(([key, { label }]) => (
                <option key={key} value={key}>{label}</option>
              ))}
            </select>
            <textarea
              value={comentario}
              onChange={(e) => setComentario(e.target.value)}
              placeholder="Comentario del cambio de estado (opcional)..."
              rows={3}
              className="w-full px-3 py-2.5 rounded-lg border border-borde text-sm text-texto placeholder-texto-3 focus:outline-none focus:ring-2 focus:ring-acento resize-none"
            />

            {esResuelto && (
              <div className="mt-3 bg-superficie-2 rounded-lg p-3">
                <label className="block text-xs font-semibold text-texto-2 uppercase tracking-wide mb-1">
                  Solución <span className="text-negativo">· obligatorio</span>
                </label>
                <p className="text-xs text-texto-2 mb-2">
                  Esto se le envía al cliente pidiéndole que confirme si quedó bien.
                </p>
                <textarea
                  value={solucion}
                  onChange={(e) => setSolucion(e.target.value)}
                  rows={3}
                  placeholder="Qué se hizo para solucionar el caso..."
                  className="w-full px-3 py-2 rounded-lg border border-borde text-sm text-texto placeholder-texto-3 focus:outline-none focus:ring-2 focus:ring-acento resize-none mb-2"
                />
                <input
                  type="file"
                  accept=".jpg,.jpeg,.png,.webp,.pdf"
                  multiple
                  onChange={(e) => setAdjuntosSolucion(Array.from(e.target.files || []))}
                  className="w-full text-xs text-texto-2 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-acento-suave file:text-acento hover:file:bg-borde"
                />
                {adjuntosSolucion.length > 0 && (
                  <p className="text-xs text-texto-2 mt-1">
                    {adjuntosSolucion.length} archivo(s): {adjuntosSolucion.map((f) => f.name).join(', ')}
                  </p>
                )}
              </div>
            )}
          </div>

          {error && (
            <p role="alert" className="text-sm text-negativo">{error}</p>
          )}
        </div>

        <div className="px-6 py-4 border-t border-borde flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg border border-borde text-sm font-semibold text-texto-2 hover:bg-fondo transition"
          >
            Cerrar
          </button>
          <button
            onClick={() => nuevoEstado === 'cerrado' ? setConfirmandoCierre(true) : mutation.mutate()}
            disabled={mutation.isPending || nuevoEstado === pqrs.estado || !listo}
            className="px-4 py-2 rounded-lg bg-acento-fuerte hover:bg-acento text-white text-sm font-bold transition disabled:opacity-50"
          >
            {mutation.isPending ? 'Guardando...' : 'Guardar cambio'}
          </button>
        </div>
      </div>

      {confirmandoCierre && (
        <ConfirmarCierre
          pqrs={pqrs}
          guardando={mutation.isPending}
          onConfirmar={() => { setConfirmandoCierre(false); mutation.mutate() }}
          onCancelar={() => setConfirmandoCierre(false)}
        />
      )}
    </div>
  )
}

// ── Pantalla principal ─────────────────────────────────────────────
export default function PQRSList() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [filtroEstado, setFiltroEstado] = useState('')
  const [filtroTipo, setFiltroTipo]     = useState('')
  const [busqueda, setBusqueda]         = useState('')
  const [modalCrear, setModalCrear]     = useState(false)
  const [seleccionada, setSeleccionada] = useState(null)

  // Cuál tarjeta del encabezado está seleccionada. `null` es «Total», que
  // no filtra nada. Va aparte de los filtros del panel porque dos de estos
  // conjuntos no se pueden expresar ahí: «Abiertas» es todo menos cerrado, y
  // «Vencidas» es una cuenta contra el reloj, no un campo.
  const [foco, setFoco] = useState(null)

  // Filtros adicionales (client-side, sobre lo ya traído del servidor)
  const [panelFiltrosAbierto, setPanelFiltrosAbierto] = useState(false)
  const [filtroFechaDesde, setFiltroFechaDesde]       = useState('')
  const [filtroFechaHasta, setFiltroFechaHasta]       = useState('')
  const [filtroPuntoVenta, setFiltroPuntoVenta]       = useState('')
  const [filtroAreaAsignada, setFiltroAreaAsignada]   = useState('')

  const { data: pqrsList = [], isLoading, isError } = useQuery({
    queryKey: ['pqrs', filtroEstado, filtroTipo],
    queryFn: async () => {
      const params = {}
      if (filtroEstado) params.estado = filtroEstado
      if (filtroTipo)   params.tipo   = filtroTipo
      const { data } = await api.get('/pqrs', { params })
      return data
    },
  })

  // Qué parte de las PQRS ve esta persona. Lo decide el servidor; aquí solo
  // se dice en voz alta y se ajusta el filtro a lo que de verdad puede ver.
  const { data: visibilidad } = useQuery({
    queryKey: ['pqrs-visibilidad'],
    queryFn: async () => { const { data } = await api.get('/pqrs/visibilidad'); return data },
  })
  const puntosVisibles = visibilidad?.restringida
    ? visibilidad.puntos.map(({ canal, prefijo }) => ({ prefijo, label: canal }))
    : PUNTOS_VENTA
  const unaSolaSede = visibilidad?.restringida && visibilidad.puntos.length === 1

  const refetch = () => queryClient.invalidateQueries({ queryKey: ['pqrs'] })

  const areasDisponibles = useMemo(() => areasParaFiltrar(pqrsList), [pqrsList])

  // Búsqueda + filtros adicionales, todo en client-side sobre lo ya traído.
  // El foco de las tarjetas NO entra aquí: esta es la base sobre la que se
  // cuentan, para que la cifra de una tarjeta sea exactamente lo que muestra
  // al pulsarla. Contándolas sobre la lista completa, filtrar por Guayabal y
  // pulsar «4 vencidas» daba una sola fila — y el 4 quedaba desmentido por
  // la pantalla.
  const base = pqrsList.filter((p) => {
    const q = busqueda.trim().toLowerCase()
    if (q) {
      const coincideBusqueda = [p.codigo_seguimiento, p.radicado_calidad, p.cliente_nombre, p.empresa, p.nit_cedula]
        .filter(Boolean)
        .some(campo => campo.toLowerCase().includes(q))
      if (!coincideBusqueda) return false
    }

    if (filtroFechaDesde && new Date(p.fecha_creacion) < new Date(filtroFechaDesde)) return false
    if (filtroFechaHasta) {
      const hasta = new Date(filtroFechaHasta)
      hasta.setHours(23, 59, 59, 999) // incluir todo el día seleccionado
      if (new Date(p.fecha_creacion) > hasta) return false
    }

    if (filtroPuntoVenta && !coincidePuntoVenta(p.codigo_seguimiento, filtroPuntoVenta)) return false

    if (!coincideAreaAsignada(p, filtroAreaAsignada)) return false

    return true
  })

  // Las cifras de las tarjetas salen de las MISMAS funciones que filtran la
  // lista (`FOCOS` en constants.js). Escritas aparte, el día que una regla
  // cambie la tarjeta diría un número y la lista mostraría otro.
  const conteos = contarPorFoco(base)

  // El foco se cruza con los demás filtros, no los reemplaza: «vencidas» y
  // «de Guayabal» a la vez es una pregunta legítima.
  const pqrsFiltrada = base.filter(p => cumpleFoco(p, foco))

  return (
    <div>
      {/* Las notas crédito no son PQRS —van en su propia tabla, sin plazo de
          ley ni encuesta al cliente— pero se piden desde aquí, que es donde la
          gente ya entra. Sin esta pestaña no habría cómo llegar a ellas. */}
      <div className="flex items-center gap-2 mb-5">
        <span className="px-3 py-1.5 rounded-lg text-sm font-semibold bg-acento-suave text-acento">
          PQRS
        </span>
        <Link
          to="/notas-credito"
          className="px-3 py-1.5 rounded-lg text-sm font-semibold text-texto-2 hover:bg-superficie-2 transition"
        >
          Notas crédito
        </Link>
      </div>

      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-acento-fuerte">
            PQRS — Peticiones, Quejas, Reclamos, Sugerencias y Felicitaciones
          </h1>
          <p className="text-sm text-texto-2 mt-1">
            Gestión de solicitudes 
          </p>
        </div>
        <button
          onClick={() => setModalCrear(true)}
          className="flex items-center gap-2 bg-ambar hover:bg-ambar-claro text-acento-fuerte font-bold px-4 py-2.5 rounded-lg text-sm transition"
        >
          + Registrar PQRS
        </button>
      </div>

      {/* Una lista acotada que no avisa que está acotada se lee como «en la
          empresa solo hay estas». Por eso se dice qué se está viendo. */}
      {visibilidad?.restringida && (
        <div className="flex items-start gap-2 bg-info-bg border border-info/25 rounded-xl px-4 py-3 mb-5">
          <IconoEmpresa tam={16} className="text-info mt-0.5" />
          <p className="text-sm text-texto">
            {unaSolaSede ? (
              <>Estás viendo las PQRS de <strong>{visibilidad.puntos[0].canal}</strong></>
            ) : (
              <>Estás viendo las PQRS de <strong>los puntos de venta</strong></>
            )}
            <span className="text-texto-2"> y las que te asignen. Las del resto de la empresa las atiende Servicio al Cliente.</span>
          </p>
        </div>
      )}

      {/* Tarjetas de resumen — las mismas de Master Planner e Inicio, y
          aquí además filtran: de «hay 4 vencidas» a «estas son». Pulsar la
          que ya está activa la suelta, que es cómo se vuelve atrás sin
          buscar dónde se apagó. */}
      <div className="mb-6">
        <TarjetasKPI tarjetas={[
          { label: 'Total', value: conteos.null,
            nota: `${conteos.abiertas} sin cerrar`,
            activa: foco === null, onClick: () => setFoco(null) },
          { label: 'Abiertas', value: conteos.abiertas,
            nota: conteos.abiertas > 0 ? 'esperan respuesta' : 'ninguna pendiente',
            activa: foco === 'abiertas',
            onClick: () => setFoco(foco === 'abiertas' ? null : 'abiertas') },
          { label: 'Alta prioridad', value: conteos.prioridad,
            nota: conteos.prioridad > 0 ? 'atender primero' : 'ninguna',
            activa: foco === 'prioridad',
            onClick: () => setFoco(foco === 'prioridad' ? null : 'prioridad') },
          { label: 'Vencidas SLA', value: conteos.vencidas,
            alerta: conteos.vencidas > 0,
            nota: conteos.vencidas > 0 ? 'fuera del plazo de ley' : 'todas dentro del plazo',
            activa: foco === 'vencidas',
            onClick: () => setFoco(foco === 'vencidas' ? null : 'vencidas') },
        ]} />
      </div>

      {/* Buscador por radicado */}
      <div className="relative mb-4">
        <span className="absolute left-3 top-1/2 -translate-y-1/2 text-texto-3"><IconoBuscar tam={16} /></span>
        <input
          value={busqueda}
          onChange={(e) => setBusqueda(e.target.value)}
          placeholder="Buscar por radicado (PK-2026-0001), cliente, NIT o empresa..."
          className="w-full pl-9 pr-4 py-2.5 rounded-lg border border-borde text-sm text-texto placeholder-texto-3 bg-white focus:outline-none focus:ring-2 focus:ring-acento transition"
        />
        {busqueda && (
          <button
            onClick={() => setBusqueda('')}
            aria-label="Limpiar la búsqueda"
            className="absolute right-3 top-1/2 -translate-y-1/2 text-texto-3 hover:text-texto-2"
          >
            <IconoCerrar tam={14} />
          </button>
        )}
      </div>

      {/* Filtros */}
      {(() => {
        // La tarjeta cuenta como filtro activo: si no, «Limpiar filtros» la
        // dejaría puesta y la lista seguiría recortada después de limpiar.
        const hayFiltrosActivos = foco || filtroEstado || filtroTipo || filtroFechaDesde || filtroFechaHasta || filtroPuntoVenta || filtroAreaAsignada
        const limpiarTodo = () => {
          setFoco(null)
          setFiltroEstado(''); setFiltroTipo('')
          setFiltroFechaDesde(''); setFiltroFechaHasta('')
          setFiltroPuntoVenta(''); setFiltroAreaAsignada('')
        }
        return (
          <div className="mb-4">
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPanelFiltrosAbierto(v => !v)}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-sm font-semibold transition ${
                  panelFiltrosAbierto || hayFiltrosActivos
                    ? 'border-acento text-acento bg-fondo'
                    : 'border-borde text-texto-2 bg-white hover:bg-fondo'
                }`}
              >
                <IconoFiltro tam={15} /> Filtros {hayFiltrosActivos && <span className="w-1.5 h-1.5 rounded-full bg-acento" />}
                <span className="text-xs">{panelFiltrosAbierto ? '▲' : '▼'}</span>
              </button>

              {hayFiltrosActivos && (
                <button
                  onClick={limpiarTodo}
                  className="px-3 py-2 rounded-lg border border-borde text-sm text-texto-2 bg-white hover:bg-fondo transition"
                >
                  <IconoCerrar tam={13} /> Limpiar filtros
                </button>
              )}
            </div>

            {panelFiltrosAbierto && (
              <div className="mt-3 p-4 bg-white rounded-xl border border-borde grid grid-cols-3 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-texto-2 uppercase tracking-wide mb-1.5">Estado</label>
                  <select
                    value={filtroEstado}
                    onChange={(e) => setFiltroEstado(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-borde text-sm text-texto bg-white focus:outline-none focus:ring-2 focus:ring-acento"
                  >
                    <option value="">Todos los estados</option>
                    {Object.entries(ESTADOS).map(([key, { label }]) => (
                      <option key={key} value={key}>{label}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-texto-2 uppercase tracking-wide mb-1.5">Tipo</label>
                  <select
                    value={filtroTipo}
                    onChange={(e) => setFiltroTipo(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-borde text-sm text-texto bg-white focus:outline-none focus:ring-2 focus:ring-acento"
                  >
                    <option value="">Todos los tipos</option>
                    {Object.entries(TIPOS).map(([key, { label }]) => (
                      <option key={key} value={key}>{label}</option>
                    ))}
                  </select>
                </div>

                {/* Una sede solo ve la suya: un filtro de una sola opción
                    solo genera la pregunta de dónde están las demás. */}
                {!unaSolaSede && (
                  <div>
                    <label className="block text-xs font-semibold text-texto-2 uppercase tracking-wide mb-1.5">Punto de venta</label>
                    <select
                      value={filtroPuntoVenta}
                      onChange={(e) => setFiltroPuntoVenta(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg border border-borde text-sm text-texto bg-white focus:outline-none focus:ring-2 focus:ring-acento"
                    >
                      <option value="">Todos</option>
                      {puntosVisibles.map(({ prefijo, label }) => (
                        <option key={prefijo} value={prefijo}>{label}</option>
                      ))}
                    </select>
                  </div>
                )}

                <div>
                  <label className="block text-xs font-semibold text-texto-2 uppercase tracking-wide mb-1.5">Área asignada</label>
                  <select
                    value={filtroAreaAsignada}
                    onChange={(e) => setFiltroAreaAsignada(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-borde text-sm text-texto bg-white focus:outline-none focus:ring-2 focus:ring-acento"
                  >
                    <option value="">Todas</option>
                    <option value={AREA_SIN_ASIGNAR}>Sin asignar</option>
                    {areasDisponibles.map(a => (
                      <option key={a} value={a}>{a}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-texto-2 uppercase tracking-wide mb-1.5">Fecha desde</label>
                  <input
                    type="date"
                    value={filtroFechaDesde}
                    onChange={(e) => setFiltroFechaDesde(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-borde text-sm text-texto bg-white focus:outline-none focus:ring-2 focus:ring-acento"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-texto-2 uppercase tracking-wide mb-1.5">Fecha hasta</label>
                  <input
                    type="date"
                    value={filtroFechaHasta}
                    onChange={(e) => setFiltroFechaHasta(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-borde text-sm text-texto bg-white focus:outline-none focus:ring-2 focus:ring-acento"
                  />
                </div>
              </div>
            )}
          </div>
        )
      })()}

      {/* Tabla */}
      <div className="bg-white rounded-xl border border-borde overflow-hidden">
        {isLoading ? (
          <div className="flex items-center justify-center py-16 text-texto-2 text-sm">
            Cargando solicitudes...
          </div>
        ) : isError ? (
          <div className="flex items-center justify-center py-16 text-negativo text-sm">
            Error al cargar las PQRS. Verifica tu conexión.
          </div>
        ) : pqrsList.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-texto-2">
            <IconoPQRS tam={26} className="mb-3 text-texto-3" />
            <span className="text-sm font-medium">No hay PQRS registradas</span>
            <span className="text-xs mt-1">Crea la primera con el botón "Registrar PQRS"</span>
          </div>
        ) : pqrsFiltrada.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-texto-2">
            <IconoBuscar tam={26} className="mb-3 text-texto-3" />
            <span className="text-sm font-medium">Sin resultados para "{busqueda}"</span>
            <span className="text-xs mt-1">Verifica el radicado o intenta con otro término</span>
          </div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="bg-fondo border-b border-borde">
                {['Radicado', 'Tipo', 'Cliente', 'Área', 'Prioridad', 'SLA', 'Estado', ''].map(h => (
                  <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-texto-2 uppercase tracking-wide">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {pqrsFiltrada.map((pqrs) => (
                <tr
                  key={pqrs.id}
                  className="border-b border-borde hover:bg-superficie-2 transition cursor-pointer"
                  onClick={() => navigate(`/pqrs/${pqrs.id}`)}
                >
                  <td className="px-4 py-3 text-xs text-acento font-mono font-semibold">
                    {pqrs.codigo_seguimiento || `#${pqrs.id}`}
                  </td>
                  <td className="px-4 py-3"><Badge map={TIPOS} value={pqrs.tipo} /></td>
                  {/* La empresa arriba —así se reconoce el cliente de un
                      vistazo— y el contacto debajo. Una persona natural sale
                      con su nombre y su correo. Ver `nombrePrincipal`. */}
                  <td className="px-4 py-3">
                    {(() => {
                      const { titulo, subtitulo } = nombrePrincipal(pqrs)
                      const segunda = subtitulo || pqrs.cliente_email
                      return (
                        <>
                          <div className="text-sm font-semibold text-texto">{titulo}</div>
                          {segunda && <div className="text-xs text-texto-2">{segunda}</div>}
                        </>
                      )
                    })()}
                  </td>
                  <td className="px-4 py-3 text-sm text-texto-2">{pqrs.area_responsable || '—'}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs font-semibold ${PRIORIDADES[pqrs.prioridad]?.color}`}>
                      ● {PRIORIDADES[pqrs.prioridad]?.label}
                    </span>
                  </td>
                  <td className="px-4 py-3"><SLALabel pqrs={pqrs} /></td>
                  <td className="px-4 py-3"><Badge map={ESTADOS} value={pqrs.estado} /></td>
                  <td className="px-4 py-3">
                    <button className="text-xs text-acento font-semibold hover:underline">
                      Ver
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Modales */}
      {modalCrear && (
        <ModalCrear
          onClose={() => setModalCrear(false)}
          onCreated={refetch}
          canalInicial={unaSolaSede ? visibilidad.puntos[0].canal : ''}
        />
      )}
      {seleccionada && (
        <ModalDetalle
          pqrs={seleccionada}
          onClose={() => setSeleccionada(null)}
          onUpdated={refetch}
        />
      )}
    </div>
  )
}