import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { AlertCircle, Scale, ShieldCheck } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export default function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [enviando, setEnviando] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setEnviando(true);
    try {
      await login(username, password);
      navigate('/app');
    } catch {
      setError('Usuario o contrasena incorrectos.');
    } finally {
      setEnviando(false);
    }
  };

  return (
    <div className="pantalla-login">
      <div className="login-panel-marca">
        <Link to="/" className="marca-top" style={{ textDecoration: 'none', color: 'inherit' }}>
          <span className="logo-mark"><ShieldCheck size={16} strokeWidth={2.4} /></span>
          VIVEPIOLA
        </Link>
        <div className="marca-claim">
          <h2><strong>VIVEPIOLA</strong> proceso, sin atajos.</h2>
          <p>
            Cada multa recorre el circuito que exige la Ley 21.442: evidencia del
            fiscalizador, aprobacion exclusiva del Comite, notificacion formal del
            Administrador y derecho a descargo del residente. El sistema bloquea
            cualquier accion fuera de rol.
          </p>
        </div>
        <div className="marca-foot">
          <Scale size={13} style={{ verticalAlign: 'middle', marginRight: 6 }} />
          Ley 21.442 sobre Copropiedad Inmobiliaria — Chile
        </div>
      </div>

      <div className="login-panel-form">
        <form className="login-tarjeta" onSubmit={handleSubmit}>
          <div>
            <h1>Iniciar sesion</h1>
            <p className="texto-secundario">Ingresa con tu cuenta del condominio.</p>
          </div>

          <label>
            Usuario
            <input value={username} onChange={(e) => setUsername(e.target.value)} required autoFocus />
          </label>
          <label>
            Contrasena
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </label>

          {error && (
            <div className="mensaje-error">
              <AlertCircle size={16} />
              {error}
            </div>
          )}

          <button className="btn btn-primario" type="submit" disabled={enviando}>
            {enviando ? 'Ingresando...' : 'Ingresar'}
          </button>
        </form>
      </div>
    </div>
  );
}
