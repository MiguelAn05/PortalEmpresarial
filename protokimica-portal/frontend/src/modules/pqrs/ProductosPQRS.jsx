import { useRef, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import api from '../../core/api.js'
import {
  IconoAlerta, IconoEditar, IconoPaquete, IconoPapelera,
} from '../../core/components/Iconos.jsx'
import { mensajeDeError } from '../../core/errores.js'
import { LIMITES_PRODUCTO, MAX_PRODUCTOS, PRESENTACIONES } from './constants.js'

// Mismos números que el buscador público y que el servidor.
const MINIMO_BUSQUEDA = 2
const ESPERA_BUSQUEDA_MS = 300

const inputCls = 'w-full px-3 py-2 rounded-lg border border-borde text-sm text-texto placeholder-texto-3 bg-white focus:outline-none focus:ring-2 focus:ring-acento'
const labelCls = 'block text-xs font-semibold text-texto-2 uppercase tracking-wide mb-1'

const CORREGIBLES = ['presentacion', 'cantidad_presentacion', 'lote', 'cantidad_factura', 'cantidad_reclamo']

/**
 * El cliente escribió este producto porque no lo encontró: aquí se cambia por
 * el del catálogo.
 *
 * Se hace ANTES de cerrar —y el servidor no deja cerrar sin esto— porque
 * después ya no se puede corregir, y el informe de qué producto da más
 * problemas quedaría contando «hipoclorito el de 20 litros» como si fuera un
 * producto aparte.
 *
 * Lo que el cliente escribió se conserva a la vista mientras se busca: es la
 * única pista de qué quiso decir.
 */
function ConfirmarProducto({ pqrsId, producto, puedeConfirmar, onConfirmado }) {
  const [busqueda, setBusqueda] = useState('')
  const [resultados, setResultados] = useState([])
  const [buscando, setBuscando] = useState(false)
  const [error, setError] = useState('')
  const temporizador = useRef(null)
  const turno = useRef(0)

  const buscar = (texto) => {
    setBusqueda(texto)
    setError('')
    clearTimeout(temporizador.current)

    if (texto.trim().length < MINIMO_BUSQUEDA) {
      setResultados([])
      setBuscando(false)
      return
    }

    setBuscando(true)
    const mio = ++turno.current
    temporizador.current = setTimeout(async () => {
      try {
        const { data } = await api.get('/catalogo/productos', { params: { q: texto.trim() } })
        if (mio === turno.current) setResultados(data)
      } catch (err) {
        if (mio === turno.current) {
          setResultados([])
          setError(mensajeDeError(err, 'No se pudo consultar el catálogo.'))
        }
      } finally {
        if (mio === turno.current) setBuscando(false)
      }
    }, ESPERA_BUSQUEDA_MS)
  }

  const confirmar = useMutation({
    mutationFn: (codigo) => {
      const datos = new FormData()
      datos.append('producto_codigo', codigo)
      return api.patch(`/pqrs/${pqrsId}/productos/${producto.id}/confirmar`, datos)
    },
    onSuccess: () => { setError(''); onConfirmado() },
    onError: (e) => setError(mensajeDeError(e, 'No se pudo confirmar el producto.')),
  })

  return (
    <div className="rounded-lg border border-alerta/30 bg-alerta-bg p-3 mt-2">
      {/* El estado no se comunica solo con color: el ámbar de la marca no
          alcanza el contraste mínimo sobre blanco. */}
      <div className="flex items-start gap-2">
        <IconoAlerta tam={15} className="text-alerta mt-0.5 flex-shrink-0" />
        <p className="text-xs text-texto-2">
          <span className="font-semibold text-alerta">Sin confirmar. </span>
          El cliente lo escribió porque no lo encontró en el buscador.
          {puedeConfirmar
            ? ' Búscalo en el catálogo: no se puede cerrar hasta confirmarlo.'
            : ' Servicio al Cliente lo confirma antes de cerrar la solicitud.'}
        </p>
      </div>

      {puedeConfirmar && (
        <div className="mt-2">
          <input
            value={busqueda}
            onChange={(e) => buscar(e.target.value)}
            placeholder="Buscar en el catálogo por nombre o código…"
            aria-label={`Buscar en el catálogo el producto «${producto.producto_nombre}»`}
            className="w-full px-3 py-2 rounded-lg border border-borde-fuerte bg-white text-sm text-texto placeholder-texto-3 focus:outline-none focus:border-acento"
          />
          {buscando && <p className="text-xs text-texto-3 mt-2">Buscando…</p>}
          {!buscando && resultados.length > 0 && (
            <ul className="mt-2 bg-white border border-borde rounded-lg divide-y divide-borde overflow-hidden max-h-56 overflow-y-auto">
              {resultados.map((p) => (
                <li key={p.codigo}>
                  <button
                    onClick={() => confirmar.mutate(p.codigo)}
                    disabled={confirmar.isPending}
                    className="w-full text-left px-3 py-2 hover:bg-superficie-2 disabled:opacity-50 transition-colors duration-150"
                  >
                    <div className="text-sm text-texto">{p.nombre}</div>
                    <div className="text-xs text-texto-3">
                      <span className="cifra">{p.codigo}</span>
                      {p.presentacion && ` · ${p.presentacion}`}
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}
          {!buscando && busqueda.trim().length >= MINIMO_BUSQUEDA && resultados.length === 0 && !error && (
            <p className="text-xs text-texto-2 mt-2">
              No hay nada con «{busqueda.trim()}» en el catálogo. Si el producto
              existe pero no aparece, avísale a TIC's: puede que la
              sincronización con el ERP esté detenida.
            </p>
          )}
          {error && <p role="alert" className="text-xs text-negativo mt-2">{error}</p>}
        </div>
      )}
    </div>
  )
}

/** Los campos de un producto: al corregir o al agregar uno que faltó. */
function CamposProducto({ datos, onChange, conNombre }) {
  const cambiar = (e) => onChange({ ...datos, [e.target.name]: e.target.value })
  const campo = (nombre, etiqueta, placeholder) => (
    <div>
      <label className={labelCls}>{etiqueta}</label>
      <input name={nombre} value={datos[nombre]} onChange={cambiar} maxLength={LIMITES_PRODUCTO[nombre]} placeholder={placeholder} className={inputCls} />
    </div>
  )
  return (
    <div className="grid grid-cols-2 gap-2">
      {conNombre && (
        <>
          <div className="col-span-2">{campo('producto_nombre', 'Nombre *', 'Como lo dijo el cliente')}</div>
          {campo('producto_codigo', 'Código', 'Si lo sabes')}
        </>
      )}
      {campo('lote', 'Lote', 'Ej: L240815')}
      <div>
        <label className={labelCls}>Presentación</label>
        <select name="presentacion" value={datos.presentacion} onChange={cambiar} className={inputCls}>
          <option value="">Sin definir</option>
          {[...PRESENTACIONES, ...(datos.presentacion && !PRESENTACIONES.includes(datos.presentacion) ? [datos.presentacion] : [])]
            .map(p => <option key={p} value={p}>{p}</option>)}
        </select>
      </div>
      {campo('cantidad_presentacion', 'Cant. presentación', 'Ej: 5')}
      {campo('cantidad_factura', 'Cant. en factura', 'Ej: 10')}
      {campo('cantidad_reclamo', 'Cant. en reclamo', 'Ej: 3')}
    </div>
  )
}

function Dato({ etiqueta, valor }) {
  if (!valor) return null
  return (
    <div>
      <div className="text-xs text-texto-3">{etiqueta}</div>
      <div className="text-sm text-texto font-medium">{valor}</div>
    </div>
  )
}

/**
 * Un producto de la PQRS: se ve, se corrige su lote y cantidades, se confirma
 * contra el catálogo o se quita.
 *
 * El nombre y el código no se editan aquí a mano: un producto identificado se
 * cambia confirmándolo contra el catálogo, igual que al radicar.
 */
function Producto({ pqrsId, producto, numero, puedeEditar, puedeConfirmar, onCambio }) {
  const [modo, setModo] = useState('ver')   // ver | corregir | quitar
  const [datos, setDatos] = useState(null)
  const [error, setError] = useState('')

  const valoresActuales = () => Object.fromEntries(CORREGIBLES.map(c => [c, producto[c] ?? '']))
  const cambios = datos
    ? Object.fromEntries(CORREGIBLES
      .filter(c => (producto[c] ?? '').trim() !== (datos[c] ?? '').trim())
      .map(c => [c, datos[c].trim()]))
    : {}

  const terminar = () => { setModo('ver'); setDatos(null); setError(''); onCambio() }

  const corregir = useMutation({
    mutationFn: () => api.patch(`/pqrs/${pqrsId}/productos/${producto.id}`, cambios),
    onSuccess: terminar,
    onError: (e) => setError(mensajeDeError(e, 'No se pudo corregir el producto.')),
  })
  const quitar = useMutation({
    mutationFn: () => api.delete(`/pqrs/${pqrsId}/productos/${producto.id}`),
    onSuccess: terminar,
    onError: (e) => setError(mensajeDeError(e, 'No se pudo quitar el producto.')),
  })

  const nombre = producto.producto_nombre || producto.producto_codigo || 'Sin nombre'
  const presentacion = producto.presentacion
    ? `${producto.presentacion}${producto.cantidad_presentacion ? ` × ${producto.cantidad_presentacion}` : ''}`
    : null

  return (
    <li className="py-3 first:pt-0 last:pb-0">
      <div className="flex items-start gap-2">
        <IconoPaquete tam={16} className={`mt-0.5 ${producto.por_confirmar ? 'text-alerta' : 'text-texto-3'}`} />
        <div className="flex-1 min-w-0">
          <div className="text-sm font-semibold text-texto break-words">
            <span className="cifra text-texto-3 font-normal mr-1">{numero}.</span>{nombre}
          </div>
          {producto.producto_codigo && (
            <div className="cifra text-xs text-texto-3">{producto.producto_codigo}</div>
          )}
        </div>
        {puedeEditar && modo === 'ver' && (
          <div className="flex gap-0.5 flex-shrink-0">
            <button
              onClick={() => { setDatos(valoresActuales()); setModo('corregir') }}
              aria-label={`Corregir lote y cantidades de ${nombre}`}
              className="p-1.5 rounded-lg text-acento hover:bg-acento-suave transition-colors duration-150"
            >
              <IconoEditar tam={14} />
            </button>
            <button
              onClick={() => setModo('quitar')}
              aria-label={`Quitar ${nombre}`}
              className="p-1.5 rounded-lg text-texto-3 hover:text-negativo hover:bg-negativo-bg transition-colors duration-150"
            >
              <IconoPapelera tam={14} />
            </button>
          </div>
        )}
      </div>

      {modo !== 'corregir' && (
        <div className="grid grid-cols-2 gap-x-3 gap-y-1.5 mt-2 pl-6">
          <Dato etiqueta="Lote" valor={producto.lote} />
          <Dato etiqueta="Presentación" valor={presentacion} />
          <Dato etiqueta="Cant. factura" valor={producto.cantidad_factura} />
          <Dato etiqueta="Cant. reclamo" valor={producto.cantidad_reclamo} />
        </div>
      )}

      {producto.por_confirmar && modo === 'ver' && (
        <div className="pl-6">
          <ConfirmarProducto pqrsId={pqrsId} producto={producto} puedeConfirmar={puedeConfirmar} onConfirmado={onCambio} />
        </div>
      )}

      {modo === 'corregir' && (
        <div className="mt-2 pl-6 space-y-2">
          <CamposProducto datos={datos} onChange={(d) => { setDatos(d); setError('') }} />
          <div className="flex gap-2">
            <button onClick={() => { setModo('ver'); setError('') }} className="flex-1 border border-borde hover:bg-superficie-2 text-texto-2 text-xs font-semibold py-2 rounded-lg transition">
              Cancelar
            </button>
            <button
              onClick={() => corregir.mutate()}
              disabled={Object.keys(cambios).length === 0 || corregir.isPending}
              className="flex-1 bg-acento-fuerte hover:bg-acento text-white text-xs font-bold py-2 rounded-lg transition disabled:opacity-50"
            >
              {corregir.isPending ? 'Guardando…' : 'Guardar'}
            </button>
          </div>
        </div>
      )}

      {modo === 'quitar' && (
        <div className="mt-2 ml-6 rounded-lg border border-negativo/25 bg-negativo-bg p-3">
          <p className="text-sm text-texto">¿Quitar «{nombre}» de esta PQRS?</p>
          <p className="text-xs text-texto-2 mt-0.5">Sus datos quedan escritos en el historial.</p>
          <div className="flex gap-2 mt-2">
            <button onClick={() => setModo('ver')} className="flex-1 border border-borde bg-white hover:bg-superficie-2 text-texto-2 text-xs font-semibold py-1.5 rounded-lg transition">
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

      {error && <p role="alert" className="text-xs text-negativo mt-2 pl-6">{error}</p>}
    </li>
  )
}

const NUEVO = {
  producto_nombre: '', producto_codigo: '', presentacion: '', cantidad_presentacion: '',
  lote: '', cantidad_factura: '', cantidad_reclamo: '',
}

/** Un producto que faltó al radicar. Escrito a mano, queda por confirmar. */
function AgregarProducto({ pqrsId, onCambio }) {
  const [abierto, setAbierto] = useState(false)
  const [datos, setDatos] = useState(NUEVO)
  const [error, setError] = useState('')

  const agregar = useMutation({
    mutationFn: () => api.post(`/pqrs/${pqrsId}/productos`,
      Object.fromEntries(Object.entries(datos).map(([k, v]) => [k, v.trim()]))),
    onSuccess: () => { setAbierto(false); setDatos(NUEVO); setError(''); onCambio() },
    onError: (e) => setError(mensajeDeError(e, 'No se pudo agregar el producto.')),
  })

  if (!abierto) {
    return (
      <button
        onClick={() => setAbierto(true)}
        className="mt-3 w-full border border-dashed border-borde-fuerte hover:border-acento hover:bg-acento-suave text-acento text-xs font-semibold py-2 rounded-lg transition"
      >
        + Agregar producto
      </button>
    )
  }

  return (
    <div className="mt-3 rounded-lg border border-acento/40 p-3 space-y-2">
      <p className="text-xs font-bold text-acento-fuerte uppercase tracking-wide">Nuevo producto</p>
      <CamposProducto datos={datos} onChange={(d) => { setDatos(d); setError('') }} conNombre />
      {!datos.producto_codigo.trim() && datos.producto_nombre.trim() && (
        <p className="text-xs text-texto-2">Sin código queda por confirmar contra el catálogo antes de cerrar.</p>
      )}
      {error && <p role="alert" className="text-xs text-negativo">{error}</p>}
      <div className="flex gap-2">
        <button onClick={() => { setAbierto(false); setDatos(NUEVO); setError('') }} className="flex-1 border border-borde hover:bg-superficie-2 text-texto-2 text-xs font-semibold py-2 rounded-lg transition">
          Cancelar
        </button>
        <button
          onClick={() => agregar.mutate()}
          disabled={!datos.producto_nombre.trim() || agregar.isPending}
          className="flex-1 bg-acento-fuerte hover:bg-acento text-white text-xs font-bold py-2 rounded-lg transition disabled:opacity-50"
        >
          {agregar.isPending ? 'Agregando…' : 'Agregar'}
        </button>
      </div>
    </div>
  )
}

/**
 * Los productos de la PQRS, cada uno con su lote y cantidades.
 *
 * `puedeEditar`: corregir, quitar y agregar (quien gestiona, no cerrada).
 * `puedeConfirmar`: amarrar al catálogo (Servicio al Cliente, no cerrada).
 * Los dos llegan resueltos del servidor en `alcance`.
 */
export function ListaProductos({ pqrs, puedeEditar, puedeConfirmar, onCambio }) {
  const productos = pqrs.productos ?? []
  return (
    <div>
      {productos.length === 0 ? (
        <p className="text-sm text-texto-3">Sin productos registrados.</p>
      ) : (
        <ul className="divide-y divide-borde">
          {productos.map((p, i) => (
            <Producto
              key={p.id}
              pqrsId={pqrs.id}
              producto={p}
              numero={i + 1}
              puedeEditar={puedeEditar}
              puedeConfirmar={puedeConfirmar}
              onCambio={onCambio}
            />
          ))}
        </ul>
      )}
      {puedeEditar && productos.length < MAX_PRODUCTOS && (
        <AgregarProducto pqrsId={pqrs.id} onCambio={onCambio} />
      )}
    </div>
  )
}
