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
