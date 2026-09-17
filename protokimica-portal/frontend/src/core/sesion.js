/**
 * Dónde se guarda la sesión: en el navegador para siempre, o solo hasta que
 * se cierre la pestaña.
 *
 * El login ofrece «Mantener sesión iniciada», y esa casilla tiene que hacer
 * algo de verdad: antes el token iba SIEMPRE a `localStorage`, así que en un
 * computador compartido —los de los puntos de venta lo son— la sesión seguía
 * abierta para el siguiente que lo prendiera. Ahora:
 *
 * - marcada    → `localStorage`: sobrevive cerrar el navegador;
 * - sin marcar → `sessionStorage`: muere con la pestaña.
 *
 * Al guardar se **limpia el otro almacén**. Si no, quien entró marcando la
 * casilla y luego entra sin marcarla dejaría el token viejo en
 * `localStorage`, y al cerrar la pestaña volvería a estar dentro sin haberlo
 * pedido — exactamente lo contrario de lo que acaba de elegir.
 *
 * Todo va en try/catch: un navegador en modo privado o con el almacenamiento
 * bloqueado **lanza** al tocar `localStorage`, y eso no puede dejar a nadie
 * sin poder entrar. En ese caso la sesión vive solo en memoria: recargar
 * obliga a entrar otra vez, que es molesto pero funciona.
 */

export const CLAVE_TOKEN = 'token'
export const CLAVE_USUARIO = 'user'
/** La casilla se recuerda: quien la marcó no tiene que volver a pensarla. */
export const CLAVE_RECORDAR = 'sesion_recordar'

/**
 * Los dos almacenes, o `null` cuando el navegador no los deja usar.
 * Se piden cada vez en vez de guardarse en una constante del módulo: en
 * algunos navegadores el permiso cambia durante la sesión.
 */
function almacen(persistente) {
  try {
    return persistente ? window.localStorage : window.sessionStorage
  } catch {
    return null
  }
}

function borrarDe(persistente) {
  const a = almacen(persistente)
  if (!a) return
  try {
    a.removeItem(CLAVE_TOKEN)
    a.removeItem(CLAVE_USUARIO)
  } catch {
    /* sin almacenamiento no hay nada que borrar */
  }
}

/** Guarda la sesión donde corresponde y limpia el otro almacén. */
export function guardarSesion(token, usuario, recordar) {
  borrarDe(!recordar)
  const a = almacen(recordar)
  if (!a) return false
  try {
    a.setItem(CLAVE_TOKEN, token)
    a.setItem(CLAVE_USUARIO, JSON.stringify(usuario))
    return true
  } catch {
    return false
  }
}

/**
 * El token de la sesión abierta, de donde esté.
 *
 * Se mira primero el de la pestaña: si por cualquier razón quedaran los dos
 * —dos pestañas, una recordada y otra no—, el de esta pestaña es el que la
 * persona eligió hace menos tiempo.
 */
export function tokenGuardado() {
  for (const persistente of [false, true]) {
    const a = almacen(persistente)
    try {
      const token = a?.getItem(CLAVE_TOKEN)
      if (token) return token
    } catch {
      /* sigue con el otro */
    }
  }
  return null
}

/** El usuario guardado, ya convertido. `null` si no hay o si quedó corrupto. */
export function usuarioGuardado() {
  for (const persistente of [false, true]) {
    const a = almacen(persistente)
    try {
      const crudo = a?.getItem(CLAVE_USUARIO)
      if (crudo) return JSON.parse(crudo)
    } catch {
      /* un JSON a medio escribir no puede dejar el portal sin arrancar */
    }
  }
  return null
}

/** Cierra la sesión en los dos almacenes. */
export function limpiarSesion() {
  borrarDe(true)
  borrarDe(false)
}

/** Si la última vez pidió que se le recordara. Por defecto sí, como antes. */
export function recordarPreferido() {
  try {
    return window.localStorage.getItem(CLAVE_RECORDAR) !== 'no'
  } catch {
    return true
  }
}

export function guardarPreferenciaRecordar(recordar) {
  try {
    window.localStorage.setItem(CLAVE_RECORDAR, recordar ? 'si' : 'no')
  } catch {
    /* que no se recuerde la preferencia no impide entrar */
  }
}
