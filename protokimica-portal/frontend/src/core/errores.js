/**
 * Convierte el error de una petición en un texto que se pueda mostrar.
 *
 * Existe por un fallo concreto: cuando el backend responde 422 (validación),
 * FastAPI NO manda `detail` como texto sino como una lista de objetos:
 *
 *   { detail: [ { type, loc, msg, input, ctx }, ... ] }
 *
 * Al hacer `setError(data.detail)` y pintarlo, React recibe objetos como
 * hijos y lanza el error #31 — la pantalla se pone en blanco y el usuario no
 * se entera de qué campo estaba mal. Un dato inválido no puede tumbar la
 * página: tiene que decir qué corregir.
 */

/** Traduce los mensajes de Pydantic, que vienen en inglés. */
const TRADUCCIONES = [
  [/field required/i, 'es obligatorio'],
  // La `s?` final no sobra: sin ella, "characters" deja su última letra
  // suelta y el mensaje sale como "300 caracteress".
  [/string should have at least (\d+) characters?/i, 'debe tener al menos $1 caracteres'],
  [/string should have at most (\d+) characters?/i, 'no puede pasar de $1 caracteres'],
  [/input should be a valid integer/i, 'debe ser un número entero'],
  [/input should be a valid number/i, 'debe ser un número'],
  [/input should be a valid date/i, 'debe ser una fecha válida'],
  [/input should be a valid datetime/i, 'debe ser una fecha válida'],
  [/input should be a valid boolean/i, 'debe ser sí o no'],
  [/value is not a valid email/i, 'no es un correo válido'],
  [/input should be greater than or equal to (\S+)/i, 'debe ser al menos $1'],
  [/input should be less than or equal to (\S+)/i, 'no puede pasar de $1'],
]

function traducir(mensaje) {
  for (const [patron, reemplazo] of TRADUCCIONES) {
    if (patron.test(mensaje)) return mensaje.replace(patron, reemplazo)
  }
  return mensaje
}

/**
 * El nombre del campo, sacado de `loc`. Viene como ["body", "descripcion"]
 * y a veces con índices: ["body", "acciones", 0, "descripcion"].
 */
function nombreDelCampo(loc) {
  if (!Array.isArray(loc)) return null
  const partes = loc.filter(p => typeof p === 'string' && !['body', 'query', 'path'].includes(p))
  if (!partes.length) return null
  return partes[partes.length - 1].replace(/_/g, ' ')
}

/** Un error de validación de Pydantic → una frase. */
function frasePorError(detalle) {
  const msg = traducir(detalle?.msg || 'tiene un valor inválido')
  const campo = nombreDelCampo(detalle?.loc)
  if (!campo) return msg
  return `${campo.charAt(0).toUpperCase()}${campo.slice(1)}: ${msg}`
}

/**
 * El mensaje que se le muestra a la persona.
 *
 * @param error       lo que capturó el catch (típicamente un error de axios)
 * @param porDefecto  qué decir cuando el backend no explicó nada
 */
export function mensajeDeError(error, porDefecto = 'No se pudo completar la acción.') {
  const detail = error?.response?.data?.detail

  // Lo normal en este portal: el backend manda un texto que ya dice qué hacer.
  if (typeof detail === 'string' && detail.trim()) return detail

  // 422: una lista de errores de validación, uno por campo.
  if (Array.isArray(detail) && detail.length) {
    return detail.map(frasePorError).join('. ')
  }

  // Algún objeto suelto con mensaje adentro.
  if (detail && typeof detail === 'object') {
    if (typeof detail.msg === 'string') return frasePorError(detail)
    return porDefecto
  }

  // Ni siquiera hubo respuesta: se cayó la red o el servidor no contestó.
  if (error?.request && !error?.response) {
    return 'No se pudo conectar con el servidor. Revisa tu conexión e intenta de nuevo.'
  }

  return porDefecto
}
