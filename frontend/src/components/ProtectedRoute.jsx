import { Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function ProtectedRoute({ roles, children }) {
  const { usuario, cargando } = useAuth();

  if (cargando) {
    return <div className="cargando-pantalla">Cargando...</div>;
  }
  if (!usuario) {
    return <Navigate to="/login" replace />;
  }
  if (roles && !roles.includes(usuario.rol)) {
    return <Navigate to="/app" replace />;
  }
  return children;
}
