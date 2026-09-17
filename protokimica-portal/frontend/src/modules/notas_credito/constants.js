/**
 * Lo que la pantalla de notas crédito sabe sin preguntarle al servidor.
 *
 * Nada de esto decide nada: **quién puede hacer qué llega en `alcance`, y en
 * qué paso va la solicitud llega redactado en `etapa_nombre`**. Aquí solo
 * viven los topes de los campos (atados al schema), cómo se pinta cada estado
 * y las dos preguntas de formulario que se pueden responder sin ir al
 * servidor.
 *
 * Va en un `.js` sin JSX para que `tests/notasCredito.test.mjs` pueda
 * importarlo: es la parte que se rompe en silencio.
 */

// Atados a los mismos números del schema del backend
// (`notas_credito/schemas.py`). Si allá cambian, aquí también: el servidor
// manda, pero un input sin tope deja escribirlo todo para recibir un error
// al final.
export const MAX_FACTURA = 60
export const MAX_OBSERVACIONES = 2000
export const MAX_NUMERO_NC = 60

/**
 * Cómo se pinta cada estado.
 *
 * Los cuatro turnos intermedios van en ámbar: todos significan lo mismo para
 * quien mira la lista —«esto está esperando a alguien»— y pintarlos de
 * colores distintos convertiría el semáforo en un adorno. `devuelta` es la
 * excepción: está esperando a QUIEN LA PIDIÓ, y eso sí es otra cosa.
 *
 * El texto nunca va solo con color: el ámbar de la marca no alcanza el
 * contraste mínimo sobre blanco, así que la etiqueta lo dice con palabras.
 */
export const ESTADOS = {
  solicitada:      { label: 'Esperando a Contabilidad', color: 'bg-alerta-bg text-alerta' },
  en_bodega:       { label: 'Esperando a la bodega',    color: 'bg-alerta-bg text-alerta' },
  en_comercial:    { label: 'Esperando a Comercial',    color: 'bg-alerta-bg text-alerta' },
  en_contabilidad: { label: 'Verificando en la DIAN',   color: 'bg-alerta-bg text-alerta' },
  aprobada:        { label: 'Aprobada, falta emitir',   color: 'bg-info-bg text-info' },
  devuelta:        { label: 'Devuelta para corregir',   color: 'bg-negativo-bg text-negativo' },
  rechazada:       { label: 'Rechazada',                color: 'bg-negativo-bg text-negativo' },
  cancelada:       { label: 'Retirada por quien la pidió', color: 'bg-superficie-2 text-texto-2' },
  aplicada:        { label: 'Nota crédito emitida',     color: 'bg-positivo-bg text-positivo' },
}

/** Las que todavía esperan a alguien. Gemelo de `ESTADOS_ABIERTOS` del modelo. */
export const ESTADOS_ABIERTOS = [
  'solicitada', 'en_bodega', 'en_comercial', 'en_contabilidad', 'aprobada', 'devuelta',
]

export function estaAbierta(estado) {
  return ESTADOS_ABIERTOS.includes(estado)
}

export function etiquetaEstado(estado) {
  return ESTADOS[estado]?.label ?? estado
}

/**
 * ¿Hay que preguntar a qué bodega entró el producto?
 *
 * Son DOS condiciones y las dos importan: el motivo tiene que implicar
 * producto **y** la solicitud tiene que ser de venta institucional. Un punto
 * de venta que devuelve mercancía la recibe en su propio mostrador; no hay
 * bodega que confirme nada, y preguntárselo sería un campo obligatorio que no
 * sabe responder.
 */
export const CANAL_INSTITUCIONAL = 'Venta institucional'

export function pideBodega(canal, motivo) {
  return canal === CANAL_INSTITUCIONAL && Boolean(motivo?.requiere_bodega)
}

/**
 * Qué le falta al formulario para poder enviarse.
 *
 * Devuelve el texto de lo que falta, o `null` si está completo. Se devuelve
 * el motivo y no un booleano porque el botón deshabilitado sin explicación
 * es la forma más rápida de que alguien crea que el portal está roto.
 */
export function faltaEnSolicitud(form, motivo) {
  if (!form.punto_venta) return 'Elige el punto de venta o el canal.'
  if (!form.factura_afectada?.trim()) return 'Escribe la factura afectada.'
  if (!form.observaciones?.trim()) return 'Cuenta qué pasó.'
  if (pideBodega(form.punto_venta, motivo) && !form.bodega) {
    return 'Este motivo implica producto devuelto: dinos a qué bodega entró.'
  }
  return null
}

/**
 * Cómo se redacta cada renglón del historial.
 *
 * El verbo depende de la ETAPA, no solo de la acción: «aprobar» en la bodega
 * es «confirmó que el producto llegó» y en Contabilidad es «verificó ante la
 * DIAN». Decir «aprobó» en los cuatro pasos haría ilegible justo lo que se
 * audita.
 */
const VERBO_AL_APROBAR = {
  en_bodega: 'confirmó que el producto llegó',
  en_comercial: 'aprobó la devolución',
  en_contabilidad: 'verificó ante la DIAN',
  solicitada: 'autorizó la solicitud',
}

export function describirPaso({ etapa, accion, usuario_nombre }) {
  const quien = usuario_nombre || 'Alguien'
  if (accion === 'creada') return `${quien} radicó la solicitud`
  if (accion === 'aprobar') return `${quien} ${VERBO_AL_APROBAR[etapa] ?? 'aprobó'}`
  if (accion === 'rechazar') return `${quien} la rechazó`
  if (accion === 'devolver') return `${quien} la devolvió para corregir`
  if (accion === 'reenviada') return `${quien} la corrigió y la volvió a mandar`
  if (accion === 'cancelada') return `${quien} la retiró`
  if (accion === 'aplicada') return `${quien} registró la nota crédito emitida`
  return `${quien} · ${accion}`
}
