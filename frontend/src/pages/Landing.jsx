import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  AlertTriangle, ArrowRight, Bell, Camera, Check, CheckCircle2, FileText, Gavel,
  LayoutGrid, Lock, Mail, MapPin, MessageSquareText, ScrollText, ShieldCheck,
  Users, Wallet, X, Zap,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import './Landing.css';

const EXIGENCIAS = [
  'Separacion de roles',
  'Libro de Novedades (20 dias)',
  'Notificacion con valor legal',
  'Derecho a descargo',
];

const ROLES = [
  { cls: 'r1', Icon: Camera, nombre: 'Conserje', limite: 'No fija multas', LimIcon: X,
    texto: 'Reporta lo que ve —ruidos, mascotas, daños— con foto. Solo registra el hecho tal como paso.' },
  { cls: 'r2', Icon: Gavel, nombre: 'Comite', limite: 'Unico que sanciona', LimIcon: Check,
    texto: 'Revisa la evidencia y aplica la multa segun el reglamento, con su monto exacto. El punto de decision.' },
  { cls: 'r3', Icon: Mail, nombre: 'Administracion', limite: 'Ejecuta, no decide', LimIcon: X,
    texto: 'Notifica al dueño, registra si objeta y, cuando la multa es firme, la suma a los gastos comunes.' },
  { cls: 'r4', Icon: Users, nombre: 'Residente', limite: 'Derecho a defensa', LimIcon: Check,
    texto: 'Recibe la notificacion y puede presentar su descargo en 5 dias. Si no esta de acuerdo, va a la asamblea.' },
];

const BENEFICIOS = [
  { Icon: Lock, titulo: 'Nadie puede alterar nada',
    texto: 'Una vez registrado, queda sellado. El respaldo perfecto para el comite en la asamblea.' },
  { Icon: MapPin, titulo: 'Cada foto guarda donde y cuando',
    texto: 'Nadie puede decir "esa foto no es de mi depto" o "es vieja". Queda marcada con hora y lugar.' },
  { Icon: Bell, titulo: 'El Libro de Novedades al dia',
    texto: 'La ley te da 20 dias para responder. El sistema te avisa antes de que se te pase el plazo.' },
  { Icon: FileText, titulo: 'Un informe listo para la asamblea',
    texto: 'Con un clic bajas el expediente ordenado y sellado. Se acabo llegar con las manos vacias.' },
];

const SALVAGUARDAS = [
  { Icon: CheckCircle2, titulo: 'Bloquea las multas inventadas',
    texto: 'Si el hecho nunca se reporto, o el comite intenta aprobar algo que no esta en el reglamento, el sistema lo detiene. No se sanciona a dedo.' },
  { Icon: AlertTriangle, titulo: 'Sin correo, no hay multa',
    texto: 'Si el dueño no tiene correo registrado, la multa queda bloqueada hasta poder notificar de verdad. La notificacion siempre es real.' },
  { Icon: Zap, titulo: 'Contencion inmediata para riesgos',
    texto: 'Ante una fuga de gas o una piscina sin vigilancia, se ordena corregir ya, sin esperar reunion. El comite ratifica despues.' },
  { Icon: ShieldCheck, titulo: 'El comite queda protegido',
    texto: 'Son vecinos voluntarios, no abogados. Cada decision queda documentada: si hay conflicto, la evidencia los respalda.' },
];

const MODULOS = [
  { Icon: ScrollText, titulo: 'Multas del reglamento',
    texto: 'La IA lee tu reglamento en PDF y el comite aplica las infracciones en un par de clics, con la redaccion exacta.' },
  { Icon: MessageSquareText, titulo: 'Libro de Novedades digital',
    texto: 'Los copropietarios dejan reclamos y solicitudes. Respondes dentro del plazo legal, sin que se te pase ninguno.' },
  { Icon: Wallet, titulo: 'Gastos comunes',
    texto: 'Las multas firmes se suman solas al aviso de cobro del mes. Sin planillas ni calculos a mano.' },
  { Icon: Users, titulo: 'Cada uno en su rol',
    texto: 'Conserje, comite y administracion: cada uno con su acceso y su funcion, tal como exige la Ley 21.442.' },
];

function nz(x, y) {
  const n = Math.sin(x * 127.1 + y * 311.7) * 43758.5453;
  return n - Math.floor(n);
}

