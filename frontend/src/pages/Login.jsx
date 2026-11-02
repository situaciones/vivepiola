import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { AlertCircle, Eye, EyeOff } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import Marca from '../components/Marca';
import IlustracionComunidad from '../components/IlustracionComunidad';
import DescargarApp from '../components/DescargarApp';

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || '';
// Sin CLIENT_ID solo existe el modo simulado, que el backend de produccion
// rechaza: en una version publicada no se ofrece un boton que no funciona.
const CON_GOOGLE = Boolean(GOOGLE_CLIENT_ID) || import.meta.env.DEV;

// Lo que pasa con cada caso, para quien nunca ha usado la app. Cada frase
// describe lo que el sistema hace de verdad: la IA cursa sola solo los casos
// claros, las primeras faltas se avisan sin cobro y las actas quedan selladas.
const PASOS = [
  {
    titulo: 'Se reporta con pruebas',
    texto: 'Un vecino, el conserje o la administración registra lo que pasó en la app, con foto, fecha y lugar.',
  },
  {
    titulo: 'La IA hace el trabajo pesado',
    texto: 'Lee el reporte y las fotos y los compara con tu reglamento. Los casos claros avanzan solos; los dudosos o graves pasan al Comité.',
  },
  {
    titulo: 'Primero una advertencia, nunca una sorpresa',
    texto: 'Recibes el aviso con la foto y el artículo exacto. Las primeras veces es solo una advertencia, sin cobro.',
  },
  {
    titulo: 'Tienes derecho a apelar',
    texto: 'Tu versión siempre cuenta. Apelas desde el mismo aviso y el Comité debe responderte con sus fundamentos.',
  },
  {
    titulo: 'Nadie puede cambiar la historia',
    texto: 'Cada paso queda sellado con fecha y hora. Ni la administración ni el Comité pueden borrarlo ni modificarlo.',
  },
];

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
  const [verCodigo, setVerCodigo] = useState(() => Boolean(searchParams.get('codigo')));
  const [verClave, setVerClave] = useState(false);
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
      setError('El usuario o la contraseña no coinciden. Revisa e intenta de nuevo.');
    } finally {
      setEnviando(false);
    }
  };

  return (
    <div className="pantalla-login">
      <aside className="login-panel-marca" aria-labelledby="como-funciona">
        <Link to="/" className="marca-top" style={{ textDecoration: 'none', color: 'inherit' }}>
          <Marca size={34} />
        </Link>

        <div className="marca-claim">
          <h2 id="como-funciona">En tu edificio, las reglas son iguales para todos.</h2>
          <p>Sin favoritos, sin sorpresas y sin discusiones en el pasillo. Así avanza cada caso:</p>
          <IlustracionComunidad />
          <ol className="login-flujo">
            {PASOS.map(({ titulo, texto }) => (
              <li key={titulo}><b>{titulo}</b> {texto}</li>
            ))}
          </ol>
        </div>

        <div className="marca-foot">Ley 21.442 de Copropiedad Inmobiliaria, Chile</div>
      </aside>

      <div className="login-cabecera-movil">
        <Marca size={36} />
      </div>

      <div className="login-panel-form">
        <form className="login-tarjeta" onSubmit={handleSubmit}>
          <div>
            <h1>Iniciar sesión</h1>
            <p className="texto-secundario">
              {CON_GOOGLE ? 'Con tu cuenta de Google o tu usuario.' : 'Con tu usuario y contraseña.'}
            </p>
          </div>

          {CON_GOOGLE && (
            <>
              {GOOGLE_CLIENT_ID ? (
                <div ref={botonGoogleRef} style={{ display: 'flex', justifyContent: 'center' }} />
              ) : (
                <button type="button" className="btn btn-secundario" onClick={googleSimulado} disabled={enviando}>
                  Continuar con Google (modo prueba)
                </button>
              )}

              <div className="login-separador">o con tu usuario</div>
            </>
          )}

          <label>
            Usuario
            <input
              value={username} onChange={(e) => setUsername(e.target.value)} required
              autoComplete="username" autoCapitalize="none" placeholder="Ej: maria.perez"
            />
          </label>
          <label>
            Contraseña
            <span className="login-clave">
              <input
                type={verClave ? 'text' : 'password'} value={password}
                onChange={(e) => setPassword(e.target.value)} required autoComplete="current-password"
              />
              <button
                type="button" className="login-ver-clave" onClick={() => setVerClave((v) => !v)}
                aria-label={verClave ? 'Ocultar contraseña' : 'Mostrar contraseña'}
              >
                {verClave ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </span>
          </label>

          {error && (
            <div className="mensaje-error">
              <AlertCircle size={16} />
              {error}
            </div>
          )}

          <button className="btn btn-primario" type="submit" disabled={enviando}>
            {enviando ? 'Entrando...' : 'Entrar'}
          </button>

          {verCodigo ? (
            <div className="login-invitacion">
              <label>
                Código de invitación
                <input
                  value={codigo} onChange={(e) => setCodigo(e.target.value)} autoCapitalize="none"
                  placeholder="Viene en el correo de bienvenida"
                  onKeyDown={(e) => { if (e.key === 'Enter' && !CON_GOOGLE) { e.preventDefault(); irAInvitacion(); } }}
                />
              </label>
              {CON_GOOGLE ? (
                <p className="texto-secundario login-nota">
                  Escríbelo y después continúa con Google. Se pide solo la primera vez.
                </p>
              ) : (
                <button type="button" className="btn btn-secundario" onClick={irAInvitacion}>
                  Crear mi cuenta
                </button>
              )}
            </div>
          ) : (
            <button type="button" className="login-enlace" onClick={() => setVerCodigo(true)}>
              Tengo un código de invitación
            </button>
          )}
          <DescargarApp />
          <a href="#como-funciona" className="login-ver-flujo">Cómo funciona SinConflicto</a>
          <p className="texto-secundario" style={{ textAlign: 'center', fontSize: '0.85rem' }}>
            <Link to="/privacidad">Política de privacidad</Link>
          </p>
        </form>
      </div>
    </div>
  );
}
