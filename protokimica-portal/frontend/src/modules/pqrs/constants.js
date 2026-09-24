/**
 * Constantes y lógica pura del módulo PQRS.
 *
 * Vive en un .js y no dentro de los .jsx para que `tests/pqrs.test.mjs` pueda
 * importarlo: Node no lee JSX.
 */
import { AREAS, normalizarArea } from '../../core/areas.js'

/**
 * Tope de cada dato corregible. ATADOS a `PQRSEditarDatos` en
 * `backend/app/modules/pqrs/schemas.py`, que a su vez copia el largo de las
 * columnas: si uno cambia, cambian los tres. Un campo sin su `maxLength` en
 * pantalla es el 422 que ya dejó una página en blanco una vez.
 */
export const LIMITES_DATOS = {
  empresa: 150,
  nit_cedula: 30,
  cliente_nombre: 150,
  cliente_email: 180,
  cliente_telefono: 40,
  ciudad: 100,
  departamento: 100,
  factura_numero: 50,
}

/**
 * Tope de cada dato de UN producto. ATADOS a las columnas de
 * `pqrs_productos` (`models/pqrs.py`, que la prueba lee) y a `ProductoIn`.
 */
export const LIMITES_PRODUCTO = {
  producto_codigo: 50,
  producto_nombre: 300,
  presentacion: 30,
  cantidad_presentacion: 20,
  lote: 50,
  cantidad_factura: 20,
  cantidad_reclamo: 20,
}

/**
 * Topes al RADICAR (formulario interno y público): datos de la solicitud y de
 * cada producto. El servidor los vuelve a revisar en `validar_largos()`. Sin
 * el tope en pantalla, escribir «5 galones de 20 litros» en una cantidad no
 * dejaba registrar la PQRS.
 */
export const LIMITES_RADICACION = {
  ...LIMITES_DATOS,
  ...LIMITES_PRODUCTO,
}

/** Cuántos productos admite una PQRS. ATADO a `MAX_PRODUCTOS` de `pqrs/productos.py`. */
export const MAX_PRODUCTOS = 20

// Cada fila lleva una clave propia y no su posición: al quitar la segunda de
// tres, React tiene que saber que la tercera sigue siendo la misma, o el
// buscador de producto de una fila aparecería con lo que se escribió en otra.
let siguienteClave = 0

/** Una fila de producto en blanco, lista para el formulario. */
export function productoVacio() {
  siguienteClave += 1
  return {
    clave: `p${siguienteClave}`,
    producto_codigo: '', producto_nombre: '', presentacion: '', cantidad_presentacion: '',
    lote: '', cantidad_factura: '', cantidad_reclamo: '',
  }
}

const CAMPOS_FILA = Object.keys(LIMITES_PRODUCTO)
const filaVacia = (fila) => CAMPOS_FILA.every(c => !(fila?.[c] ?? '').trim())

/**
 * Las filas listas para mandar como `productos`: sin espacios de sobra, sin la
 * clave de pantalla y sin filas en blanco. Una fila que alguien agregó y no
 * llenó no es un producto.
 */
export function productosParaEnviar(filas) {
  return (filas ?? [])
    .filter(f => !filaVacia(f))
    .map(f => Object.fromEntries(CAMPOS_FILA.map(c => [c, (f[c] ?? '').trim()])))
}

/**
 * Qué le falta a la lista de productos, o `null` si está completa.
 *
 * El formulario público exige lote y cantidad en factura de CADA producto
 * (igual que antes con el único); el interno no, porque una PQRS que entra
 * por teléfono se escribe con lo que el cliente sabe en ese momento.
 * El mensaje dice cuál producto, porque «falta el lote» con cuatro filas en
 * pantalla obliga a revisarlas todas.
 */
