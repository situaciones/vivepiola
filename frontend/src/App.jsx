import { Navigate, Route, BrowserRouter, Routes } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import Landing from './pages/Landing';
import Login from './pages/Login';
import FiscalizadorDashboard from './pages/dashboards/FiscalizadorDashboard';
import ComiteDashboard from './pages/dashboards/ComiteDashboard';
import AdministradorDashboard from './pages/dashboards/AdministradorDashboard';
import ResidenteDashboard from './pages/dashboards/ResidenteDashboard';

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
