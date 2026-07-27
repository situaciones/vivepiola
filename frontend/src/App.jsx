import { Navigate, Route, BrowserRouter, Routes } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import AtajoMulta from './pages/AtajoMulta';
import Landing from './pages/Landing';
import Login from './pages/Login';
import FiscalizadorDashboard from './pages/dashboards/FiscalizadorDashboard';
import ComiteDashboard from './pages/dashboards/ComiteDashboard';
import AdministradorDashboard from './pages/dashboards/AdministradorDashboard';
import ResidenteDashboard from './pages/dashboards/ResidenteDashboard';

function PendienteAsignacion() {
  const { usuario, logout } = useAuth();
  return (
    <div className="contenedor" style={{ maxWidth: 560, margin: '80px auto', textAlign: 'center' }}>
      <h2>Tu cuenta esta casi lista</h2>
      <p style={{ margin: '16px 0' }}>
        Hola {usuario?.first_name || usuario?.username}. Tu ingreso con Google quedo registrado,
        pero el Administrador de tu comunidad aun debe confirmar tu rol
        (residente, conserje o comite) antes de que puedas usar la plataforma.
      </p>
      <p className="texto-secundario">
        {usuario?.condominio
          ? 'Tu solicitud ya esta en la bandeja del Administrador de tu comunidad.'
          : 'Si tienes un codigo de invitacion o de comunidad, cierra sesion y vuelve a entrar ingresandolo.'}
      </p>
      <button className="btn btn-secundario" style={{ marginTop: 20 }} onClick={logout}>
        Cerrar sesion
      </button>
    </div>
  );
}

function Home() {
  const { usuario } = useAuth();
  switch (usuario?.rol) {
    case 'FISCALIZADOR':
      return <FiscalizadorDashboard />;
    case 'COMITE':
      return <ComiteDashboard />;
    case 'ADMINISTRADOR':
      return <AdministradorDashboard />;
    case 'RESIDENTE':
      return <ResidenteDashboard />;
    case 'PENDIENTE':
      return <PendienteAsignacion />;
    default:
      return <div className="contenedor">Bienvenido, {usuario?.username}.</div>;
  }
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login />} />
          {/* Atajo de los avisos de WhatsApp: /m/12 abre ese expediente. */}
          <Route path="/m/:id" element={<AtajoMulta />} />
          <Route
            path="/app"
            element={
              <ProtectedRoute>
                <Home />
              </ProtectedRoute>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
