import axios from 'axios'
import { limpiarSesion, tokenGuardado } from './sesion.js'

const api = axios.create({
  baseURL: '/api',
})

// Antes de cada request, agrega el token JWT automáticamente.
// Dónde está guardado —localStorage o solo esta pestaña— lo resuelve
// `sesion.js`, según si en el login se marcó «Mantener sesión iniciada».
api.interceptors.request.use((config) => {
  const token = tokenGuardado()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

/**
 * El 401 de «se venció la sesión» y el de «esa contraseña no es» son el mismo
 * código y no son la misma cosa.
 *
 * Al iniciar sesión el 401 es la respuesta esperada a un dato equivocado, y
 * la pantalla ya lo muestra. Mandar ahí a `/login` recargaba la página entera
 * y se llevaba el mensaje por delante: quien escribía mal la contraseña veía
 * el formulario parpadear y volver en blanco, sin saber qué pasó.
 */
export function esPeticionDeLogin(url) {
  return /\/auth\/login$/.test(String(url ?? ''))
}

/**
 * ¿Vale la pena repetir una petición que falló?
 *
 * React Query reintenta tres veces por defecto, y eso está pensado para una
 * red que se cayó un segundo. Cuando el servidor respondió 403 o 404 —«esto
 * no es tuyo», «no existe»— la respuesta va a ser la misma las tres veces:
 * son tres viajes al servidor por cada pantalla que no se puede abrir, y el
 * error tarda varios segundos en aparecer por esperar entre intento e
 * intento.
 *
 * Se reintenta una vez lo que sí puede cambiar solo: un corte de red o un
 * 500 pasajero.
 */
export function debeReintentar(fallos, error) {
  const codigo = error?.response?.status
  if (codigo >= 400 && codigo < 500) return false
  return fallos < 1
}

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const url = error.config?.url || ''
    if (error.response?.status === 401 && !esPeticionDeLogin(url)) {
      // Token vencido o inválido: se cierra la sesión y se vuelve a la puerta.
      limpiarSesion()
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

export default api
