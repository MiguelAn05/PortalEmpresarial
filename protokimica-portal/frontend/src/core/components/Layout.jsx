import { useState } from 'react'
import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../AuthContext.jsx'

const navItems = [
  { to: '/',        icon: '🏠', label: 'Inicio',          exact: true  },
  { to: '/pqrs', icon: '📨', label: 'PQRS' },
  { TO: '/master-planner', icon: '🗂️', label:'MasterPlanner'}
  // Cuando agregues Indicadores, solo añades una línea aquí:
  //{ to: '/indicadores', icon: '📈', label: 'Indicadores' },
]

export default function Layout() {
  const [collapsed, setCollapsed] = useState(false)
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const initials = user?.nombre
    ? user.nombre.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase()
    : 'U'

  return (
    <div className="flex h-screen bg-[#F0F4FA] overflow-hidden">

      {/* ── SIDEBAR ── */}
      <aside
        className={`
          flex flex-col bg-[#0D2B5E] transition-all duration-300 flex-shrink-0
          ${collapsed ? 'w-16' : 'w-60'}
        `}
      >


{/* Logo */}
      
<div
  className="flex items-center gap-3 px-4 border-b border-white/10 flex-shrink-0"
  style={{ height: "60px" }}
>
  <img
    src="/logo.png"
    alt="Protokimica"
    className="h-10 w-auto object-contain"
  />

  {!collapsed && (
    <div>
      <div className="text-white font-bold text-sm leading-tight">
        Protokimica
      </div>
      <div className="text-white/40 text-xs">
        Portal de Gestión
      </div>
    </div>
  )}
</div>

        {/* Nav items */}
        <nav className="flex-1 py-3 overflow-y-auto overflow-x-hidden">
          {!collapsed && (
            <div className="px-4 py-2 text-white/30 text-xs font-semibold uppercase tracking-widest">
              Gestión
            </div>
          )}

          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.exact}
              className={({ isActive }) => `
                flex items-center gap-3 px-4 py-2.5 mx-1 rounded-lg
                transition-all duration-150 cursor-pointer
                border-l-2 ml-0 pl-4
                ${isActive
                  ? 'bg-[#F5A800]/15 text-[#F5A800] border-[#F5A800] font-semibold'
                  : 'text-white/60 border-transparent hover:bg-white/7 hover:text-white'
                }
              `}
            >
              <span className="text-base flex-shrink-0">{item.icon}</span>
              {!collapsed && (
                <span className="text-sm truncate">{item.label}</span>
              )}
            </NavLink>
          ))}

          {!collapsed && (
            <div className="px-4 py-2 mt-3 text-white/30 text-xs font-semibold uppercase tracking-widest">
              PROXIMO
            </div>
          )}

          {[
            //{ to: '/reportes',    icon: '📊', label: 'Reportes'      },
            {to: '/indicadores', icon: '📈', label: 'Indicadores'},
            {to: '/fichas de seguridad', icon:'📋', label:'Fichas de Seguridad'},
            {to: '/documentos',  icon: '📁', label: 'Documentación' },
          ].map((item) => (
            <div
              key={item.to}
              title={collapsed ? item.label : ''}
              className="flex items-center gap-3 px-4 py-2.5 mx-1 rounded-lg
                text-white/30 border-l-2 border-transparent cursor-not-allowed"
            >
              <span className="text-base flex-shrink-0">{item.icon}</span>
              {!collapsed && <span className="text-sm truncate">{item.label}</span>}
              {!collapsed && (
                <span className="ml-auto text-xs bg-white/10 text-white/30 px-1.5 py-0.5 rounded-full">
                  Pronto
                </span>
              )}
            </div>
          ))}

          {!collapsed && (
            <div className="px-4 py-2 mt-3 text-white/30 text-xs font-semibold uppercase tracking-widest">
              Sistema
            </div>
          )}

          <NavLink
            to="/admin"
            className={({ isActive }) => `
              flex items-center gap-3 px-4 py-2.5 mx-1 rounded-lg
              transition-all duration-150 cursor-pointer
              border-l-2 ml-0 pl-4
              ${isActive
                ? 'bg-[#F5A800]/15 text-[#F5A800] border-[#F5A800] font-semibold'
                : 'text-white/60 border-transparent hover:bg-white/7 hover:text-white'
              }
            `}
          >
            <span className="text-base flex-shrink-0">⚙️</span>
            {!collapsed && <span className="text-sm truncate">Administración</span>}
          </NavLink>
          
        </nav>

        {/* Bottom: Copilot + usuario */}
        <div className="border-t border-white/10 py-2 flex-shrink-0">
          <div className="flex items-center gap-3 px-4 py-2.5 text-white/40 text-sm">
            <span className="text-base flex-shrink-0">🤖</span>
            {!collapsed && <span className="truncate">Agente IA</span>}
            {!collapsed && (
              <span className="ml-auto text-xs bg-white/10 px-1.5 py-0.5 rounded-full">
                Pronto
              </span>
            )}
          </div>

          <button
            onClick={handleLogout}
            className="w-full flex items-center gap-3 px-4 py-2.5
              text-white/50 hover:text-white hover:bg-white/7
              transition text-sm"
          >
            <span className="text-base flex-shrink-0">🚪</span>
            {!collapsed && <span className="truncate">Cerrar sesión</span>}
          </button>
        </div>
      </aside>

      {/* ── MAIN ── */}
      <div className="flex flex-col flex-1 overflow-hidden">

        {/* Topbar */}
        <header className="h-[60px] bg-white border-b border-[#D6E0F0] flex items-center px-5 gap-3 flex-shrink-0">
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="w-8 h-8 flex items-center justify-center rounded-lg
              text-[#6B7EA8] hover:bg-[#F0F4FA] hover:text-[#0D2B5E] transition"
          >
            ☰
          </button>

          <div className="flex-1" />

          {/* Usuario */}
          <div className="flex items-center gap-2 bg-[#F0F4FA] border border-[#D6E0F0]
            rounded-full px-3 py-1.5 cursor-pointer hover:bg-[#D6E0F0] transition">
            <div className="w-6 h-6 rounded-full bg-[#1A4FA0] flex items-center justify-center">
              <span className="text-white text-xs font-bold">{initials}</span>
            </div>
            <span className="text-sm font-medium text-[#1A2B47]">{user?.nombre}</span>
          </div>
        </header>

        {/* Contenido — cada pantalla se renderiza aquí */}
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}