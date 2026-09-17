import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../core/AuthContext.jsx'
import api from '../../core/api.js'
import { CORREO_SOPORTE, LOGO, LOGO_ALT, NOMBRE_EMPRESA } from '../../core/marca.js'
import { VERSION_APP } from '../../core/version.js'
import { mensajeDeError } from '../../core/errores.js'
import { guardarPreferenciaRecordar, recordarPreferido } from '../../core/sesion.js'
import {
  IconoAlerta, IconoCargando, IconoCandado, IconoCheck,
  IconoOjo, IconoOjoTachado, IconoSobre,
} from '../../core/components/Iconos.jsx'

/**
 * La puerta del portal.
 *
 * Es panel dividido: a la izquierda la marca y qué es esto, a la derecha el
 * formulario. La mitad oscura no es decoración — mucha gente llega aquí por
 * un enlace de un correo o por el QR de un punto de venta y necesita saber
 * en un vistazo a dónde llegó y que es interno; una tarjeta suelta en medio
 * de una pantalla vacía no dice ninguna de las dos cosas.
 *
 * Debajo de `lg` el panel desaparece y el logo se sube encima del
 * formulario: en un celular el claim le robaría la pantalla a lo único que
 * la persona vino a hacer.
 *
 * No hay «¿Olvidaste tu contraseña?» a propósito: el portal todavía no tiene
 * forma de restablecerla, y un enlace que no lleva a ninguna parte es peor
 * que no tenerlo. Mientras tanto, el pie manda a soporte, que es quien de
 * verdad la cambia.
 */

