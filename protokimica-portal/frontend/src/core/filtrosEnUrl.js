/**
 * Los filtros de una pantalla viven en la URL, y la pestaña los recuerda.
 *
 * Vivían en `useState`, que es memoria de la PANTALLA: al abrir el detalle
 * de una PQRS la lista se desmonta y los olvida, así que volver obligaba a
 * poner otra vez «Cerradas», el área y la fecha. Pasaba en todo el portal.
 *
 * - **En la URL** (`/pqrs?vista=cerradas&area=Calidad`): el «atrás» del
 *   navegador y F5 vuelven al mismo recorte, y un enlace filtrado se puede
 *   mandar por chat.
 * - **Y en `sessionStorage`**, por pantalla: entrar por el menú lleva a
 *   `/pqrs` limpio, y sin esto irse a Indicadores y volver también los
 *   borraba. Muere con la pestaña, a propósito: mañana se empieza de cero.
 *
 * Solo se escribe lo que difiere del valor por defecto, para que la URL de
 * quien no filtró nada siga siendo `/pqrs`. «Limpiar» borra también lo
 * guardado; si no, el siguiente `/pqrs` limpio lo restauraría.
 *
 * Este archivo no importa React: es la regla, y se prueba en
 * `tests/filtrosEnUrl.test.mjs`. El hook está en `useFiltrosEnUrl.js`.
 */

const PREFIJO_ALMACEN = 'filtros:'

/** El nombre del parámetro en la URL. El prefijo separa dos listas de una misma ruta. */
const nombre = (prefijo, clave) => `${prefijo}${clave}`

/** ¿La URL trae ALGUNO de los filtros de esta lista? */
export function tieneFiltros(params, porDefecto, prefijo = '') {
  return Object.keys(porDefecto).some(clave => params.has(nombre(prefijo, clave)))
}

/** Los filtros que dice la URL, con el valor por defecto en lo que no traiga. */
export function leerFiltros(params, porDefecto, prefijo = '') {
  const filtros = {}
  for (const [clave, defecto] of Object.entries(porDefecto)) {
    const valor = params.get(nombre(prefijo, clave))
    filtros[clave] = valor === null ? defecto : valor
  }
  return filtros
}

/**
 * La URL con los cambios aplicados. Lo que vuelve a su valor por defecto (o
 * a vacío) se quita; los demás parámetros —`?tarea=42` y compañía— se dejan.
 */
export function escribirFiltros(params, cambios, porDefecto, prefijo = '') {
  const siguientes = new URLSearchParams(params)
  for (const [clave, valor] of Object.entries(cambios)) {
    if (!(clave in porDefecto)) continue
    const texto = valor === null || valor === undefined ? '' : String(valor)
    if (texto === String(porDefecto[clave] ?? '')) siguientes.delete(nombre(prefijo, clave))
    else siguientes.set(nombre(prefijo, clave), texto)
  }
  return siguientes
}

/** Solo los parámetros de esta lista, para guardarlos. Vacío si no hay ninguno. */
export function soloFiltros(params, porDefecto, prefijo = '') {
  const propios = new URLSearchParams()
  for (const clave of Object.keys(porDefecto)) {
    const valor = params.get(nombre(prefijo, clave))
    if (valor !== null) propios.set(nombre(prefijo, clave), valor)
  }
  return propios
}

// ── Lo que recuerda la pestaña ────────────────────────────────────

const claveAlmacen = (ruta, prefijo) => `${PREFIJO_ALMACEN}${ruta}:${prefijo}`

// En modo privado tocar el almacén LANZA: eso no puede tumbar una lista.
function almacen() {
  try { return window.sessionStorage } catch { return null }
}

export function filtrosGuardados(ruta, prefijo = '') {
  try {
    return new URLSearchParams(almacen()?.getItem(claveAlmacen(ruta, prefijo)) || '')
  } catch {
    return new URLSearchParams()
  }
}

export function guardarFiltros(ruta, prefijo, propios) {
  const a = almacen()
  if (!a) return
  try {
    const texto = propios.toString()
    if (texto) a.setItem(claveAlmacen(ruta, prefijo), texto)
    else a.removeItem(claveAlmacen(ruta, prefijo))
  } catch {
    /* sin almacén, la URL sigue funcionando */
  }
}

/** Al cerrar sesión: quien entre después en esa pestaña no hereda los filtros. */
export function olvidarFiltros() {
  const a = almacen()
  if (!a) return
  try {
    Object.keys(a).filter(k => k.startsWith(PREFIJO_ALMACEN)).forEach(k => a.removeItem(k))
  } catch {
    /* nada que olvidar */
  }
}
