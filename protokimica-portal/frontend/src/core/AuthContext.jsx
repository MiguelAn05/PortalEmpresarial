import { useEffect, useState } from 'react'
import api from './api.js'
import {
  actualizarUsuarioGuardado, guardarSesion, limpiarSesion, usuarioGuardado,
} from './sesion.js'
import { AuthContext } from './useAuth.js'

export function AuthProvider({ children }) {
  // Dónde está guardada la sesión lo decide `sesion.js`: el login ofrece
  // «Mantener sesión iniciada», y sin eso el token iba siempre a
  // localStorage aunque la persona hubiera pedido lo contrario.
  const [user, setUser] = useState(() => usuarioGuardado())

  // El usuario guardado es una foto del día que inició sesión. Su rol, su
  // área o los módulos que su empresa tiene contratados pueden haber cambiado
  // desde entonces, y el menú se arma con esa foto: se refresca una vez al
  // abrir el portal. Si falla no pasa nada —sigue la foto, y el servidor
  // sigue bloqueando lo que no corresponde—; un 401 lo atiende `api.js`.
  const hayUsuario = Boolean(user)
  useEffect(() => {
    if (!hayUsuario) return
    let vigente = true
    api.get('/auth/me')
      .then(({ data }) => {
        if (!vigente) return
        actualizarUsuarioGuardado(data)
        setUser(data)
      })
      .catch(() => {})
    return () => { vigente = false }
  }, [hayUsuario])

  const login = (userData, token, recordar = true) => {
    guardarSesion(token, userData, recordar)
    setUser(userData)
  }

  const logout = () => {
    limpiarSesion()
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}
