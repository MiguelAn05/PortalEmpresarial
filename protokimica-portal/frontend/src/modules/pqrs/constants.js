/**
 * Constantes y lógica pura del módulo PQRS.
 *
 * Vive en un .js y no dentro de los .jsx para que `tests/pqrs.test.mjs` pueda
 * importarlo: Node no lee JSX.
 */
import { normalizarArea } from '../../core/areas.js'

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
 * Las áreas a ofrecer en el desplegable: las de la empresa más las que
 * traigan los datos y ya no estén en él. Sin ese añadido, una PQRS asignada
 * a un área que se retiró del catálogo no tendría con qué filtrarse y solo
 * podría encontrarse mirando la lista entera.
 */
export function areasParaFiltrar(lista, areas) {
  const fuera = new Set()
  for (const pqrs of lista || []) {
    const area = normalizarArea(pqrs.area_responsable)
    if (area && !areas.includes(area)) fuera.add(area)
  }
  return [...areas, ...[...fuera].sort()]
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
/** Días corridos que le quedan al plazo (negativo: ya venció). Null si no corre. */
export function diasParaVencer(pqrs, ahora = new Date()) {
  if (!plazoCorriendo(pqrs)) return null
  return Math.ceil((new Date(pqrs.fecha_limite_sla) - ahora) / (1000 * 60 * 60 * 24))
}

// «Vencen esta semana»: siete días corridos o menos.
export const DIAS_POR_VENCER = 7

export function estadoDelPlazo(pqrs, ahora = new Date()) {
  const dias = diasParaVencer(pqrs, ahora)
  if (dias === null) return null

  if (dias < 0) return { tono: 'negativo', texto: 'Vencida' }
  if (dias === 0) return { tono: 'negativo', texto: 'Vence hoy' }
  if (dias <= 2) return { tono: 'alerta', texto: `Vence en ${dias}d` }
  return { tono: 'neutro', texto: `Vence en ${dias}d` }
}

/**
 * Cuánto lleva la PQRS en su área actual, en palabras. Regla de negocio:
 * máximo 3 días hábiles por área (ver `backend/app/modules/pqrs/tiempo_en_area.py`).
 *
 * No calcula nada: los días hábiles y si ya se pasó llegan del servidor
 * (`dias_en_area`, `area_vencida`), que es quien sabe de festivos. Sin
 * `area_desde` no hay reloj corriendo —sin área, o ya respondida— y no se
 * muestra nada.
 */
export function tiempoEnArea(pqrs) {
  if (!pqrs?.area_desde) return null
  const dias = pqrs.dias_en_area ?? 0
  const cuanto = dias === 0 ? 'Llegó hoy al área' : `${dias} ${dias === 1 ? 'día hábil' : 'días hábiles'} en el área`
  if (pqrs.area_vencida) return { tono: 'negativo', texto: `${cuanto}: se pasó del máximo` }
  return { tono: 'neutro', texto: cuanto }
}

/** Para el conteo del encabezado: las que de verdad están vencidas hoy. */
export function estaVencida(pqrs, ahora = new Date()) {
  return estadoDelPlazo(pqrs, ahora)?.texto === 'Vencida'
}

/**
 * Las tarjetas del encabezado, que además FILTRAN la lista.
 *
 * Existen porque el número solo no sirve: leer «4 vencidas» y no poder
 * llegar a esas cuatro obliga a ir a los filtros a reconstruir a mano la
 * misma condición que la tarjeta ya sabe. Y dos de estas ni siquiera se
 * podían reconstruir: «Abiertas» no es un estado (es todo menos cerrado) y
 * «Vencidas» no es un campo, es una cuenta contra el reloj.
 *
 * **La cifra y el filtro salen de la MISMA función.** Antes cada conteo
 * estaba escrito suelto arriba de las tarjetas; con la condición repetida en
 * dos sitios, el día que una cambie la tarjeta va a decir un número y la
 * lista va a mostrar otro — y quien lo note no va a saber cuál creer.
 *
 * `null` (la tarjeta «Total») es no filtrar nada.
 */
export const FOCOS = [
  {
    clave: null,
    label: 'Todas',
    cumple: () => true,
  },
  {
    clave: 'abiertas',
    label: 'Abiertas',
    cumple: (pqrs) => pqrs?.estado !== 'cerrado',
  },
  {
    clave: 'vencidas',
    label: 'Plazo vencido',
    // La misma regla de la columna de SLA: una resuelta o una cerrada no
    // vence. Si aquí se escribiera aparte, la tarjeta contaría una cosa y la
    // columna diría otra sobre la misma PQRS.
    cumple: (pqrs, ahora) => estaVencida(pqrs, ahora),
  },
  {
    clave: 'por_vencer',
    label: 'Vencen esta semana',
    // Todavía en término, pero se les acaba en siete días o menos: es lo que
    // hay que mover HOY para no tener que explicar mañana una vencida.
    cumple: (pqrs, ahora) => {
      const dias = diasParaVencer(pqrs, ahora)
      return dias !== null && dias >= 0 && dias <= DIAS_POR_VENCER
    },
  },
  {
    clave: 'area_vencida',
    label: 'Pasadas en su área',
    // Más de 3 días hábiles en la misma área. Reemplaza a «Sin asignar»:
    // desde la 0.49 toda PQRS nace con quien reparte, así que «sin área» ya
    // no es la señal; la señal es el área que se quedó con el caso.
    cumple: (pqrs) => ESTADOS_CON_PLAZO.includes(pqrs?.estado) && Boolean(pqrs?.area_vencida),
  },
]

/** ¿Esta PQRS entra en el foco elegido? Sin foco, entran todas. */
export function cumpleFoco(pqrs, clave, ahora = new Date()) {
  if (!clave) return true
  const foco = FOCOS.find(f => f.clave === clave)
  // Un foco que no existe no esconde nada: mejor mostrar de más que dejar
  // una lista vacía sin explicación.
  return foco ? foco.cumple(pqrs, ahora) : true
}

/** Cuántas hay en cada foco, para las cifras de las tarjetas. */
export function contarPorFoco(lista, ahora = new Date()) {
  return Object.fromEntries(
    FOCOS.map(f => [String(f.clave), (lista || []).filter(p => f.cumple(p, ahora)).length]),
  )
}

/**
 * Cuánto del plazo ya se gastó, de 0 a 1, para la barrita de la columna de
 * SLA. Null si el plazo ya no corre. Es una proporción de tiempo, no una
 * regla: quién está vencido lo sigue diciendo `estadoDelPlazo`.
 */
export function avancePlazo(pqrs, ahora = new Date()) {
  if (!plazoCorriendo(pqrs) || !pqrs?.fecha_creacion) return null
  const inicio = new Date(pqrs.fecha_creacion).getTime()
  const fin = new Date(pqrs.fecha_limite_sla).getTime()
  if (!(fin > inicio)) return 1
  return Math.min(1, Math.max(0, (ahora.getTime() - inicio) / (fin - inicio)))
}

/**
 * Las vistas de la lista: qué PARTE se está mirando. Las tarjetas (`FOCOS`)
 * recortan dentro de la vista, no la reemplazan.
 *
 * «De mi área» es la pregunta de todos los días —«qué tengo yo»— y solo se
 * ofrece a quien tiene área. Abiertas es la de arranque: lo cerrado se
 * consulta, no se trabaja.
 */
export const VISTAS = [
  { clave: 'abiertas', label: 'Abiertas', cumple: (p) => p?.estado !== 'cerrado' },
  {
    clave: 'mi_area', label: 'De mi área',
    cumple: (p, { area } = {}) => p?.estado !== 'cerrado' && Boolean(area) && p?.area_responsable === area,
  },
  { clave: 'cerradas', label: 'Cerradas', cumple: (p) => p?.estado === 'cerrado' },
  { clave: 'todas', label: 'Todas', cumple: () => true },
]

export function cumpleVista(pqrs, clave, contexto = {}) {
  const vista = VISTAS.find(v => v.clave === clave)
  return vista ? vista.cumple(pqrs, contexto) : true
}

// En qué punto del recorrido queda cada estado.
const RANGO_ESTADO = { recibido: 0, asignado: 1, en_proceso: 1, resuelto: 3, cerrado: 4 }

const plural = (n, palabra) => `${n} ${palabra}${n === 1 ? '' : 's'}`

/**
 * La línea de vida del caso: Recibida → En gestión → (Autorizaciones) →
 * Resuelta → Cerrada. Cada paso dice si ya pasó (`hecho`), si es donde está
 * ahora (`actual`) o si falta (`pendiente`), y cuándo pasó.
 *
 * Las fechas salen del historial (`estado_nuevo`) y de las columnas de la
 * PQRS: nada se inventa. El paso de autorizaciones solo aparece si hubo
 * alguna; un paso vacío en cada PQRS haría creer que siempre hay que pedirla.
 */
export function lineaDeVida(pqrs, autorizaciones = []) {
  if (!pqrs) return []
  const seguimientos = [...(pqrs.seguimientos || [])].sort((a, b) => new Date(a.fecha) - new Date(b.fecha))
  const primera = (estados) => seguimientos.find(s => estados.includes(s.estado_nuevo))?.fecha || null
  const rango = RANGO_ESTADO[pqrs.estado] ?? 0
  const cuenta = (estado) => autorizaciones.filter(a => a.estado === estado).length
  const pendientes = cuenta('pendiente')

  const pasos = [
    { clave: 'recibida', titulo: 'Recibida', fecha: pqrs.fecha_creacion, hecho: true },
    { clave: 'gestion', titulo: 'En gestión', fecha: primera(['asignado', 'en_proceso']), hecho: rango >= 1 },
  ]
  if (autorizaciones.length) {
    pasos.push({
      clave: 'autorizaciones',
      titulo: autorizaciones.length === 1 ? '1 autorización' : `${autorizaciones.length} autorizaciones`,
      detalle: [
        cuenta('aprobada') && plural(cuenta('aprobada'), 'aprobada'),
        cuenta('rechazada') && plural(cuenta('rechazada'), 'rechazada'),
        cuenta('devuelta') && plural(cuenta('devuelta'), 'devuelta'),
        pendientes && plural(pendientes, 'pendiente'),
      ].filter(Boolean).join(' · '),
      hecho: pendientes === 0,
    })
  }
  pasos.push(
    { clave: 'resuelta', titulo: 'Resuelta', fecha: pqrs.fecha_resuelto || primera(['resuelto']), hecho: rango >= 3 },
    { clave: 'cerrada', titulo: 'Cerrada', fecha: pqrs.fecha_cierre, hecho: rango >= 4 },
  )

  // Dónde está ahora: la autorización que se espera, o el primer paso que falta.
  const actual = pendientes ? 'autorizaciones' : (pasos.find(p => !p.hecho)?.clave ?? null)
  return pasos.map(p => ({
    ...p,
    fecha: p.hecho || p.clave === actual ? p.fecha : null,
    estado: p.clave === actual ? 'actual' : p.hecho ? 'hecho' : 'pendiente',
    detalle: p.detalle || (p.clave === 'cerrada' && actual === 'cerrada' ? 'Esperando al cliente' : null),
  }))
}

/**
 * Los filtros del historial. Un caso con autorizaciones junta treinta
 * eventos, y quien entra a ver «cuándo se resolvió» no tiene por qué leer
 * todos los comentarios para llegar ahí.
 */
const EVENTOS_DE_MOVIMIENTO = new Set([
  'cambio_estado', 'asignacion', 'asignacion_area', 'autorizacion_solicitada',
  'autorizacion_respondida', 'reclasificacion', 'causa',
])
export const FILTROS_HISTORIAL = [
  { clave: 'todo', label: 'Todo', cumple: () => true },
  { clave: 'movimientos', label: 'Movimientos', cumple: (s) => EVENTOS_DE_MOVIMIENTO.has(s.tipo_evento) },
  { clave: 'comentarios', label: 'Comentarios', cumple: (s) => s.tipo_evento === 'comentario' },
  { clave: 'adjuntos', label: 'Adjuntos', cumple: (s) => Boolean(s.adjunto_evidencia) || s.tipo_evento === 'cambio_adjunto' },
]

/** El historial filtrado, del más reciente al más antiguo. */
export function filtrarHistorial(seguimientos, clave = 'todo') {
  const filtro = FILTROS_HISTORIAL.find(f => f.clave === clave) || FILTROS_HISTORIAL[0]
  return [...(seguimientos || [])]
    .filter(filtro.cumple)
    .sort((a, b) => new Date(b.fecha) - new Date(a.fecha) || b.id - a.id)
}

/** «Ana María Vargas» → «AV», para el círculo de quien firma. */
export function iniciales(nombre) {
  const partes = (nombre || '').trim().split(/\s+/).filter(Boolean)
  if (!partes.length) return '?'
  const letras = partes.length === 1 ? partes[0].slice(0, 2) : partes[0][0] + partes[partes.length - 1][0]
  return letras.toUpperCase()
}


/**
 * Cómo se llama y con qué gravedad se pinta cada tipo, estado y prioridad.
 * Una sola vez para la lista, el detalle y los filtros (las insignias están
 * en `piezas.jsx`). El tono es una escala de gravedad, no un color por
 * categoría.
 */
export const TIPOS = {
  peticion:     { label: 'Petición',     tono: 'neutro'   },
  queja:        { label: 'Queja',        tono: 'alerta'   },
  reclamo:      { label: 'Reclamo',      tono: 'negativo' },
  sugerencia:   { label: 'Sugerencia',   tono: 'info'     },
  felicitacion: { label: 'Felicitación', tono: 'positivo' },
}

export const ESTADOS = {
  recibido:   { label: 'Recibido',   tono: 'info'     },
  asignado:   { label: 'Asignado',   tono: 'info'     },
  en_proceso: { label: 'En proceso', tono: 'alerta'   },
  resuelto:   { label: 'Resuelto',   tono: 'positivo' },
  cerrado:    { label: 'Cerrado',    tono: 'neutro'   },
}

export const PRIORIDADES = {
  baja:    { label: 'Prioridad baja',    tono: 'neutro'   },
  media:   { label: 'Prioridad media',   tono: 'neutro'   },
  alta:    { label: 'Prioridad alta',    tono: 'alerta'   },
  critica: { label: 'Prioridad crítica', tono: 'negativo' },
}
