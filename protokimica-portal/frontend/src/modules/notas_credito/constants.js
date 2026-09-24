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
// Declarados EN EL ORDEN DEL FLUJO: bodega, Comercial, Contabilidad, emitir.
// El orden de esta lista termina siendo el de cualquier cosa que la recorra,
// y una lista que empieza por Contabilidad afirma —sin que nadie lo escriba—
// que el proceso empieza ahí.
//
// TODA solicitud empieza por Comercial, venga del mostrador o de una venta
// institucional: quien decide si se le devuelve la plata al cliente es
// Comercial, y eso no cambia con el canal.
//
// `solicitada` era el turno en que Contabilidad autorizaba las del
// mostrador, y ese paso ya no existe: Comercial aprueba y el punto emite.
// Se queda aquí porque es una etapa del HISTORIAL —las que pasaron por ella
// lo siguen diciendo— pero ninguna solicitud viva está en ese estado.
export const ESTADOS = {
  en_bodega:       { label: 'Esperando a la bodega',    color: 'bg-alerta-bg text-alerta' },
  en_comercial:    { label: 'Esperando a Comercial',    color: 'bg-alerta-bg text-alerta' },
  solicitada:      { label: 'Esperando a Contabilidad', color: 'bg-alerta-bg text-alerta' },
  en_contabilidad: { label: 'Esperando a Contabilidad', color: 'bg-alerta-bg text-alerta' },
  aprobada:        { label: 'Aprobada, falta emitir',   color: 'bg-info-bg text-info' },
  devuelta:        { label: 'Devuelta para corregir',   color: 'bg-negativo-bg text-negativo' },
  aplicada:        { label: 'Nota crédito emitida',     color: 'bg-positivo-bg text-positivo' },
  rechazada:       { label: 'Rechazada',                color: 'bg-negativo-bg text-negativo' },
  cancelada:       { label: 'Retirada por quien la pidió', color: 'bg-superficie-2 text-texto-2' },
}

/**
 * Las opciones del desplegable de filtros, agrupadas y en el orden del flujo.
 *
 * Eran once botones sueltos en dos renglones. Once opciones no son un
 * conjunto de botones: son una lista, y una lista se despliega. Además cada
 * clave es un GRUPO que resuelve el servidor (`flujo.GRUPOS_FILTRO`), no un
 * estado: «Contabilidad» cubre los dos momentos en que le toca a ella, y
 * pedirlos por separado obligaría a la pantalla a conocer la cadena.
 */
export const FILTROS = [
  { clave: 'mi_turno', texto: 'Lo que me toca' },
  { clave: '',         texto: 'Todas' },
  { clave: 'abiertas', texto: 'En trámite' },
  {
    grupo: 'Esperando a',
    opciones: [
      { clave: 'bodega',       texto: 'La bodega' },
      { clave: 'comercial',    texto: 'Coordinación Comercial' },
      { clave: 'contabilidad', texto: 'Contabilidad' },
      { clave: 'por_emitir',   texto: 'Que la emitan' },
      { clave: 'devueltas',    texto: 'Que la corrijan' },
    ],
  },
  {
    grupo: 'Ya cerradas',
    opciones: [
      { clave: 'emitidas',   texto: 'Emitidas' },
      { clave: 'rechazadas', texto: 'Rechazadas' },
      { clave: 'retiradas',  texto: 'Retiradas' },
    ],
  },
]

/** Todas las claves que el desplegable puede mandar, aplanadas. */
export function clavesDeFiltro() {
  return FILTROS.flatMap(f => (f.opciones ? f.opciones.map(o => o.clave) : [f.clave]))
}

/** Las que todavía esperan a alguien. Gemelo de `ESTADOS_ABIERTOS` del modelo. */
export const ESTADOS_ABIERTOS = [
  'en_bodega', 'en_comercial', 'en_contabilidad', 'aprobada', 'devuelta',
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
  en_comercial: 'aprobó la nota crédito',
  en_contabilidad: 'verificó ante la DIAN',
  // Etapa histórica: Contabilidad ya no autoriza las del mostrador, pero las
  // que autorizó en su día tienen que seguir diciéndolo.
  solicitada: 'autorizó la solicitud',
}

export function describirPaso({ etapa, accion, usuario_nombre, comentario }) {
  const quien = usuario_nombre || 'Alguien'
  // Un paso que el portal se saltó al cambiar el flujo. No lo hizo nadie, así
  // que no lleva nombre delante: el comentario explica por qué se movió sola.
  if (accion === 'omitido') return comentario ? 'El portal la movió' : 'Se omitió un paso'
  if (accion === 'creada') return `${quien} radicó la solicitud`
  if (accion === 'aprobar') return `${quien} ${VERBO_AL_APROBAR[etapa] ?? 'aprobó'}`
  if (accion === 'rechazar') return `${quien} la rechazó`
  if (accion === 'devolver') return `${quien} la devolvió para corregir`
  if (accion === 'reenviada') return `${quien} la corrigió y la volvió a mandar`
  if (accion === 'cancelada') return `${quien} la retiró`
  if (accion === 'aplicada') return `${quien} registró la nota crédito emitida`
  return `${quien} · ${accion}`
}
