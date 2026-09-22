import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from './core/AuthContext.jsx'
import { debeReintentar } from './core/api.js'
import './index.css'
import App from './App.jsx'

/**
 * Cuánto vale un dato ya traído antes de volver a pedirlo.
 *
 * Sin esto, cada dato se considera viejo apenas llega: entrar a PQRS, pasar
 * a Inicio y volver son tres consultas completas en veinte segundos, y eso
 * se multiplica por cada persona conectada. Treinta segundos no le quitan
 * frescura a nada porque lo que uno mismo cambia se refresca aparte —cada
 * pantalla invalida lo suyo al guardar— y al volver a la pestaña se vuelve a
 * consultar igual.
 */
const MEDIO_MINUTO = 30 * 1000

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: MEDIO_MINUTO,
      retry: debeReintentar,
    },
  },
})

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
