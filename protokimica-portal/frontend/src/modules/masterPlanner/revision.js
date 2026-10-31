// Lógica pura de la aprobación de documentos, sin JSX para poder probarla.
//
// El servidor es la autoridad (`master_planner/revision.py`): esto solo
// evita mandar algo que se sabe que va a rechazar, con el mismo mensaje.

export const REVISION_VACIA = { plantilla_id: null, revisores: [] }

/**
 * Qué le falta a la elección de revisores, o null si está completa. Mismas
 * reglas que `revision.configurar()`: una persona por paso, personas
 * distintas, y nunca quien tiene la tarea.
 */
export function problemaRevisores(plantilla, revisores, asignadoId = null) {
  if (!plantilla) return 'Elige una cadena de revisión.'
  const faltan = plantilla.pasos.filter((_, i) => !revisores[i])
  if (faltan.length) return `Falta elegir quién firma como ${faltan.map(p => p.nombre).join(' y ')}.`
  if (new Set(revisores).size !== revisores.length) {
    return 'Cada paso lo firma una persona distinta: si no, la segunda firma no revisa nada.'
  }
  if (asignadoId && revisores.includes(Number(asignadoId))) {
    return 'Quien tiene la tarea no puede firmar su propio documento.'
  }
  return null
}

/**
 * Dónde cayó un clic sobre la página, como fracción de 0 a 1. Así lo guarda
 * el servidor: en píxeles, el punto se movería con el zoom o con otra
 * pantalla.
 */
export function puntoEnPagina(clienteX, clienteY, rect) {
  const limitar = (v) => Math.min(1, Math.max(0, v))
  const redondear = (v) => Math.round(v * 10000) / 10000
  return {
    pos_x: redondear(limitar((clienteX - rect.left) / rect.width)),
    pos_y: redondear(limitar((clienteY - rect.top) / rect.height)),
  }
}

/**
 * Las observaciones numeradas en el orden en que se hicieron: el número del
 * punto en la página y el de la lista tienen que ser el mismo.
 */
export function numerarObservaciones(observaciones = []) {
  return observaciones.map((o, i) => ({ ...o, numero: i + 1 }))
}

/** La dirección de una celda como la dice Excel y como la guarda el servidor. */
export function claveCelda(hoja, celda) {
  return `${hoja}!${celda}`
}

const FECHA_ISO = /^(\d{4})-(\d{2})-(\d{2})$/

/**
 * Cómo se lee un valor de la hoja. El servidor manda los números como
 * números y las fechas como `AAAA-MM-DD` (ver `core/hoja_calculo.py`): aquí
 * se escriben como los escribe una persona en Colombia.
 */
export function textoCelda(valor) {
  if (valor === null || valor === undefined) return ''
  if (typeof valor === 'number') return valor.toLocaleString('es-CO', { maximumFractionDigits: 4 })
  const fecha = FECHA_ISO.exec(valor)
  if (fecha) return `${fecha[3]}/${fecha[2]}/${fecha[1]}`
  return String(valor)
}

/** Dónde queda una observación, en palabras: «página 3», «Balance · C14», «general». */
export function lugarObservacion(o) {
  if (o.pagina) return `página ${o.pagina}`
  if (o.celda) return `${o.hoja} · ${o.celda}`
  return 'general'
}

// Cuánto hay que mover el mouse para que deje de ser un clic y sea un
// recuadro. Menos que esto es el temblor de la mano al hacer clic.
export const UMBRAL_ARRASTRE_PX = 6

/**
 * Lo que dejó el mouse entre que se apretó y se soltó: un PUNTO si casi no
 * se movió, o un RECUADRO (esquina superior izquierda + tamaño, todo como
 * fracción de la página) si se arrastró. Se arrastre hacia donde se
 * arrastre, la esquina es la de arriba a la izquierda, y nunca se sale de
 * la página: así lo exige el servidor.
 */
export function marcaEnPagina(inicio, fin, rect) {
  const quieto = Math.abs(fin.x - inicio.x) < UMBRAL_ARRASTRE_PX && Math.abs(fin.y - inicio.y) < UMBRAL_ARRASTRE_PX
  if (quieto) return puntoEnPagina(fin.x, fin.y, rect)
  const a = puntoEnPagina(Math.min(inicio.x, fin.x), Math.min(inicio.y, fin.y), rect)
  const b = puntoEnPagina(Math.max(inicio.x, fin.x), Math.max(inicio.y, fin.y), rect)
  const tamano = (v) => Math.floor(v * 10000) / 10000
  const ancho = tamano(b.pos_x - a.pos_x)
  const alto = tamano(b.pos_y - a.pos_y)
  // Arrastrado por fuera del borde puede quedar sin alto o sin ancho: eso
  // no enmarca nada, y se toma como un punto donde se soltó.
  if (!ancho || !alto) return puntoEnPagina(fin.x, fin.y, rect)
  return { ...a, ancho, alto }
}