const VENTAJAS = [
  'PQRS con trazabilidad y tiempos de respuesta',
  'Proyectos, tareas y ejecución presupuestal',
  'Indicadores y acciones de mejora ISO 9001',
]

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()

  const [form, setForm] = useState({
    email: '',
    password: '',
    tenant_slug: 'protokimica',
  })
  const [verClave, setVerClave] = useState(false)
  const [recordar, setRecordar] = useState(() => recordarPreferido())
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

      // 3. Guardar sesión y redirigir. `recordar` decide si el token
      //    sobrevive a cerrar el navegador (ver core/sesion.js).
      guardarPreferenciaRecordar(recordar)
      login(meRes.data, data.access_token, recordar)
      navigate('/')
    } catch (err) {
      setError(
        mensajeDeError(err, 'Error al iniciar sesión. Verifica tus datos.')
      )
    } finally {
      setLoading(false)
    }
  }

  const claseCampo =
    'w-full pl-11 pr-4 py-3 rounded-lg border border-borde bg-superficie text-sm ' +
    'text-texto placeholder-texto-3 focus:outline-none focus:ring-2 focus:ring-acento ' +
    'focus:border-transparent transition'

  return (
    <div className="min-h-screen bg-superficie lg:grid lg:grid-cols-2">

      {/* ── Panel de marca ─────────────────────────────────────────
          Solo desde `lg`. En pantallas angostas su contenido no cabe
          sin empujar el formulario fuera de la vista. */}
      <aside className="hidden lg:flex relative overflow-hidden panel-marca
        flex-col justify-between px-14 py-12 text-white">
        <div className="absolute inset-0 reticula" aria-hidden="true" />

        <div className="relative flex items-center gap-3">
          <img src={LOGO} alt={LOGO_ALT} className="h-11 w-auto object-contain" />
          <div className="leading-tight">
            <div className="font-semibold">{NOMBRE_EMPRESA}</div>
            <div className="text-[11px] text-nav-texto">Portal empresarial</div>
          </div>
        </div>

        <div className="relative max-w-md">
          <h2 className="text-4xl font-bold leading-tight tracking-tight">
            Toda la gestión de la compañía,{' '}
            <span className="text-ambar">en un solo lugar.</span>
          </h2>
          <ul className="mt-8 space-y-3">
            {VENTAJAS.map((texto) => (
              <li key={texto} className="flex items-start gap-3 text-sm text-nav-texto">
                <span className="mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center
                  rounded-full bg-ambar text-nav">
                  <IconoCheck tam={13} />
                </span>
                {texto}
              </li>
            ))}
          </ul>
        </div>

        <p className="relative text-xs text-nav-seccion">
          Portal interno · Solo personal autorizado
          <span className="cifra ml-1">· v{VERSION_APP}</span>
        </p>
      </aside>

      {/* ── Formulario ─────────────────────────────────────────── */}
      <main className="flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-sm">

          {/* El logo solo cuando el panel no está: si no, saldría dos veces. */}
          <div className="lg:hidden flex flex-col items-center mb-8">
            <img src={LOGO} alt={LOGO_ALT} className="h-16 w-auto object-contain" />
            <h1 className="mt-3 text-xl font-bold text-acento-fuerte">{NOMBRE_EMPRESA}</h1>
            <p className="text-sm text-texto-2">Portal empresarial</p>
          </div>

          <h1 className="text-2xl font-bold text-acento-fuerte">Iniciar sesión</h1>
          <p className="text-sm text-texto-2 mt-1">Ingresa con tu correo corporativo.</p>

          <form onSubmit={handleSubmit} className="mt-8 space-y-4">
            <div>
              <label htmlFor="email"
                className="block text-xs font-semibold text-texto-2 uppercase tracking-wide mb-1.5">
                Correo electrónico
              </label>
              <div className="relative">
                <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-texto-3">
                  <IconoSobre tam={17} />
                </span>
                <input
                  id="email"
                  type="email"
                  name="email"
                  value={form.email}
                  onChange={handleChange}
                  placeholder="nombre@protokimica.com"
                  autoComplete="username"
                  autoFocus
                  required
                  className={claseCampo}
                />
              </div>
            </div>

            <div>
              <label htmlFor="password"
                className="block text-xs font-semibold text-texto-2 uppercase tracking-wide mb-1.5">
                Contraseña
              </label>
              <div className="relative">
                <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-texto-3">
                  <IconoCandado tam={17} />
                </span>
                <input
                  id="password"
                  type={verClave ? 'text' : 'password'}
                  name="password"
                  value={form.password}
                  onChange={handleChange}
                  placeholder="Tu contraseña"
                  autoComplete="current-password"
                  required
                  className={`${claseCampo} pr-11`}
                />
                {/* Ver la contraseña evita el otro camino: escribirla en el
                    campo de correo para revisarla. */}
                <button
                  type="button"
                  onClick={() => setVerClave(!verClave)}
                  aria-label={verClave ? 'Ocultar la contraseña' : 'Mostrar la contraseña'}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-texto-3
                    hover:text-texto-2 transition p-1"
                >
                  {verClave ? <IconoOjoTachado tam={17} /> : <IconoOjo tam={17} />}
                </button>
              </div>
            </div>

            <label className="flex items-center gap-2 text-sm text-texto-2 cursor-pointer">
              <input
                type="checkbox"
                checked={recordar}
                onChange={(e) => setRecordar(e.target.checked)}
                className="rounded border-borde accent-acento"
              />
              Mantener sesión iniciada
            </label>

            {error && (
              <div role="alert" className="flex items-start gap-2 bg-negativo-bg
                border border-negativo/25 rounded-lg px-4 py-3 text-sm text-negativo">
                <span className="mt-0.5"><IconoAlerta tam={16} /></span>
                <span>{error}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 bg-acento-fuerte
                hover:bg-acento text-white font-semibold py-3 rounded-lg text-sm transition
                disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {loading && <IconoCargando tam={16} className="animate-spin" />}
              {loading ? 'Verificando…' : 'Ingresar'}
            </button>
          </form>

          <p className="text-xs text-texto-3 mt-8 text-center">
            ¿Problemas para entrar? Escribe a{' '}
            <a href={`mailto:${CORREO_SOPORTE}`}
              className="text-acento font-medium hover:underline">
              {CORREO_SOPORTE}
            </a>
          </p>

          {/* En celular el panel no está, así que la versión se muestra aquí:
              es lo primero que se pregunta cuando algo no cuadra. */}
          <p className="lg:hidden text-center text-xs text-texto-3 mt-4">
            Portal interno · Solo personal autorizado
            <span className="cifra ml-1">· v{VERSION_APP}</span>
          </p>
        </div>
      </main>
    </div>
  )
}