function drawTerrain(canvas) {
  const ctx = canvas.getContext('2d');
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const W = canvas.clientWidth;
  const H = canvas.clientHeight;
  if (!W || !H) return;
  canvas.width = W * dpr;
  canvas.height = H * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, W, H);
  const cols = Math.max(26, Math.floor(W / 26));
  const rows = 13;
  const horizon = H * 0.18;
  const pts = [];
  for (let j = 0; j < rows; j++) {
    const row = [];
    const persp = j / (rows - 1);
    const yBase = horizon + persp * persp * (H - horizon);
    for (let i = 0; i <= cols; i++) {
      const t = i / cols;
      let h = Math.sin(t * 6.283 * 1.6 + 0.6) * 0.5 + Math.sin(t * 6.283 * 3.2 + 1.3) * 0.26 + Math.sin(t * 6.283 * 0.7) * 0.42;
      h += (nz(i, j) * 2 - 1) * 0.42;
      const shape = Math.abs(Math.cos(t * Math.PI));
      h = h * 0.5 + shape * 1.25;
      const amp = 64 * (0.22 + persp);
      row.push({ x: t * W, y: yBase - h * amp, h, p: persp });
    }
    pts.push(row);
  }
  for (let j = 0; j < rows; j++) {
    for (let i = 0; i <= cols; i++) {
      const pt = pts[j][i];
      const b = Math.min(1, 0.12 + pt.h * 0.42) * (0.28 + 0.72 * pt.p);
      if (i < cols) {
        const q = pts[j][i + 1];
        ctx.strokeStyle = `rgba(90,236,222,${0.05 + b * 0.30})`;
        ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(pt.x, pt.y); ctx.lineTo(q.x, q.y); ctx.stroke();
      }
      if (j < rows - 1) {
        const q2 = pts[j + 1][i];
        ctx.strokeStyle = `rgba(66,206,200,${0.04 + b * 0.18})`;
        ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(pt.x, pt.y); ctx.lineTo(q2.x, q2.y); ctx.stroke();
      }
    }
  }
}

function BrandMark({ size = 17 }) {
  return <span className="mk"><ShieldCheck size={size} strokeWidth={2.4} /></span>;
}

