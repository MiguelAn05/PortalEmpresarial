import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import api from '../api.js'
import { IconoCerrar, IconoRecargar } from './Iconos.jsx'
import {
  VERSION_APP, hayNovedades, marcarVersionVista, servidorAdelantado, versionVista,
} from '../version.js'

/** Cada diez minutos basta: una versión no cambia mientras alguien trabaja. */
const CADA_DIEZ_MINUTOS = 10 * 60 * 1000

function useVersionDelServidor() {
  return useQuery({
    queryKey: ['version'],
    queryFn: () => api.get('/version').then(r => r.data),
    refetchInterval: CADA_DIEZ_MINUTOS,
    retry: false,
  })
}

/**
 * Aviso de que el servidor ya está en otra versión.
 *
 * Aparece solo cuando de verdad pasó, y no se puede cerrar sin recargar a
 * propósito: seguir trabajando con un bundle viejo contra un backend nuevo es
 * exactamente el error que nadie logra reproducir después.
 */
export function AvisoVersionNueva() {
  const { data } = useVersionDelServidor()
  if (!servidorAdelantado(data?.version)) return null

  return (
    <div className="flex items-center gap-3 mb-5 px-4 py-2.5 rounded-lg
      bg-alerta-bg border border-ambar/40 text-sm text-ambar-texto shadow-xs">
      <IconoRecargar tam={16} />
      <span className="flex-1">
        El portal se actualizó a la versión <strong>{data.version}</strong>.
        Recarga la página para trabajar con la última.
      </span>
      <button
        onClick={() => window.location.reload()}
        className="px-3 py-1.5 rounded-lg bg-acento-fuerte text-white text-xs font-semibold
          hover:bg-acento transition-colors duration-150 ease-suave flex-shrink-0"
      >
        Recargar
      </button>
    </div>
  )
}

function Novedades({ onClose }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['version-historial'],
    queryFn: () => api.get('/version/historial').then(r => r.data),
    staleTime: Infinity,
  })

  return (
    <div
      className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-xl w-full max-w-lg max-h-[80vh] flex flex-col overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="px-5 py-4 border-b border-borde flex items-start justify-between gap-3">
          <div>
            <h2 className="font-bold text-acento-fuerte">Novedades del portal</h2>
            <p className="text-xs text-texto-2 mt-0.5">
              Estás en la versión {VERSION_APP}
            </p>
          </div>
          <button
            onClick={onClose}
            aria-label="Cerrar"
            className="w-8 h-8 flex items-center justify-center rounded-lg text-texto-3
              hover:bg-superficie-2 hover:text-acento-fuerte transition-colors duration-150"
          >
            <IconoCerrar tam={16} />
          </button>
        </header>

        <div className="overflow-y-auto px-5 py-4">
          {isLoading && <p className="text-sm text-texto-2">Cargando…</p>}
          {isError && (
            <p className="text-sm text-texto-2">
              No se pudo cargar el historial. Vuelve a intentarlo en un momento.
            </p>
          )}

          <ol className="relative">
            {data?.historial?.map((v, i) => (
              <li key={v.version} className="relative pl-6 pb-6 last:pb-0">
                {/* La línea del tiempo: se corta en la última entrada. */}
                {i < data.historial.length - 1 && (
                  <span className="absolute left-[5px] top-4 bottom-0 w-px bg-borde" />
                )}
                <span
                  className="absolute left-0 top-1.5 w-2.5 h-2.5 rounded-full"
                  style={{ background: i === 0 ? 'var(--color-acento)' : 'var(--color-borde)' }}
                />

                <div className="flex items-baseline gap-2 flex-wrap">
                  <span className="font-bold text-acento-fuerte text-sm">{v.titulo}</span>
                  <span className="text-[11px] font-mono text-texto-2 bg-fondo
                    border border-borde rounded-full px-2 py-0.5">
                    v{v.version}
                  </span>
                  {i === 0 && (
                    <span className="text-[11px] font-semibold text-acento">actual</span>
                  )}
                </div>
                <div className="text-[11px] text-texto-3 mb-2">{v.fecha}</div>

                <ul className="space-y-1.5">
                  {v.cambios.map((c, j) => (
                    <li key={j} className="flex gap-2 text-sm text-texto">
                      {/* Punto y etiqueta: el color solo no se lee. */}
                      <span className="flex items-center gap-1 flex-shrink-0 mt-0.5">
                        <span
                          className="w-1.5 h-1.5 rounded-full"
                          style={{ background: c.color }}
                          aria-hidden="true"
                        />
                        <span className="text-[11px] font-semibold uppercase tracking-wide text-texto-2 w-16">
                          {c.etiqueta}
                        </span>
                      </span>
                      <span className="flex-1">{c.texto}</span>
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ol>
        </div>
      </div>
    </div>
  )
}

/**
 * La versión en el pie del menú. Se puede tocar: abre las novedades.
 *
 * Lleva un punto ámbar cuando hay una versión que esta persona todavía no ha
 * abierto — así el cambio se entera solo, sin mandar un correo a nadie.
 */
export function ChipVersion({ collapsed }) {
  const [abierto, setAbierto] = useState(false)
  const [vista, setVista] = useState(versionVista)
  const { data } = useVersionDelServidor()

  const version = data?.version ?? VERSION_APP
  const nuevo = hayNovedades(version, vista)

  // Quien entra por primera vez no tiene «novedades» de nada: se anota la
  // versión en silencio para que el punto solo salga en la siguiente. No hace
  // falta actualizar el estado —sin versión guardada el punto ya no sale—,
  // así que esto no vuelve a pintar nada.
  useEffect(() => {
    if (version && !versionVista()) marcarVersionVista(version)
  }, [version])

  const abrir = () => {
    setAbierto(true)
    marcarVersionVista(version)
    setVista(version)
  }

  return (
    <>
      <button
        onClick={abrir}
        title={`Versión ${version} — ver novedades`}
        className="w-full flex items-center gap-2 px-5 py-1.5 text-nav-texto/50
          hover:text-nav-texto transition-colors duration-150 ease-suave text-[11px]"
      >
        <span className="font-mono cifra">v{version}</span>
        {nuevo && (
          <>
            <span className="w-1.5 h-1.5 rounded-full bg-ambar flex-shrink-0" aria-hidden="true" />
            {!collapsed && <span className="text-ambar">novedades</span>}
          </>
        )}
      </button>

      {abierto && <Novedades onClose={() => setAbierto(false)} />}
    </>
  )
}