export function faltaEnProductos(filas, { exigirDetalle = false } = {}) {
  const llenas = (filas ?? []).filter(f => !filaVacia(f))
  if (llenas.length === 0) {
    return 'Agregue al menos un producto. Si no lo encuentra, use «No encuentro mi producto».'
  }
  if (llenas.length > MAX_PRODUCTOS) {
    return `Una solicitud admite hasta ${MAX_PRODUCTOS} productos.`
  }
  for (const [i, f] of (filas ?? []).entries()) {
    if (filaVacia(f)) continue
    const n = i + 1
    if (!f.producto_nombre?.trim() && !f.producto_codigo?.trim()) {
      return `Producto ${n}: elija cuál es, o quite esa fila.`
    }
    if (exigirDetalle && !f.lote?.trim()) return `Producto ${n}: falta el lote.`
    if (exigirDetalle && !f.cantidad_factura?.trim()) return `Producto ${n}: falta la cantidad en factura.`
  }
  return null
}

/** Los datos corregibles, en el orden de la pantalla. */
export const CAMPOS_EDITABLES = Object.keys(LIMITES_DATOS)

export const DEPARTAMENTOS = [
  'Amazonas', 'Antioquia', 'Arauca', 'Atlántico', 'Bolívar', 'Boyacá', 'Caldas',
  'Caquetá', 'Casanare', 'Cauca', 'Cesar', 'Chocó', 'Córdoba', 'Cundinamarca',
  'Guainía', 'Guaviare', 'Huila', 'La Guajira', 'Magdalena', 'Meta', 'Nariño',
  'Norte de Santander', 'Putumayo', 'Quindío', 'Risaralda', 'San Andrés',
  'Santander', 'Sucre', 'Tolima', 'Valle del Cauca', 'Vaupés', 'Vichada',
]

export const PRESENTACIONES = ['Unidad', 'Kilo', 'Gramo', 'Litro', 'Mililitro']

const normalizar = (texto) => (texto ?? '').trim().toLowerCase().replace(/\s+/g, ' ')

/**
 * Con qué nombre se reconoce una PQRS en la lista y en la cabecera.
 *
 * Una empresa se reconoce por la empresa, no por quién llamó: «Industrias del
 * Valle» se encuentra de un vistazo, «Juan Pérez» obliga a abrirla para saber
 * de qué cliente es. El contacto baja a la segunda línea.
 *
 * Una persona natural escribe su propio nombre en «Empresa / Persona» — el
 * formulario público lo pide obligatorio —, así que empresa y contacto
 * coinciden. Ahí se muestra el nombre una sola vez: repetirlo debajo es
 * ruido. Lo mismo si la empresa viene vacía (PQRS internas viejas).
 *
 * Devuelve `{ titulo, subtitulo }`; `subtitulo` es null cuando no aporta.
 */
export function nombrePrincipal(pqrs) {
  const empresa = (pqrs?.empresa ?? '').trim()
  const contacto = (pqrs?.cliente_nombre ?? '').trim()
  if (empresa && normalizar(empresa) !== normalizar(contacto)) {
    return { titulo: empresa, subtitulo: contacto || null }
  }
  return { titulo: contacto || empresa, subtitulo: null }
}

/**
 * Si a esta PQRS le aplica la sección de producto y factura.
 *
 * Una queja es sobre el servicio y una felicitación no trae producto — el
 * formulario público ni los pide —, así que ahí no se ofrecen. Salvo que ya
 * tenga algo de eso escrito: lo que existe tiene que poder corregirse.
 */
export function aplicaProducto(pqrs) {
  if (!['queja', 'felicitacion'].includes(pqrs?.tipo)) return true
  return Boolean(pqrs.productos?.length)
    || ['factura_numero', 'adjunto_producto', 'adjunto_factura'].some(c => pqrs[c])
}

/** Los valores de la PQRS que se ponen en el formulario de corrección. */
export function datosEditables(pqrs) {
  return Object.fromEntries(CAMPOS_EDITABLES.map(c => [c, pqrs?.[c] ?? '']))
}

/**
 * Solo lo que de verdad cambió, listo para `PATCH /pqrs/{id}/datos`.
 *
 * Mandar el formulario entero haría que el servidor anotara en el historial
 * «Ciudad: Bello → Bello» por cada campo que nadie tocó. Se compara sin los
 * espacios de los extremos, que es como el servidor lo guarda; un campo
 * vaciado viaja como cadena vacía, que el servidor entiende como «bórralo».
 */
