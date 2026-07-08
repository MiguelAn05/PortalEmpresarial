import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
})

// Antes de cada request, agrega el token JWT automáticamente
// si existe en localStorage. Así no hay que pegarlo manualmente
// en cada llamada a la API.
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Si el servidor responde 401 (token vencido o inválido),
// limpia la sesión y manda al usuario al login automáticamente.
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default api