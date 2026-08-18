import { useEffect, useState } from 'react'
import { Outlet, NavLink, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../AuthContext.jsx'
import { moduloDeRuta, puedeVerModulo } from '../modulos.js'
import CambiarPasswordModal from './CambiarPasswordModal.jsx'
import { AvisoVersionNueva, ChipVersion } from './Version.jsx'
import {
  IconoAdmin, IconoAgente, IconoCarpeta, IconoEncuestas, IconoFicha,
  IconoIndicadores, IconoInicio, IconoLlave, IconoPQRS, IconoPanel,
  IconoProyectos, IconoSalir,
} from './Iconos.jsx'

// Cada entrada dice de qué módulo es, para esconder la que el usuario no
// puede abrir. Un menú que lleva a un 403 es peor que no tener el menú.
const navItems = [
  { to: '/', Icono: IconoInicio, label: 'Inicio', modulo: 'inicio', exact: true },
  { to: '/pqrs', Icono: IconoPQRS, label: 'PQRS', modulo: 'pqrs' },
  { to: '/master-planner', Icono: IconoProyectos, label: 'Master Planner', modulo: 'master_planner' },
  { to: '/indicadores', Icono: IconoIndicadores, label: 'Indicadores', modulo: 'indicadores' },
  { to: '/encuestas', Icono: IconoEncuestas, label: 'Encuestas', modulo: 'encuestas' },
]

// Lo que todavía no existe va junto y al final, no intercalado entre lo que
// sí funciona: un menú salpicado de «Pronto» se lee como producto a medias.
const proximos = [
  { clave: 'fichas', Icono: IconoFicha, label: 'Fichas de seguridad' },
  { clave: 'documentos', Icono: IconoCarpeta, label: 'Documentación' },
  { clave: 'agente', Icono: IconoAgente, label: 'Agente IA' },
]

const TITULO_DE_MODULO = {
  inicio: 'Inicio',
  pqrs: 'PQRS',
  master_planner: 'Master Planner',
  indicadores: 'Indicadores',
  encuestas: 'Encuestas',
  admin: 'Administración',
}

/** Un solo interruptor sirve para dos cosas distintas según el ancho:
 *  en escritorio encoge el menú, en celular lo abre encima del contenido. */
function useEsEscritorio() {
  const [esEscritorio, setEsEscritorio] = useState(
    () => typeof window !== 'undefined' && window.matchMedia('(min-width: 768px)').matches,
  )
  useEffect(() => {
    const mq = window.matchMedia('(min-width: 768px)')
    const alCambiar = (e) => setEsEscritorio(e.matches)
    mq.addEventListener('change', alCambiar)
    return () => mq.removeEventListener('change', alCambiar)
  }, [])
  return esEscritorio
}

function Seccion({ children, collapsed }) {
  if (collapsed) return <div className="h-4" aria-hidden="true" />
  return (
    <div className="px-3 pt-5 pb-1.5 text-[10.5px] font-semibold uppercase
      tracking-[0.09em] text-nav-seccion">
      {children}
    </div>
  )
}

/** El ítem activo se marca con fondo, peso y barra ámbar — no solo color:
 *  el ámbar sobre el azul oscuro no alcanza a leerse por sí solo. */
function ItemMenu({ to, exact, Icono, label, collapsed, onNavegar }) {
  return (
    <NavLink
      to={to}
      end={exact}
      onClick={onNavegar}
      title={collapsed ? label : undefined}
      className={({ isActive }) => `
        relative flex items-center gap-3 mx-2 px-3 py-2.5 rounded-lg
        text-[13.5px] transition-colors duration-150 ease-suave
        ${isActive
          ? 'bg-white/[0.08] text-white font-medium'
          : 'text-nav-texto font-normal hover:bg-white/[0.05] hover:text-white'}
      `}
    >
      {({ isActive }) => (
        <>
          {isActive && (
            <span
              className="absolute left-0 top-1/2 -translate-y-1/2 -ml-2 w-[3px] h-5
                rounded-r bg-ambar"
              aria-hidden="true"
            />
          )}
          <Icono tam={18} className={isActive ? '' : 'opacity-80'} />
          {!collapsed && <span className="truncate">{label}</span>}
        </>
      )}
    </NavLink>
  )
}

export default function Layout() {
  const [collapsed, setCollapsed] = useState(false)
  const [abierto, setAbierto] = useState(false)
  const [mostrarPassword, setMostrarPassword] = useState(false)
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const esEscritorio = useEsEscritorio()

  const alternarMenu = () => {
    if (esEscritorio) setCollapsed(v => !v)
    else setAbierto(v => !v)
  }

  // En celular el menú tapa el contenido: Escape lo cierra, como cualquier
  // panel que se abre encima de algo.
  useEffect(() => {
    if (!abierto) return
    const alTeclear = (e) => { if (e.key === 'Escape') setAbierto(false) }
    window.addEventListener('keydown', alTeclear)
    return () => window.removeEventListener('keydown', alTeclear)
  }, [abierto])

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const iniciales = user?.nombre
    ? user.nombre.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase()
    : 'U'

  const tituloActual = TITULO_DE_MODULO[moduloDeRuta(pathname)] ?? ''
  const encogido = esEscritorio && collapsed

  return (
    <div className="flex h-screen bg-fondo overflow-hidden">

      {/* En celular el menú entra encima del contenido; el velo lo cierra. */}
      {abierto && (
        <div
          className="fixed inset-0 z-30 bg-texto/40 md:hidden"
          onClick={() => setAbierto(false)}
          aria-hidden="true"
        />
      )}

      {/* ── MENÚ LATERAL ──
          `inert` cuando está fuera de pantalla: si no, el tabulador se pasea
          por seis enlaces invisibles antes de llegar al contenido. */}
      <aside
        inert={!esEscritorio && !abierto ? '' : undefined}
        className={`
          fixed inset-y-0 left-0 z-40 md:static md:z-auto
          flex flex-col bg-nav flex-shrink-0
          transition-[width,transform] duration-200 ease-suave
          ${encogido ? 'md:w-16' : 'md:w-60'}
          w-60 ${abierto ? 'translate-x-0' : '-translate-x-full'} md:translate-x-0
        `}
      >
        {/* Logo */}
        <div className="flex items-center gap-3 px-4 h-[60px] flex-shrink-0
          border-b border-nav-borde">
          <img src="/logo.png" alt="" className="h-9 w-auto object-contain flex-shrink-0" />
          {!encogido && (
            <div className="min-w-0">
              <div className="text-white font-semibold text-sm leading-tight truncate">
                Protokimica
              </div>
              <div className="text-nav-seccion text-[11px] leading-tight">
                Portal de gestión
              </div>
            </div>
          )}
        </div>

        <nav className="flex-1 py-1 overflow-y-auto overflow-x-hidden">
          <Seccion collapsed={encogido}>Gestión</Seccion>

          {navItems.filter(item => puedeVerModulo(user, item.modulo)).map(item => (
            <ItemMenu
              key={item.to}
              {...item}
              collapsed={encogido}
              onNavegar={() => setAbierto(false)}
            />
          ))}

          {/* Configuración: solo administradores. Desaparece la sección
              entera, no nada más el enlace. */}
          {puedeVerModulo(user, 'admin') && (
            <>
              <Seccion collapsed={encogido}>Sistema</Seccion>
              <ItemMenu
                to="/admin"
                Icono={IconoAdmin}
                label="Administración"
                collapsed={encogido}
                onNavegar={() => setAbierto(false)}
              />
            </>
          )}

          <Seccion collapsed={encogido}>Próximamente</Seccion>
          {proximos.map(({ clave, Icono, label }) => (
            <div
              key={clave}
              aria-disabled="true"
              title={encogido ? `${label} — próximamente` : undefined}
              className="flex items-center gap-3 mx-2 px-3 py-2.5 rounded-lg
                text-[13.5px] text-nav-texto/45 cursor-default"
            >
              <Icono tam={18} />
              {!encogido && (
                <>
                  <span className="truncate">{label}</span>
                  <span className="ml-auto text-[10px] px-1.5 py-0.5 rounded-md
                    bg-white/[0.06] text-nav-texto/70">
                    Pronto
                  </span>
                </>
              )}
            </div>
          ))}
        </nav>

        {/* Pie: salir y versión */}
        <div className="border-t border-nav-borde py-1.5 flex-shrink-0">
          <button
            onClick={handleLogout}
            title={encogido ? 'Cerrar sesión' : undefined}
            className="w-full flex items-center gap-3 px-5 py-2.5 text-[13.5px]
              text-nav-texto hover:text-white hover:bg-white/[0.05]
              transition-colors duration-150 ease-suave"
          >
            <IconoSalir tam={18} />
            {!encogido && <span className="truncate">Cerrar sesión</span>}
          </button>

          <ChipVersion collapsed={encogido} />
        </div>
      </aside>

      {/* ── CONTENIDO ── */}
      <div className="flex flex-col flex-1 overflow-hidden min-w-0">

        <header className="h-[60px] bg-superficie border-b border-borde
          flex items-center px-4 sm:px-5 gap-3 flex-shrink-0">
          <button
            onClick={alternarMenu}
            aria-label={
              esEscritorio
                ? (collapsed ? 'Mostrar el menú' : 'Ocultar el menú')
                : (abierto ? 'Cerrar el menú' : 'Abrir el menú')
            }
            aria-expanded={esEscritorio ? !collapsed : abierto}
            className="w-9 h-9 flex items-center justify-center rounded-lg
              text-texto-3 hover:bg-superficie-2 hover:text-acento-fuerte
              transition-colors duration-150 ease-suave"
          >
            <IconoPanel tam={18} />
          </button>

          {tituloActual && (
            <span className="text-[13.5px] font-semibold text-texto truncate">
              {tituloActual}
            </span>
          )}

          <div className="flex-1" />

          <button
            onClick={() => setMostrarPassword(true)}
            title="Cambiar contraseña"
            className="group flex items-center gap-2.5 pl-1 pr-2.5 py-1 rounded-full
              hover:bg-superficie-2 transition-colors duration-150 ease-suave"
          >
            <span className="w-8 h-8 rounded-full bg-acento-suave flex items-center
              justify-center text-acento text-xs font-semibold">
              {iniciales}
            </span>
            <span className="hidden sm:block text-[13px] font-medium text-texto truncate max-w-[14rem]">
              {user?.nombre}
            </span>
            <IconoLlave
              tam={14}
              className="text-texto-3 opacity-0 group-hover:opacity-100 transition-opacity"
            />
          </button>
        </header>

        <main className="flex-1 overflow-y-auto p-4 sm:p-6">
          <AvisoVersionNueva />
          <Outlet />
        </main>
      </div>

      {mostrarPassword && (
        <CambiarPasswordModal onClose={() => setMostrarPassword(false)} />
      )}
    </div>
  )
}
