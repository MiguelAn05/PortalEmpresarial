import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from './core/AuthContext.jsx'
import './index.css'
import App from './App.jsx'

const queryClient = new QueryClient()

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <App />
        </AuthProvider>
      </QueryClientProvider>
    </BrowserRouter>
  </StrictMode>
)

/**
 * Retira la pantalla de arranque de `index.html` ahora que React ya pintó.
 *
 * Se marca con un atributo en vez de borrar el nodo: así la transición de
 * opacidad que declara el HTML alcanza a correr y el portal aparece en vez
 * de saltar. El nodo se elimina después, para no dejar una capa invisible
 * encima de todo — aunque no reciba clics, está en el árbol y la leería un
 * lector de pantalla.
 *
 * Todo en try/catch y sin fallar si no existe: si alguien sirve otro
 * `index.html`, el portal tiene que arrancar igual.
 */
const arranque = document.getElementById('arranque')
if (arranque) {
  requestAnimationFrame(() => {
    arranque.setAttribute('data-listo', '')
    setTimeout(() => arranque.remove(), 400)
  })
}
