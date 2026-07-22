import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Activity, AlertTriangle, ArrowRight, Bot, Camera, Check, CheckCircle2, FileText,
  Gavel, LayoutGrid, Lock, Mail, MessageSquareText, Scale, ScrollText, ShieldCheck,
  Sparkles, TrendingUp, Upload, Users, Wallet, X,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import './Landing.css';

const EXIGENCIAS = [
  'Alineado a la Ley 21.442',
  'Notificacion con valor legal',
  'Trazabilidad total',
  'Derecho a descargo',
];

const NODOS = [
  { cls: 'n1', Icon: Camera, titulo: 'Se levanta el reporte', sub: 'Un vecino o el personal, con foto', pill: 'ok', pillTxt: 'Reportado' },
  { cls: 'n2', Icon: Sparkles, titulo: 'La IA clasifica', sub: 'Tipo y monto segun tu reglamento', pill: 'ok', pillTxt: '3 UF' },
  { cls: 'n3', Icon: Gavel, titulo: 'Comite o administracion revisa', sub: 'Acepta o rechaza · app, WhatsApp o correo', pill: 'ok', pillTxt: 'Aceptada' },
  { cls: 'n4', Icon: Mail, titulo: 'Notificacion al residente', sub: 'Con valor legal', pill: 'ok', pillTxt: 'Enviada' },
  { cls: 'n5', Icon: MessageSquareText, titulo: 'Descargo del residente', sub: '5 dias para defenderse · se resuelve y se le explica', pill: 'warn', pillTxt: '5 dias' },
  { cls: 'n6', Icon: Wallet, titulo: 'Multa firme → expediente', sub: 'Comprobante generado · pasa a obligacion economica', pill: '', pillTxt: 'En curso' },
];

const ROLES = [
  { cls: 'r1', Icon: Camera, nombre: 'Quien reporta', limite: 'Solo reporta', LimIcon: X,
    texto: 'Cualquiera puede levantar un caso: el personal, la administracion o un vecino, con foto.' },
  { cls: 'r2', Icon: Gavel, nombre: 'Quien decide', limite: 'Acepta o rechaza', LimIcon: Check,
    texto: 'El comite o la administracion, segun tu condominio, revisa la evidencia y aplica la multa segun el reglamento.' },
  { cls: 'r3', Icon: Mail, nombre: 'Administracion', limite: 'Ejecuta y cobra', LimIcon: Check,
    texto: 'Notifica, lleva el expediente y, cuando la multa es firme, la ingresa como obligacion economica.' },
  { cls: 'r4', Icon: Users, nombre: 'Residente', limite: 'Derecho a defensa', LimIcon: Check,
    texto: 'Recibe la notificacion y puede presentar su descargo en 5 dias. Siempre sabe el porque.' },
];

const BENEFICIOS = [
  { Icon: FileText, titulo: 'Informe por unidad',
    texto: 'Descarga el detalle de multas de cada unidad, sus reincidencias y como evolucionan en el tiempo.' },
  { Icon: Activity, titulo: 'Puntos criticos de la comunidad',
    texto: 'El comite y la administracion ven los temas y zonas mas conflictivos, para actuar con un plan concreto.' },
  { Icon: Scale, titulo: 'Valido ante entidades legales',
    texto: 'Si algun dia hay que presentarlo en un juzgado u otra entidad, generas un informe formal y verificable.' },
  { Icon: TrendingUp, titulo: 'Mas multas pagadas, mas ingresos',
    texto: 'La trazabilidad y la notificacion real elevan el pago de las multas: mas ingresos para el condominio.' },
];

const SALVAGUARDAS = [
  { Icon: CheckCircle2, titulo: 'Nada es discrecional',
    texto: 'No hay multas porque si: la IA valida cada caso contra la Ley 21.442 y el reglamento de tu comunidad.' },
  { Icon: Bot, titulo: 'Un bot filtra lo que no corresponde',
    texto: 'Antes de llegar a quien decide, un bot descarta lo que claramente no es una infraccion.' },
  { Icon: AlertTriangle, titulo: 'Sin contacto, no hay multa',
    texto: 'Si el residente no tiene contacto registrado, el caso queda en pausa hasta poder notificar de verdad.' },
  { Icon: ShieldCheck, titulo: 'Comite, administracion y residente protegidos',
    texto: 'Cada decision y cada paso queda documentado. Todos los involucrados quedan respaldados.' },
];