export default function Landing() {
  const { usuario } = useAuth();
  const rutaApp = usuario ? '/app' : '/login';
  const terrainRef = useRef(null);
  const [form, setForm] = useState({ nombre: '', correo: '', empresa: '' });
  const [enviado, setEnviado] = useState(false);

  useEffect(() => {
    const canvas = terrainRef.current;
    if (!canvas) return undefined;
    let t;
    const build = () => drawTerrain(canvas);
    build();
    const onResize = () => { clearTimeout(t); t = setTimeout(build, 120); };
    window.addEventListener('resize', onResize);
    return () => { window.removeEventListener('resize', onResize); clearTimeout(t); };
  }, []);

  const enviarLead = (e) => {
    e.preventDefault();
    setEnviado(true);
  };

  return (
    <div className="vp">
      <nav>
        <div className="nav-in">
          <Link to="/" className="brand"><BrandMark />VIVEPIOLA</Link>
          <div className="nav-links">
            <a href="#flujo">El ciclo</a>
            <a href="#roles">Roles</a>
            <a href="#salvaguardas">Salvaguardas</a>
            <a href="#modulos">Modulos</a>
          </div>
          <div className="nav-right">
            <Link to={rutaApp} className="nav-login">Entrar</Link>
            <a href="#demo" className="btn btn-cyan">Quiero una demo</a>
          </div>
        </div>
      </nav>

      {/* ---------- HERO ---------- */}
      <header className="hero">
        <div className="axis">
          <span>20d</span><span>15d</span><span>10d</span><span>5d</span><span>0</span>
        </div>
        <div className="hero-inner">
          <span className="h-eyebrow rise d1">● Cumple la Ley 21.442</span>
          <h1 className="rise d2">Nadie es <span className="hl">juez y parte.</span></h1>
          <p className="hero-lead rise d2">
            Una sola plataforma que hace cumplir el orden que manda la ley: el conserje reporta,
            el comite aplica la multa y la administracion notifica y cobra. Todo con foto, fecha y sello.
          </p>
          <div className="hero-ctas rise d3">
            <a href="#demo" className="btn btn-cyan">Quiero verlo funcionando</a>
            <a href="#flujo" className="btn btn-outline-l">Ver el ciclo de la multa</a>
          </div>
        </div>

        <div className="hero-trust rise d4">
          <div className="lbl">El respaldo legal en el que se apoyan los comites de administracion</div>
          <div className="items">
            {EXIGENCIAS.map((c) => (
              <span key={c}><Check size={15} strokeWidth={3} /> {c}</span>
            ))}
          </div>
        </div>

        <div className="stats rise d4">
          <div className="stat"><div className="n">100<em>%</em></div><div className="t">Trazable · cada paso queda sellado y verificable</div></div>
          <div className="stat"><div className="n">20<em> dias</em></div><div className="t">El plazo legal de respuesta, siempre vigilado</div></div>
          <div className="stat"><div className="n">0</div><div className="t">Multas sin respaldo que se caen en la asamblea</div></div>
        </div>
        <div className="hero-foot" />
        <canvas id="terrain" ref={terrainRef} aria-hidden="true" />
      </header>

      {/* ---------- FLUJO / MAPA ---------- */}
      <section id="flujo">
        <div className="wrap flow-grid">
          <div className="flow-copy">
            <div className="eye">El ciclo de la multa</div>
            <h2>Cada sancion, del reporte al cobro, en un solo mapa</h2>
            <p>Como un mapa de infraestructura, ves en que paso va cada multa y quien la tiene en sus manos.
              Nadie avanza sin cumplir el paso anterior.</p>
            <p>Y todo queda <strong>sellado</strong>: aunque pasen años, cualquiera puede verificar que nada fue alterado.</p>
          </div>
          <div className="map">
            <div className="map-top">
              <span className="map-title"><LayoutGrid size={15} strokeWidth={2} /> Ciclo de la multa · Depto 302</span>
              <span className="seal"><Lock size={11} strokeWidth={2.4} /> SELLADO</span>
            </div>
            <div className="map-sub">Ruidos molestos · 23:04</div>
            <div className="nodes">
              <div className="node n1">
                <span className="ico"><Camera size={19} strokeWidth={2} /></span>
                <div className="body"><b>Conserje reporta</b><small>Con foto · fecha y hora</small></div>
                <span className="pill ok">Hecho</span>
              </div>
              <div className="connector" />
              <div className="node n2">
                <span className="ico"><Gavel size={19} strokeWidth={2} /></span>
                <div className="body"><b>Comite aplica</b><small>Segun reglamento · Art. 4</small></div>
                <span className="pill ok">3 UF</span>
              </div>
              <div className="connector" />
              <div className="node n3">
                <span className="ico"><Mail size={19} strokeWidth={2} /></span>
                <div className="body"><b>Notificacion</b><small>Correo con valor legal</small></div>
                <span className="pill ok">Enviada</span>
              </div>
              <div className="connector" />
              <div className="node n5">
                <span className="ico"><MessageSquareText size={19} strokeWidth={2} /></span>
                <div className="body"><b>Descargo del dueño</b><small>5 dias para defenderse · el comite resuelve</small></div>
                <span className="pill warn">5 dias</span>
              </div>
              <div className="connector" />
              <div className="node n4">
                <span className="ico"><Wallet size={19} strokeWidth={2} /></span>
                <div className="body"><b>Firme → Gastos comunes</b><small>Se suma al cobro del mes</small></div>
                <span className="pill">En curso</span>
              </div>
            </div>
            <div className="map-foot"><Lock size={12} strokeWidth={2.2} /> Si el comite acepta el descargo, la multa se anula · todo queda sellado</div>
          </div>
        </div>
      </section>

      {/* ---------- ROLES ---------- */}
      <section id="roles" className="band">
        <div className="wrap">
          <div className="sec-head">
            <div className="sec-eye">El valor central</div>
            <h2>Nadie es juez y parte</h2>
            <p>La ley separa quien reporta, quien decide y quien cobra. Si alguien intenta saltarse un paso, el sistema lo bloquea.</p>
          </div>
          <div className="roles">
            {ROLES.map((r) => (
              <div key={r.nombre} className={`role ${r.cls}`}>
                <span className="ri"><r.Icon size={20} strokeWidth={2} /></span>
                <h3>{r.nombre}</h3>
                <p>{r.texto}</p>
                <span className="limit"><r.LimIcon size={12} strokeWidth={3} /> {r.limite}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ---------- BENEFICIOS ---------- */}
      <section>
        <div className="wrap">
          <div className="sec-head">
            <div className="sec-eye">Lo que ganas</div>
            <h2>La prueba siempre esta de tu lado</h2>
            <p>Cualquiera puede verificar que nada fue alterado, aunque hayan pasado años.</p>
          </div>
          <div className="grid2">
            {BENEFICIOS.map((b) => (
              <div key={b.titulo} className="feat">
                <span className="fi"><b.Icon size={20} strokeWidth={2} /></span>
                <div><h3>{b.titulo}</h3><p>{b.texto}</p></div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ---------- SALVAGUARDAS ---------- */}
      <section id="salvaguardas" className="band">
        <div className="wrap">
          <div className="sec-head">
            <div className="sec-eye">A prueba de reclamos</div>
            <h2>Las salvaguardas que te protegen</h2>
            <p>No basta con seguir el orden: el sistema tambien frena los abusos y cubre los casos dificiles.</p>
          </div>
          <div className="grid2">
            {SALVAGUARDAS.map((s) => (
              <div key={s.titulo} className="feat">
                <span className="fi"><s.Icon size={20} strokeWidth={2} /></span>
                <div><h3>{s.titulo}</h3><p>{s.texto}</p></div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ---------- MODULOS ---------- */}
      <section id="modulos">
        <div className="wrap">
          <div className="sec-head">
            <div className="sec-eye">Para tu administracion</div>
            <h2>Todo lo que necesita tu comunidad, en un solo lugar</h2>
          </div>
          <div className="grid2">
            {MODULOS.map((m) => (
              <div key={m.titulo} className="feat">
                <span className="fi"><m.Icon size={20} strokeWidth={2} /></span>
                <div><h3>{m.titulo}</h3><p>{m.texto}</p></div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ---------- THESIS ---------- */}
      <section className="band">
        <div className="wrap thesis">
          <div className="mk-lg"><ShieldCheck size={26} strokeWidth={2.2} /></div>
          <p className="q">
            VIVEPIOLA es un <span className="hl">guardia digital</span> que sigue cada sancion desde el
            reporte hasta el cobro, verificando que cada paso sea valido segun la ley y dejando un rastro
            que nadie puede negar.
          </p>
        </div>
      </section>

      {/* ---------- CTA ---------- */}
      <section id="demo">
        <div className="wrap">
          <div className="cta">
            <div className="cta-grid">
              <div>
                <h2>Que tu comite y tu administracion duerman tranquilos</h2>
                <p>Agenda una demo de 20 minutos. Te mostramos, con las multas de tu propio condominio,
                  como dejar todo en orden y a prueba de reclamos.</p>
                <ul>
                  <li><CheckCircle2 size={16} strokeWidth={2.6} /> Al dia con la Ley 21.442, sin abogados</li>
                  <li><CheckCircle2 size={16} strokeWidth={2.6} /> Te acompañamos en la puesta en marcha</li>
                  <li><CheckCircle2 size={16} strokeWidth={2.6} /> No cambias como trabaja tu conserje hoy</li>
                </ul>
              </div>
              <div className="form">
                {enviado ? (
                  <div className="form-ok">
                    <ShieldCheck size={40} strokeWidth={1.8} />
                    <h3>Listo, recibimos tus datos</h3>
                    <p>Te contactamos para coordinar tu demo de 20 minutos.</p>
                  </div>
                ) : (
                  <form onSubmit={enviarLead}>
                    <h3>Agenda tu reunion</h3>
                    <label>Nombre
                      <input required value={form.nombre} onChange={(e) => setForm({ ...form, nombre: e.target.value })} />
                    </label>
                    <label>Correo
                      <input type="email" required value={form.correo} onChange={(e) => setForm({ ...form, correo: e.target.value })} />
                    </label>
                    <label>Condominio o administradora
                      <input required value={form.empresa} onChange={(e) => setForm({ ...form, empresa: e.target.value })} />
                    </label>
                    <button type="submit" className="btn btn-cyan">Agendar reunion <ArrowRight size={16} /></button>
                    <p className="form-note">Te respondemos en menos de un dia. Cero spam.</p>
                  </form>
                )}
              </div>
            </div>
          </div>
        </div>
      </section>

      <footer>
        <div className="wrap foot-in">
          <span className="brand"><BrandMark size={15} />VIVEPIOLA</span>
          <span>© 2026 VIVEPIOLA · Al dia con la Ley 21.442</span>
          <Link to={rutaApp}>Entrar a la plataforma →</Link>
        </div>
      </footer>
    </div>
  );
}
