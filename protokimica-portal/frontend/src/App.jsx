import { Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { useAuth } from './core/AuthContext.jsx'
import { moduloDeRuta, puedeVerModulo, RUTA_POR_DEFECTO } from './core/modulos.js'
import Login from './modules/auth/Login.jsx'
import Layout from './core/components/Layout.jsx'
import Inicio from './modules/inicio/Inicio.jsx'
import PQRSList from './modules/pqrs/PQRSList.jsx'
import PQRSDetail from './modules/pqrs/PQRSDetail.jsx'
import FormularioPQRS from './modules/publico/FormularioPQRS.jsx'
import SeguimientoPQRS from './modules/publico/SeguimientoPQRS.jsx'
import EncuestaPQRS from './modules/publico/EncuestaPQRS.jsx'
import EncuestaPublica from './modules/publico/EncuestaPublica.jsx'
import Admin from './modules/admin/Admin.jsx'
import MasterPlanner from './modules/masterPlanner/MasterPlanner.jsx'
import Indicadores from './modules/indicadores/Indicadores.jsx'
import Mejora from './modules/mejora/Mejora.jsx'
import Encuestas from './modules/encuestas/Encuestas.jsx'


function PrivateRoute({ children }) {
  const { user } = useAuth()
  return user ? children : <Navigate to="/login" replace />
}

/**
 * Cierra la pantalla de un módulo que este rol no puede abrir.
 *
 * Es cortesía, no seguridad: quien escriba la URL a mano igual choca con el
 * 403 del backend. Lo que evita es la pantalla rota —el módulo cargando,
 * fallando y mostrando un error feo— cuando la respuesta ya se sabe.
 */
function RutaDeModulo({ children }) {
  const { user } = useAuth()
  const { pathname } = useLocation()
  const modulo = moduloDeRuta(pathname)

  if (modulo && !puedeVerModulo(user, modulo)) {
    return <Navigate to={RUTA_POR_DEFECTO} replace />
  }
  return children
}

export default function App() {
  return (
    <Routes>
      {/* ── Rutas públicas (sin login) ── */}
      <Route path="/login"       element={<Login />} />
      <Route path="/formulario"  element={<FormularioPQRS />} />
      <Route path="/seguimiento" element={<SeguimientoPQRS />} />
      <Route path="/encuesta/:codigo" element={<EncuestaPQRS />} />
      {/* Corta a propósito: va impresa en el QR de un punto de venta. */}
      <Route path="/e/:slug" element={<EncuestaPublica />} />

      {/* ── Rutas protegidas (empleados) ── */}
      <Route path="/" element={
        <PrivateRoute>
          <RutaDeModulo>
            <Layout />
          </RutaDeModulo>
        </PrivateRoute>
      }>
        <Route index element={<Inicio />} />
        <Route path="pqrs"     element={<PQRSList />} />
        <Route path="pqrs/:id" element={<PQRSDetail />} />
        <Route path="admin" element={<Admin />} />
        <Route path="master-planner" element={<MasterPlanner />} />
        <Route path="indicadores" element={<Indicadores />} />
        <Route path="mejora"      element={<Mejora />} />
        <Route path="encuestas" element={<Encuestas />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}