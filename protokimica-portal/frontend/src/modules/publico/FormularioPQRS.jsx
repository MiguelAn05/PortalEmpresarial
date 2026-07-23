import { useState, useRef } from 'react'
import api from '../../core/api.js'

// ── Constantes ─────────────────────────────────────────────────────
const TIPOS = [
  { value: 'peticion',   label: 'Petición',    descripcion: 'Solicitar información, documentos o servicios', icon: '📋', color: 'border-purple-200 bg-purple-50', colorActivo: 'border-purple-500 bg-purple-100 ring-2 ring-purple-300' },
  { value: 'queja',      label: 'Queja',       descripcion: 'Expresar inconformidad con nuestro servicio',   icon: '😟', color: 'border-red-200 bg-red-50',       colorActivo: 'border-red-500 bg-red-100 ring-2 ring-red-300'       },
  { value: 'reclamo',    label: 'Reclamo',     descripcion: 'Exigir solución por producto o servicio',       icon: '⚠️', color: 'border-orange-200 bg-orange-50', colorActivo: 'border-orange-500 bg-orange-100 ring-2 ring-orange-300'},
  { value: 'sugerencia', label: 'Sugerencia',  descripcion: 'Proponer mejoras a nuestros productos',         icon: '💡', color: 'border-blue-200 bg-blue-50',  colorActivo: 'border-blue-500 bg-blue-100 ring-2 ring-blue-300'  },
  { value: 'felicitacion',label:'Felicitacion',descripcion: 'Nos importa conocer tu opinion de nuestros servicios',   icon: '🤩', color: 'border-green-200 bg-green-50', colorActivo: 'border-green-500 bg-green-100 ring-2 ring-green-300'}
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
function CampoAdjunto({ label, descripcion, icono, onChange, archivo, obligatorio }) {
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
      <label className="block text-xs font-semibold text-[#6B7EA8] uppercase tracking-wide mb-1.5">
        {label} {obligatorio && <span className="text-red-500">*</span>}
      </label>
      <div
        onClick={() => inputRef.current?.click()}
        onDrop={handleDrop}
        onDragOver={(e) => e.preventDefault()}
        className={`
          border-2 border-dashed rounded-xl p-5 text-center cursor-pointer transition
          ${archivo
            ? 'border-green-400 bg-green-50'
            : 'border-[#D6E0F0] bg-[#F8FAFD] hover:border-[#1A4FA0] hover:bg-[#F0F4FA]'
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
            ) : (
              <div className="w-16 h-16 bg-green-100 rounded-lg flex items-center justify-center text-2xl">
                📄
              </div>
            )}
            <div className="text-left">
              <div className="text-sm font-semibold text-green-700">{archivo.name}</div>
              <div className="text-xs text-green-600 mt-0.5">
                {(archivo.size / 1024 / 1024).toFixed(2)} MB
              </div>
              <button
                onClick={(e) => { e.stopPropagation(); onChange(null) }}
                className="text-xs text-red-500 hover:underline mt-1"
              >
                Cambiar archivo
              </button>
            </div>
          </div>
        ) : (
          <div>
            <div className="text-3xl mb-2">{icono}</div>
            <div className="text-sm font-semibold text-[#1A2B47] mb-1">{descripcion}</div>
            <div className="text-xs text-[#9BACC8]">
              Toca para seleccionar o arrastra aquí
            </div>
            <div className="text-xs text-[#9BACC8] mt-1">
              JPG, PNG, PDF — máx. 10MB
            </div>
          </div>
        )}
      </div>
      <input
        ref={inputRef}
        type="file"
        accept="image/*,.pdf"
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
      <label className="block text-xs font-semibold text-[#6B7EA8] uppercase tracking-wide mb-1.5">
        Producto <span className="text-red-500">*</span>
      </label>

      {value ? (
        // Producto seleccionado
        <div className="flex items-center gap-3 p-3 bg-green-50 border border-green-300 rounded-xl">
          <div className="text-2xl">📦</div>
          <div className="flex-1">
            <div className="text-sm font-bold text-[#1A2B47]">{value.nombre}</div>
            <div className="text-xs text-[#6B7EA8] font-mono mt-0.5">{value.codigo}</div>
          </div>
          <button
            onClick={limpiar}
            className="text-xs text-red-500 hover:underline flex-shrink-0"
          >
            Cambiar
          </button>
        </div>
      ) : (
        // Buscador
        <div>
          <div className="relative">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-[#9BACC8] text-sm">🔍</span>
            <input
              value={busqueda}
              onChange={(e) => buscar(e.target.value)}
              onFocus={() => busqueda.length >= 2 && setAbierto(true)}
              placeholder="Escribe el nombre o código del producto..."
              className="w-full pl-9 pr-4 py-3 rounded-xl border border-[#D6E0F0] text-sm text-[#1A2B47] placeholder-[#9BACC8] focus:outline-none focus:ring-2 focus:ring-[#1A4FA0] transition"
            />
          </div>

          {abierto && resultados.length > 0 && (
            <div className="absolute z-20 w-full mt-1 bg-white border border-[#D6E0F0] rounded-xl shadow-lg overflow-hidden">
              {resultados.map((p) => (
                <button
                  key={p.codigo}
                  onClick={() => seleccionar(p)}
                  className="w-full flex items-center gap-3 px-4 py-3 hover:bg-[#F0F4FA] transition text-left"
                >
                  <span className="text-lg">📦</span>
                  <div>
                    <div className="text-sm font-semibold text-[#1A2B47]">{p.nombre}</div>
                    <div className="text-xs text-[#9BACC8] font-mono">{p.codigo}</div>
                  </div>
                </button>
              ))}
            </div>
          )}

          {abierto && busqueda.length >= 2 && resultados.length === 0 && (
            <div className="absolute z-20 w-full mt-1 bg-white border border-[#D6E0F0] rounded-xl shadow-lg px-4 py-3 text-sm text-[#6B7EA8]">
              No encontramos productos con ese nombre o código.
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
    <div className="min-h-screen bg-[#F0F4FA] flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="bg-white rounded-2xl shadow-sm border border-[#D6E0F0] p-8 text-center">
          <div className="w-20 h-20 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-5">
            <span className="text-4xl">✅</span>
          </div>
          <h2 className="text-xl font-bold text-[#0D2B5E] mb-2">¡Solicitud radicada!</h2>
          <p className="text-sm text-[#6B7EA8] mb-6">
            Tu {tipo} fue recibida exitosamente. Guarda tu código para consultar el estado.
          </p>

          <div className="bg-[#F0F4FA] rounded-xl p-5 mb-6">
            <p className="text-xs font-semibold text-[#6B7EA8] uppercase tracking-wide mb-2">
              Código de seguimiento
            </p>
            <div className="text-3xl font-black text-[#0D2B5E] tracking-wider mb-3 font-mono">
              {codigo}
            </div>
            <button
              onClick={copiar}
              className="text-sm text-[#1A4FA0] font-semibold hover:underline flex items-center gap-1.5 mx-auto"
            >
              {copiado ? '✓ Copiado' : '📋 Copiar código'}
            </button>
          </div>

          <div className="bg-[#FFF4E0] border border-[#F5A800]/30 rounded-xl p-4 mb-6 text-left">
            <p className="text-xs font-semibold text-[#B87700] mb-1">¿Qué sigue?</p>
            <ul className="text-xs text-[#6B7EA8] space-y-1.5">
              <li>• Nuestro equipo revisará tu solicitud</li>
              <li>• Recibirás respuesta en el tiempo establecido</li>
              <li>• Con tu código puedes consultar el estado en cualquier momento</li>
            </ul>
          </div>

          <div className="flex flex-col gap-3">
            <a
              href="/seguimiento"
              className="w-full bg-[#0D2B5E] hover:bg-[#1A4FA0] text-white font-bold py-3 rounded-xl text-sm transition text-center block"
            >
              Consultar estado de mi solicitud
            </a>
            <button
              onClick={onNueva}
              className="w-full border border-[#D6E0F0] text-[#6B7EA8] hover:bg-[#F0F4FA] font-semibold py-3 rounded-xl text-sm transition"
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
                w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold mb-1
                ${completado ? 'bg-green-500 text-white' : activo ? 'bg-[#0D2B5E] text-white' : 'bg-[#D6E0F0] text-[#9BACC8]'}
              `}>
                {completado ? '✓' : n}
              </div>
              <span className={`text-xs font-medium ${activo ? 'text-[#0D2B5E]' : 'text-[#9BACC8]'}`}>
                {label}
              </span>
            </div>
          )
        })}
      </div>
      <div className="h-1.5 bg-[#D6E0F0] rounded-full overflow-hidden">
        <div
          className="h-full bg-[#0D2B5E] rounded-full transition-all duration-500"
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
    canal_atencion: '',
    descripcion: '',
    comentario: '',
  })
  const [productoSeleccionado, setProductoSeleccionado] = useState(null)
  const [adjuntoProducto, setAdjuntoProducto] = useState(null)
  const [adjuntoFactura, setAdjuntoFactura]   = useState(null)
  const [codigoGenerado, setCodigoGenerado]   = useState('')
  const [loading, setLoading]                 = useState(false)
  const [error, setError]                     = useState('')

  const handleChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value })
    setError('')
  }

  // Una felicitación no necesita producto, factura ni evidencias —
  // solo canal de atención y un comentario opcional. Por eso su flujo
  // es más corto (3 pasos en vez de 4).
  const esFelicitacion = form.tipo === 'felicitacion'
  const totalPasosActual = esFelicitacion ? 3 : 4
  const labelsActuales = esFelicitacion
    ? ['Tipo', 'Cliente', 'Comentario']
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
    if (paso === 3 && !esFelicitacion) {
      if (!productoSeleccionado)      { setError('Selecciona el producto.'); return false }
      if (!form.lote.trim())          { setError('El lote es obligatorio.'); return false }
      if (!form.factura_numero.trim()){ setError('El número de factura es obligatorio.'); return false }
      if (!form.cantidad_factura.trim()){ setError('La cantidad en factura es obligatoria.'); return false }
    }
    if (paso === 4 && !esFelicitacion) {
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
      } else {
        formData.append('descripcion', form.descripcion)
        formData.append('producto_codigo', productoSeleccionado?.codigo || '')
        formData.append('producto_nombre', productoSeleccionado?.nombre || '')
        formData.append('lote', form.lote)
        formData.append('factura_numero', form.factura_numero)
        formData.append('cantidad_factura', form.cantidad_factura)
        formData.append('cantidad_reclamo', form.cantidad_reclamo)
        if (adjuntoProducto) formData.append('adjunto_producto', adjuntoProducto)
        if (adjuntoFactura)  formData.append('adjunto_factura', adjuntoFactura)
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
      canal_atencion: '',
      descripcion: '', comentario: '',
    })
    setProductoSeleccionado(null)
    setAdjuntoProducto(null)
    setAdjuntoFactura(null)
    setCodigoGenerado('')
    setPaso(1)
  }

  if (paso === 5) {
    const tipoLabel = TIPOS.find(t => t.value === form.tipo)?.label?.toLowerCase() || 'solicitud'
    return <Confirmacion codigo={codigoGenerado} tipo={tipoLabel} onNueva={reiniciar} />
  }

  return (
    <div className="min-h-screen bg-[#F0F4FA] p-4 pb-10">
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

        <h1 className="text-2xl font-bold text-[#0D2B5E]">
         Protokimica
        </h1>

        <p className="text-sm text-[#6B7EA8] mt-1">
         Portal de Radicación de PQRS
       </p>
       </div>

        <BarraPasos pasoActual={paso} totalPasos={totalPasosActual} labels={labelsActuales} />

        <div className="bg-white rounded-2xl shadow-sm border border-[#D6E0F0] overflow-hidden">

          {/* ── PASO 1: Tipo ── */}
          {paso === 1 && (
            <div className="p-6">
              <h2 className="text-lg font-bold text-[#0D2B5E] mb-1">¿Qué tipo de solicitud quieres radicar?</h2>
              <p className="text-sm text-[#6B7EA8] mb-5">Selecciona la opción que mejor describe tu caso.</p>
              <div className="grid grid-cols-1 gap-3">
                {TIPOS.map((tipo) => (
                  <button
                    key={tipo.value}
                    onClick={() => { setForm({ ...form, tipo: tipo.value }); setError('') }}
                    className={`flex items-center gap-4 p-4 rounded-xl border-2 text-left transition-all ${form.tipo === tipo.value ? tipo.colorActivo : tipo.color}`}
                  >
                    <span className="text-3xl flex-shrink-0">{tipo.icon}</span>
                    <div>
                      <div className="font-bold text-[#1A2B47] text-sm">{tipo.label}</div>
                      <div className="text-xs text-[#6B7EA8] mt-0.5">{tipo.descripcion}</div>
                    </div>
                    {form.tipo === tipo.value && <span className="ml-auto text-[#0D2B5E] text-lg">✓</span>}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* ── PASO 2: Datos del cliente ── */}
          {paso === 2 && (
            <div className="p-6 space-y-4">
              <div>
                <h2 className="text-lg font-bold text-[#0D2B5E] mb-1">Datos de la empresa / persona</h2>
                <p className="text-sm text-[#6B7EA8]">Información del cliente que realiza la solicitud.</p>
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#6B7EA8] uppercase tracking-wide mb-1.5">Empresa / Persona <span className="text-red-500">*</span></label>
                <input name="empresa" value={form.empresa} onChange={handleChange} placeholder="Nombre de la empresa" className="w-full px-4 py-3 rounded-xl border border-[#D6E0F0] text-sm text-[#1A2B47] placeholder-[#9BACC8] focus:outline-none focus:ring-2 focus:ring-[#1A4FA0] transition" />
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#6B7EA8] uppercase tracking-wide mb-1.5">NIT / Cédula <span className="text-red-500">*</span></label>
                <input name="nit_cedula" value={form.nit_cedula} onChange={handleChange} placeholder="Ej: 900123456-1" className="w-full px-4 py-3 rounded-xl border border-[#D6E0F0] text-sm text-[#1A2B47] placeholder-[#9BACC8] focus:outline-none focus:ring-2 focus:ring-[#1A4FA0] transition" />
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#6B7EA8] uppercase tracking-wide mb-1.5">Nombre del contacto <span className="text-red-500">*</span></label>
                <input name="cliente_nombre" value={form.cliente_nombre} onChange={handleChange} placeholder="Nombre completo" className="w-full px-4 py-3 rounded-xl border border-[#D6E0F0] text-sm text-[#1A2B47] placeholder-[#9BACC8] focus:outline-none focus:ring-2 focus:ring-[#1A4FA0] transition" />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-[#6B7EA8] uppercase tracking-wide mb-1.5">Teléfono <span className="text-red-500">*</span></label>
                  <input name="cliente_telefono" value={form.cliente_telefono} onChange={handleChange} placeholder="3001234567" className="w-full px-4 py-3 rounded-xl border border-[#D6E0F0] text-sm text-[#1A2B47] placeholder-[#9BACC8] focus:outline-none focus:ring-2 focus:ring-[#1A4FA0] transition" />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-[#6B7EA8] uppercase tracking-wide mb-1.5">Correo</label>
                  <input name="cliente_email" type="email" value={form.cliente_email} onChange={handleChange} placeholder="correo@empresa.com" className="w-full px-4 py-3 rounded-xl border border-[#D6E0F0] text-sm text-[#1A2B47] placeholder-[#9BACC8] focus:outline-none focus:ring-2 focus:ring-[#1A4FA0] transition" />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-[#6B7EA8] uppercase tracking-wide mb-1.5">Ciudad <span className="text-red-500">*</span></label>
                  <input name="ciudad" value={form.ciudad} onChange={handleChange} placeholder="Ej: Medellín" className="w-full px-4 py-3 rounded-xl border border-[#D6E0F0] text-sm text-[#1A2B47] placeholder-[#9BACC8] focus:outline-none focus:ring-2 focus:ring-[#1A4FA0] transition" />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-[#6B7EA8] uppercase tracking-wide mb-1.5">Departamento <span className="text-red-500">*</span></label>
                  <select name="departamento" value={form.departamento} onChange={handleChange} className="w-full px-4 py-3 rounded-xl border border-[#D6E0F0] text-sm text-[#1A2B47] focus:outline-none focus:ring-2 focus:ring-[#1A4FA0] transition">
                    <option value="">Selecciona...</option>
                    {DEPARTAMENTOS.map(d => <option key={d} value={d}>{d}</option>)}
                  </select>
                </div>
              </div>
            </div>
          )}

          {/* ── PASO 3: Producto (no aplica a felicitaciones) ── */}
          {paso === 3 && !esFelicitacion && (
            <div className="p-6 space-y-4">
              <div>
                <h2 className="text-lg font-bold text-[#0D2B5E] mb-1">Información del producto</h2>
                <p className="text-sm text-[#6B7EA8]">Datos del producto y la factura relacionada.</p>
              </div>

              <BuscadorProducto
                value={productoSeleccionado}
                onChange={setProductoSeleccionado}
              />

              <div>
                <label className="block text-xs font-semibold text-[#6B7EA8] uppercase tracking-wide mb-1.5">
                  Canal de atención
                </label>
                <select
                  name="canal_atencion"
                  value={form.canal_atencion}
                  onChange={handleChange}
                  className="w-full px-4 py-3 rounded-xl border border-[#D6E0F0] text-sm text-[#1A2B47] focus:outline-none focus:ring-2 focus:ring-[#1A4FA0] transition"
                >
                  <option value="">Selecciona...</option>
                  {CANALES_ATENCION.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-[#6B7EA8] uppercase tracking-wide mb-1.5">Lote <span className="text-red-500">*</span></label>
                  <input name="lote" value={form.lote} onChange={handleChange} placeholder="Ej: L240815" className="w-full px-4 py-3 rounded-xl border border-[#D6E0F0] text-sm text-[#1A2B47] placeholder-[#9BACC8] focus:outline-none focus:ring-2 focus:ring-[#1A4FA0] transition" />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-[#6B7EA8] uppercase tracking-wide mb-1.5">N° Factura <span className="text-red-500">*</span></label>
                  <input name="factura_numero" value={form.factura_numero} onChange={handleChange} placeholder="Ej: FV-2026-1234" className="w-full px-4 py-3 rounded-xl border border-[#D6E0F0] text-sm text-[#1A2B47] placeholder-[#9BACC8] focus:outline-none focus:ring-2 focus:ring-[#1A4FA0] transition" />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-[#6B7EA8] uppercase tracking-wide mb-1.5">Cant. en factura <span className="text-red-500">*</span></label>
                  <input name="cantidad_factura" value={form.cantidad_factura} onChange={handleChange} placeholder="Ej: 10" className="w-full px-4 py-3 rounded-xl border border-[#D6E0F0] text-sm text-[#1A2B47] placeholder-[#9BACC8] focus:outline-none focus:ring-2 focus:ring-[#1A4FA0] transition" />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-[#6B7EA8] uppercase tracking-wide mb-1.5">Cant. en reclamo</label>
                  <input name="cantidad_reclamo" value={form.cantidad_reclamo} onChange={handleChange} placeholder="Ej: 3" className="w-full px-4 py-3 rounded-xl border border-[#D6E0F0] text-sm text-[#1A2B47] placeholder-[#9BACC8] focus:outline-none focus:ring-2 focus:ring-[#1A4FA0] transition" />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#6B7EA8] uppercase tracking-wide mb-1.5">Área relacionada</label>
                <select name="area_responsable" value={form.area_responsable} onChange={handleChange} className="w-full px-4 py-3 rounded-xl border border-[#D6E0F0] text-sm text-[#1A2B47] focus:outline-none focus:ring-2 focus:ring-[#1A4FA0] transition">
                  <option value="">No sé / No aplica</option>
                  {['Comercial','Logística','Calidad','HSEQ','Facturación','Servicio al cliente'].map(a => (
                    <option key={a} value={a}>{a}</option>
                  ))}
                </select>
              </div>
            </div>
          )}

          {/* ── PASO 3 (felicitaciones): Canal + comentario ── */}
          {paso === 3 && esFelicitacion && (
            <div className="p-6 space-y-4">
              <div>
                <h2 className="text-lg font-bold text-[#0D2B5E] mb-1">¡Gracias por tu felicitación! 🤩</h2>
                <p className="text-sm text-[#6B7EA8]">Cuéntanos por dónde nos conociste y, si quieres, déjanos un comentario.</p>
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#6B7EA8] uppercase tracking-wide mb-1.5">
                  Canal de atención <span className="text-red-500">*</span>
                </label>
                <select
                  name="canal_atencion"
                  value={form.canal_atencion}
                  onChange={handleChange}
                  className="w-full px-4 py-3 rounded-xl border border-[#D6E0F0] text-sm text-[#1A2B47] focus:outline-none focus:ring-2 focus:ring-[#1A4FA0] transition"
                >
                  <option value="">Selecciona...</option>
                  {CANALES_ATENCION_FELICITACION.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#6B7EA8] uppercase tracking-wide mb-1.5">
                  Comentario <span className="font-normal normal-case text-[#9BACC8]">(opcional)</span>
                </label>
                <textarea
                  name="comentario"
                  value={form.comentario}
                  onChange={handleChange}
                  placeholder="Cuéntanos qué te gustó..."
                  rows={4}
                  className="w-full px-4 py-3 rounded-xl border border-[#D6E0F0] text-sm text-[#1A2B47] placeholder-[#9BACC8] focus:outline-none focus:ring-2 focus:ring-[#1A4FA0] transition resize-none"
                />
              </div>
            </div>
          )}

          {/* ── PASO 4: Descripción y evidencias (no aplica a felicitaciones) ── */}
          {paso === 4 && !esFelicitacion && (
            <div className="p-6 space-y-4">
              <div>
                <h2 className="text-lg font-bold text-[#0D2B5E] mb-1">Descripción y evidencias</h2>
                <p className="text-sm text-[#6B7EA8]">Cuéntanos qué ocurrió y adjunta las fotos.</p>
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#6B7EA8] uppercase tracking-wide mb-1.5">
                  Descripción detallada <span className="text-red-500">*</span>
                </label>
                <textarea
                  name="descripcion"
                  value={form.descripcion}
                  onChange={handleChange}
                  placeholder="Describe detalladamente qué ocurrió, cuándo fue y cómo podemos ayudarte..."
                  rows={5}
                  className="w-full px-4 py-3 rounded-xl border border-[#D6E0F0] text-sm text-[#1A2B47] placeholder-[#9BACC8] focus:outline-none focus:ring-2 focus:ring-[#1A4FA0] transition resize-none"
                />
              </div>

              <CampoAdjunto
                label="Foto del producto"
                descripcion="Toma una foto clara del producto con el problema"
                icono="📷"
                obligatorio
                archivo={adjuntoProducto}
                onChange={setAdjuntoProducto}
              />

              <CampoAdjunto
                label="Foto o imagen de la factura"
                descripcion="Adjunta la factura de compra del producto"
                icono="🧾"
                obligatorio
                archivo={adjuntoFactura}
                onChange={setAdjuntoFactura}
              />
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="mx-6 mb-4 bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          {/* Botones de navegación */}
          <div className="px-6 pb-6 flex gap-3">
            {paso > 1 && (
              <button
                onClick={() => { setPaso(paso - 1); setError('') }}
                className="flex-1 border border-[#D6E0F0] text-[#6B7EA8] hover:bg-[#F0F4FA] font-semibold py-3 rounded-xl text-sm transition"
              >
                ← Atrás
              </button>
            )}
            {paso < totalPasosActual ? (
              <button
                onClick={siguientePaso}
                className="flex-1 bg-[#F5A800] hover:bg-[#FFC840] text-[#0D2B5E] font-bold py-3 rounded-xl text-sm transition"
              >
                Continuar →
              </button>
            ) : (
              <button
                onClick={handleSubmit}
                disabled={loading}
                className="flex-1 bg-[#0D2B5E] hover:bg-[#1A4FA0] text-white font-bold py-3 rounded-xl text-sm transition disabled:opacity-60"
              >
                {loading ? 'Enviando...' : 'Enviar solicitud ✓'}
              </button>
            )}
          </div>
        </div>

        <p className="text-center text-xs text-[#9BACC8] mt-4">
          Al enviar aceptas que tus datos sean usados para gestionar tu solicitud.
        </p>
      </div>
    </div>
  )
}