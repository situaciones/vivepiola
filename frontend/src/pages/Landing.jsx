import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Activity, AlertTriangle, ArrowRight, Bot, Camera, Check, CheckCircle2, Database,
  FileText, Flag, Gavel, Mail, MessageSquareText, Play, Pause, Scale, ShieldCheck,
  Sparkles, TrendingUp, Users, Wallet, X,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import './Landing.css';

const EXIGENCIAS = [
  'Alineado a la Ley 21.442',
  'Notificacion con valor legal',
  'Trazabilidad total',
  'Derecho a descargo',
];

const FLUJO = [
  { Icon: Database, actor: 'Configuracion', corto: 'Configuracion inicial', titulo: 'Configuracion inicial',
    desc: 'Se carga la nomina de residentes (planilla tipo Excel) junto con todos los reglamentos aplicables: copropiedad, estacionamientos, uso de espacios comunes y mas.' },
  { Icon: Flag, actor: 'Denunciante', corto: 'Ingreso de la denuncia', titulo: 'Ingreso de la denuncia',
    desc: 'Un conserje, un miembro del comite o un vecino —con opcion de mantener el anonimato— ingresa el reporte de la infraccion al sistema.' },
  { Icon: Sparkles, actor: 'Inteligencia Artificial', corto: 'Analisis con IA', titulo: 'Analisis con IA',
    desc: 'La IA cruza los datos de la denuncia con los reglamentos: identifica los articulos infringidos, tipifica la falta, calcula el monto y redacta una propuesta formal de multa.' },
  { Icon: Gavel, actor: 'Comite', corto: 'Primer filtro: el comite', titulo: 'Primer filtro: el comite revisa',
    desc: 'El comite revisa la propuesta de la IA. Puede rechazarla (el proceso termina) o aprobarla. Si la aprueba, el sistema emite la notificacion al residente.' },
  { Icon: MessageSquareText, actor: 'Residente', corto: 'Derecho a apelacion', titulo: 'Derecho a apelacion',
    desc: 'El residente recibe la notificacion y tiene un plazo de 5 dias para presentar su apelacion a traves de los canales integrados: app, correo o WhatsApp.' },
  { Icon: Scale, actor: 'Comite', corto: 'Resolucion del comite', titulo: 'Resolucion del comite',
    desc: 'El comite evalua la apelacion. Puede mantener la multa intacta, aplicar un porcentaje de descuento (30%, 50%) o condonarla dejandola en cero.' },
  { Icon: Wallet, actor: 'Administrador', corto: 'Traspaso a cobro', titulo: 'Traspaso a cobro',
    desc: 'Si la resolucion determina que hay un monto a pagar, la instruccion pasa a la administracion para cargarla en la proxima boleta de gastos comunes.' },
  { Icon: FileText, actor: 'Sistema', corto: 'Trazabilidad e historial', titulo: 'Trazabilidad e historial',
    desc: 'Todo el proceso —fechas, actores, apelaciones y resoluciones— queda en un informe dentro de la carpeta digital del residente. El sistema aplica multiplicadores automaticos si hay reincidencia.' },
];

