/**
 * Las cuatro capas de espera del portal, cada una para un momento distinto.
 *
 * Se usaba una sola para todo —«Cargando...» centrado en la página— y eso
 * tiene dos costos. El layout SALTA cuando llegan los datos, porque el texto
 * ocupa una línea y la tabla veinte; y un texto en el centro de la pantalla
 * no dice si falta un segundo o un minuto.
 *
 *   1. El arranque         — vive en `index.html`, no aquí: escrito en React
 *                            solo aparecería DESPUÉS de descargar el bundle,
 *                            que es exactamente el rato que hay que cubrir
 *   2. `BarraDeCarga`      — cambiar de módulo o de mes: no tapa nada
 *   3. `Esqueleto` y cía.  — datos dentro de una vista que ya está en pantalla
 *   4. `Spinner`           — dentro del botón que disparó la acción
 *
 * Regla que vale para las cuatro: **nunca reemplaces datos ya visibles por
 * un esqueleto.** Al refrescar, lo anterior se atenúa (`Atenuado`) y sigue
 * ahí; taparlo obliga a esperar para volver a ver algo que ya se estaba
 * leyendo.
 */
import { useIsFetching } from '@tanstack/react-query'

// ── 1 · Cambio de módulo ────────────────────────────────────────
/**
 * Una barra de 2,5 px pegada arriba del todo.
 *
 * Quien navega ya está viendo el portal: taparlo con un overlay le quita lo
 * que estaba leyendo para no mostrarle nada. Va fija sobre todo lo demás y
 * no recibe clics, así que la página sigue usándose mientras carga.
 */
export function BarraDeCarga() {
  // Cuántas peticiones hay en vuelo AHORA, las pida quien las pida. Así una
  // pantalla nueva no tiene que acordarse de encender nada: si consulta al
  // servidor, la barra aparece sola.
  const enVuelo = useIsFetching()

  return (
    <div className="fixed top-0 inset-x-0 h-[2.5px] z-50 pointer-events-none" aria-hidden="true">
      <span
        className={`block h-full bg-acento transition-[width,opacity] duration-200 ease-suave ${
          enVuelo ? 'w-4/5 opacity-100' : 'w-full opacity-0'
        }`}
      />
    </div>
  )
}

// ── 2 · Datos dentro de la vista ────────────────────────────────
/**
 * Un bloque gris con brillo, del tamaño del contenido que va a llegar.
 *
 * `ancho` y `alto` se pasan como clases de Tailwind para no escribir estilos
 * sueltos: `<Esqueleto ancho="w-3/5" alto="h-6" />`.
 */
export function Esqueleto({ ancho = 'w-full', alto = 'h-4', className = '' }) {
  return (
    <span
      aria-hidden="true"
      className={`block esqueleto ${ancho} ${alto} ${className}`}
    />
  )
}

/**
 * La fila de tarjetas de KPI, con la primera más ancha.
 *
 * Tiene la MISMA forma que `TarjetasKPI` a propósito: si el esqueleto no
 * coincide con lo que llega, la página da un salto y se percibe peor que
 * haber esperado en blanco.
 */
export function EsqueletoKPIs({ cuantas = 5, principal = true }) {
  return (
    <div
      className="grid gap-3 sm:grid-cols-2 xl:grid-cols-[1.6fr_repeat(4,1fr)]"
      role="status" aria-label="Cargando indicadores del periodo"
    >
      {Array.from({ length: cuantas }, (_, i) => (
        <div key={i} className="bg-superficie rounded-xl border border-borde p-4 shadow-sm space-y-3">
          <Esqueleto ancho="w-3/5" alto="h-2.5" />
          <Esqueleto ancho={principal && i === 0 ? 'w-2/5' : 'w-1/3'} alto="h-7" />
          <Esqueleto ancho="w-4/5" alto="h-2" />
        </div>
      ))}
    </div>
  )
}

/** Filas de una tabla o de una lista, con su separador. */
export function EsqueletoFilas({ filas = 5, className = '' }) {
  return (
    <div className={`divide-y divide-borde ${className}`} role="status" aria-label="Cargando">
      {Array.from({ length: filas }, (_, i) => (
        <div key={i} className="flex items-center gap-4 px-5 py-3.5">
          <div className="flex-1 space-y-2">
            <Esqueleto ancho="w-2/5" alto="h-3" />
            <Esqueleto ancho="w-1/4" alto="h-2" />
          </div>
          <Esqueleto ancho="w-16" alto="h-3" />
          <Esqueleto ancho="w-20" alto="h-5" className="rounded-md" />
        </div>
      ))}
    </div>
  )
}

/** Tarjetas en rejilla, como las del tablero de indicadores. */
export function EsqueletoTarjetas({ cuantas = 6 }) {
  return (
    <div
      className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4"
      role="status" aria-label="Cargando"
    >
      {Array.from({ length: cuantas }, (_, i) => (
        <div key={i} className="bg-superficie rounded-xl border border-borde p-5 shadow-sm space-y-3">
          <Esqueleto ancho="w-4/5" alto="h-3" />
          <Esqueleto ancho="w-1/3" alto="h-8" />
          <Esqueleto ancho="w-full" alto="h-1.5" className="rounded-full" />
          <Esqueleto ancho="w-2/3" alto="h-2" />
        </div>
      ))}
    </div>
  )
}

/**
 * Lo que ya estaba en pantalla, mientras se refresca.
 *
 * Es la otra mitad de la regla: un esqueleto es para cuando NO hay nada que
 * mostrar. Si los datos anteriores siguen siendo válidos —cambiar de mes,
 * aplicar un filtro—, se atenúan y se quedan. Así se compara lo viejo con lo
 * nuevo en vez de mirar un hueco.
 */
export function Atenuado({ cargando, children }) {
  return (
    <div
      className={`transition-opacity duration-200 ease-suave ${
        cargando ? 'opacity-50 pointer-events-none' : 'opacity-100'
      }`}
      aria-busy={cargando || undefined}
    >
      {children}
    </div>
  )
}

// ── 3 · Acción puntual ──────────────────────────────────────────
/**
 * El círculo que gira dentro de un botón. `claro` para fondo oscuro.
 *
 * Dibujado con bordes y no con un SVG animado: son dos propiedades de CSS y
 * no hay nada que descargar.
 */
export function Spinner({ claro = false, tam = 15 }) {
  return (
    <span
      aria-hidden="true"
      style={{ width: tam, height: tam }}
      className={`inline-block rounded-full border-2 animar-girar shrink-0 ${
        claro
          ? 'border-white/30 border-t-white'
          : 'border-borde-fuerte border-t-acento'
      }`}
    />
  )
}

/**
 * Aviso en línea para lo que tarda de verdad (recalcular todo un periodo,
 * exportar). Pasados unos segundos, un botón girando sin decir nada se lee
 * como que se quedó pegado.
 */
export function CargandoEnLinea({ children }) {
  return (
    <span className="inline-flex items-center gap-2.5 text-sm text-texto-3" role="status">
      <Spinner />{children}
    </span>
  )
}
