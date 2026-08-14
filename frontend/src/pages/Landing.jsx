import { useState } from 'react';
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
 * Cada pantalla tiene su lugar para una foto grande. Mientras no existan, el
 * degradado de marca ocupa ese lugar y la pagina se sostiene igual: se veria
 * incompleta con marcos vacios, no con color.
 */

const PANTALLAS = [
  {
    id: 'reglas',
    titulo: ['Las reglas', 'ya existen.'],
    bajada: 'Tu reglamento de copropiedad, tus actas, la ley chilena. Nada que el sistema invente.',
    imagen: 'reglamento',
  },
  {
    id: 'iguales',
    titulo: ['Iguales', 'para todos.'],
    bajada: 'La misma norma, el mismo criterio, el mismo procedimiento. Siempre.',
    imagen: 'comunidad',
  },
  {
    id: 'aviso',
    titulo: ['No toda falta', 'termina en multa.'],
    bajada: 'Las primeras veces se avisa. Sin cobro.',
    imagen: 'aviso',
    destacada: true,
  },
  {
    id: 'defensa',
    titulo: ['Notificar', 'no es enviar.'],
    bajada: 'El plazo para defenderse empieza cuando la persona confirma que recibio.',
    imagen: 'notificacion',
  },
  {
    id: 'respaldo',
    titulo: ['Si mañana preguntan', 'que paso, esta todo.'],
    bajada: 'Cada paso queda registrado y sellado.',
    imagen: 'expediente',
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
      <div className={`pantalla-imagen img-${pantalla.imagen}`} aria-hidden="true" />
    </section>
  );
}

export default function Landing() {
  const { usuario } = useAuth();
  const rutaApp = usuario ? '/app' : '/login';
  const [form, setForm] = useState({ nombre: '', correo: '', empresa: '' });
  const [enviado, setEnviado] = useState(false);

  return (
    <div className="vp vp-min">
      <nav>
        <div className="nav-in">
          <Link to="/" className="brand">
            <LogoVivePiola size={34} className="mk" />
            <span className="wordmark"><b>VIVE</b><b>PIOLA</b></span>
          </Link>
          <div className="nav-right">
            <Link to={rutaApp} className="nav-login">Entrar</Link>
            <a href="#demo" className="btn btn-cyan">Ver una demo</a>
          </div>
        </div>
      </nav>

      {/* ---------- HERO ---------- */}
      <header className="hero-min">
        <div className="hero-min-texto">
          <h1>
            Reglas claras.<br />
            <span className="acento">Menos conflictos.</span>
          </h1>
          <p>Convivencia en condominios, con el reglamento que tu comunidad ya escribio.</p>
          <a href="#demo" className="btn btn-cyan btn-grande">
            Ver una demo <ArrowRight size={18} />
          </a>
        </div>
        <div className="hero-min-imagen img-hero" aria-hidden="true" />
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
        </div>
      </section>

      {/* ---------- CTA ---------- */}
      <section id="demo" className="cierre">
        <div className="cierre-in">
          <h2>Empieza por ver<br /><span className="acento">un caso real.</span></h2>

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
