/**
 * Lógica pura de Fichas de seguridad, sin React: se prueba con `npm test`.
 *
 * Las validaciones repiten las del servidor con las mismas palabras
 * (`modules/fichas_seguridad/service.py`): el servidor decide, esto evita el
 * viaje cuando el error ya se ve en pantalla.
 */
import {
  CAPACIDAD_GESTIONAR, MAX_CODIGO, MAX_LOTE, MAX_MB, MAX_MB_LECTURA, MAX_NOMBRE, MAX_OBSERVACIONES, MAX_VERSION,
  MIN_NOMBRE, SECCIONES_FDS,
} from './constants.js'
import { tieneCapacidad } from '../../core/capacidades.js'

/**
 * ¿Ofrece los botones de escribir? Pide la capacidad y descarta a `lectura` y
 * `gerencia`, que el servidor bloquea en toda escritura (`solo_lectura_no`)
 * aunque la tengan: un botón que siempre da 403 solo genera la pregunta de
 * por qué no funciona. El servidor sigue siendo quien decide.
 */
export function puedeGestionarFichas(usuario) {
  if (!usuario || usuario.rol === 'lectura' || usuario.rol === 'gerencia') return false
  return tieneCapacidad(usuario, CAPACIDAD_GESTIONAR)
}

/** Hoy como `AAAA-MM-DD` en la hora del computador: tope del campo de fecha. */
export function hoyISO(ahora = new Date()) {
  const mes = String(ahora.getMonth() + 1).padStart(2, '0')
  const dia = String(ahora.getDate()).padStart(2, '0')
  return `${ahora.getFullYear()}-${mes}-${dia}`
}

/**
 * «21 sep 2023». Se arma con las partes del texto y no con `new Date('2023-09-21')`,
 * que se lee como UTC y en Colombia muestra el día anterior.
 */
export function formatoFechaEmision(iso) {
  const partes = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso ?? '')
  if (!partes) return '—'
  const fecha = new Date(Number(partes[1]), Number(partes[2]) - 1, Number(partes[3]))
  return fecha.toLocaleDateString('es-CO', { day: '2-digit', month: 'short', year: 'numeric' })
}

/** Cuándo se subió (llega con hora y zona del servidor): «06 nov 2026». */
export function formatoFechaSubida(iso) {
  const fecha = new Date(iso ?? '')
  if (Number.isNaN(fecha.getTime())) return '—'
  return fecha.toLocaleDateString('es-CO', { day: '2-digit', month: 'short', year: 'numeric' })
}

