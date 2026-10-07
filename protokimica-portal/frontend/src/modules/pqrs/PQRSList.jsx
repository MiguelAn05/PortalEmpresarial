import { useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../../core/api.js'
import { puedeVerModulo } from '../../core/modulos.js'
import { useAuth } from '../../core/useAuth.js'
import { useAreas } from '../../core/areas.js'
import {
  SIN_CAUSA, agruparAsociados, coincideAsociado, etiquetaAsociado, useAsociados,
} from './asociados.js'
import { canalesConPrefijo, nombresDe, useCanales } from '../../core/canales.js'
import TarjetasKPI from '../../core/components/TarjetasKPI.jsx'
import { EsqueletoFilas } from '../../core/components/Cargando.jsx'
import {
  IconoBuscar, IconoCerrar, IconoChevron, IconoClip, IconoEmpresa, IconoFiltro,
  IconoIndicadores, IconoPapelera, IconoPQRS, IconoRecibo,
} from '../../core/components/Iconos.jsx'
import { mensajeDeError } from '../../core/errores.js'
import {
  AREA_SIN_ASIGNAR, DEPARTAMENTOS, LIMITES_RADICACION, MAX_PRODUCTOS, PRESENTACIONES, VISTAS,
  areasParaFiltrar, avancePlazo, coincideAreaAsignada, contarPorFoco, cumpleFoco, cumpleVista,
  estadoDelPlazo, faltaEnProductos, nombrePrincipal, productoVacio, productosParaEnviar, tiempoEnArea,
  ESTADOS, PRIORIDADES, TIPOS,
} from './constants.js'
import { InsigniaDe } from './piezas.jsx'

// Compara el prefijo exacto del radicado (evita que "PVC" matchee "PVCR0010")
function coincidePuntoVenta(codigo, prefijo) {
  if (!codigo) return false
  return new RegExp(`^${prefijo}\\d+$`).test(codigo)
}

const TONO_TEXTO = {
  negativo: 'text-negativo font-semibold',
  alerta: 'text-alerta font-semibold',
  neutro: 'text-texto-2',
}
const TONO_BARRA = {
  negativo: 'bg-negativo-vivo',
  alerta: 'bg-ambar',
  neutro: 'bg-positivo-vivo',
}

/**
 * La columna de plazo: cuánto le queda, en palabras, y una barrita con cuánto
 * del plazo ya se gastó. Recibe la PQRS entera porque **el estado es parte
 * de la cuenta**: una resuelta o una cerrada ya no corren contra el reloj, y
 * por eso no tienen barra. La regla vive en `estadoDelPlazo()`, gemela de la
 * del servidor y con prueba.
 */
function Plazo({ pqrs }) {
  const plazo = estadoDelPlazo(pqrs)
  if (!plazo) {
    return <span className="text-xs text-texto-3">{pqrs.estado === 'resuelto' ? 'Respondida' : '—'}</span>
  }
  const avance = avancePlazo(pqrs) ?? 0
  return (
    <div>
      <span className={`cifra text-xs ${TONO_TEXTO[plazo.tono]}`}>{plazo.texto}</span>
      <span className="block w-16 h-1 mt-1.5 rounded-full bg-superficie-2 overflow-hidden" aria-hidden="true">
        <span className={`block h-full rounded-full ${TONO_BARRA[plazo.tono]}`} style={{ width: `${Math.round(avance * 100)}%` }} />
      </span>
    </div>
  )
}

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
  const listaCanales = useCanales()
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

          {/* Tipo. El área no se pide: quien radica no tiene con qué saber
              cuál le toca. La PQRS nace con quien reparte (Servicio al
              Cliente) y ahí se asigna. */}
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
              {nombresDe(listaCanales).map(c => <option key={c} value={c}>{c}</option>)}
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

// ── Pantalla principal ─────────────────────────────────────────────
const claseSelect = 'h-9 px-3 rounded-lg border border-borde-fuerte text-sm text-texto bg-superficie focus:outline-none focus:ring-2 focus:ring-acento'
const claseCampo = 'w-full px-3 py-2 rounded-lg border border-borde text-sm text-texto bg-white focus:outline-none focus:ring-2 focus:ring-acento'

export default function PQRSList() {
  const listaAreas = useAreas()
  const listaCanales = useCanales()
  const listaAsociados = useAsociados()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const { user } = useAuth()
  const verNotasCredito = puedeVerModulo(user, 'notas_credito')

  // Qué PARTE se mira (Abiertas, De mi área, Cerradas, Todas) y, dentro de
  // ella, qué tarjeta recorta. Son dos cosas: «vencidas de mi área» es una
  // pregunta legítima.
  const [vista, setVista] = useState('abiertas')
  const [foco, setFoco] = useState(null)
  const [busqueda, setBusqueda] = useState('')
  const [filtroArea, setFiltroArea] = useState('')
  const [filtroTipo, setFiltroTipo] = useState('')
  const [modalCrear, setModalCrear] = useState(false)

  // Lo que se pide menos va en el panel: estado, sede, causa y fechas.
  const [panelFiltrosAbierto, setPanelFiltrosAbierto] = useState(false)
  const [filtroEstado, setFiltroEstado] = useState('')
  const [filtroPuntoVenta, setFiltroPuntoVenta] = useState('')
  const [filtroAsociado, setFiltroAsociado] = useState('')
  const [filtroFechaDesde, setFiltroFechaDesde] = useState('')
  const [filtroFechaHasta, setFiltroFechaHasta] = useState('')

  const { data: pqrsList = [], isLoading, isError } = useQuery({
    queryKey: ['pqrs', filtroEstado, filtroTipo],
    queryFn: async () => {
      const params = {}
      if (filtroEstado) params.estado = filtroEstado
      if (filtroTipo) params.tipo = filtroTipo
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
    : canalesConPrefijo(listaCanales)
  const unaSolaSede = visibilidad?.restringida && visibilidad.puntos.length === 1

  const refetch = () => queryClient.invalidateQueries({ queryKey: ['pqrs'] })
  const areasDisponibles = useMemo(() => areasParaFiltrar(pqrsList, listaAreas), [pqrsList, listaAreas])
  const vistas = VISTAS.filter(v => v.clave !== 'mi_area' || user?.area)
  const contextoVista = { area: user?.area }

  // La base: búsqueda y filtros, sin vista ni tarjeta. Sobre ella se cuenta
  // la tarjeta principal («Abiertas de N radicadas»).
  const base = pqrsList.filter((p) => {
    const q = busqueda.trim().toLowerCase()
    if (q) {
      const coincide = [p.codigo_seguimiento, p.radicado_calidad, p.cliente_nombre, p.empresa, p.nit_cedula]
        .filter(Boolean).some(campo => campo.toLowerCase().includes(q))
      if (!coincide) return false
    }
    if (filtroFechaDesde && new Date(p.fecha_creacion) < new Date(filtroFechaDesde)) return false
    if (filtroFechaHasta) {
      const hasta = new Date(filtroFechaHasta)
      hasta.setHours(23, 59, 59, 999) // incluir todo el día seleccionado
      if (new Date(p.fecha_creacion) > hasta) return false
    }
    if (filtroPuntoVenta && !coincidePuntoVenta(p.codigo_seguimiento, filtroPuntoVenta)) return false
    if (!coincideAreaAsignada(p, filtroArea)) return false
    if (!coincideAsociado(p, filtroAsociado)) return false
    return true
  })

  // Las cifras de las tarjetas salen de las MISMAS funciones que filtran
  // (`FOCOS`), y se cuentan sobre la vista: la tarjeta dice exactamente lo
  // que muestra al pulsarla.
  const enVista = base.filter(p => cumpleVista(p, vista, contextoVista))
  const conteos = contarPorFoco(enVista)
  const abiertasTotal = base.filter(p => p.estado !== 'cerrado').length
  const cerradasTotal = base.length - abiertasTotal
  const lista = enVista.filter(p => cumpleFoco(p, foco))

  const filtrosDelPanel = [filtroEstado, filtroPuntoVenta, filtroAsociado, filtroFechaDesde, filtroFechaHasta].filter(Boolean).length
  const hayFiltros = Boolean(foco || busqueda || filtroArea || filtroTipo || filtrosDelPanel)
  const limpiarTodo = () => {
    setFoco(null); setBusqueda(''); setFiltroArea(''); setFiltroTipo('')
    setFiltroEstado(''); setFiltroPuntoVenta(''); setFiltroAsociado('')
    setFiltroFechaDesde(''); setFiltroFechaHasta('')
  }
  // Una tarjeta de plazo sobre las cerradas siempre da cero: pulsarla vuelve
  // a las abiertas, que es donde esa pregunta tiene respuesta.
  const enfocar = (clave) => {
    if (foco === clave) { setFoco(null); return }
    if (vista === 'cerradas') setVista('abiertas')
    setFoco(clave)
  }
  const nombreVista = vistas.find(v => v.clave === vista)?.label.toLowerCase()

  return (
    <div>
      {/* Encabezado */}
      <div className="flex flex-wrap items-start justify-between gap-4 mb-5">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-texto">PQRS</h1>
          <p className="text-sm text-texto-2 mt-1">Peticiones, quejas, reclamos, sugerencias y felicitaciones</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {/* Las notas crédito no son PQRS —van en su propia tabla, sin plazo
              de ley ni encuesta— pero se piden desde aquí, que es donde la
              gente ya entra. Sin el módulo contratado, el botón no aparece. */}
          {verNotasCredito && (
            <button onClick={() => navigate('/notas-credito')}
                    className="inline-flex items-center gap-2 h-9 px-3.5 rounded-lg border border-borde-fuerte bg-superficie text-sm font-semibold text-texto hover:bg-superficie-2 transition">
              <IconoRecibo tam={15} /> Notas crédito
            </button>
          )}
          <button onClick={() => navigate('/pqrs/informe')}
                  className="inline-flex items-center gap-2 h-9 px-3.5 rounded-lg border border-borde-fuerte bg-superficie text-sm font-semibold text-texto hover:bg-superficie-2 transition">
            <IconoIndicadores tam={15} /> Generar informe
          </button>
          <button onClick={() => setModalCrear(true)}
                  className="inline-flex items-center gap-2 h-9 px-3.5 rounded-lg bg-acento-fuerte hover:bg-acento text-white text-sm font-semibold shadow-sm transition">
            <span aria-hidden="true" className="text-base leading-none">+</span> Registrar PQRS
          </button>
        </div>
      </div>

      {/* Una lista acotada que no avisa que está acotada se lee como «en la
          empresa solo hay estas». Por eso se dice qué se está viendo. */}
      {visibilidad?.restringida && (
        <div className="flex items-start gap-2 bg-info-bg border border-info/25 rounded-xl px-4 py-3 mb-5">
          <IconoEmpresa tam={16} className="text-info mt-0.5" />
          <p className="text-sm text-texto">
            {unaSolaSede
              ? <>Estás viendo las PQRS de <strong>{visibilidad.puntos[0].canal}</strong></>
              : <>Estás viendo las PQRS de <strong>los puntos de venta</strong></>}
            <span className="text-texto-2"> y las que te asignen. Las del resto de la empresa las atiende Servicio al Cliente.</span>
          </p>
        </div>
      )}

      {/* Las tarjetas filtran: de «hay 4 vencidas» a «estas son». Pulsar la
          que ya está activa la suelta. */}
      <div className="mb-5">
        <TarjetasKPI conPrincipal tarjetas={[
          { label: 'Abiertas', value: abiertasTotal,
            nota: `de ${base.length} radicadas${cerradasTotal ? ` · ${cerradasTotal} cerradas` : ''}`,
            activa: vista === 'abiertas' && !foco,
            onClick: () => { setVista('abiertas'); setFoco(null) } },
          { label: 'Plazo vencido', value: conteos.vencidas, punto: 'negativo',
            alerta: conteos.vencidas > 0,
            nota: conteos.vencidas > 0 ? 'fuera del plazo de ley' : 'todas en término',
            activa: foco === 'vencidas', onClick: () => enfocar('vencidas') },
          { label: 'Vencen esta semana', value: conteos.por_vencer, punto: 'alerta',
            nota: conteos.por_vencer > 0 ? 'responder antes de que venzan' : 'ninguna por vencer',
            activa: foco === 'por_vencer', onClick: () => enfocar('por_vencer') },
          { label: 'Pasadas en su área', value: conteos.area_vencida, punto: 'neutro',
            nota: conteos.area_vencida > 0 ? 'más de 3 días hábiles en un área' : 'todas las áreas al día',
            activa: foco === 'area_vencida', onClick: () => enfocar('area_vencida') },
        ]} />
      </div>

      {/* Barra de herramientas: la vista, la búsqueda y lo que más se filtra. */}
      <div className="flex flex-wrap items-center gap-2.5 mb-3">
        <div role="group" aria-label="Vista" className="flex gap-0.5 bg-superficie-2 rounded-lg p-0.5">
          {vistas.map(v => (
            <button key={v.clave} type="button" aria-pressed={vista === v.clave}
                    onClick={() => setVista(v.clave)}
                    className={`px-3 py-1.5 rounded-md text-xs font-semibold transition ${
                      vista === v.clave ? 'bg-superficie text-texto shadow-sm' : 'text-texto-2 hover:text-texto'
                    }`}>
              {v.label}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2 h-9 px-3 rounded-lg border border-borde-fuerte bg-superficie flex-1 min-w-[15rem] max-w-md focus-within:ring-2 focus-within:ring-acento">
          <IconoBuscar tam={15} className="text-texto-3" />
          <input value={busqueda} onChange={(e) => setBusqueda(e.target.value)}
                 placeholder="Radicado, cliente, NIT o empresa…" aria-label="Buscar PQRS"
                 className="w-full text-sm text-texto placeholder-texto-3 bg-transparent focus:outline-none" />
          {busqueda && (
            <button onClick={() => setBusqueda('')} aria-label="Borrar la búsqueda" className="text-texto-3 hover:text-texto">
              <IconoCerrar tam={13} />
            </button>
          )}
        </div>

        <select value={filtroArea} onChange={(e) => setFiltroArea(e.target.value)} aria-label="Área" className={claseSelect}>
          <option value="">Todas las áreas</option>
          <option value={AREA_SIN_ASIGNAR}>Sin asignar</option>
          {areasDisponibles.map(a => <option key={a} value={a}>{a}</option>)}
        </select>

        <select value={filtroTipo} onChange={(e) => setFiltroTipo(e.target.value)} aria-label="Tipo" className={claseSelect}>
          <option value="">Todos los tipos</option>
          {Object.entries(TIPOS).map(([clave, { label }]) => <option key={clave} value={clave}>{label}</option>)}
        </select>

        <button type="button" onClick={() => setPanelFiltrosAbierto(v => !v)} aria-expanded={panelFiltrosAbierto}
                className={`inline-flex items-center gap-2 h-9 px-3 rounded-lg border text-sm font-semibold transition ${
                  panelFiltrosAbierto || filtrosDelPanel ? 'border-acento text-acento bg-acento-suave' : 'border-borde-fuerte text-texto-2 bg-superficie hover:bg-superficie-2'
                }`}>
          <IconoFiltro tam={15} /> Más filtros
          {filtrosDelPanel > 0 && <span className="cifra text-xs bg-acento text-white rounded-full px-1.5">{filtrosDelPanel}</span>}
        </button>

        {/* «Limpiar» apaga también la tarjeta: un recorte que no se sabe cómo
            quitar se lee como PQRS que faltan. */}
        {hayFiltros && (
          <button type="button" onClick={limpiarTodo}
                  className="inline-flex items-center gap-1.5 h-9 px-2.5 rounded-lg text-sm text-texto-2 hover:bg-superficie-2 transition">
            <IconoCerrar tam={13} /> Limpiar
          </button>
        )}

        <span className="ml-auto cifra text-xs text-texto-3">
          {lista.length} {lista.length === 1 ? 'resultado' : 'resultados'}
        </span>
      </div>

      {panelFiltrosAbierto && (
        <div className="mb-3 p-4 bg-superficie rounded-xl border border-borde shadow-sm grid sm:grid-cols-2 lg:grid-cols-5 gap-4">
          <div>
            <label htmlFor="filtro-estado" className="etiqueta block mb-1.5">Estado</label>
            <select id="filtro-estado" value={filtroEstado} onChange={(e) => setFiltroEstado(e.target.value)} className={claseCampo}>
              <option value="">Todos los estados</option>
              {Object.entries(ESTADOS).map(([clave, { label }]) => <option key={clave} value={clave}>{label}</option>)}
            </select>
          </div>
          {/* Una sede solo ve la suya: un filtro de una sola opción solo
              genera la pregunta de dónde están las demás. */}
          {!unaSolaSede && (
            <div>
              <label htmlFor="filtro-punto" className="etiqueta block mb-1.5">Punto de venta</label>
              <select id="filtro-punto" value={filtroPuntoVenta} onChange={(e) => setFiltroPuntoVenta(e.target.value)} className={claseCampo}>
                <option value="">Todos</option>
                {puntosVisibles.map(({ prefijo, label }) => <option key={prefijo} value={prefijo}>{label}</option>)}
              </select>
            </div>
          )}
          {/* «Sin causa» encuentra las que faltan por clasificar, sobre todo
              las que cerró el cliente sin pasar por Servicio al Cliente. */}
          <div>
            <label htmlFor="filtro-asociado" className="etiqueta block mb-1.5">Asociado a</label>
            <select id="filtro-asociado" value={filtroAsociado} onChange={(e) => setFiltroAsociado(e.target.value)} className={claseCampo}>
              <option value="">Todos</option>
              <option value={SIN_CAUSA}>Sin causa (falta clasificar)</option>
              {agruparAsociados(listaAsociados).map(({ grupo, items }) => (
                <optgroup key={grupo} label={grupo}>
                  {items.map(a => <option key={a.id} value={a.id}>{etiquetaAsociado(a)}</option>)}
                </optgroup>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="filtro-desde" className="etiqueta block mb-1.5">Radicada desde</label>
            <input id="filtro-desde" type="date" value={filtroFechaDesde} onChange={(e) => setFiltroFechaDesde(e.target.value)} className={claseCampo} />
          </div>
          <div>
            <label htmlFor="filtro-hasta" className="etiqueta block mb-1.5">Hasta</label>
            <input id="filtro-hasta" type="date" value={filtroFechaHasta} onChange={(e) => setFiltroFechaHasta(e.target.value)} className={claseCampo} />
          </div>
        </div>
      )}

      {/* Tabla */}
      <div className="bg-superficie rounded-xl border border-borde shadow-sm overflow-hidden">
        {isLoading ? (
          <EsqueletoFilas filas={6} />
        ) : isError ? (
          <div className="flex items-center justify-center py-16 text-negativo text-sm">
            No se pudieron cargar las PQRS. Revisa tu conexión y recarga la página.
          </div>
        ) : pqrsList.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-texto-2">
            <IconoPQRS tam={26} className="mb-3 text-texto-3" />
            <span className="text-sm font-medium">No hay PQRS registradas</span>
            <span className="text-xs mt-1">Crea la primera con el botón «Registrar PQRS».</span>
          </div>
        ) : lista.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-texto-2">
            <IconoBuscar tam={26} className="mb-3 text-texto-3" />
            <span className="text-sm font-medium">Ninguna PQRS coincide</span>
            <span className="text-xs mt-1">
              {busqueda ? `Nada con «${busqueda}» en ${nombreVista}. ` : ''}
              Prueba con otra vista o limpia los filtros.
            </span>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-superficie-2 border-b border-borde">
                <th className="etiqueta text-left px-4 py-2.5 w-36">Radicado</th>
                <th className="etiqueta text-left px-4 py-2.5">Cliente</th>
                <th className="etiqueta text-left px-4 py-2.5 w-52">Área · en cola</th>
                <th className="etiqueta text-left px-4 py-2.5 w-36">Plazo</th>
                <th className="etiqueta text-left px-4 py-2.5 w-32">Estado</th>
                <th className="w-8" aria-hidden="true" />
              </tr>
            </thead>
            <tbody className="divide-y divide-borde">
              {lista.map((pqrs) => {
                const { titulo, subtitulo } = nombrePrincipal(pqrs)
                const segunda = subtitulo || pqrs.cliente_email
                const tiempo = tiempoEnArea(pqrs)
                const urgente = ['alta', 'critica'].includes(pqrs.prioridad)
                const abrir = () => navigate(`/pqrs/${pqrs.id}`)
                return (
                  <tr key={pqrs.id} onClick={abrir} tabIndex={0}
                      onKeyDown={(e) => { if (e.key === 'Enter') abrir() }}
                      className="group cursor-pointer hover:bg-superficie-2 focus:bg-superficie-2 focus:outline-none transition-colors">
                    <td className="px-4 py-3">
                      <div className="font-mono text-xs text-texto-2">{pqrs.codigo_seguimiento || `#${pqrs.id}`}</div>
                      <div className="text-xs text-texto-3 mt-0.5">
                        {TIPOS[pqrs.tipo]?.label || pqrs.tipo}
                        {urgente && (
                          <span className={pqrs.prioridad === 'critica' ? 'text-negativo font-semibold' : 'text-alerta font-semibold'}>
                            {' · '}{PRIORIDADES[pqrs.prioridad].label.replace('Prioridad ', '')}
                          </span>
                        )}
                      </div>
                    </td>
                    {/* La empresa arriba —así se reconoce el cliente de un
                        vistazo— y el contacto debajo. Ver `nombrePrincipal`. */}
                    <td className="px-4 py-3 min-w-0">
                      <div className="font-medium text-texto truncate max-w-xs">{titulo}</div>
                      {segunda && <div className="text-xs text-texto-3 truncate max-w-xs">{segunda}</div>}
                    </td>
                    <td className="px-4 py-3">
                      <div className={pqrs.area_responsable ? 'text-texto-2' : 'text-texto-3'}>{pqrs.area_responsable || 'Sin asignar'}</div>
                      {tiempo && (
                        <div className={`cifra text-xs mt-0.5 ${pqrs.area_vencida ? 'text-negativo font-semibold' : 'text-texto-3'}`}>
                          {tiempo.texto}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3"><Plazo pqrs={pqrs} /></td>
                    <td className="px-4 py-3"><InsigniaDe mapa={ESTADOS} valor={pqrs.estado} /></td>
                    <td className="pr-3 text-texto-3">
                      <IconoChevron tam={15} className="opacity-0 -translate-x-1 group-hover:opacity-100 group-hover:translate-x-0 group-focus:opacity-100 transition" />
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
        {!isLoading && lista.length > 0 && (
          <div className="flex items-center justify-between px-4 py-2.5 border-t border-borde text-xs text-texto-3">
            <span className="cifra">
              {lista.length === enVista.length
                ? `${lista.length} ${nombreVista}`
                : `${lista.length} de ${enVista.length} ${nombreVista}`}
            </span>
            {vista === 'abiertas' && cerradasTotal > 0 && (
              <button type="button" onClick={() => { setVista('cerradas'); setFoco(null) }}
                      className="font-semibold text-acento hover:underline">
                Ver las {cerradasTotal} cerradas →
              </button>
            )}
          </div>
        )}
      </div>

      {modalCrear && (
        <ModalCrear
          onClose={() => setModalCrear(false)}
          onCreated={refetch}
          canalInicial={unaSolaSede ? visibilidad.puntos[0].canal : ''}
        />
      )}
    </div>
  )
}
