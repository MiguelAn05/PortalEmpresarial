import { readFileSync } from 'node:fs'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

/**
 * La versión se lee del backend al compilar — `app/core/version.py` es la
 * única fuente. Así no hay un segundo número que se quede atrás, y el bundle
 * queda marcado con la versión con la que se construyó: es lo que permite
 * detectar que el navegador y el servidor están desfasados.
 */
function versionDelBackend() {
  const py = readFileSync(new URL('../backend/app/core/version.py', import.meta.url), 'utf8')
  const m = py.match(/^VERSION = "([^"]+)"/m)
  if (!m) throw new Error('No se encontro VERSION en backend/app/core/version.py')
  return m[1]
}

export default defineConfig({
  define: {
    __VERSION__: JSON.stringify(versionDelBackend()),
  },
  plugins: [
    react(),
    tailwindcss(),
  ],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
      '/uploads': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})