import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, Building2, CheckCircle2, Landmark } from 'lucide-react';
import client from '../api/client';
import { useAuth } from '../context/AuthContext';
import { LogoSinConflicto } from '../components/Marca';
import './Landing.css';
import './LandingMinimal.css';

/**
 * Landing minimalista: una idea por pantalla.
 *
 * SOBRE LAS PALABRAS
 * ------------------
 * No se dice que el sistema "analiza", "evalua" o "determina": esos verbos
 * sugieren que hay un criterio propio detras, y no lo hay. El sistema
 * ENCUENTRA cual de las reglas que la comunidad ya escribio corresponde al
 * hecho, y las aplica igual para todos.
 *
 * El protagonista es la norma. El software es el mecanismo. Si alguien sale de
 * esta pagina creyendo que una maquina decide sus multas, la pagina fallo.
 *
 * SOBRE LAS IMAGENES
 * ------------------
 * Son la mitad del diseño, asi que van como <img> y no como fondo CSS: asi
 * llevan alt, el navegador puede postergar las que estan mas abajo, y las
 * medidas declaradas evitan que el texto salte cuando cargan.
 */

// Fichas de la app en las tiendas. La de Play sale del applicationId
// (cl.sinconflicto.app); la de App Store la asigna Apple al crear la app en
// App Store Connect: hay que reemplazar el id cuando exista.
const TIENDAS = {
  android: 'https://play.google.com/store/apps/details?id=cl.sinconflicto.app',
  iphone: 'https://apps.apple.com/cl/app/sinconflicto/id0000000000',
};

const PANTALLAS = [
  {
    id: 'reglas',
    titulo: ['Las reglas', 'ya existen.'],
    bajada: 'Tu reglamento de copropiedad, tus actas, la ley chilena. Nada que el sistema invente.',
    imagen: 'reglamento',
    alt: 'Un reglamento de copropiedad impreso, abierto sobre una superficie oscura.',
  },
  {
    id: 'iguales',
    titulo: ['Iguales', 'para todos.'],
    bajada: 'La misma norma, el mismo criterio, el mismo procedimiento. Siempre.',
    imagen: 'comunidad',
    alt: 'Fachada de un edificio de noche, con balcones identicos repetidos en una grilla.',
  },
  {
    id: 'aviso',
    titulo: ['No toda falta', 'termina en multa.'],
    bajada: 'Las primeras veces se avisa. Sin cobro.',
    imagen: 'aviso',
    alt: 'Un edificio a oscuras con una sola ventana encendida de luz calida.',
    destacada: true,
  },
  {
    id: 'defensa',
    titulo: ['Notificar', 'no es enviar.'],
    bajada: 'El plazo para defenderse empieza cuando la persona confirma que recibio.',
    imagen: 'notificacion',
    alt: 'Una mano sostiene un telefono encendido en el pasillo de un edificio.',
  },
  {
    id: 'respaldo',
    titulo: ['Si mañana preguntan', 'que paso, esta todo.'],
    bajada: 'Cada paso queda registrado y sellado.',
    imagen: 'expediente',
    alt: 'Carpetas de archivo apiladas en la oscuridad, con los cantos iluminados.',
  },
];

function LogoApple() {
  return (
    <svg viewBox="0 0 24 24" width="26" height="26" aria-hidden="true" fill="currentColor">
      <path d="M16.37 12.6c-.02-2.3 1.88-3.4 1.96-3.46-1.07-1.56-2.73-1.78-3.32-1.8-1.41-.14-2.76.83-3.47.83-.72 0-1.82-.81-2.99-.79-1.54.02-2.96.9-3.75 2.27-1.6 2.78-.41 6.88 1.15 9.13.76 1.1 1.67 2.34 2.86 2.3 1.15-.05 1.58-.74 2.97-.74 1.38 0 1.77.74 2.98.72 1.23-.02 2.01-1.12 2.76-2.23.87-1.28 1.23-2.52 1.25-2.58-.03-.01-2.39-.92-2.4-3.65zM14.1 5.86c.63-.77 1.06-1.83.94-2.89-.91.04-2.01.61-2.67 1.37-.58.67-1.1 1.76-.96 2.8 1.02.08 2.05-.52 2.69-1.28z" />
    </svg>
  );
}

function LogoPlay() {
  return (
    <svg viewBox="0 0 24 24" width="24" height="24" aria-hidden="true">
      <path d="M4.2 2.5 13.6 12l-9.4 9.5c-.3-.2-.5-.6-.5-1.1V3.6c0-.5.2-.9.5-1.1z" fill="#00d7fe" />
      <path d="M16.8 8.8 13.6 12 4.2 2.5c.3-.2.8-.2 1.2 0l11.4 6.3z" fill="#00f076" />
      <path d="M16.8 15.2 5.4 21.5c-.4.2-.9.2-1.2 0l9.4-9.5 3.2 3.2z" fill="#ff3a44" />
      <path d="M20.6 12c0 .5-.3.9-.7 1.1l-3.1 2.1-3.2-3.2 3.2-3.2 3.1 2.1c.4.2.7.6.7 1.1z" fill="#ffd400" />
    </svg>
  );
}

