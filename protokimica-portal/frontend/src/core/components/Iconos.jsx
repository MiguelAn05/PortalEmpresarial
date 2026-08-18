/**
 * Los iconos del portal.
 *
 * Están dibujados a mano —una sola familia, trazo de 1.5, caja de 24— en vez
 * de instalarse de un paquete, por lo mismo que las gráficas: el servidor no
 * reinstala dependencias con fiabilidad. Un icono que no carga deja un
 * cuadro vacío en el menú.
 *
 * Todos heredan el color del texto (`stroke="currentColor"`), así que se
 * pintan con `text-...` y nunca traen color propio.
 *
 * NO se usan emojis: cambian de forma en cada sistema operativo, no heredan
 * el color, y son la señal más rápida de que algo es un prototipo.
 */

function Icono({ children, tam = 18, className = '', ...resto }) {
  return (
    <svg
      width={tam}
      height={tam}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`flex-shrink-0 ${className}`}
      aria-hidden="true"
      {...resto}
    >
      {children}
    </svg>
  )
}

// ── Módulos ───────────────────────────────────────────────────

export const IconoInicio = (p) => (
  <Icono {...p}>
    <path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
    <path d="M9 22V12h6v10" />
  </Icono>
)

export const IconoPQRS = (p) => (
  <Icono {...p}>
    <path d="M22 12h-6l-2 3h-4l-2-3H2" />
    <path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z" />
  </Icono>
)

export const IconoProyectos = (p) => (
  <Icono {...p}>
    <rect x="3" y="3" width="18" height="18" rx="2" />
    <path d="M8 7v9" />
    <path d="M12 7v5" />
    <path d="M16 7v12" />
  </Icono>
)

export const IconoIndicadores = (p) => (
  <Icono {...p}>
    <path d="M16 7h6v6" />
    <path d="m22 7-8.5 8.5-5-5L2 17" />
  </Icono>
)

export const IconoEncuestas = (p) => (
  <Icono {...p}>
    <path d="m12 2.8 2.85 5.77 6.37.93-4.61 4.49 1.09 6.34L12 17.34l-5.7 3-1.08-6.35L.61 9.5l6.37-.93z" />
  </Icono>
)

export const IconoAdmin = (p) => (
  <Icono {...p}>
    <path d="M20 7h-9" />
    <path d="M14 17H5" />
    <circle cx="17" cy="17" r="3" />
    <circle cx="7" cy="7" r="3" />
  </Icono>
)

// ── Menú y sesión ─────────────────────────────────────────────

export const IconoPanel = (p) => (
  <Icono {...p}>
    <rect x="3" y="3" width="18" height="18" rx="2" />
    <path d="M9 3v18" />
  </Icono>
)

export const IconoSalir = (p) => (
  <Icono {...p}>
    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
    <path d="m16 17 5-5-5-5" />
    <path d="M21 12H9" />
  </Icono>
)

export const IconoAgente = (p) => (
  <Icono {...p}>
    <path d="M12 8V4" />
    <rect x="4" y="8" width="16" height="12" rx="2" />
    <path d="M2 14h2" />
    <path d="M20 14h2" />
    <path d="M9 13v2" />
    <path d="M15 13v2" />
  </Icono>
)

export const IconoLlave = (p) => (
  <Icono {...p}>
    <circle cx="7.5" cy="15.5" r="3.5" />
    <path d="m10 13 8.5-8.5" />
    <path d="m16 7 2 2" />
    <path d="m19 4 2 2" />
  </Icono>
)

// ── Próximamente ──────────────────────────────────────────────

export const IconoFicha = (p) => (
  <Icono {...p}>
    <path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7z" />
    <path d="M14 2v4a2 2 0 0 0 2 2h4" />
    <path d="M16 13H8" />
    <path d="M16 17H8" />
    <path d="M10 9H8" />
  </Icono>
)

export const IconoCarpeta = (p) => (
  <Icono {...p}>
    <path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2z" />
  </Icono>
)

// ── Estado ────────────────────────────────────────────────────

export const IconoAlerta = (p) => (
  <Icono {...p}>
    <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3" />
    <path d="M12 9v4" />
    <path d="M12 17h.01" />
  </Icono>
)