/** «580 KB», «1,2 MB». */
export function formatoTamano(bytes) {
  if (!Number.isFinite(bytes) || bytes < 0) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1).replace('.', ',')} MB`
}

/**
 * La versión que probablemente sigue, solo como sugerencia editable: si la
 * vigente es un entero («10») propone «11». Con cualquier otro formato
 * («10.1», «B») no adivina: la versión es la que trae el documento.
 */
export function versionSugerida(versiones) {
  const vigente = (versiones ?? []).find(v => v.vigente) ?? versiones?.[0]
  if (!vigente || !/^\d+$/.test(vigente.version)) return ''
  return String(Number(vigente.version) + 1)
}

/** El archivo elegido, antes de enviarlo. null si está bien. */
export function validarArchivo(archivo) {
  if (!archivo) return 'Elige el PDF de la ficha.'
  if (!/\.pdf$/i.test(archivo.name ?? '')) {
    return 'Las fichas de seguridad se suben en PDF. Si la tienes en Excel o Word, expórtala a PDF y vuelve a subirla.'
  }
  if (archivo.size === 0) return 'El archivo llegó vacío. Vuelve a elegirlo.'
  if (archivo.size > MAX_MB * 1024 * 1024) {
    return `El documento no puede superar ${MAX_MB} MB. Si es un PDF escaneado, guárdalo con menos resolución.`
  }
  return null
}

/**
 * Los campos del formulario, antes de enviarlos. `modo`: `crear` (producto +
 * versión), `version` o `corregir_version` (solo versión) o `editar` (producto). Devuelve el primer
 * problema como texto, o null.
 */
export function validarCampos(campos, modo, hoy = hoyISO()) {
  if (modo === 'crear' || modo === 'editar') {
    const nombre = (campos.nombre_producto ?? '').trim()
    if (nombre.length < MIN_NOMBRE) {
      return `Escribe el nombre del producto (mínimo ${MIN_NOMBRE} letras): así se encuentra la ficha en el buscador.`
    }
    if (nombre.length > MAX_NOMBRE) return `El nombre del producto no puede pasar de ${MAX_NOMBRE} caracteres.`
    if ((campos.codigo_producto ?? '').trim().length > MAX_CODIGO) {
      return `El código del producto no puede pasar de ${MAX_CODIGO} caracteres.`
    }
  }
  if (modo === 'editar') return null

  const version = (campos.version ?? '').trim()
  if (!version) return 'Escribe la versión tal como aparece en el encabezado de la ficha (por ejemplo «10»).'
  if (version.length > MAX_VERSION) return `La versión no puede pasar de ${MAX_VERSION} caracteres.`
  if (!campos.fecha_emision) return 'Indica la fecha de emisión que aparece en el encabezado de la ficha.'
  if (campos.fecha_emision > hoy) {
    return 'La fecha de emisión no puede ser futura. Revisa la que trae el encabezado de la ficha.'
  }
  if ((campos.observaciones ?? '').trim().length > MAX_OBSERVACIONES) {
    return `Las observaciones no pueden pasar de ${MAX_OBSERVACIONES} caracteres.`
  }
  return null
}

// ── Documentos generados (certificado AP-F-06 y FDS AP-F-08) ──

/** Los datos en blanco de un documento, para llenarlos a mano. */
export function datosVacios(tipo) {
  if (tipo === 'fds') {
    return {
      producto: '', codigo_producto: '', proveedor: '', version: '', fecha_emision: '',
      secciones: SECCIONES_FDS.map((titulo, i) => ({ numero: i + 1, titulo, contenido: '' })),
    }
  }
  return {
    producto: '', codigo_producto: '', proveedor: '', lote_fabricante: '', lote_protokimica: '',
    fecha_fabricacion: '', fecha_vencimiento: '', parametros: [],
  }
}

/** Parámetro en blanco para la fila nueva de la tabla. */
export const parametroVacio = () => ({ nombre: '', unidad: '', requisito: '', metodo: '', resultado: '' })

/**
 * Lo que llega de la lectura, listo para el formulario: una FDS siempre con
 * sus 16 secciones en orden (las que no se leyeron, vacías) y los textos sin
 * `null`. No inventa nada: solo da forma.
 */
export function datosParaFormulario(tipo, leidos) {
  const base = datosVacios(tipo)
  const datos = { ...base }
  Object.keys(base).forEach((k) => { if (typeof base[k] === 'string') datos[k] = String(leidos?.[k] ?? '') })
  if (tipo === 'fds') {
    const porNumero = new Map((leidos?.secciones ?? []).map(s => [Number(s.numero), s]))
    datos.secciones = base.secciones.map(s => ({ ...s, contenido: String(porNumero.get(s.numero)?.contenido ?? '') }))
  } else {
    datos.parametros = (leidos?.parametros ?? []).map(p => ({ ...parametroVacio(), ...p }))
  }
  return datos
}

/**
 * Antes de generar: solo el producto es obligatorio (lo demás puede quedar
 * vacío, como en el servidor). null si está bien.
 */
export function validarDocumento(datos) {
  if (!(datos?.producto ?? '').trim()) return 'Escribe el nombre del producto para poder generar el documento.'
  return null
}

/** El PDF que se va a leer, antes de enviarlo. null si está bien. */
export function validarArchivoLectura(archivo) {
  if (!archivo) return 'Elige el documento del proveedor.'
  if (!/\.pdf$/i.test(archivo.name ?? '')) {
    return 'Solo se pueden leer documentos en PDF. Si está en Word o Excel, expórtalo a PDF; si es una foto, llena el documento a mano.'
  }
  if (archivo.size === 0) return 'El archivo llegó vacío. Vuelve a elegirlo.'
  if (archivo.size > MAX_MB_LECTURA * 1024 * 1024) {
    return `El documento no puede superar ${MAX_MB_LECTURA} MB. Si es un PDF escaneado, guárdalo con menos resolución.`
  }
  return null
}

/** Los archivos del lote: hasta `MAX_LOTE`. Devuelve los que caben y cuántos sobraron. */
export function recortarLote(archivos) {
  const lista = Array.from(archivos ?? [])
  return { archivos: lista.slice(0, MAX_LOTE), sobran: Math.max(0, lista.length - MAX_LOTE) }
}

/**
 * Corre `tarea` sobre cada elemento con a lo sumo `limite` a la vez. Una
 * tarea que falla NO detiene a las demás: queda en su posición como
 * `{ ok: false, error }`. El resultado conserva el orden de entrada.
 */
export async function procesarConConcurrencia(elementos, limite, tarea, alTerminar = () => {}) {
  const resultados = new Array(elementos.length)
  let siguiente = 0
  const trabajador = async () => {
    while (siguiente < elementos.length) {
      const i = siguiente++
      try { resultados[i] = { ok: true, valor: await tarea(elementos[i], i) } }
      catch (error) { resultados[i] = { ok: false, error } }
      alTerminar(i, resultados[i])
    }
  }
  await Promise.all(Array.from({ length: Math.min(limite, elementos.length) }, trabajador))
  return resultados
}

/** Los generados bajan al final de la lista del lote; el resto conserva su orden. */
export function ordenarLote(items) {
  return [...items].sort((a, b) => Number(a.estado === 'generado') - Number(b.estado === 'generado'))
}