/**
 * Una pantalla completa: titulo grande, una linea, una imagen.
 *
 * La aparicion al hacer scroll la resuelve el CSS con animation-timeline.
 * Se probo antes con IntersectionObserver y el navegador no entregaba nunca
 * la primera notificacion, asi que las cinco pantallas quedaban en opacity:0
 * para siempre. Que el contenido de la pagina dependa de que una animacion
 * arranque es un mal negocio: si falla, no se ve nada. Donde el CSS no
 * soporta el efecto, el texto simplemente esta ahi.
 */
function Pantalla({ pantalla, invertida }) {
  return (
    <section
      id={pantalla.id}
      className={[
        'pantalla',
        invertida ? 'invertida' : '',
        pantalla.destacada ? 'pantalla-clave' : '',
      ].join(' ').trim()}
    >
      <div className="pantalla-texto">
        <h2>
          {pantalla.titulo[0]}<br />
          <span className="acento">{pantalla.titulo[1]}</span>
        </h2>
        <p>{pantalla.bajada}</p>
      </div>
      <div className={`pantalla-imagen tono-${pantalla.imagen}`}>
        <img
          src={`/img/${pantalla.imagen}.webp`}
          alt={pantalla.alt}
          width={1100}
          height={1100}
          loading="lazy"
          decoding="async"
        />
      </div>
    </section>
  );
}