export const IconoAlDia = (p) => (
  <Icono {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="m8.5 12 2.5 2.5 4.5-5" />
  </Icono>
)

export const IconoReloj = (p) => (
  <Icono {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7v5l3.5 2" />
  </Icono>
)

export const IconoRecargar = (p) => (
  <Icono {...p}>
    <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8" />
    <path d="M21 3v5h-5" />
    <path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16" />
    <path d="M8 16H3v5" />
  </Icono>
)

// ── Navegación y datos ────────────────────────────────────────

export const IconoFlecha = (p) => (
  <Icono {...p}>
    <path d="M5 12h14" />
    <path d="m12 5 7 7-7 7" />
  </Icono>
)

export const IconoChevron = (p) => (
  <Icono {...p}>
    <path d="m9 18 6-6-6-6" />
  </Icono>
)

export const IconoPersonas = (p) => (
  <Icono {...p}>
    <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
    <circle cx="9" cy="7" r="4" />
    <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
    <path d="M16 3.13a4 4 0 0 1 0 7.75" />
  </Icono>
)

export const IconoEmpresa = (p) => (
  <Icono {...p}>
    <path d="M6 22V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18" />
    <path d="M2 22h20" />
    <path d="M10 7h4" />
    <path d="M10 11h4" />
    <path d="M10 15h4" />
  </Icono>
)

export const IconoDinero = (p) => (
  <Icono {...p}>
    <rect x="2" y="6" width="20" height="12" rx="2" />
    <circle cx="12" cy="12" r="2.5" />
    <path d="M6 12h.01" />
    <path d="M18 12h.01" />
  </Icono>
)

export const IconoTarea = (p) => (
  <Icono {...p}>
    <path d="M11 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-6" />
    <path d="m9 11 3 3 8.5-8.5" />
  </Icono>
)

export const IconoCerrar = (p) => (
  <Icono {...p}>
    <path d="M18 6 6 18" />
    <path d="m6 6 12 12" />
  </Icono>
)

export const IconoCheck = (p) => (
  <Icono {...p}>
    <path d="M4 12.5 9 17.5 20 6.5" />
  </Icono>
)

export const IconoBuscar = (p) => (
  <Icono {...p}>
    <circle cx="11" cy="11" r="7" />
    <path d="m20 20-3.5-3.5" />
  </Icono>
)

// ── Los cinco tipos de PQRS ───────────────────────────────────
// Cada tipo tiene su forma, no solo su color: alguien que no distingue el
// morado del rojo tiene que poder elegir bien igual.

export const IconoPeticion = (p) => (
  <Icono {...p}>
    <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" />
    <rect x="8" y="2" width="8" height="4" rx="1" />
    <path d="M9 12h6" />
    <path d="M9 16h4" />
  </Icono>
)

export const IconoQueja = (p) => (
  <Icono {...p}>
    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    <path d="M12 7v4" />
    <path d="M12 14h.01" />
  </Icono>
)

export const IconoIdea = (p) => (
  <Icono {...p}>
    <path d="M9 18h6" />
    <path d="M10 22h4" />
    <path d="M12 2a7 7 0 0 0-4 12.7V18h8v-3.3A7 7 0 0 0 12 2" />
  </Icono>
)

export const IconoFelicitacion = (p) => (
  <Icono {...p}>
    <path d="M7 10v11H4a1 1 0 0 1-1-1v-9a1 1 0 0 1 1-1z" />
    <path d="M7 10l4.2-7.4a2 2 0 0 1 3.5 1.9L13.5 8H19a2 2 0 0 1 2 2.4l-1.6 8A2 2 0 0 1 17.4 20H7" />
  </Icono>
)

// ── Adjuntos y evidencia ──────────────────────────────────────

export const IconoPaquete = (p) => (
  <Icono {...p}>
    <path d="M21 8v8a2 2 0 0 1-1 1.73l-7 4a2 2 0 0 1-2 0l-7-4A2 2 0 0 1 3 16V8a2 2 0 0 1 1-1.73l7-4a2 2 0 0 1 2 0l7 4A2 2 0 0 1 21 8" />
    <path d="m3.3 7 8.7 5 8.7-5" />
    <path d="M12 22V12" />
  </Icono>
)

export const IconoFoto = (p) => (
  <Icono {...p}>
    <path d="M14.5 4h-5L8 6H4a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-4z" />
    <circle cx="12" cy="13" r="3.5" />
  </Icono>
)

export const IconoVideo = (p) => (
  <Icono {...p}>
    <rect x="2" y="6" width="14" height="12" rx="2" />
    <path d="m22 8-6 4 6 4z" />
  </Icono>
)

export const IconoRecibo = (p) => (
  <Icono {...p}>
    <path d="M4 2v20l2.5-1.5L9 22l2.5-1.5L14 22l2.5-1.5L19 22V2l-2.5 1.5L14 2l-2.5 1.5L9 2 6.5 3.5z" />
    <path d="M8 8h8" />
    <path d="M8 12h6" />
  </Icono>
)

export const IconoCopiar = (p) => (
  <Icono {...p}>
    <rect x="9" y="9" width="12" height="12" rx="2" />
    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
  </Icono>
)

export const IconoCandado = (p) => (
  <Icono {...p}>
    <rect x="4" y="10" width="16" height="11" rx="2" />
    <path d="M8 10V7a4 4 0 0 1 8 0v3" />
  </Icono>
)

export const IconoUsuario = (p) => (
  <Icono {...p}>
    <circle cx="12" cy="8" r="4" />
    <path d="M4 21v-1a6 6 0 0 1 6-6h4a6 6 0 0 1 6 6v1" />
  </Icono>
)

export const IconoHistorial = (p) => (
  <Icono {...p}>
    <path d="M3 12a9 9 0 1 0 3-6.7L3 8" />
    <path d="M3 3v5h5" />
    <path d="M12 7.5V12l3 2" />
  </Icono>
)

// ── Vistas de Master Planner ──────────────────────────────────

export const IconoTabla = (p) => (
  <Icono {...p}>
    <rect x="3" y="4" width="18" height="16" rx="2" />
    <path d="M3 10h18" />
    <path d="M3 15h18" />
    <path d="M9 10v10" />
  </Icono>
)

export const IconoCronograma = (p) => (
  <Icono {...p}>
    <path d="M6 6h10" />
    <path d="M4 12h13" />
    <path d="M8 18h9" />
  </Icono>
)

export const IconoCalendario = (p) => (
  <Icono {...p}>
    <rect x="3" y="5" width="18" height="16" rx="2" />
    <path d="M3 10h18" />
    <path d="M8 3v4" />
    <path d="M16 3v4" />
  </Icono>
)

export const IconoTablero = (p) => (
  <Icono {...p}>
    <path d="M3 3v16a2 2 0 0 0 2 2h16" />
    <path d="M7 15v-3" />
    <path d="M12 15V7" />
    <path d="M17 15v-5" />
  </Icono>
)

export const IconoInfo = (p) => (
  <Icono {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 11v5" />
    <path d="M12 8h.01" />
  </Icono>
)

export const IconoBandera = (p) => (
  <Icono {...p}>
    <path d="M4 21V4" />
    <path d="M4 4h13l-2 4 2 4H4" />
  </Icono>
)

export const IconoOjo = (p) => (
  <Icono {...p}>
    <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7" />
    <circle cx="12" cy="12" r="3" />
  </Icono>
)

export const IconoRayo = (p) => (
  <Icono {...p}>
    <path d="M13 2 4 14h7l-1 8 9-12h-7z" />
  </Icono>
)

export const IconoFiltro = (p) => (
  <Icono {...p}>
    <path d="M3 5h18" />
    <path d="M6.5 12h11" />
    <path d="M10 19h4" />
  </Icono>
)

export const IconoClip = (p) => (
  <Icono {...p}>
    <path d="M21.4 11.6 12.3 20.7a5 5 0 0 1-7.1-7.1l9.2-9.2a3.3 3.3 0 1 1 4.7 4.7l-9.1 9.2a1.7 1.7 0 0 1-2.4-2.4l8.5-8.4" />
  </Icono>
)

export const IconoComentario = (p) => (
  <Icono {...p}>
    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
  </Icono>
)

export const IconoEtiqueta = (p) => (
  <Icono {...p}>
    <path d="M12.6 2.6a2 2 0 0 0-1.4-.6H4a2 2 0 0 0-2 2v7.2a2 2 0 0 0 .6 1.4l8.2 8.2a2 2 0 0 0 2.8 0l7.2-7.2a2 2 0 0 0 0-2.8z" />
    <path d="M7 7h.01" />
  </Icono>
)

export const IconoWeb = (p) => (
  <Icono {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M3 12h18" />
    <path d="M12 3a15 15 0 0 1 0 18a15 15 0 0 1 0-18" />
  </Icono>
)

export const IconoRechazo = (p) => (
  <Icono {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="m15 9-6 6" />
    <path d="m9 9 6 6" />
  </Icono>
)

export const IconoNota = (p) => (
  <Icono {...p}>
    <path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8" />
    <path d="M18.4 2.6a2 2 0 0 1 2.8 2.8L15 11.6l-3 .8.8-3z" />
  </Icono>
)

export const IconoEscalar = (p) => (
  <Icono {...p}>
    <path d="M3 11v3a1 1 0 0 0 1 1h3l6 4V6L7 10H4a1 1 0 0 0-1 1" />
    <path d="M17 8a5 5 0 0 1 0 8" />
  </Icono>
)

/** La estrella de las encuestas. `relleno` la marca como elegida — y quien
 *  la lee con lector de pantalla recibe el número, no la forma. */
export const IconoEstrella = ({ relleno = false, ...p }) => (
  <Icono {...p} fill={relleno ? 'currentColor' : 'none'}>
    <path d="m12 2.8 2.85 5.77 6.37.93-4.61 4.49 1.09 6.34L12 17.34l-5.7 3-1.08-6.35L.61 9.5l6.37-.93z" />
  </Icono>
)
