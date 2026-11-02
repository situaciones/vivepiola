import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { AlertCircle, Scale } from 'lucide-react';
import client from '../api/client';
import { useAuth } from '../context/AuthContext';
import Marca from '../components/Marca';

/**
 * Se llega desde el correo de invitacion (/invitacion/<codigo>). La persona
 * ve a que comunidad y con que rol la invitan, elige usuario y contrasena, y
 * queda adentro. Publica a proposito: todavia no tiene cuenta.
 */

// El primer error de cada campo, en el orden del formulario.
function primerError(datos) {
  if (!datos) return 'No se pudo crear la cuenta. Intenta de nuevo.';
  if (datos.detail) return datos.detail;
  for (const campo of ['first_name', 'last_name', 'username', 'password']) {
    const valor = datos[campo];
    if (valor) return Array.isArray(valor) ? valor.join(' ') : String(valor);
  }
  return 'Revisa los datos e intenta de nuevo.';
}

export default function AceptarInvitacion() {
  const { codigo } = useParams();
  const { entrarConTokens } = useAuth();
  const navigate = useNavigate();
  const [invitacion, setInvitacion] = useState(null);
  const [problema, setProblema] = useState('');
  const [form, setForm] = useState({ first_name: '', last_name: '', username: '', password: '', repetir: '' });
  const [error, setError] = useState('');
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    client.get(`/auth/invitacion/${encodeURIComponent(codigo)}/`)
      .then(({ data }) => {
        setInvitacion(data);
        setForm((f) => ({ ...f, username: data.usuario_sugerido }));
      })
      .catch((err) => setProblema(err.response?.data?.detail || 'No se pudo abrir la invitacion.'));
  }, [codigo]);

  const cambiar = (campo) => (e) => setForm({ ...form, [campo]: e.target.value });

  const crear = async (e) => {
    e.preventDefault();
    setError('');
    if (form.password !== form.repetir) {
      setError('Las contrasenas no coinciden.');
      return;
    }
    setEnviando(true);
    try {
      const { repetir, ...datos } = form;
      const { data } = await client.post(`/auth/invitacion/${encodeURIComponent(codigo)}/`, datos);
      await entrarConTokens(data);
      navigate('/app', { replace: true });
    } catch (err) {
      setError(primerError(err.response?.data));
      setEnviando(false);
    }
  };

  return (
    <div className="pantalla-login">
      <div className="login-panel-marca">
        <Link to="/" className="marca-top" style={{ textDecoration: 'none', color: 'inherit' }}>
          <Marca size={34} />
        </Link>
        <div className="marca-claim">
          <h2><strong>Bienvenido</strong> a tu comunidad.</h2>
          <p>
            Con tu cuenta veras los avisos y multas de tu unidad, podras presentar
            descargos y escribir a la administracion.
          </p>
        </div>
        <div className="marca-foot">
          <Scale size={13} style={{ verticalAlign: 'middle', marginRight: 6 }} />
          Ley 21.442 sobre Copropiedad Inmobiliaria — Chile
        </div>
      </div>

      <div className="login-cabecera-movil">
        <Marca size={40} />
        <div>
          <h2>Bienvenido a tu <strong>comunidad</strong>.</h2>
          <p>Crea tu cuenta para entrar a SinConflicto.</p>
        </div>
      </div>

      <div className="login-panel-form">
        {problema ? (
          <div className="login-tarjeta">
            <h1>Invitacion no disponible</h1>
            <div className="mensaje-error"><AlertCircle size={16} />{problema}</div>
            <Link to="/login" className="btn btn-secundario">Ir a iniciar sesion</Link>
          </div>
        ) : !invitacion ? (
          <div className="login-tarjeta"><p className="texto-secundario">Cargando invitacion…</p></div>
        ) : (
          <form className="login-tarjeta" onSubmit={crear}>
            <div>
              <h1>Crea tu cuenta</h1>
              <p className="texto-secundario">
                Te invitaron a <b>{invitacion.comunidad}</b> como <b>{invitacion.rol}</b>
                {invitacion.unidad ? <> de <b>{invitacion.unidad}</b></> : null}.
                La cuenta queda con el correo {invitacion.correo}.
              </p>
            </div>

            <div className="fila-formulario">
              <label>
                Nombre
                <input value={form.first_name} onChange={cambiar('first_name')} autoComplete="given-name" required />
              </label>
              <label>
                Apellido
                <input value={form.last_name} onChange={cambiar('last_name')} autoComplete="family-name" />
              </label>
            </div>
            <label>
              Usuario (con el que entraras)
              <input
                value={form.username} onChange={cambiar('username')} required
                autoCapitalize="none" autoCorrect="off" autoComplete="username"
              />
            </label>
            <label>
              Contrasena (minimo 8 caracteres)
              <input type="password" value={form.password} onChange={cambiar('password')} autoComplete="new-password" required />
            </label>
            <label>
              Repite la contrasena
              <input type="password" value={form.repetir} onChange={cambiar('repetir')} autoComplete="new-password" required />
            </label>

            {error && <div className="mensaje-error"><AlertCircle size={16} />{error}</div>}

            <button className="btn btn-primario" type="submit" disabled={enviando}>
              {enviando ? 'Creando cuenta...' : 'Crear cuenta y entrar'}
            </button>
            <p className="texto-secundario" style={{ textAlign: 'center', fontSize: '0.85rem' }}>
              ¿Ya tienes cuenta? <Link to="/login">Inicia sesion</Link> · <Link to="/privacidad">Privacidad</Link>
            </p>
          </form>
        )}
      </div>
    </div>
  );
}
