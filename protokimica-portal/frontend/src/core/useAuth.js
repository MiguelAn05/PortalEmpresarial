import { createContext, useContext } from 'react'

// El contexto y su hook viven aparte del proveedor: un archivo .jsx que
// exporta algo más que componentes rompe el refresco en caliente de Vite
// (regla `react-refresh/only-export-components`).
export const AuthContext = createContext(null)

// En cualquier componente: const { user, login, logout } = useAuth()
export function useAuth() {
  return useContext(AuthContext)
}
