import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { AlertCircle, KeyRound, Scale } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import Marca from '../components/Marca';

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || '';
// Sin CLIENT_ID solo existe el modo simulado, que el backend de produccion
// rechaza: en una version publicada no se ofrece un boton que no funciona.
const CON_GOOGLE = Boolean(GOOGLE_CLIENT_ID) || import.meta.env.DEV;

export default function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [enviando, setEnviando] = useState(false);
  const { login, loginGoogle } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  // Codigo de invitacion o Codigo Unico de Comunidad (viene en el link del correo).
  const [codigo, setCodigo] = useState(() => searchParams.get('codigo') || '');
  // A donde volver despues de entrar: los avisos de WhatsApp llegan con ?next=/m/12
  // Solo se aceptan rutas internas, para que un link externo no pueda redirigir fuera.
  const solicitado = searchParams.get('next') || '';
  const destino = solicitado.startsWith('/') && !solicitado.startsWith('//') ? solicitado : '/app';
  // Sin Google, la invitacion se acepta creando usuario y contrasena en su
  // propia pagina. Los correos viejos traian /login?codigo=..., asi que se
  // redirigen alla.
  const [verCodigo, setVerCodigo] = useState(false);
  useEffect(() => {
    const delEnlace = searchParams.get('codigo');
    if (!CON_GOOGLE && delEnlace) navigate(`/invitacion/${encodeURIComponent(delEnlace)}`, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const irAInvitacion = () => {
    const limpio = codigo.trim();
    if (limpio) navigate(`/invitacion/${encodeURIComponent(limpio)}`);
  };
  const codigoRef = useRef(codigo);
  codigoRef.current = codigo;
  const botonGoogleRef = useRef(null);

  const entrarConCredencial = async (credential) => {
    setError('');
    setEnviando(true);
    try {
      await loginGoogle(credential, codigoRef.current.trim());
      navigate(destino);
    } catch (err) {
      setError(err.response?.data?.detail || 'No se pudo iniciar sesion con Google.');
    } finally {
      setEnviando(false);
    }
  };

  // Google Identity Services: solo si hay CLIENT_ID configurado.
  useEffect(() => {
    if (!GOOGLE_CLIENT_ID) return undefined;
    const script = document.createElement('script');
    script.src = 'https://accounts.google.com/gsi/client';
    script.async = true;
    script.onload = () => {
      if (!window.google || !botonGoogleRef.current) return;
      window.google.accounts.id.initialize({
        client_id: GOOGLE_CLIENT_ID,
        callback: (resp) => entrarConCredencial(resp.credential),
      });
      window.google.accounts.id.renderButton(botonGoogleRef.current, {
        theme: 'outline', size: 'large', width: 320, text: 'continue_with',
      });
    };
    document.head.appendChild(script);
    return () => { document.head.removeChild(script); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Modo simulado (sin CLIENT_ID): pide el correo y usa la credencial mock del backend.
  const googleSimulado = async () => {
    const correo = window.prompt('Modo prueba - correo de Google:');
    if (!correo) return;
    await entrarConCredencial(`mock:${correo.trim()}`);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setEnviando(true);
    try {
      await login(username, password);
      navigate(destino);
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
          <Marca size={34} />
        </Link>
        <div className="marca-claim">
          <h2><strong>SINCONFLICTO</strong> proceso, sin atajos.</h2>
          <p>
            Cada multa recorre el circuito que exige la Ley 21.442: evidencia del
            denunciante, aprobacion exclusiva del Comite, notificacion formal del
            Administrador y derecho a descargo del residente. El sistema bloquea
            cualquier accion fuera de rol.
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
          <h2>Convivencia con <strong>respaldo</strong>.</h2>
          <p>Reclamos, multas y notificaciones de tu comunidad, con cada paso a la vista.</p>
        </div>
      </div>

      <div className="login-panel-form">
        <form className="login-tarjeta" onSubmit={handleSubmit}>
          <div>
            <h1>Iniciar sesion</h1>
            <p className="texto-secundario">
              {CON_GOOGLE ? 'Entra con Google o con tu cuenta del condominio.' : 'Entra con tu cuenta del condominio.'}
            </p>
          </div>

          {CON_GOOGLE && (
            <>
              <label>
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                  <KeyRound size={13} /> Codigo de invitacion o comunidad (opcional)
                </span>
                <input
                  value={codigo}
                  onChange={(e) => setCodigo(e.target.value)}
                  placeholder="Solo la primera vez, si te lo compartieron"
                />
              </label>

              {GOOGLE_CLIENT_ID ? (
                <div ref={botonGoogleRef} style={{ display: 'flex', justifyContent: 'center' }} />
              ) : (
                <button type="button" className="btn btn-secundario" onClick={googleSimulado} disabled={enviando}>
                  Continuar con Google (modo prueba)
                </button>
              )}

              <div className="login-separador">o con usuario y contrasena</div>
            </>
          )}

          <label>
            Usuario
            <input value={username} onChange={(e) => setUsername(e.target.value)} required />
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
          {!CON_GOOGLE && (verCodigo ? (
            <div className="login-invitacion">
              <label>
                Codigo de invitacion (viene en el correo)
                <input
                  value={codigo} onChange={(e) => setCodigo(e.target.value)} autoCapitalize="none"
                  onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); irAInvitacion(); } }}
                />
              </label>
              <button type="button" className="btn btn-secundario" onClick={irAInvitacion}>
                Crear mi cuenta
              </button>
            </div>
          ) : (
            <button type="button" className="btn btn-fantasma" onClick={() => setVerCodigo(true)}>
              <KeyRound size={15} /> ¿Te invitaron? Crea tu cuenta con el codigo
            </button>
          ))}
          <p className="texto-secundario" style={{ textAlign: 'center', fontSize: '0.85rem' }}>
            <Link to="/privacidad">Politica de privacidad</Link>
          </p>
        </form>
      </div>
    </div>
  );
}
