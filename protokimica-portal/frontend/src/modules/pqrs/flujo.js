/**
 * El flujo de conceptos de una PQRS, del lado de la pantalla.
 *
 * Quién sigue, cuándo se detiene y qué se propone lo decide el servidor
 * (`backend/app/modules/pqrs/flujo.py`). Aquí solo se nombra cada estado y se
 * edita la lista de pasos ANTES de mandarla: mover, quitar, agregar.
 */

// Cómo va el flujo entero. Gemelo de `estado_cadena()` del servidor.
export const ESTADOS_FLUJO = {
  sin_flujo: { label: 'Sin iniciar', tono: 'neutro' },
  en_curso:  { label: 'En curso',    tono: 'info'   },
  detenida:  { label: 'Detenido',    tono: 'negativo' },
  lista:     { label: 'Esperando que se reanude', tono: 'alerta' },
  completa:  { label: 'Completo',    tono: 'positivo' },
}

// Cómo va cada paso. Gemelo de `ESTADOS_PASO` de `models/pqrs.py`.
export const ESTADOS_PASO = {
  pendiente: { label: 'Falta',      tono: 'neutro'   },
  en_curso:  { label: 'Esperando',  tono: 'alerta'   },
  aprobado:  { label: 'Aprobado',   tono: 'positivo' },
  rechazado: { label: 'Rechazado',  tono: 'negativo' },
  devuelto:  { label: 'Devuelto',   tono: 'neutro'   },
}

// De dónde salió cada paso, para que se entienda por qué está ahí.
export const ORIGENES = {
  bodega: 'por la bodega',
  tecnico: 'por la causa',
  concepto: 'de la plantilla',
  agregado: 'agregado a mano',
}

// Las clases de paso de una plantilla. Gemelo de `CLASES_PASO`.
export const CLASES_PASO = {
  bodega: 'Concepto de la bodega de despacho',
  tecnico: 'Concepto técnico según la causa',
  concepto: 'Concepto fijo',
}

// Para qué canal es una plantilla. Gemelo de `flujo.TIPOS_CANAL`.
export const APLICA_A = {
  '': 'Cualquier canal',
  institucional: 'Venta institucional',
  sede: 'Punto de venta',
  general: 'Otros canales',
}

// Los tipos de PQRS que puede declarar una plantilla. Gemelo de
// `TIPOS_PQRS` de `models/pqrs.py`; los nombres salen de `TIPOS` de
// `constants.js`.
export const TIPOS_PQRS = ['peticion', 'queja', 'reclamo', 'sugerencia', 'felicitacion']

/**
 * Para quién es una plantilla, en palabras: «Reclamo · Venta institucional».
 * Recibe `TIPOS` para no importar las constantes de toda la PQRS aquí.
 */
export function paraQuien(plantilla, tipos) {
  const nombres = (plantilla.tipos || []).map(t => tipos[t]?.label || t)
  return `${nombres.length ? nombres.join(', ') : 'Cualquier tipo'} · ${APLICA_A[plantilla.aplica_a || '']}`
}

// Tope de pasos: atado a `max_length=20` de `router_flujo.py`.
export const MAX_PASOS = 20

/** Mueve el paso `i` una posición arriba (-1) o abajo (+1). No sale de la lista. */
export function mover(lista, i, delta) {
  const j = i + delta
  if (j < 0 || j >= lista.length) return lista
  const copia = [...lista]
  ;[copia[i], copia[j]] = [copia[j], copia[i]]
  return copia
}

export function quitar(lista, i) {
  return lista.filter((_, k) => k !== i)
}

/**
 * Agrega un concepto al final. Un concepto que ya está no se repite: dos
 * veces el mismo en la misma cadena es pedirle a un área lo que ya dijo.
 * Para volver a pedir uno rechazado está «Volver a pedir».
 */
export function agregar(lista, tipo) {
  if (!tipo || lista.length >= MAX_PASOS) return lista
  if (lista.some(p => p.tipo_autorizacion_id === tipo.id)) return lista
  return [...lista, {
    tipo_autorizacion_id: tipo.id, concepto: tipo.nombre, area: tipo.area_autorizadora, origen: 'agregado',
  }]
}

/** Lo que viaja al servidor: solo el id del paso (si ya existía), el concepto y su origen. */
export function paraEnviar(lista) {
  return lista.map(p => ({
    ...(p.id ? { id: p.id } : {}),
    tipo_autorizacion_id: p.tipo_autorizacion_id,
    origen: p.origen || 'agregado',
  }))
}

/** El último concepto que se rechazó o se devolvió: lo que «Volver a pedir» repite. */
export function ultimoDetenido(pasos) {
  return [...(pasos || [])].reverse().find(p => p.estado === 'rechazado' || p.estado === 'devuelto') || null
}

/**
 * En qué va el flujo, en una línea: lo dice la tarjeta «Conceptos» a quien no
 * lo mueve (el área que firma también quiere saber qué viene después). Recibe
 * el estado que calculó el servidor (`estado_cadena`), no lo deduce.
 */
export function resumenCadena(estado, pasos) {
  const total = pasos?.length || 0
  if (!total || estado === 'sin_flujo') return null
  if (estado === 'en_curso') {
    const i = pasos.findIndex(p => p.estado === 'en_curso')
    return `Paso ${i + 1} de ${total} · esperando a ${pasos[i].area}`
  }
  if (estado === 'detenida') {
    const d = ultimoDetenido(pasos)
    return `Detenido · ${d?.concepto} salió ${d?.estado === 'devuelto' ? 'devuelto' : 'rechazado'}`
  }
  if (estado === 'lista') {
    const faltan = pasos.filter(p => p.estado === 'pendiente').length
    return `Esperando que se reanude · ${faltan === 1 ? 'falta 1 concepto' : `faltan ${faltan} conceptos`}`
  }
  return `Flujo completo · ${total === 1 ? '1 concepto' : `${total} conceptos`}`
}
