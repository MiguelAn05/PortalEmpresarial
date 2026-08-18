import { useState, useRef } from 'react'
import api from '../../core/api.js'
import { AREAS } from '../../core/areas.js'
import {
  IconoAlerta, IconoBuscar, IconoCheck, IconoCopiar, IconoFelicitacion,
  IconoFicha, IconoFoto, IconoIdea, IconoPaquete, IconoPeticion, IconoQueja,
  IconoRecibo, IconoVideo,
} from '../../core/components/Iconos.jsx'

// ── Constantes ─────────────────────────────────────────────────────
// Cada tipo se distingue por su ICONO, no por un color de fondo distinto.
// Cinco tarjetas de cinco colores obligan a leerlas todas para encontrar la
// que se quiere; con una sola forma por tipo se reconocen de un vistazo, y
// además funciona para quien no distingue el morado del rojo.
const TIPOS = [
  { value: 'peticion', label: 'Petición', Icono: IconoPeticion,
    descripcion: 'Solicitar información, documentos o servicios' },
  { value: 'queja', label: 'Queja', Icono: IconoQueja,
    descripcion: 'Expresar inconformidad con nuestro servicio' },
  { value: 'reclamo', label: 'Reclamo', Icono: IconoAlerta,
    descripcion: 'Exigir solución por producto o servicio' },
  { value: 'sugerencia', label: 'Sugerencia', Icono: IconoIdea,
    descripcion: 'Proponer mejoras a nuestros productos' },
  { value: 'felicitacion', label: 'Felicitación', Icono: IconoFelicitacion,
    descripcion: 'Nos importa conocer tu opinión de nuestros servicios' },
]

const DEPARTAMENTOS = [
  'Amazonas','Antioquia','Arauca','Atlántico','Bolívar','Boyacá','Caldas',
  'Caquetá','Casanare','Cauca','Cesar','Chocó','Córdoba','Cundinamarca',
  'Guainía','Guaviare','Huila','La Guajira','Magdalena','Meta','Nariño',
  'Norte de Santander','Putumayo','Quindío','Risaralda','San Andrés',
  'Santander','Sucre','Tolima','Valle del Cauca','Vaupés','Vichada',
]

const CANALES_ATENCION = [
  'Venta institucional',
  'WhatsApp',
  'Punto de venta Centro',
  'Punto de venta Belén',
  'Punto de venta Guayabal',
  'Punto de venta La 65',
  'Punto de venta Cristo Rey',
  'Punto de venta Itagüí',
  'Línea telefónica',
]

const CANALES_ATENCION_FELICITACION = [
  'Venta institucional',
  'Llamada telefónica',
  'WhatsApp',
  'Punto de venta Centro',
  'Punto de venta Belén',
  'Punto de venta Guayabal',
  'Punto de venta La 65',
  'Punto de venta Cristo Rey',
  'Punto de venta Itagüí',
]

const PRESENTACIONES = ['Unidad', 'Kilo', 'Gramo', 'Litro', 'Mililitro']

// Productos de prueba — aquí irá la integración con Geminus
const PRODUCTOS_PRUEBA = [
  { codigo: 'PK-001', nombre: 'Hipoclorito de Sodio 13% x 20L' },
  { codigo: 'PK-002', nombre: 'Sulfato de Aluminio Tipo B x 25Kg' },
  { codigo: 'PK-003', nombre: 'Lauril Éter Sulfato de Sodio 70% x 200Kg' },
  { codigo: 'PK-004', nombre: 'Ácido Sulfúrico 98% x 35Kg' },
  { codigo: 'PK-005', nombre: 'Alcohol Isopropílico 99% x 4L' },
  { codigo: 'PK-006', nombre: 'Soda Cáustica Escamas x 25Kg' },
  { codigo: 'PK-007', nombre: 'Agua Oxigenada 50% x 30Kg' },
  { codigo: 'PK-008', nombre: 'Ácido Clorhídrico 33% x 35Kg' },
]

