import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ShieldCheck, Trash2, X } from 'lucide-react';
import client from '../api/client';
import { useAuth } from '../context/AuthContext';

/**
 * Mi cuenta: los datos de la sesion, la politica de privacidad y eliminar la
 * cuenta. Apple exige que eliminar la cuenta se pueda hacer dentro de la app,
 * sin escribirle a nadie; lo que se borra y lo que queda lo explica
 * Usuario.eliminar_cuenta en el backend y la politica de privacidad.
 */
export default function MiCuenta({ onCerrar }) {
  const { usuario, logout } = useAuth();
  const [eliminando, setEliminando] = useState(false);
  const [confirmacion, setConfirmacion] = useState('');
  const [error, setError] = useState('');
  const [enviando, setEnviando] = useState(false);

  const nombre = [usuario?.first_name, usuario?.last_name].filter(Boolean).join(' ') || usuario?.username;
  const listo = confirmacion.trim().toUpperCase() === 'ELIMINAR';

  const eliminar = async (e) => {
    e.preventDefault();
    setError('');
    setEnviando(true);
    try {
      await client.post('/auth/me/eliminar/', { confirmacion });
      logout();
    } catch (err) {
      const datos = err.response?.data;
      setError(datos?.detail || datos?.confirmacion || 'No se pudo eliminar la cuenta. Intenta de nuevo.');
      setEnviando(false);
    }
  };

  return (
    <div className="cuenta-overlay" onClick={onCerrar}>
      <div className="cuenta-dialogo" role="dialog" aria-modal="true" aria-label="Mi cuenta" onClick={(e) => e.stopPropagation()}>
        <div className="cuenta-cabecera">
          <strong>Mi cuenta</strong>
          <button type="button" className="btn btn-fantasma" onClick={onCerrar} aria-label="Cerrar">
            <X size={18} />
          </button>
        </div>

        <p><b>{nombre}</b></p>
        {usuario?.email && <p className="texto-secundario">{usuario.email}</p>}

        <Link to="/privacidad" className="cuenta-enlace" onClick={onCerrar}>
          <ShieldCheck size={17} /> Politica de privacidad
        </Link>

        {!eliminando ? (
          <button type="button" className="cuenta-enlace peligro" onClick={() => setEliminando(true)}>
            <Trash2 size={17} /> Eliminar mi cuenta
          </button>
        ) : (
          <form className="cuenta-eliminar" onSubmit={eliminar}>
            <p>
              Se borran tu nombre, tu correo y tu telefono, y no podras volver a entrar con esta
              cuenta. Las denuncias y actuaciones que hiciste quedan en los expedientes de tu
              comunidad como "Cuenta eliminada", porque son parte del procedimiento.
            </p>
            <label>
              Escribe ELIMINAR para confirmar
              <input
                value={confirmacion} onChange={(e) => setConfirmacion(e.target.value)}
                autoCapitalize="characters" autoComplete="off" autoFocus
              />
            </label>
            {error && <div className="mensaje-error">{error}</div>}
            <div className="cuenta-acciones">
              <button type="button" className="btn btn-secundario" onClick={() => setEliminando(false)}>
                Cancelar
              </button>
              <button type="submit" className="btn btn-peligro" disabled={!listo || enviando}>
                {enviando ? 'Eliminando…' : 'Eliminar mi cuenta'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