export function cambiosDeDatos(pqrs, form) {
  const cambios = {}
  for (const campo of CAMPOS_EDITABLES) {
    const antes = (pqrs?.[campo] ?? '').trim()
    const ahora = (form?.[campo] ?? '').trim()
    if (antes !== ahora) cambios[campo] = ahora
  }
  return cambios
}

// ── Filtro por área asignada ──────────────────────────────────────
/**
 * El filtro de área de la lista es por la que HOY tiene la PQRS
 * (`area_responsable`), no por la causante: lo que se busca ahí es «qué le
 * toca a mi área», mientras que la causante es un dato de indicadores que se
 * marca al cerrar y que la mayoría de las solicitudes abiertas aún no tiene.
 */
export const AREA_SIN_ASIGNAR = '__sin_asignar__'

/**
 * Las áreas a ofrecer en el desplegable: el catálogo completo más las que
 * traigan los datos y ya no estén en él. Sin ese añadido, una PQRS asignada
 * a un área que se retiró del catálogo no tendría con qué filtrarse y solo
 * podría encontrarse mirando la lista entera.
 */
export function areasParaFiltrar(lista) {
  const fuera = new Set()
  for (const pqrs of lista || []) {
    const area = normalizarArea(pqrs.area_responsable)
    if (area && !AREAS.includes(area)) fuera.add(area)
  }
  return [...AREAS, ...[...fuera].sort()]
}

/**
 * ¿Esta PQRS entra en el filtro de área elegido?
 *
 * Se compara el área normalizada para que una solicitud vieja guardada como
 * «Servicio al cliente» aparezca al filtrar por «Servicio al Cliente». Con
 * `AREA_SIN_ASIGNAR` se buscan justamente las que no tienen dueño, que son
 * las peligrosas: el plazo de ley corre igual.
 */
export function coincideAreaAsignada(pqrs, filtro) {
  if (!filtro) return true
  const area = normalizarArea(pqrs?.area_responsable)
  return filtro === AREA_SIN_ASIGNAR ? !area : area === filtro
}

/**
 * Los estados en los que el plazo TODAVÍA corre.
 *
 * Gemelo de `ESTADOS_ABIERTOS` de `modules/pqrs/pendientes.py`, y
 * `tests/pqrs.test.mjs` verifica que coincidan. El servidor ya tenía la
 * regla bien —los recordatorios de «por vencer» nunca miraron una resuelta
 * ni una cerrada—; era la pantalla la que seguía contando.
 */
export const ESTADOS_CON_PLAZO = ['recibido', 'asignado', 'en_proceso']

/**
 * ¿Al plazo de esta PQRS todavía le corre el reloj?
 *
 * **Una PQRS resuelta o cerrada no vence.** La respuesta ya salió, así que
 * el plazo dejó de correr el día que se respondió: seguir contra el reloj
 * del calendario hace que una PQRS cerrada hace medio año aparezca hoy como
 * «Vencida», que no es cierto y es justo lo que nadie quiere ver en un
 * listado que se audita.
 */
export function plazoCorriendo(pqrs) {
  return Boolean(pqrs?.fecha_limite_sla) && ESTADOS_CON_PLAZO.includes(pqrs?.estado)
}

/**
 * Qué decir en la columna de SLA, o `null` si no hay plazo que contar.
 *
 * `ahora` se inyecta para poder probarlo sin depender del reloj.
 */
export function estadoDelPlazo(pqrs, ahora = new Date()) {
  if (!plazoCorriendo(pqrs)) return null

  const dias = Math.ceil((new Date(pqrs.fecha_limite_sla) - ahora) / (1000 * 60 * 60 * 24))
  if (dias < 0) return { tono: 'negativo', texto: 'Vencida' }
  if (dias === 0) return { tono: 'negativo', texto: 'Vence hoy' }
  if (dias <= 2) return { tono: 'alerta', texto: `Vence en ${dias}d` }
  return { tono: 'neutro', texto: `Vence en ${dias}d` }
}

/** Para el conteo del encabezado: las que de verdad están vencidas hoy. */
export function estaVencida(pqrs, ahora = new Date()) {
  return estadoDelPlazo(pqrs, ahora)?.texto === 'Vencida'
}
