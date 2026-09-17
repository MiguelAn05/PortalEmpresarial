import { createContext, useContext, useState } from 'react'
import { guardarSesion, limpiarSesion, usuarioGuardado } from './sesion.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  // Dónde está guardada la sesión lo decide `sesion.js`: el login ofrece
  // «Mantener sesión iniciada», y sin eso el token iba siempre a
  // localStorage aunque la persona hubiera pedido lo contrario.
  const [user, setUser] = useState(() => usuarioGuardado())

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

// Hook personalizado: en cualquier componente puedes hacer
// const { user, login, logout } = useAuth()
export function useAuth() {
  return useContext(AuthContext)
}