const MODULOS = [
  { Icon: Upload, titulo: 'Arranca en minutos',
    texto: 'Sube el registro de residentes con sus contactos y el reglamento. Una IA los lee y deja todo listo, alineado a la Ley 21.442 y a tu reglamento.' },
  { Icon: Sparkles, titulo: 'La IA clasifica cada caso',
    texto: 'Determina el tipo y el monto segun tu reglamento. Quien decide solo confirma. Nada queda al azar.' },
  { Icon: MessageSquareText, titulo: 'Libro de Novedades digital',
    texto: 'Los copropietarios dejan reclamos y solicitudes. Respondes dentro del plazo legal, sin que se te pase ninguno.' },
  { Icon: Wallet, titulo: 'Gastos comunes',
    texto: 'Las multas firmes pasan a obligacion economica en el aviso de cobro del mes.' },
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
      let h = Math.sin(t * 6.283 * 1.7 + 0.6) * 0.5 + Math.sin(t * 6.283 * 3.1 + 1.3) * 0.28 + Math.sin(t * 6.283 * 0.9 + 0.4) * 0.34;
      h += (nz(i, j) * 2 - 1) * 0.4;
      h = h * 0.6 + 0.5;
      const amp = 62 * (0.25 + persp);
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
        ctx.strokeStyle = `rgba(90,236,222,${0.06 + b * 0.34})`;
        ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(pt.x, pt.y); ctx.lineTo(q.x, q.y); ctx.stroke();
      }
      if (j < rows - 1) {
        const q2 = pts[j + 1][i];
        ctx.strokeStyle = `rgba(66,206,200,${0.05 + b * 0.22})`;
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
            <a href="#roles">Trazabilidad</a>
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
          <h1 className="rise d2">Trazabilidad de multas, <span className="hl">notificaciones y reclamos.</span></h1>
          <p className="hero-lead rise d2">
            Sube el registro de residentes y tu reglamento: una IA los lee y clasifica cada caso,
            alineada a la Ley 21.442. Desde el reporte hasta el cobro, todos los involucrados saben
            en que va cada multa. Nada es discrecional.
          </p>
          <div className="hero-ctas rise d3">
            <a href="#demo" className="btn btn-cyan">Quiero verlo funcionando</a>
            <a href="#flujo" className="btn btn-outline-l">Ver el ciclo de la multa</a>
          </div>
        </div>

        <div className="hero-trust rise d4">
          <div className="lbl">El respaldo legal en el que se apoyan comites y administraciones</div>
          <div className="items">
            {EXIGENCIAS.map((c) => (
              <span key={c}><Check size={15} strokeWidth={3} /> {c}</span>
            ))}
          </div>
        </div>

        <div className="stats rise d4">
          <div className="stat"><div className="n">100<em>%</em></div><div className="t">Trazable · todos ven el estado en tiempo real</div></div>
          <div className="stat"><div className="n">3<em> canales</em></div><div className="t">Notificacion por app, WhatsApp y correo</div></div>
          <div className="stat"><div className="n">20<em> dias</em></div><div className="t">Plazo legal del Libro de Novedades, vigilado</div></div>
        </div>
        <div className="hero-foot" />
        <canvas id="terrain" ref={terrainRef} aria-hidden="true" />
      </header>

      {/* ---------- FLUJO / MAPA ---------- */}
      <section id="flujo">
        <div className="wrap flow-grid">
          <div className="flow-copy">
            <div className="eye">El ciclo de la multa</div>
            <h2>Cada caso, del reporte al cobro, en un solo mapa</h2>
            <p>Ves en que paso va cada multa, notificacion o reclamo y quien lo tiene en sus manos.
              Nadie avanza sin cumplir el paso anterior.</p>
            <p>Y todo queda <strong>registrado</strong>: aunque pasen años, cualquiera puede verificar que nada fue alterado.</p>
          </div>
          <div className="map">
            <div className="map-top">
              <span className="map-title"><LayoutGrid size={15} strokeWidth={2} /> Ciclo de la multa · Depto 302</span>
              <span className="seal"><Lock size={11} strokeWidth={2.4} /> SELLADO</span>
            </div>
            <div className="map-sub">Ruidos molestos · 23:04</div>
            <div className="nodes">
              {NODOS.map((n, i) => (
                <div key={n.cls}>
                  <div className={`node ${n.cls}`}>
                    <span className="ico"><n.Icon size={19} strokeWidth={2} /></span>
                    <div className="body"><b>{n.titulo}</b><small>{n.sub}</small></div>
                    <span className={`pill ${n.pill}`}>{n.pillTxt}</span>
                  </div>
                  {i < NODOS.length - 1 && <div className="connector" />}
                </div>
              ))}
            </div>
            <div className="map-foot"><Lock size={12} strokeWidth={2.2} /> Todos los involucrados ven el estado en tiempo real · queda en el expediente de la unidad</div>
          </div>
        </div>
      </section>

      {/* ---------- TRAZABILIDAD (valor central) ---------- */}
      <section id="roles" className="band">
        <div className="wrap">
          <div className="sec-head">
            <div className="sec-eye">El valor central</div>
            <h2>Trazabilidad de multas, notificaciones y reclamos</h2>
            <p>Desde el reporte hasta el cobro, cada involucrado —quien reporta, quien decide, la administracion
              y el residente— sabe en que estado va cada caso. Esa trazabilidad es el corazon de VIVEPIOLA.</p>
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
            <h2>La informacion siempre esta de tu lado</h2>
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
            VIVEPIOLA sigue cada sancion desde el reporte hasta el cobro, verificando que cada paso sea
            valido segun la ley y dejando <span className="hl">un rastro que nadie puede negar.</span>
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
                  <li><CheckCircle2 size={16} strokeWidth={2.6} /> No cambias como trabaja tu equipo hoy</li>
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
