import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, CheckCircle2 } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { LogoVivePiola } from '../components/Marca';
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
  const [form, setForm] = useState({ nombre: '', correo: '', empresa: '' });
  const [enviado, setEnviado] = useState(false);

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
            <LogoVivePiola size={34} className="mk" />
            <span className="wordmark"><b>VIVE</b><b>PIOLA</b></span>
          </Link>
          <div className="nav-right">
            <Link to="/como-funciona" className="nav-login">Como funciona</Link>
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

      {/* ---------- EL PAPEL DEL SOFTWARE ---------- */}
      <section className="claridad">
        <div className="claridad-in">
          <h2>El sistema no decide.</h2>
          <p>
            Encuentra cual de tus reglas corresponde y la propone.
            Quien decide sigue siendo el comite.
          </p>
          <Link to="/como-funciona" className="ver-proceso">
            Ver el proceso completo <ArrowRight size={16} />
          </Link>
        </div>
      </section>

      {/* ---------- CTA ---------- */}
      <section id="demo" className="cierre">
        <div className="cierre-in">
          <h2>Empieza por ver<br /><span className="acento">un caso real.</span></h2>
          {/* Quien llega hasta aca todavia puede dudar de si esto es para el. */}
          <p className="cierre-quien">
            Para administradores, comites, conserjes y residentes.
            Funciona desde el celular, sin instalar nada.
          </p>

          {enviado ? (
            <div className="ok-min">
              <CheckCircle2 size={26} />
              <p>Gracias. Te escribimos a {form.correo}.</p>
            </div>
          ) : (
            <form
              className="form-min"
              onSubmit={(e) => { e.preventDefault(); setEnviado(true); }}
            >
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
              <button className="btn btn-cyan btn-grande" type="submit">Solicitar demo</button>
            </form>
          )}
        </div>
      </section>

      <footer>
        <div className="foot-min">
          <LogoVivePiola size={26} className="mk" />
          <span>Condominios de Chile · Ley 21.442</span>
        </div>
      </footer>
    </div>
  );
}
