/**
 * La versión con la que se compiló este bundle.
 *
 * No se escribe a mano: Vite la inyecta leyendo
 * `backend/app/core/version.py`, que es la única fuente. Si algún día
 * `__VERSION__` no existe (por ejemplo en `node` corriendo una prueba), se
 * dice «dev» en vez de reventar.
 */
export const VERSION_APP =
  typeof __VERSION__ !== 'undefined' ? __VERSION__ : 'dev'

/**
 * Compara dos versiones `MAYOR.MENOR.PARCHE`.
 * Devuelve <0 si `a` es anterior, 0 si son iguales, >0 si `a` es posterior.
 *
 * Comparar como texto no sirve: '0.9.0' > '0.11.0' alfabéticamente, que es
 * justo al revés de lo que uno quiere.
 */
export function compararVersiones(a, b) {
  const partes = (v) => String(v ?? '').split('.').map(n => parseInt(n, 10) || 0)
  const [x, y] = [partes(a), partes(b)]
  for (let i = 0; i < Math.max(x.length, y.length); i++) {
    const d = (x[i] || 0) - (y[i] || 0)
    if (d !== 0) return d
  }
  return 0
}

/**
 * ¿El servidor va adelante del bundle que tiene cargado el navegador?
 *
 * Pasa de verdad en este portal: el `dist/` se commitea y el backend se
 * reconstruye aparte, así que el servidor puede tener funciones que esta
 * pestaña todavía no conoce. Recargar lo arregla; no saberlo produce
 * reportes de errores que nadie puede reproducir.
 */
export function servidorAdelantado(versionServidor, versionApp = VERSION_APP) {
  if (!versionServidor || versionApp === 'dev') return false
  return compararVersiones(versionServidor, versionApp) > 0
}

/**
 * Recargar de verdad, no volver a leer lo que ya estaba guardado.
 *
 * `location.reload()` a secas confía en la caché del navegador para el HTML,
 * y el HTML es justamente lo que se queda viejo: es el único archivo cuyo
 * nombre no cambia entre versiones. Alguien pulsaba «Recargar», la página
 * parpadeaba y seguía en la versión de antes — hasta que un técnico le
 * borraba la caché a mano.
 *
 * `fetch(cache: 'reload')` obliga a ir a la red y deja el HTML nuevo en la
 * caché; la recarga que sigue ya lee ese. Si el fetch falla —sin red, o el
 * navegador no lo permite— se recarga igual: lo peor que pasa es que quede
 * como estaba, que es donde ya estábamos.
 */
export async function recargarDeVerdad() {
  try {
    await fetch(window.location.href, { cache: 'reload', credentials: 'same-origin' })
  } catch {
    /* sin red o bloqueado: la recarga de abajo sigue siendo lo correcto */
  }
  window.location.reload()
}

const CLAVE_VISTA = 'version_novedades_vista'

/**
 * Si hay novedades que esta persona todavía no ha abierto.
 *
 * La primera vez no molesta: quien entra por primera vez no tiene «novedades»
 * de nada, y estrenar el portal con un aviso rojo sobra.
 */
export function hayNovedades(version, guardada) {
  if (!version) return false
  if (!guardada) return false
  return compararVersiones(version, guardada) > 0
}

export function versionVista() {
  try {
    return localStorage.getItem(CLAVE_VISTA)
  } catch {
    return null   // navegador con el almacenamiento bloqueado
  }
}

export function marcarVersionVista(version) {
  try {
    localStorage.setItem(CLAVE_VISTA, version)
  } catch {
    /* si no se puede guardar, lo peor que pasa es que el punto vuelva a salir */
  }
}
