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
