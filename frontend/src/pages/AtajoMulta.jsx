import { Navigate, useParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

/**
 * Atajo /m/:id — el destino de los links que van en los avisos de WhatsApp.
 *
 * El link NO lleva la sesion adentro (los mensajes se reenvian, quedan en
 * respaldos y en historiales). Aqui se resuelve quien es la persona:
 *   - sin sesion  -> al login, recordando a donde queria ir
 *   - con sesion  -> a su panel, ya abierto en ese expediente
 */
export default function AtajoMulta() {
  const { id } = useParams();
  const { usuario, cargando } = useAuth();

  if (cargando) {
    return <div className="cargando-pantalla">Abriendo el expediente...</div>;
  }
  if (!usuario) {
    return <Navigate to={`/login?next=${encodeURIComponent(`/m/${id}`)}`} replace />;
  }
  return <Navigate to={`/app?multa=${id}`} replace />;
}