export default function Landing() {
  const { usuario } = useAuth();
  const rutaApp = usuario ? '/app' : '/login';
  const [form, setForm] = useState({ nombre: '', correo: '', empresa: '', sitio_web: '' });
  const [enviado, setEnviado] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState('');

  // Antes el boton solo mostraba "Gracias" y la solicitud se perdia: nadie
  // se enteraba de que alguien habia pedido una demo.
  const solicitarDemo = async (e) => {
    e.preventDefault();
    setEnviando(true);
    setError('');
    try {
      await client.post('/contacto/demo/', form);
      setEnviado(true);
    } catch (err) {
      setError(
        err.response?.status === 429
          ? 'Ya recibimos varias solicitudes desde aquí. Escríbenos a sinconflicto.cl@gmail.com.'
          : 'No se pudo enviar. Revisa tu conexión e intenta de nuevo.',
      );
    } finally {
      setEnviando(false);
    }
  };

  // Al llegar desde otra pagina con /#demo, el router monta la landing pero no
  // baja: sin esto el boton "Solicitar una demo" de Como funciona dejaba a la
  // persona arriba de todo, buscando el formulario que le prometieron.
  useEffect(() => {
    const destino = window.location.hash && document.querySelector(window.location.hash);
    if (destino) destino.scrollIntoView({ block: 'start' });
  }, []);

  return (
    <div className="vp vp-min">
      <nav>
        <div className="nav-in">
          <Link to="/" className="brand">
            <LogoSinConflicto size={34} className="mk" />
            <span className="wordmark"><b>SIN</b><b>CONFLICTO</b></span>
          </Link>
          <div className="nav-right">
            {/* En el celular no caben todos: quedan Entrar y la demo, y "La app"
                se encuentra bajando. */}
            <Link to="/como-funciona" className="nav-login nav-opcional">Como funciona</Link>
            <a href="#app" className="nav-login nav-opcional">La app</a>
            <Link to={rutaApp} className="nav-login">Entrar</Link>
            <a href="#demo" className="btn btn-cyan">Ver una demo</a>
          </div>
        </div>
      </nav>

      {/* ---------- HERO ---------- */}
      <header className="hero-min">
        <div className="hero-min-texto">
          {/* Lo primero que se lee tiene que ser la categoria. La marca todavia
              no le dice nada a nadie, y sin esto "Reglas claras" podria ser un
              estudio de abogados, una mediadora o un chat de vecinos. */}
          {/* Cabe en una linea a 375px. Con "· Condominios de Chile" no cabia
              y partia dejando "Chile" solo en la segunda linea. Que es de
              Chile lo dicen el pie, el titulo de la pagina y la ley citada. */}
          <span className="hero-et">Convivencia y multas en condominios</span>

          <h1>
            Reglas claras.<br />
            <span className="acento">Menos conflictos.</span>
          </h1>

          {/* La frase que faltaba: cuatro verbos y se entiende que hace. */}
          <p className="hero-que">
            Recibe los reclamos de tu comunidad, busca en tu reglamento la regla
            que corresponde, notifica al responsable y deja constancia de todo.
          </p>

          <ol className="hero-flujo">
            <li>Alguien reporta</li>
            <li>Aparece la regla</li>
            <li>Se notifica</li>
            <li>Queda escrito</li>
          </ol>

          <a href="#demo" className="btn btn-cyan btn-grande">
            Ver una demo <ArrowRight size={18} />
          </a>
        </div>
        {/* La unica que carga de inmediato: es lo primero que se ve. */}
        <div className="hero-min-imagen tono-hero">
          <img
            src="/img/hero.webp"
            alt="Condominio residencial al anochecer, con sus patios iluminados."
            width={1100}
            height={1298}
            fetchPriority="high"
            decoding="async"
          />
        </div>
      </header>

      {/* ---------- UNA IDEA POR PANTALLA ---------- */}
      {PANTALLAS.map((p, i) => (
        <Pantalla key={p.id} pantalla={p} invertida={i % 2 === 1} />
      ))}

      {/* ---------- EL PAPEL DEL SOFTWARE ----------
          Quien acaba de leer que el sistema no decide es justo quien quiere
          saber en que se apoya. Por eso las dos fuentes van aqui y no en otra
          seccion: la afirmacion y su respaldo, juntos. */}
      <section className="claridad">
        <div className="claridad-in">
          <h2>El sistema no decide.</h2>
          <p>
            Propone. Y todo lo que propone sale de un texto que ya existe,
            citado con su articulo.
          </p>

          <div className="fuentes">
            <div className="fuente">
              <Landmark size={22} />
              <span className="fuente-et">Lo cargamos nosotros</span>
              <p>
                La normativa vigente de Chile, que mantiene al dia nuestro
                equipo legal.
              </p>
            </div>
            <div className="fuente">
              <Building2 size={22} />
              <span className="fuente-et">Lo sube tu comunidad</span>
              <p>
                Reglamento de copropiedad, reglamento interno y actas de
                asamblea.
              </p>
            </div>
          </div>

          <p className="claridad-cierre">Quien decide sigue siendo el comite.</p>

          <Link to="/como-funciona" className="ver-proceso">
            Ver el proceso completo <ArrowRight size={16} />
          </Link>
        </div>
      </section>

      {/* ---------- LA APP ----------
          Despues de entender que hace y antes de pedir la demo: quien ya esta
          convencido busca donde bajarla. */}
      <section id="app" className="descarga">
        <div className="descarga-in">
          <h2>Lleva tu comunidad<br /><span className="acento">en el bolsillo.</span></h2>
          <p>
            Reporta, revisa y responde desde el celular. Con aviso cuando algo
            te necesita.
          </p>
          <div className="tiendas">
            <a className="tienda" href={TIENDAS.android} target="_blank" rel="noopener noreferrer">
              <LogoPlay />
              <span><small>Disponible en</small>Google Play</span>
            </a>
            <a className="tienda" href={TIENDAS.iphone} target="_blank" rel="noopener noreferrer">
              <LogoApple />
              <span><small>Descárgala en</small>App Store</span>
            </a>
          </div>
          <p className="descarga-nota">Android y iPhone. También funciona desde el navegador.</p>
        </div>
      </section>

      {/* ---------- CTA ---------- */}
      <section id="demo" className="cierre">
        <div className="cierre-in">
          <h2>Empieza por ver<br /><span className="acento">un caso real.</span></h2>
          {/* Quien llega hasta aca todavia puede dudar de si esto es para el. */}
          <p className="cierre-quien">
            Para administradores, comites, denunciantes y residentes.
            Funciona desde el celular, sin instalar nada.
          </p>

          {enviado ? (
            <div className="ok-min">
              <CheckCircle2 size={26} />
              <p>Gracias. Te escribimos a {form.correo}.</p>
            </div>
          ) : (
            <form className="form-min" onSubmit={solicitarDemo}>
              <input
                required placeholder="Tu nombre" value={form.nombre}
                onChange={(e) => setForm({ ...form, nombre: e.target.value })}
              />
              <input
                required type="email" placeholder="Correo" value={form.correo}
                onChange={(e) => setForm({ ...form, correo: e.target.value })}
              />
              <input
                placeholder="Condominio o administradora" value={form.empresa}
                onChange={(e) => setForm({ ...form, empresa: e.target.value })}
              />
              {/* Trampa para robots: una persona no la ve ni la llena. */}
              <input
                className="campo-trampa" tabIndex={-1} autoComplete="off" aria-hidden="true"
                name="sitio_web" value={form.sitio_web}
                onChange={(e) => setForm({ ...form, sitio_web: e.target.value })}
              />
              {error && <p className="form-min-error" role="alert">{error}</p>}
              <button className="btn btn-cyan btn-grande" type="submit" disabled={enviando}>
                {enviando ? 'Enviando...' : 'Solicitar demo'}
              </button>
            </form>
          )}
        </div>
      </section>

      <footer>
        <div className="foot-min">
          <LogoSinConflicto size={26} className="mk" />
          <span>Condominios de Chile · Ley 21.442</span>
          <Link to="/privacidad">Privacidad</Link>
        </div>
      </footer>
    </div>
  );
}
