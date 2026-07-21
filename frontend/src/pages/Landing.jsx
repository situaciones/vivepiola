import { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowRight, Bell, Camera, CheckCircle2, FileText, Gavel, Lock, MapPin,
  MessageSquareText, ScrollText, ShieldCheck, Users, Wallet,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import './Landing.css';

const EXIGENCIAS = [
  'Separacion de roles por ley',
  'Libro de Novedades (20 dias)',
  'Notificacion con valor legal',
  'Derecho a descargo',
];

const PASOS = [
  {
    icon: Camera,
    n: '1',
    titulo: 'El conserje reporta',
    texto: 'Ve una infraccion al reglamento —ruido, mascota suelta, daño— y la registra con una foto. Queda con la hora y el lugar. El no decide nada.',
  },
  {
    icon: Gavel,
    n: '2',
    titulo: 'El comite decide',
    texto: 'El comite revisa la evidencia y aplica la multa que dice el reglamento. Nadie mas puede hacerlo. Asi lo manda la ley.',
  },
  {
    icon: Lock,
    n: '3',
    titulo: 'Queda todo respaldado',
    texto: 'Se notifica al copropietario por correo con valor legal y queda guardado y sellado, listo para la asamblea o donde haga falta.',
  },
];

const DOLORES = [
  {
    icon: Gavel,
    titulo: '¿Se te caen las multas en la asamblea?',
    texto: 'El copropietario reclama que no le avisaron o que la multa es injusta, y sin respaldo el comite tiene que dar pie atras.',
  },
  {
    icon: Users,
    titulo: '¿El comite tiene miedo de quedar pegado?',
    texto: 'Son vecinos voluntarios. Si una sancion esta mal hecha, la responsabilidad les puede caer encima a ellos.',
  },
  {
    icon: FileText,
    titulo: '¿Todo queda en un cuaderno que se pierde?',
    texto: 'El conserje anota en una libreta, los avisos se hacen por WhatsApp, y a la hora de un problema no hay nada firme que mostrar.',
  },
];

const BENEFICIOS = [
  {
    icon: Lock,
    titulo: 'Nadie puede borrar ni cambiar nada',
    texto: 'Una vez registrado, queda sellado. Ideal para respaldar al comite en la asamblea o cuando alguien reclama.',
  },
  {
    icon: MapPin,
    titulo: 'Cada foto guarda donde y cuando',
    texto: 'Nadie puede decir "esa foto no es de mi depto" o "es vieja". Queda marcada con hora y lugar.',
  },
  {
    icon: Bell,
    titulo: 'El Libro de Novedades al dia',
    texto: 'La ley te da 20 dias corridos para responder los reclamos. El sistema te avisa antes de que se te pase el plazo.',
  },
  {
    icon: FileText,
    titulo: 'Un informe listo para la asamblea',
    texto: 'Con un clic bajas todo el expediente ordenado y sellado. Se acabo llegar a la asamblea con las manos vacias.',
  },
];

const MODULOS = [
  {
    icon: ScrollText,
    titulo: 'Multas del reglamento',
    texto: 'Carga las infracciones de tu reglamento —la IA te ayuda a leer el PDF— y el comite las aplica en un par de clics, con la redaccion exacta.',
  },
  {
    icon: MessageSquareText,
    titulo: 'Libro de Novedades digital',
    texto: 'Los copropietarios dejan sus reclamos y solicitudes. Tu respondes dentro del plazo legal, sin que se te pase ninguno.',
  },
  {
    icon: Wallet,
    titulo: 'Gastos comunes',
    texto: 'Las multas firmes se suman solas al aviso de cobro del mes. Sin planillas ni calculos a mano.',
  },
  {
    icon: Users,
    titulo: 'Cada uno en su rol',
    texto: 'Conserje, comite y administracion: cada uno con su acceso y su funcion, tal como exige la Ley 21.442.',
  },
];

function Icono({ Icon }) {
  return <Icon size={22} strokeWidth={1.9} />;
}

export default function Landing() {
  const { usuario } = useAuth();
  const rutaApp = usuario ? '/app' : '/login';
  const [form, setForm] = useState({ nombre: '', correo: '', empresa: '' });
  const [enviado, setEnviado] = useState(false);

  const enviarLead = (e) => {
    e.preventDefault();
    setEnviado(true);
  };

  return (
    <div className="landing landing-enterprise">
      <nav className="landing-nav">
        <div className="landing-nav-inner">
          <Link to="/" className="landing-nav-marca">
            <span className="logo-mark"><ShieldCheck size={16} strokeWidth={2.4} /></span>
            VIVEPIOLA
          </Link>
          <div className="landing-nav-links">
            <a href="#pasos">Como funciona</a>
            <a href="#modulos">Para tu administracion</a>
            <a href="#demo">Contacto</a>
          </div>
          <a href="#demo" className="landing-nav-cta">Quiero una demo</a>
        </div>
      </nav>

      {/* ---------- 1. Hero ---------- */}
      <header className="ent-hero">
        <div className="ent-hero-grid">
          <div className="ent-hero-texto">
            <span className="ent-kicker">Cumple la Ley 21.442 sin dolores de cabeza</span>
            <h1>Nadie es juez y parte.</h1>
            <p className="ent-lead">
              En tu condominio la ley es clara: el conserje reporta, el comite aplica la multa
              y la administracion notifica y cobra. VIVEPIOLA hace que se cumpla ese orden paso a
              paso y guarda todo con foto, fecha y hora. Asi ninguna multa se te cae en la
              asamblea y el comite duerme tranquilo.
            </p>
            <div className="ent-hero-ctas">
              <a href="#demo" className="landing-btn landing-btn-accion">
                Quiero verlo funcionando <ArrowRight size={16} />
              </a>
              <Link to={rutaApp} className="landing-btn landing-btn-secundario">Entrar a la plataforma</Link>
            </div>
          </div>

          <div className="ent-hero-visual" aria-hidden="true">
            <div className="cert">
              <div className="cert-sello">
                <Lock size={16} strokeWidth={2.2} />
                Sellado · no se puede alterar
              </div>
              <div className="cert-titulo">Registro de la multa</div>
              <div className="cert-sub">Depto 302 · Ruidos molestos</div>
              <ol className="cert-cadena">
                {[
                  ['Reportado', 'Conserje · con foto'],
                  ['Aprobado', 'Comite de Administracion'],
                  ['Notificado', 'Al copropietario, por correo'],
                  ['Firme', 'Va a gastos comunes'],
                ].map(([a, b], i) => (
                  <li key={a} className={i < 3 ? 'ok' : 'actual'}>
                    <span className="cert-check"><CheckCircle2 size={13} /></span>
                    <span><strong>{a}</strong><em>{b}</em></span>
                  </li>
                ))}
              </ol>
              <div className="cert-hash"><Lock size={11} /> Guardado para siempre · listo para la asamblea</div>
            </div>
          </div>
        </div>

        {/* ---------- 2. Franja: lo que exige la ley ---------- */}
        <div className="ent-trust">
          <span className="ent-trust-label">Todo lo que la Ley 21.442 te exige, cubierto:</span>
          <div className="ent-trust-logos">
            {EXIGENCIAS.map((c) => (
              <span key={c} className="ent-trust-item"><CheckCircle2 size={13} /> {c}</span>
            ))}
          </div>
        </div>
      </header>

      {/* ---------- 3. Como funciona en 3 pasos ---------- */}
      <section id="pasos" className="ent-seccion">
        <div className="landing-container">
          <div className="ent-seccion-head">
            <p className="ent-kicker-oscuro">Asi de simple</p>
            <h2>Tres pasos, y cada quien en lo suyo.</h2>
          </div>
          <div className="ent-pasos">
            {PASOS.map((p, i) => (
              <div key={p.n} className="ent-paso">
                <div className="ent-paso-num">{p.n}</div>
                <span className="ent-paso-icono"><Icono Icon={p.icon} /></span>
                <h3>{p.titulo}</h3>
                <p>{p.texto}</p>
                {i < PASOS.length - 1 && <span className="ent-paso-flecha"><ArrowRight size={20} /></span>}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ---------- 4. Dolor ---------- */}
      <section className="ent-seccion ent-seccion-gris">
        <div className="landing-container">
          <div className="ent-seccion-head">
            <p className="ent-kicker-oscuro">Lo que pasa hoy</p>
            <h2>Cuando una sola persona hace todo, la multa se cae.</h2>
          </div>
          <div className="ent-cols">
            {DOLORES.map((d) => (
              <div key={d.titulo} className="ent-col ent-col-dolor">
                <span className="ent-col-icono"><Icono Icon={d.icon} /></span>
                <h3>{d.titulo}</h3>
                <p>{d.texto}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ---------- 5. Beneficios ---------- */}
      <section id="solucion" className="ent-seccion ent-seccion-oscura">
        <div className="landing-container">
          <div className="ent-seccion-head">
            <p className="ent-kicker">Lo que ganas</p>
            <h2>La prueba siempre esta de tu lado.</h2>
            <p className="ent-seccion-sub">
              No te pedimos que confies en nuestra palabra. Cualquiera puede revisar que nada
              fue alterado, aunque hayan pasado años. El respaldo perfecto para el comite.
            </p>
          </div>
          <div className="ent-cols ent-cols-2">
            {BENEFICIOS.map((s) => (
              <div key={s.titulo} className="ent-col ent-col-solucion">
                <span className="ent-col-icono tech"><Icono Icon={s.icon} /></span>
                <div>
                  <h3>{s.titulo}</h3>
                  <p>{s.texto}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ---------- 6. Todo para tu administracion ---------- */}
      <section id="modulos" className="ent-seccion">
        <div className="landing-container">
          <div className="ent-seccion-head">
            <p className="ent-kicker-oscuro">Para tu administracion</p>
            <h2>Todo lo que necesita tu comunidad, en un solo lugar.</h2>
            <p className="ent-seccion-sub">
              No es solo multas: es la gestion completa de la convivencia, hecha para
              administradores y comites de verdad, no para expertos en sistemas.
            </p>
          </div>
          <div className="ent-cols ent-cols-2">
            {MODULOS.map((m) => (
              <div key={m.titulo} className="ent-col ent-col-solucion">
                <span className="ent-col-icono modulo"><Icono Icon={m.icon} /></span>
                <div>
                  <h3>{m.titulo}</h3>
                  <p>{m.texto}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ---------- 7. Cierre + captura ---------- */}
      <section id="demo" className="ent-cierre">
        <div className="ent-cierre-inner">
          <div className="ent-cierre-texto">
            <ShieldCheck size={30} className="ent-cierre-icono" strokeWidth={1.8} />
            <h2>Que tu comite y tu administracion duerman tranquilos.</h2>
            <p>
              Agenda una demo de 20 minutos. Te mostramos con las multas y los reclamos de tu
              propio condominio como dejar todo en orden y a prueba de reclamos. Sin compromiso.
            </p>
            <ul className="ent-cierre-bullets">
              <li><CheckCircle2 size={15} /> Al dia con la Ley 21.442, sin abogados de por medio</li>
              <li><CheckCircle2 size={15} /> Te acompañamos en la puesta en marcha</li>
              <li><CheckCircle2 size={15} /> No tienes que cambiar como trabaja tu conserje hoy</li>
            </ul>
          </div>

          <div className="ent-form-card">
            {enviado ? (
              <div className="ent-form-ok">
                <ShieldCheck size={40} strokeWidth={1.8} />
                <h3>Listo, recibimos tus datos</h3>
                <p>Te contactamos para coordinar tu demo de 20 minutos.</p>
              </div>
            ) : (
              <form onSubmit={enviarLead}>
                <h3>Agenda tu reunion</h3>
                <label>
                  Nombre
                  <input required value={form.nombre} onChange={(e) => setForm({ ...form, nombre: e.target.value })} />
                </label>
                <label>
                  Correo
                  <input type="email" required value={form.correo} onChange={(e) => setForm({ ...form, correo: e.target.value })} />
                </label>
                <label>
                  Condominio o administradora
                  <input required value={form.empresa} onChange={(e) => setForm({ ...form, empresa: e.target.value })} />
                </label>
                <button type="submit" className="landing-btn landing-btn-accion" style={{ width: '100%', justifyContent: 'center' }}>
                  Agendar reunion <ArrowRight size={16} />
                </button>
                <p className="ent-form-nota">Te respondemos en menos de un dia. Cero spam.</p>
              </form>
            )}
          </div>
        </div>
      </section>

      <footer className="ent-footer">
        <div className="ent-footer-inner">
          <span className="landing-footer-marca">
            <span className="logo-mark"><ShieldCheck size={14} strokeWidth={2.4} /></span>
            VIVEPIOLA
          </span>
          <span>© 2026 VIVEPIOLA · Al dia con la Ley 21.442</span>
          <Link to="/login">Entrar a la plataforma</Link>
        </div>
      </footer>
    </div>
  );
}
