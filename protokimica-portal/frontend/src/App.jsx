import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './core/AuthContext.jsx'
import Login from './modules/auth/Login.jsx'
import Layout from './core/components/Layout.jsx'
import PQRSList from './modules/pqrs/PQRSList.jsx'
import PQRSDetail from './modules/pqrs/PQRSDetail.jsx'
import FormularioPQRS from './modules/publico/FormularioPQRS.jsx'
import SeguimientoPQRS from './modules/publico/SeguimientoPQRS.jsx'
import EncuestaPQRS from './modules/publico/EncuestaPQRS.jsx'
import EncuestaPublica from './modules/publico/EncuestaPublica.jsx'
import Admin from './modules/admin/Admin.jsx'
import MasterPlanner from './modules/masterPlanner/MasterPlanner.jsx'
import Indicadores from './modules/indicadores/Indicadores.jsx'
import Encuestas from './modules/encuestas/Encuestas.jsx'


function PrivateRoute({ children }) {
  const { user } = useAuth()
  return user ? children : <Navigate to="/login" replace />
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
          <Layout />
        </PrivateRoute>
      }>
        <Route index element={<Navigate to="/pqrs" replace />} />
        <Route path="pqrs"     element={<PQRSList />} />
        <Route path="pqrs/:id" element={<PQRSDetail />} />
        <Route path="admin" element={<Admin />} />
        <Route path="master-planner" element={<MasterPlanner />} />
        <Route path="indicadores" element={<Indicadores />} />
        <Route path="encuestas" element={<Encuestas />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}