// ── Componente: campo de adjunto ───────────────────────────────────
function CampoAdjunto({ label, descripcion, Icono = IconoFoto, onChange, archivo, obligatorio, accept = 'image/*,.pdf', hint = 'JPG, PNG, PDF — máx. 10MB' }) {
  const inputRef = useRef(null)

  const handleChange = (e) => {
    const file = e.target.files[0]
    if (file) onChange(file)
  }

  const handleDrop = (e) => {
    e.preventDefault()
    const file = e.dataTransfer.files[0]
    if (file) onChange(file)
  }

  return (
    <div>
      <label className="etiqueta block mb-1.5">
        {label} {obligatorio && <span className="text-negativo">*</span>}
      </label>
      <div
        onClick={() => inputRef.current?.click()}
        onDrop={handleDrop}
        onDragOver={(e) => e.preventDefault()}
        className={`
          border-2 border-dashed rounded-xl p-5 text-center cursor-pointer
          transition-colors duration-150 ease-suave
          ${archivo
            ? 'border-positivo-vivo bg-positivo-bg'
            : 'border-borde-fuerte bg-superficie-2 hover:border-acento hover:bg-acento-suave'
          }
        `}
      >
        {archivo ? (
          <div className="flex items-center justify-center gap-3">
            {archivo.type.startsWith('image/') ? (
              <img
                src={URL.createObjectURL(archivo)}
                alt="preview"
                className="w-16 h-16 object-cover rounded-lg"
              />
            ) : archivo.type.startsWith('video/') ? (
              <video
                src={URL.createObjectURL(archivo)}
                className="w-16 h-16 object-cover rounded-lg"
                muted
              />
            ) : (
              <div className="w-16 h-16 bg-superficie rounded-lg border border-borde
                flex items-center justify-center text-positivo">
                <IconoFicha tam={24} />
              </div>
            )}
            <div className="text-left">
              <div className="text-sm font-semibold text-positivo">{archivo.name}</div>
              <div className="cifra text-xs text-texto-2 mt-0.5">
                {(archivo.size / 1024 / 1024).toFixed(2)} MB
              </div>
              <button
                onClick={(e) => { e.stopPropagation(); onChange(null) }}
                className="text-xs text-negativo hover:underline mt-1"
              >
                Cambiar archivo
              </button>
            </div>
          </div>
        ) : (
          <div>
            <div className="flex justify-center mb-2 text-texto-3">
              <Icono tam={26} />
            </div>
            <div className="text-sm font-semibold text-texto mb-1">{descripcion}</div>
            <div className="text-xs text-texto-3">
              Toca para seleccionar o arrastra aquí
            </div>
            <div className="text-xs text-texto-3 mt-1">
              {hint}
            </div>
          </div>
        )}
      </div>
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        onChange={handleChange}
        className="hidden"
      />
    </div>
  )
}

