import { useState } from 'react';
import { Capacitor } from '@capacitor/core';
import { Navigate, Route, BrowserRouter, Routes } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import MiCuenta from './components/MiCuenta';
import ProtectedRoute from './components/ProtectedRoute';
import AcuseNotificacion from './pages/AcuseNotificacion';
import AtajoMulta from './pages/AtajoMulta';
import ComoFunciona from './pages/ComoFunciona';
import Landing from './pages/Landing';
import Login from './pages/Login';
import Privacidad from './pages/Privacidad';
import FiscalizadorDashboard from './pages/dashboards/FiscalizadorDashboard';
import ComiteDashboard from './pages/dashboards/ComiteDashboard';
import AdministradorDashboard from './pages/dashboards/AdministradorDashboard';
import ResidenteDashboard from './pages/dashboards/ResidenteDashboard';

function PendienteAsignacion() {
  const { usuario, logout } = useAuth();
  const [cuenta, setCuenta] = useState(false);
  return (
    <div className="contenedor" style={{ maxWidth: 560, margin: '80px auto', textAlign: 'center' }}>
      <h2>Tu cuenta esta casi lista</h2>
      <p style={{ margin: '16px 0' }}>
        Hola {usuario?.first_name || usuario?.username}. Tu ingreso con Google quedo registrado,
        pero el Administrador de tu comunidad aun debe confirmar tu rol
        (residente, denunciante o comite) antes de que puedas usar la plataforma.
      </p>
      <p className="texto-secundario">
        {usuario?.condominio
          ? 'Tu solicitud ya esta en la bandeja del Administrador de tu comunidad.'
          : 'Si tienes un codigo de invitacion o de comunidad, cierra sesion y vuelve a entrar ingresandolo.'}
      </p>
      <div style={{ display: 'flex', gap: 10, justifyContent: 'center', marginTop: 20, flexWrap: 'wrap' }}>
        <button className="btn btn-secundario" onClick={() => setCuenta(true)}>Mi cuenta</button>
        <button className="btn btn-secundario" onClick={logout}>Cerrar sesion</button>
      </div>
      {cuenta && <MiCuenta onCerrar={() => setCuenta(false)} />}
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
          {/* En la app Android la portada de marketing sobra: se entra directo. */}
          <Route
            path="/"
            element={Capacitor.isNativePlatform() ? <Navigate to="/app" replace /> : <Landing />}
          />
          <Route path="/como-funciona" element={<ComoFunciona />} />
          <Route path="/login" element={<Login />} />
          <Route path="/privacidad" element={<Privacidad />} />
          {/* Atajo de los avisos de WhatsApp: /m/12 abre ese expediente. */}
          <Route path="/m/:id" element={<AtajoMulta />} />
          {/* Publica a proposito: se llega por el enlace del correo, sin cuenta. */}
          <Route path="/acuse/:token" element={<AcuseNotificacion />} />
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