const ACTORES = [
  { Icon: Sparkles, nombre: 'Inteligencia Artificial', rol: 'Analiza los hechos, cruza con los reglamentos, calcula montos y redacta.' },
  { Icon: Flag, nombre: 'Denunciante', rol: 'Ingresa el reporte inicial de la infraccion.' },
  { Icon: Gavel, nombre: 'Comite de administracion', rol: 'Aprueba las multas y resuelve las apelaciones.' },
  { Icon: Users, nombre: 'Residente', rol: 'Recibe notificaciones, ejerce su defensa y asume el pago.' },
  { Icon: Wallet, nombre: 'Administrador', rol: 'Ejecuta el cobro en el gasto comun, con un informe transparente.' },
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

function FlujoInteractivo() {
  const [activo, setActivo] = useState(0);
  const [pausado, setPausado] = useState(false);
  const total = FLUJO.length;

  useEffect(() => {
    if (pausado) return undefined;
    const id = setInterval(() => setActivo((a) => (a + 1) % total), 4200);
    return () => clearInterval(id);
  }, [pausado, total, activo]);

  const paso = FLUJO[activo];
  const PasoIcon = paso.Icon;

  return (
    <div className="flujo" onMouseEnter={() => setPausado(true)} onMouseLeave={() => setPausado(false)}>
      <div className="stepper">
        <div className="stepper-rail">
          <span className="stepper-fill" style={{ height: `${(activo / (total - 1)) * 100}%` }} />
        </div>
        {FLUJO.map((p, i) => {
          const estado = i < activo ? 'done' : i === activo ? 'now' : '';
          return (
            <button key={p.corto} type="button" className={`step ${estado}`} onClick={() => setActivo(i)} aria-current={i === activo}>
              <span className="step-dot">{i < activo ? <Check size={14} strokeWidth={3} /> : i + 1}</span>
              <span className="step-label"><b>{p.corto}</b><em>{p.actor}</em></span>
            </button>
          );
        })}
      </div>

      <div className="flow-panel">
        <div className="panel-head">
          <span className="panel-ico"><PasoIcon size={26} strokeWidth={1.9} /></span>
          <span className="panel-step">Paso {String(activo + 1).padStart(2, '0')} / {String(total).padStart(2, '0')}</span>
          <button type="button" className="panel-play" onClick={() => setPausado((p) => !p)} aria-label={pausado ? 'Reanudar' : 'Pausar'}>
            {pausado ? <Play size={14} /> : <Pause size={14} />}
          </button>
        </div>
        <h3 key={`t${activo}`} className="panel-title fade">{paso.titulo}</h3>
        <p key={`d${activo}`} className="panel-desc fade">{paso.desc}</p>
        <div className="panel-actor"><span className="dotmini" /> Responsable: <b>{paso.actor}</b></div>
        {!pausado && <span className="autobar" key={activo} />}
      </div>
    </div>
  );
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
    const schedule = () => { clearTimeout(t); t = setTimeout(build, 80); };
    build();
    // El canvas mide 0 en el primer render: el observer redibuja apenas tiene tamaño real.
    const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(schedule) : null;
    if (ro) ro.observe(canvas);
    window.addEventListener('resize', schedule);
    return () => {
      window.removeEventListener('resize', schedule);
      if (ro) ro.disconnect();
      clearTimeout(t);
    };
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
          <span className="h-eyebrow rise d1">● Ley 21.442, su reglamento y el de tu condominio</span>
          <h1 className="rise d2">Trazabilidad de multas, <span className="hl">notificaciones y reclamos.</span></h1>
          <p className="hero-lead rise d2">
            Sube, clasifica y cobra con certeza. IA alineada a la Ley 21.442, al reglamento
            de la ley y a los reglamentos de tu condominio.
          </p>
          <p className="hero-kicker rise d3">Sin rodeos, sin favoritismos, sin demoras.</p>
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
        </div>
        <div className="hero-foot" />
        <canvas id="terrain" ref={terrainRef} aria-hidden="true" />
      </header>

      {/* ---------- FLUJO INTERACTIVO ---------- */}
      <section id="flujo">
        <div className="wrap">
          <div className="sec-head">
            <div className="sec-eye">El ciclo de la multa</div>
            <h2>De la denuncia al cobro, con trazabilidad total</h2>
            <p>Ocho pasos, cada uno con su responsable. Toca una etapa para ver el detalle, o deja que avance solo.</p>
          </div>
          <FlujoInteractivo />
          <div className="actores">
            {ACTORES.map((a) => (
              <div key={a.nombre} className="actor">
                <span className="actor-ico"><a.Icon size={18} strokeWidth={2} /></span>
                <div><b>{a.nombre}</b><span>{a.rol}</span></div>
              </div>
            ))}
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
            <p>Conoce el estatus real y quien es el responsable en cada punto o parte del proceso.</p>
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

      {/* ---------- CTA ---------- */}
      <section id="demo">
        <div className="wrap">
          <div className="cta">
            <div className="cta-grid">
              <div>
                <h2>Que tu comite y tu administracion duerman tranquilos</h2>
                <p>Agenda una demo de 20 minutos. Te mostramos, con las multas de tu propio condominio,
                  como dejar todo en orden y con trazabilidad completa.</p>
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