// ── Componente: buscador de productos ─────────────────────────────
function BuscadorProducto({ value, onChange }) {
  const [busqueda, setBusqueda] = useState('')
  const [resultados, setResultados] = useState([])
  const [abierto, setAbierto] = useState(false)

  const buscar = (texto) => {
    setBusqueda(texto)
    if (texto.length < 2) {
      setResultados([])
      setAbierto(false)
      return
    }
    // Filtrar productos de prueba — aquí irá la llamada a la API de Geminus
    const filtrados = PRODUCTOS_PRUEBA.filter(p =>
      p.nombre.toLowerCase().includes(texto.toLowerCase()) ||
      p.codigo.toLowerCase().includes(texto.toLowerCase())
    )
    setResultados(filtrados)
    setAbierto(true)
  }

  const seleccionar = (producto) => {
    onChange(producto)
    setBusqueda(producto.nombre)
    setAbierto(false)
  }

  const limpiar = () => {
    onChange(null)
    setBusqueda('')
    setResultados([])
  }

  return (
    <div className="relative">
      <label className="etiqueta block mb-1.5">
        Producto <span className="text-negativo">*</span>
      </label>

      {value ? (
        // Producto seleccionado
        <div className="flex items-center gap-3 p-3 bg-positivo-bg border border-positivo/30 rounded-xl">
          <IconoPaquete tam={22} className="text-positivo" />
          <div className="flex-1 min-w-0">
            <div className="text-sm font-semibold text-texto">{value.nombre}</div>
            <div className="text-xs text-texto-2 font-mono mt-0.5">{value.codigo}</div>
          </div>
          <button
            onClick={limpiar}
            className="text-xs text-negativo hover:underline flex-shrink-0"
          >
            Cambiar
          </button>
        </div>
      ) : (
        // Buscador
        <div>
          <div className="relative">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-texto-3">
              <IconoBuscar tam={16} />
            </span>
            <input
              value={busqueda}
              onChange={(e) => buscar(e.target.value)}
              onFocus={() => busqueda.length >= 2 && setAbierto(true)}
              placeholder="Escribe el nombre o código del producto…"
              className="w-full pl-10 pr-4 py-3 rounded-xl border border-borde-fuerte text-sm
                text-texto placeholder-texto-3 focus:outline-none focus:border-acento
                focus:ring-2 focus:ring-acento/25 transition"
            />
          </div>

          {abierto && resultados.length > 0 && (
            <div className="absolute z-20 w-full mt-1 bg-superficie border border-borde
              rounded-xl shadow-lg overflow-hidden">
              {resultados.map((p) => (
                <button
                  key={p.codigo}
                  onClick={() => seleccionar(p)}
                  className="w-full flex items-center gap-3 px-4 py-3 hover:bg-superficie-2
                    transition-colors duration-150 ease-suave text-left"
                >
                  <IconoPaquete tam={18} className="text-texto-3" />
                  <div>
                    <div className="text-sm font-medium text-texto">{p.nombre}</div>
                    <div className="text-xs text-texto-3 font-mono">{p.codigo}</div>
                  </div>
                </button>
              ))}
            </div>
          )}

          {abierto && busqueda.length >= 2 && resultados.length === 0 && (
            <div className="absolute z-20 w-full mt-1 bg-superficie border border-borde
              rounded-xl shadow-lg px-4 py-3 text-sm text-texto-2">
              No encontramos productos con ese nombre o código. Escríbelo en la
              descripción y nosotros lo identificamos.
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Pantalla de confirmación ───────────────────────────────────────
function Confirmacion({ codigo, tipo, onNueva }) {
  const [copiado, setCopiado] = useState(false)

  const copiar = () => {
    navigator.clipboard.writeText(codigo)
    setCopiado(true)
    setTimeout(() => setCopiado(false), 2000)
  }

  return (
    <div className="min-h-screen bg-fondo flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="bg-superficie rounded-2xl shadow-md border border-borde p-8 text-center">
          <div className="w-16 h-16 bg-positivo-bg text-positivo rounded-full
            flex items-center justify-center mx-auto mb-5">
            <IconoCheck tam={30} />
          </div>
          <h2 className="text-xl font-semibold text-texto mb-2">¡Solicitud radicada!</h2>
          <p className="text-sm text-texto-2 mb-6">
            Tu {tipo} quedó registrada. Guarda el código: es lo único que
            necesitas para consultar el estado.
          </p>

          <div className="bg-superficie-2 border border-borde rounded-xl p-5 mb-6">
            <p className="etiqueta mb-2">Código de seguimiento</p>
            <div className="cifra text-3xl font-semibold text-texto tracking-wider mb-3 font-mono">
              {codigo}
            </div>
            <button
              onClick={copiar}
              className={`text-sm font-medium hover:underline flex items-center gap-1.5 mx-auto
                ${copiado ? 'text-positivo' : 'text-acento'}`}
            >
              {copiado
                ? <><IconoCheck tam={14} /> Copiado</>
                : <><IconoCopiar tam={14} /> Copiar código</>}
            </button>
          </div>

          <div className="bg-alerta-bg border border-ambar/30 rounded-xl p-4 mb-6 text-left">
            <p className="text-xs font-semibold text-ambar-texto mb-1.5">¿Qué sigue?</p>
            <ul className="text-xs text-texto-2 space-y-1.5">
              <li>· Nuestro equipo revisará tu solicitud</li>
              <li>· Recibirás respuesta dentro del plazo de ley</li>
              <li>· Con tu código puedes consultar el estado cuando quieras</li>
            </ul>
          </div>

          <div className="flex flex-col gap-3">
            <a
              href="/seguimiento"
              className="w-full bg-acento-fuerte hover:bg-acento text-white font-semibold
                py-3 rounded-xl text-sm transition-colors duration-150 ease-suave text-center block"
            >
              Consultar estado de mi solicitud
            </a>
            <button
              onClick={onNueva}
              className="w-full border border-borde-fuerte text-texto-2 hover:bg-superficie-2
                font-medium py-3 rounded-xl text-sm transition-colors duration-150 ease-suave"
            >
              Radicar otra solicitud
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Barra de progreso ──────────────────────────────────────────────
function BarraPasos({ pasoActual, totalPasos, labels }) {
  return (
    <div className="mb-6">
      <div className="flex items-center justify-between mb-2">
        {labels.map((label, idx) => {
          const n = idx + 1
          const activo = pasoActual === n
          const completado = pasoActual > n
          return (
            <div key={n} className="flex flex-col items-center flex-1">
              <div className={`
                w-8 h-8 rounded-full flex items-center justify-center text-xs font-semibold mb-1
                ${completado
                  ? 'bg-positivo text-white'
                  : activo ? 'bg-acento-fuerte text-white' : 'bg-superficie-2 text-texto-3'}
              `}>
                {completado ? <IconoCheck tam={14} /> : n}
              </div>
              <span className={`text-xs font-medium ${activo ? 'text-texto' : 'text-texto-3'}`}>
                {label}
              </span>
            </div>
          )
        })}
      </div>
      <div className="h-1.5 bg-superficie-2 rounded-full overflow-hidden">
        <div
          className="h-full bg-acento-fuerte rounded-full transition-all duration-500"
          style={{ width: `${((pasoActual - 1) / (totalPasos - 1)) * 100}%` }}
        />
      </div>
    </div>
  )
}

// ── Componente principal ───────────────────────────────────────────
export default function FormularioPQRS() {
  const [paso, setPaso] = useState(1)
  const [form, setForm] = useState({
    tipo: '',
    empresa: '',
    nit_cedula: '',
    cliente_nombre: '',
    cliente_email: '',
    cliente_telefono: '',
    ciudad: '',
    departamento: '',
    lote: '',
    factura_numero: '',
    cantidad_factura: '',
    cantidad_reclamo: '',
    presentacion: '',
    cantidad_presentacion: '',
    canal_atencion: '',
    descripcion: '',
    comentario: '',
  })
  const [productoSeleccionado, setProductoSeleccionado] = useState(null)
  const [adjuntoProducto, setAdjuntoProducto] = useState(null)
  const [adjuntoFactura, setAdjuntoFactura]   = useState(null)
  const [adjuntoVideo, setAdjuntoVideo]       = useState(null)
  const [codigoGenerado, setCodigoGenerado]   = useState('')
  const [loading, setLoading]                 = useState(false)
  const [error, setError]                     = useState('')

  const handleChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value })
    setError('')
  }

  // Felicitación y queja no necesitan producto/factura — una queja es por
  // el servicio (ej: "me atendieron mal"), no por un producto específico.
  const esFelicitacion = form.tipo === 'felicitacion'
  const esQueja = form.tipo === 'queja'
  const requiereProducto = !esFelicitacion && !esQueja
  const totalPasosActual = requiereProducto ? 4 : 3
  const labelsActuales = esFelicitacion
    ? ['Tipo', 'Cliente', 'Comentario']
    : esQueja
      ? ['Tipo', 'Cliente', 'Detalle']
      : ['Tipo', 'Cliente', 'Producto', 'Evidencias']

  // Validaciones por paso
  const validarPaso = () => {
    if (paso === 1 && !form.tipo) {
      setError('Selecciona el tipo de solicitud.'); return false
    }
    if (paso === 2) {
      if (!form.empresa.trim())        { setError('El nombre de la empresa es obligatorio.'); return false }
      if (!form.nit_cedula.trim())     { setError('El NIT o cédula es obligatorio.'); return false }
      if (!form.cliente_nombre.trim()) { setError('El nombre del contacto es obligatorio.'); return false }
      if (!form.cliente_telefono.trim()){ setError('El teléfono es obligatorio.'); return false }
      if (!form.ciudad.trim())         { setError('La ciudad es obligatoria.'); return false }
      if (!form.departamento)          { setError('El departamento es obligatorio.'); return false }
    }
    if (paso === 3 && esFelicitacion) {
      if (!form.canal_atencion)       { setError('Selecciona el canal de atención.'); return false }
    }
    if (paso === 3 && esQueja) {
      if (!form.canal_atencion)       { setError('Selecciona el canal de atención.'); return false }
      if (!form.descripcion.trim())   { setError('Cuéntanos qué ocurrió.'); return false }
    }
    if (paso === 3 && requiereProducto) {
      if (!productoSeleccionado)      { setError('Selecciona el producto.'); return false }
      if (!form.lote.trim())          { setError('El lote es obligatorio.'); return false }
      if (!form.factura_numero.trim()){ setError('El número de factura es obligatorio.'); return false }
      if (!form.cantidad_factura.trim()){ setError('La cantidad en factura es obligatoria.'); return false }
    }
    if (paso === 4 && requiereProducto) {
      if (!form.descripcion.trim())   { setError('La descripción es obligatoria.'); return false }
      if (!adjuntoProducto)           { setError('La foto del producto es obligatoria.'); return false }
      if (!adjuntoFactura)            { setError('La foto de la factura es obligatoria.'); return false }
    }
    return true
  }

  const siguientePaso = () => {
    setError('')
    if (!validarPaso()) return
    setPaso(paso + 1)
    window.scrollTo(0, 0)
  }

  const handleSubmit = async () => {
    setError('')
    if (!validarPaso()) return

    setLoading(true)
    try {
      // Usamos FormData para enviar archivos junto con los campos de texto
      const formData = new FormData()
      formData.append('tipo', form.tipo)
      formData.append('empresa', form.empresa)
      formData.append('nit_cedula', form.nit_cedula)
      formData.append('cliente_nombre', form.cliente_nombre)
      formData.append('cliente_email', form.cliente_email)
      formData.append('cliente_telefono', form.cliente_telefono)
      formData.append('ciudad', form.ciudad)
      formData.append('departamento', form.departamento)
      formData.append('canal_atencion', form.canal_atencion)

      if (esFelicitacion) {
        // El backend exige 'descripcion'; el comentario opcional la reemplaza.
        formData.append('descripcion', form.comentario.trim() || 'Felicitación registrada sin comentario adicional.')
      } else if (esQueja) {
        formData.append('descripcion', form.descripcion)
        if (adjuntoVideo) formData.append('adjunto_video', adjuntoVideo)
      } else {
        formData.append('descripcion', form.descripcion)
        formData.append('producto_codigo', productoSeleccionado?.codigo || '')
        formData.append('producto_nombre', productoSeleccionado?.nombre || '')
        formData.append('presentacion', form.presentacion)
        formData.append('cantidad_presentacion', form.cantidad_presentacion)
        formData.append('lote', form.lote)
        formData.append('factura_numero', form.factura_numero)
        formData.append('cantidad_factura', form.cantidad_factura)
        formData.append('cantidad_reclamo', form.cantidad_reclamo)
        if (adjuntoProducto) formData.append('adjunto_producto', adjuntoProducto)
        if (adjuntoFactura)  formData.append('adjunto_factura', adjuntoFactura)
        if (adjuntoVideo)    formData.append('adjunto_video', adjuntoVideo)
      }

      const { data } = await api.post('/public/pqrs', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })

      setCodigoGenerado(data.codigo_seguimiento)
      setPaso(5) // pantalla de confirmación
    } catch (err) {
      setError(err.response?.data?.detail || 'Error al enviar. Intenta de nuevo.')
    } finally {
      setLoading(false)
    }
  }

  const reiniciar = () => {
    setForm({
      tipo: '', empresa: '', nit_cedula: '', cliente_nombre: '',
      cliente_email: '', cliente_telefono: '', ciudad: '', departamento: '',
      lote: '', factura_numero: '', cantidad_factura: '', cantidad_reclamo: '',
      presentacion: '', cantidad_presentacion: '',
      canal_atencion: '',
      descripcion: '', comentario: '',
    })
    setProductoSeleccionado(null)
    setAdjuntoProducto(null)
    setAdjuntoFactura(null)
    setAdjuntoVideo(null)
    setCodigoGenerado('')
    setPaso(1)
  }

  if (paso === 5) {
    const tipoLabel = TIPOS.find(t => t.value === form.tipo)?.label?.toLowerCase() || 'solicitud'
    return <Confirmacion codigo={codigoGenerado} tipo={tipoLabel} onNueva={reiniciar} />
  }

  return (
    <div className="min-h-screen bg-fondo p-4 pb-10">
      <div className="w-full max-w-lg mx-auto">

        {/* Header */}
       <div className="text-center py-6">
       <div className="flex justify-center mb-4">
        <img
         src="/logo.png"
         alt="Protokimica"
         className="h-20 w-auto object-contain drop-shadow-sm"
         />
       </div>

        <h1 className="text-2xl font-bold text-acento-fuerte">
         Protokimica
        </h1>

        <p className="text-sm text-texto-2 mt-1">
         Portal de Radicación de PQRS
       </p>
       </div>

        <BarraPasos pasoActual={paso} totalPasos={totalPasosActual} labels={labelsActuales} />

        <div className="bg-white rounded-2xl shadow-sm border border-borde overflow-hidden">

          {/* ── PASO 1: Tipo ── */}
          {paso === 1 && (
            <div className="p-6">
              <h2 className="text-lg font-bold text-acento-fuerte mb-1">¿Qué tipo de solicitud quieres radicar?</h2>
              <p className="text-sm text-texto-2 mb-5">Selecciona la opción que mejor describe tu caso.</p>
              <div className="grid grid-cols-1 gap-2">
                {TIPOS.map(({ value, label, descripcion, Icono }) => {
                  const elegido = form.tipo === value
                  return (
                    <button
                      key={value}
                      onClick={() => { setForm({ ...form, tipo: value }); setError('') }}
                      aria-pressed={elegido}
                      className={`flex items-center gap-4 p-4 rounded-xl border text-left
                        transition-all duration-150 ease-suave
                        ${elegido
                          ? 'border-acento bg-acento-suave shadow-sm'
                          : 'border-borde hover:border-borde-fuerte hover:bg-superficie-2'}`}
                    >
                      <span className={`w-10 h-10 rounded-lg flex items-center justify-center
                        flex-shrink-0 ${elegido ? 'bg-acento text-white' : 'bg-superficie-2 text-texto-2'}`}>
                        <Icono tam={20} />
                      </span>
                      <div className="min-w-0">
                        <div className="font-semibold text-texto text-sm">{label}</div>
                        <div className="text-xs text-texto-2 mt-0.5">{descripcion}</div>
                      </div>
                      {elegido && <IconoCheck tam={18} className="ml-auto text-acento" />}
                    </button>
                  )
                })}
              </div>
            </div>
          )}

          {/* ── PASO 2: Datos del cliente ── */}
          {paso === 2 && (
            <div className="p-6 space-y-4">
              <div>
                <h2 className="text-lg font-bold text-acento-fuerte mb-1">Datos de la empresa / persona</h2>
                <p className="text-sm text-texto-2">Información del cliente que realiza la solicitud.</p>
              </div>

              <div>
                <label className="block text-xs font-semibold text-texto-2 uppercase tracking-wide mb-1.5">Empresa / Persona <span className="text-negativo">*</span></label>
                <input name="empresa" value={form.empresa} onChange={handleChange} placeholder="Nombre de la empresa" className="w-full px-4 py-3 rounded-xl border border-borde text-sm text-texto placeholder-texto-3 focus:outline-none focus:ring-2 focus:ring-acento transition" />
              </div>

              <div>
                <label className="block text-xs font-semibold text-texto-2 uppercase tracking-wide mb-1.5">NIT / Cédula <span className="text-negativo">*</span></label>
                <input name="nit_cedula" value={form.nit_cedula} onChange={handleChange} placeholder="Ej: 900123456-1" className="w-full px-4 py-3 rounded-xl border border-borde text-sm text-texto placeholder-texto-3 focus:outline-none focus:ring-2 focus:ring-acento transition" />
              </div>

              <div>
                <label className="block text-xs font-semibold text-texto-2 uppercase tracking-wide mb-1.5">Nombre del contacto <span className="text-negativo">*</span></label>
                <input name="cliente_nombre" value={form.cliente_nombre} onChange={handleChange} placeholder="Nombre completo" className="w-full px-4 py-3 rounded-xl border border-borde text-sm text-texto placeholder-texto-3 focus:outline-none focus:ring-2 focus:ring-acento transition" />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-texto-2 uppercase tracking-wide mb-1.5">Teléfono <span className="text-negativo">*</span></label>
                  <input name="cliente_telefono" value={form.cliente_telefono} onChange={handleChange} placeholder="3001234567" className="w-full px-4 py-3 rounded-xl border border-borde text-sm text-texto placeholder-texto-3 focus:outline-none focus:ring-2 focus:ring-acento transition" />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-texto-2 uppercase tracking-wide mb-1.5">Correo</label>
                  <input name="cliente_email" type="email" value={form.cliente_email} onChange={handleChange} placeholder="correo@empresa.com" className="w-full px-4 py-3 rounded-xl border border-borde text-sm text-texto placeholder-texto-3 focus:outline-none focus:ring-2 focus:ring-acento transition" />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-texto-2 uppercase tracking-wide mb-1.5">Ciudad <span className="text-negativo">*</span></label>
                  <input name="ciudad" value={form.ciudad} onChange={handleChange} placeholder="Ej: Medellín" className="w-full px-4 py-3 rounded-xl border border-borde text-sm text-texto placeholder-texto-3 focus:outline-none focus:ring-2 focus:ring-acento transition" />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-texto-2 uppercase tracking-wide mb-1.5">Departamento <span className="text-negativo">*</span></label>
                  <select name="departamento" value={form.departamento} onChange={handleChange} className="w-full px-4 py-3 rounded-xl border border-borde text-sm text-texto focus:outline-none focus:ring-2 focus:ring-acento transition">
                    <option value="">Selecciona...</option>
                    {DEPARTAMENTOS.map(d => <option key={d} value={d}>{d}</option>)}
                  </select>
                </div>
              </div>
            </div>
          )}

          {/* ── PASO 3: Producto (no aplica a felicitación ni queja) ── */}
          {paso === 3 && requiereProducto && (
            <div className="p-6 space-y-4">
              <div>
                <h2 className="text-lg font-bold text-acento-fuerte mb-1">Información del producto</h2>
                <p className="text-sm text-texto-2">Datos del producto y la factura relacionada.</p>
              </div>

              <BuscadorProducto
                value={productoSeleccionado}
                onChange={setProductoSeleccionado}
              />

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-texto-2 uppercase tracking-wide mb-1.5">
                    Presentación
                  </label>
                  <div className="flex gap-2">
                    <select
                      name="presentacion"
                      value={form.presentacion}
                      onChange={handleChange}
                      className="w-full px-4 py-3 rounded-xl border border-borde text-sm text-texto focus:outline-none focus:ring-2 focus:ring-acento transition"
                    >
                      <option value="">Selecciona...</option>
                      {PRESENTACIONES.map(p => <option key={p} value={p}>{p}</option>)}
                    </select>
                    <input
                      type="text"
                      name="cantidad_presentacion"
                      value={form.cantidad_presentacion}
                      onChange={handleChange}
                      disabled={!form.presentacion}
                      placeholder="Cant."
                      className="w-20 px-3 py-3 rounded-xl border border-borde text-sm text-texto focus:outline-none focus:ring-2 focus:ring-acento transition disabled:bg-superficie-2 disabled:cursor-not-allowed"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-texto-2 uppercase tracking-wide mb-1.5">
                    Canal de atención
                  </label>
                  <select
                    name="canal_atencion"
                    value={form.canal_atencion}
                    onChange={handleChange}
                    className="w-full px-4 py-3 rounded-xl border border-borde text-sm text-texto focus:outline-none focus:ring-2 focus:ring-acento transition"
                  >
                    <option value="">Selecciona...</option>
                    {CANALES_ATENCION.map(c => <option key={c} value={c}>{c}</option>)}
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-texto-2 uppercase tracking-wide mb-1.5">Lote <span className="text-negativo">*</span></label>
                  <input name="lote" value={form.lote} onChange={handleChange} placeholder="Ej: L240815" className="w-full px-4 py-3 rounded-xl border border-borde text-sm text-texto placeholder-texto-3 focus:outline-none focus:ring-2 focus:ring-acento transition" />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-texto-2 uppercase tracking-wide mb-1.5">N° Factura <span className="text-negativo">*</span></label>
                  <input name="factura_numero" value={form.factura_numero} onChange={handleChange} placeholder="Ej: FV-2026-1234" className="w-full px-4 py-3 rounded-xl border border-borde text-sm text-texto placeholder-texto-3 focus:outline-none focus:ring-2 focus:ring-acento transition" />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-texto-2 uppercase tracking-wide mb-1.5">Cant. en factura <span className="text-negativo">*</span></label>
                  <input name="cantidad_factura" value={form.cantidad_factura} onChange={handleChange} placeholder="Ej: 10" className="w-full px-4 py-3 rounded-xl border border-borde text-sm text-texto placeholder-texto-3 focus:outline-none focus:ring-2 focus:ring-acento transition" />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-texto-2 uppercase tracking-wide mb-1.5">Cant. en reclamo</label>
                  <input name="cantidad_reclamo" value={form.cantidad_reclamo} onChange={handleChange} placeholder="Ej: 3" className="w-full px-4 py-3 rounded-xl border border-borde text-sm text-texto placeholder-texto-3 focus:outline-none focus:ring-2 focus:ring-acento transition" />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-texto-2 uppercase tracking-wide mb-1.5">Área relacionada</label>
                <select name="area_responsable" value={form.area_responsable} onChange={handleChange} className="w-full px-4 py-3 rounded-xl border border-borde text-sm text-texto focus:outline-none focus:ring-2 focus:ring-acento transition">
                  <option value="">No sé / No aplica</option>
                  {AREAS.map(a => (
                    <option key={a} value={a}>{a}</option>
                  ))}
                </select>
              </div>
            </div>
          )}

          {/* ── PASO 3 (quejas): Canal + descripción + evidencia opcional ── */}
          {paso === 3 && esQueja && (
            <div className="p-6 space-y-4">
              <div>
                <h2 className="text-lg font-bold text-acento-fuerte mb-1">Cuéntanos qué pasó</h2>
                <p className="text-sm text-texto-2">Las quejas son sobre el servicio recibido, no requieren un producto asociado.</p>
              </div>

              <div>
                <label className="block text-xs font-semibold text-texto-2 uppercase tracking-wide mb-1.5">
                  Canal de atención <span className="text-negativo">*</span>
                </label>
                <select
                  name="canal_atencion"
                  value={form.canal_atencion}
                  onChange={handleChange}
                  className="w-full px-4 py-3 rounded-xl border border-borde text-sm text-texto focus:outline-none focus:ring-2 focus:ring-acento transition"
                >
                  <option value="">Selecciona...</option>
                  {CANALES_ATENCION.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-texto-2 uppercase tracking-wide mb-1.5">
                  Descripción detallada <span className="text-negativo">*</span>
                </label>
                <textarea
                  name="descripcion"
                  value={form.descripcion}
                  onChange={handleChange}
                  placeholder="Cuéntanos qué ocurrió, cuándo fue y quién te atendió..."
                  rows={5}
                  className="w-full px-4 py-3 rounded-xl border border-borde text-sm text-texto placeholder-texto-3 focus:outline-none focus:ring-2 focus:ring-acento transition resize-none"
                />
              </div>

              <CampoAdjunto
                label="Video o foto de evidencia"
                descripcion="Si tienes alguna evidencia, adjúntala aquí"
                Icono={IconoVideo}
                accept="image/*,video/mp4,video/quicktime,video/webm"
                hint="Imagen o video — video máx. 20MB"
                archivo={adjuntoVideo}
                onChange={setAdjuntoVideo}
              />
            </div>
          )}

          {/* ── PASO 3 (felicitaciones): Canal + comentario ── */}
          {paso === 3 && esFelicitacion && (
            <div className="p-6 space-y-4">
              <div>
                <h2 className="text-lg font-bold text-acento-fuerte mb-1">¡Gracias por tu felicitación!</h2>
                <p className="text-sm text-texto-2">Cuéntanos por dónde nos conociste y, si quieres, déjanos un comentario.</p>
              </div>

              <div>
                <label className="block text-xs font-semibold text-texto-2 uppercase tracking-wide mb-1.5">
                  Canal de atención <span className="text-negativo">*</span>
                </label>
                <select
                  name="canal_atencion"
                  value={form.canal_atencion}
                  onChange={handleChange}
                  className="w-full px-4 py-3 rounded-xl border border-borde text-sm text-texto focus:outline-none focus:ring-2 focus:ring-acento transition"
                >
                  <option value="">Selecciona...</option>
                  {CANALES_ATENCION_FELICITACION.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-texto-2 uppercase tracking-wide mb-1.5">
                  Comentario <span className="font-normal normal-case text-texto-3">(opcional)</span>
                </label>
                <textarea
                  name="comentario"
                  value={form.comentario}
                  onChange={handleChange}
                  placeholder="Cuéntanos qué te gustó..."
                  rows={4}
                  className="w-full px-4 py-3 rounded-xl border border-borde text-sm text-texto placeholder-texto-3 focus:outline-none focus:ring-2 focus:ring-acento transition resize-none"
                />
              </div>
            </div>
          )}

          {/* ── PASO 4: Descripción y evidencias (no aplica a felicitación ni queja) ── */}
          {paso === 4 && requiereProducto && (
            <div className="p-6 space-y-4">
              <div>
                <h2 className="text-lg font-bold text-acento-fuerte mb-1">Descripción y evidencias</h2>
                <p className="text-sm text-texto-2">Cuéntanos qué ocurrió y adjunta las fotos.</p>
              </div>

              <div>
                <label className="block text-xs font-semibold text-texto-2 uppercase tracking-wide mb-1.5">
                  Descripción detallada <span className="text-negativo">*</span>
                </label>
                <textarea
                  name="descripcion"
                  value={form.descripcion}
                  onChange={handleChange}
                  placeholder="Describe detalladamente qué ocurrió, cuándo fue y cómo podemos ayudarte..."
                  rows={5}
                  className="w-full px-4 py-3 rounded-xl border border-borde text-sm text-texto placeholder-texto-3 focus:outline-none focus:ring-2 focus:ring-acento transition resize-none"
                />
              </div>

              <CampoAdjunto
                label="Foto del producto"
                descripcion="Toma una foto clara del producto con el problema"
                Icono={IconoFoto}
                obligatorio
                archivo={adjuntoProducto}
                onChange={setAdjuntoProducto}
              />

              <CampoAdjunto
                label="Foto o imagen de la factura"
                descripcion="Adjunta la factura de compra del producto"
                Icono={IconoRecibo}
                obligatorio
                archivo={adjuntoFactura}
                onChange={setAdjuntoFactura}
              />

              <CampoAdjunto
                label="Video (opcional)"
                descripcion="Si quieres, adjunta un video corto del problema"
                Icono={IconoVideo}
                accept="video/mp4,video/quicktime,video/webm"
                hint="MP4, MOV o WEBM — máx. 20MB (~20-30 seg)"
                archivo={adjuntoVideo}
                onChange={setAdjuntoVideo}
              />
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="mx-6 mb-4 bg-negativo-bg border border-negativo/25 rounded-xl px-4 py-3 text-sm text-negativo">
              {error}
            </div>
          )}

          {/* Botones de navegación */}
          <div className="px-6 pb-6 flex gap-3">
            {paso > 1 && (
              <button
                onClick={() => { setPaso(paso - 1); setError('') }}
                className="flex-1 border border-borde text-texto-2 hover:bg-fondo font-semibold py-3 rounded-xl text-sm transition"
              >
                ← Atrás
              </button>
            )}
            {paso < totalPasosActual ? (
              <button
                onClick={siguientePaso}
                className="flex-1 bg-ambar hover:bg-ambar-claro text-acento-fuerte font-bold py-3 rounded-xl text-sm transition"
              >
                Continuar →
              </button>
            ) : (
              <button
                onClick={handleSubmit}
                disabled={loading}
                className="flex-1 bg-acento-fuerte hover:bg-acento text-white font-bold py-3 rounded-xl text-sm transition disabled:opacity-60"
              >
                {loading ? 'Enviando…' : 'Enviar solicitud'}
              </button>
            )}
          </div>
        </div>

        <p className="text-center text-xs text-texto-3 mt-4">
          Al enviar aceptas que tus datos sean usados para gestionar tu solicitud.
        </p>
      </div>
    </div>
  )
}