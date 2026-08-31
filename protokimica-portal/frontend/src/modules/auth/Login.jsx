import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../core/AuthContext.jsx'
import api from '../../core/api.js'
import { VERSION_APP } from '../../core/version.js'
import { mensajeDeError } from '../../core/errores.js'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()

  const [form, setForm] = useState({
    email: '',
    password: '',
    tenant_slug: 'protokimica',
  })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value })
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      // 1. Obtener el token
      const { data } = await api.post('/auth/login', form)

      // 2. Obtener los datos del usuario con ese token
      const meRes = await api.get('/auth/me', {
        headers: { Authorization: `Bearer ${data.access_token}` },
      })

      // 3. Guardar sesión y redirigir
      login(meRes.data, data.access_token)
      navigate('/')
    } catch (err) {
      setError(
        mensajeDeError(err, 'Error al iniciar sesión. Verifica tus datos.')
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-fondo flex items-center justify-center p-4">
      <div className="w-full max-w-md">

       {/* Logo y título */}
       <div className="text-center mb-8">
       <div className="flex justify-center mb-4">
       <img
         src="/logo.png"
         alt="Protokimica"
         className="h-20 w-auto object-contain"
         />
       </div>
         <h1 className="text-2xl font-bold text-acento-fuerte">
           Protokimica
         </h1>
         <p className="text-sm text-texto-2 mt-1">
           Portal de Gestión Empresarial
         </p>
       </div>

        {/* Card del formulario */}
        <div className="bg-white rounded-2xl shadow-sm border border-borde p-8">
          <h2 className="text-lg font-semibold text-texto mb-6">
            Iniciar sesión
          </h2>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-texto-2 uppercase tracking-wide mb-1.5">
                Correo electrónico
              </label>
              <input
                type="email"
                name="email"
                value={form.email}
                onChange={handleChange}
                placeholder="tu@correo.com"
                required
                className="w-full px-4 py-2.5 rounded-lg border border-borde text-sm text-texto placeholder-texto-3 focus:outline-none focus:ring-2 focus:ring-acento focus:border-transparent transition"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-texto-2 uppercase tracking-wide mb-1.5">
                Contraseña
              </label>
              <input
                type="password"
                name="password"
                value={form.password}
                onChange={handleChange}
                placeholder="••••••••"
                required
                className="w-full px-4 py-2.5 rounded-lg border border-borde text-sm text-texto placeholder-texto-3 focus:outline-none focus:ring-2 focus:ring-acento focus:border-transparent transition"
              />
            </div>

            {error && (
              <div className="bg-negativo-bg border border-negativo/25 rounded-lg px-4 py-3 text-sm text-negativo">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-ambar hover:bg-ambar-claro text-acento-fuerte font-bold py-2.5 rounded-lg text-sm transition disabled:opacity-60 disabled:cursor-not-allowed mt-2"
            >
              {loading ? 'Iniciando sesión...' : 'Ingresar'}
            </button>
          </form>
        </div>

        <p className="text-center text-xs text-texto-3 mt-6">
          Portal interno · Solo personal autorizado
          <span className="font-mono ml-1">· v{VERSION_APP}</span>
        </p>
      </div>
    </div>
  )
}