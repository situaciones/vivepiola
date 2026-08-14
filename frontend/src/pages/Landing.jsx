import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  AlertTriangle, ArrowRight, Bell, BookOpen, Camera, Check, CheckCircle2, FileText,
  Gavel, Inbox, Mail, MessageSquareText, Play, Pause, Scale, ScrollText, ShieldCheck,
  Sparkles, Users, Wallet, X,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { LogoVivePiola } from '../components/Marca';
import './Landing.css';
import './LandingSecciones.css';

/**
 * Landing comercial.
 *
 * REGLA QUE MANDA AQUI: no se promete nada que el sistema no haga hoy. Es una
 * pagina de un producto que emite sanciones; prometer de mas se descubre en la
 * primera demo y cuesta la venta y la confianza.
 *
 * Por eso NO aparecen: dashboard de metricas, informes agregados, ni apelar
 * respondiendo el correo (el enlace si funciona). Cuando existan, entran.
 */

const FLUJO = [
  { Icon: BookOpen, actor: 'Configuracion', corto: 'Se cargan las reglas', titulo: 'Se cargan las reglas',
    desc: 'La nomina de residentes y los documentos de tu comunidad: reglamento de copropiedad, estacionamientos, espacios comunes, normas de seguridad y actas de asamblea. La normativa general de Chile ya viene en la plataforma.' },
  { Icon: Camera, actor: 'Quien reporta', corto: 'Alguien reporta algo', titulo: 'Alguien reporta algo',
    desc: 'El conserje, un miembro del comite o un vecino —con opcion de mantener el anonimato— describe lo que paso y adjunta foto o video. El sistema detecta si otro ya reporto el mismo hecho.' },
  { Icon: Sparkles, actor: 'La plataforma', corto: 'Se analiza y se notifica', titulo: 'Se analiza y se notifica',
    desc: 'Se mira la evidencia, se busca la norma aplicable entre las de tu comunidad y las generales, se revisa el historial de la unidad y se notifica. Sin reuniones previas: el residente se entera mientras el hecho esta fresco.' },
  { Icon: MessageSquareText, actor: 'Residente', corto: 'Puede apelar', titulo: 'Puede apelar',
    desc: 'Recibe el caso con la norma aplicada y la evidencia. Puede confirmar, descargar el documento y presentar su version, sin crear ninguna cuenta. El plazo corre desde que confirma, no desde que se envio.' },
  { Icon: Scale, actor: 'Comite', corto: 'Resuelve, si hay apelacion', titulo: 'Resuelve, si hay apelacion',
    desc: 'Es su unica intervencion. Ve el caso preparado, con los antecedentes y el historial, y decide: mantener, rebajar, dar parte de cortesia o anular. Si nadie apela, el caso se cierra solo.' },
  { Icon: Wallet, actor: 'Administracion', corto: 'Se traspasa al cobro', titulo: 'Se traspasa al cobro',
    desc: 'Si quedo un monto por pagar, se incorpora al proximo aviso de gastos comunes a nombre de quien responde por la unidad.' },
  { Icon: FileText, actor: 'Sistema', corto: 'Queda el expediente', titulo: 'Queda el expediente',
    desc: 'Todo el recorrido queda registrado y sellado: quien reporto, que se vio, que norma se aplico, cuando se notifico, quien confirmo, que se resolvio y por que.' },
];

const COMPARATIVA = [
  ['Denuncias por WhatsApp, correo o de palabra', 'Un solo lugar donde entran todos los reportes'],
  ['Reglamentos repartidos en carpetas y correos', 'Toda la normativa junta y consultable'],
  ['Buscar a mano el articulo que corresponde', 'Se busca solo, en las reglas de tu comunidad y en la ley'],
  ['Criterios distintos segun quien revise', 'Las mismas reglas, configuradas y aprobadas antes'],
  ['Nadie recuerda cuantas veces paso', 'Historial de reincidencias automatico'],
  ['Se multa desde la primera vez', 'Primero se avisa sin cobrar; se multa cuando corresponde'],
  ['"Te mande un correo" como unica prueba', 'Registro de cada intento de entrega y del acuse'],
  ['El comite revisa todos los casos', 'El comite entra cuando hay apelacion'],
  ['Fotos sueltas en el telefono de alguien', 'Evidencia unida al caso y sellada'],
  ['Reconstruir un caso viejo es imposible', 'El expediente completo, siempre'],
];

const SEMAFORO = [
  { color: 'verde', nivel: 'Leve', que: 'Primero se avisa sin cobrar. La falta queda registrada, pero no se carga nada al gasto comun.' },
  { color: 'ambar', nivel: 'Grave', que: 'Se avisa igual las primeras veces, y a la tercera se multa. La comunidad define cuantos avisos da.' },
  { color: 'rojo', nivel: 'Muy grave', que: 'Se multa desde la primera vez. Frente a un riesgo real, avisar sin consecuencia seria el mensaje contrario.' },
];

const ACTORES = [
  {
    Icon: Users, nombre: 'Administrador',
    puntos: ['Deja de perseguir casos por WhatsApp', 'Todo en un solo lugar', 'No se le pasa ningun paso', 'El cobro sale listo'],
  },
  {
    Icon: Gavel, nombre: 'Comite',
    puntos: ['Menos reuniones', 'Llega el caso preparado', 'Ve el historial de la unidad', 'Sus decisiones quedan respaldadas'],
  },
  {
    Icon: ShieldCheck, nombre: 'Residente',
    puntos: ['Sabe que paso y que norma se aplico', 'Puede defenderse sin crear cuenta', 'Conoce sus plazos', 'Primero lo avisan, no lo multan'],
  },
];

const EXPEDIENTE = [
  'El reporte original', 'La foto o el video', 'Si alguien mas reporto lo mismo',
  'La norma que se aplico', 'Por que se aplico esa', 'Cortesias anteriores',
  'Reincidencias', 'Cada intento de notificacion', 'El acuse de recibo',
  'La apelacion', 'Antecedentes que se sumaron', 'La reunion, si la hubo',
  'Los votos del comite', 'La resolucion', 'El monto final',
];

function BrandMark({ size = 36 }) {
  return <LogoVivePiola size={size} className="mk" />;
}

/** El caso de ejemplo del hero: cuenta el producto entero en cinco lineas. */
function CasoDemo() {
  return (
    <div className="caso rise d3">
      <div className="caso-barra">
        <span /><span /><span />
        <em>Caso #248</em>
      </div>
      <div className="caso-cuerpo">
        <div className="caso-paso">
          <span className="caso-et">Reporte recibido</span>
          <b>Auto sobre la rampa de acceso</b>
        </div>
        <ArrowRight size={14} className="caso-flecha" />
        <div className="caso-paso">
          <span className="caso-et">Norma identificada</span>
          <b>Instructivo de estacionamientos, Art. 3</b>
        </div>
        <ArrowRight size={14} className="caso-flecha" />
        <div className="caso-paso">
          <span className="caso-et">Nivel</span>
          <b><i className="punto ambar" /> Grave</b>
        </div>
        <ArrowRight size={14} className="caso-flecha" />
        <div className="caso-paso">
          <span className="caso-et">Historial de la unidad</span>
          <b>2 avisos anteriores</b>
        </div>
        <div className="caso-resultado">
          <CheckCircle2 size={16} />
          <div>
            <b>Corresponde multa</b>
            <span>Notificada, con 5 dias para apelar</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function FlujoInteractivo() {
  const [activo, setActivo] = useState(0);
  const [pausado, setPausado] = useState(false);
  const total = FLUJO.length;

  useEffect(() => {
    if (pausado) return undefined;
    const id = setInterval(() => setActivo((a) => (a + 1) % total), 4600);
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
  const [form, setForm] = useState({ nombre: '', correo: '', empresa: '' });
  const [enviado, setEnviado] = useState(false);

  const enviar = (e) => {
    e.preventDefault();
    setEnviado(true);
  };

  return (
    <div className="vp">
      <nav>
        <div className="nav-in">
          <Link to="/" className="brand"><BrandMark size={38} /><span className="wordmark"><b>VIVE</b><b>PIOLA</b></span></Link>
          <div className="nav-links">
            <a href="#flujo">Como funciona</a>
            <a href="#cortesia">No todo es multa</a>
            <a href="#expediente">Respaldo</a>
          </div>
          <div className="nav-right">
            <Link to={rutaApp} className="nav-login">Entrar</Link>
            <a href="#demo" className="btn btn-cyan">Quiero una demo</a>
          </div>
        </div>
      </nav>

      {/* ---------- 1. HERO ---------- */}
      <header className="hero">
        <div className="hero-inner">
          <h1 className="rise d1">
            Reglas claras. Menos conflictos.<br />
            <span className="hl">Una comunidad mas ordenada.</span>
          </h1>
          <p className="hero-sub rise d2">
            Reportes, notificaciones, reincidencias y apelaciones en un solo lugar,
            aplicando siempre las mismas reglas de tu comunidad.
          </p>
          <div className="hero-ctas rise d2">
            <a href="#demo" className="btn btn-cyan">Solicitar una demostracion</a>
            <a href="#flujo" className="btn btn-outline-l">Ver como funciona</a>
          </div>
          <p className="hero-nota rise d3">
            Para administradores, comites y comunidades de condominios en Chile.
          </p>
          <CasoDemo />
        </div>

        <div className="hero-foot" />
        <div className="hero-photo" aria-hidden="true" />
      </header>

      {/* ---------- 2. LA TRANSFORMACION ---------- */}
      <section id="problema">
        <div className="wrap">
          <div className="sec-head">
            <div className="sec-eye">El problema</div>
            <h2>Hacer cumplir las reglas no deberia terminar en pelea</h2>
            <p>Cuando las normas estan repartidas entre reglamentos, actas, correos y grupos de
              WhatsApp, aplicarlas igual para todos se vuelve imposible. Y ahi empieza el conflicto:
              no por la multa, sino por el "¿por que a mi?".</p>
          </div>

          <div className="comparativa">
            <div className="comp-cab">
              <span className="comp-antes">Como se hace hoy</span>
              <span className="comp-despues">Con VIVEPIOLA</span>
            </div>
            {COMPARATIVA.map(([antes, despues]) => (
              <div key={antes} className="comp-fila">
                <span className="comp-antes"><X size={14} /> {antes}</span>
                <span className="comp-despues"><Check size={14} strokeWidth={3} /> {despues}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ---------- 3. COMO FUNCIONA ---------- */}
      <section id="flujo" className="band">
        <div className="wrap">
          <div className="sec-head">
            <div className="sec-eye">Como funciona</div>
            <h2>De un reporte a un caso resuelto</h2>
            <p>Siete pasos, cada uno con su responsable. Toca una etapa para ver el detalle,
              o deja que avance solo.</p>
          </div>
          <FlujoInteractivo />
        </div>
      </section>

      {/* ---------- 4. NO TODO TERMINA EN MULTA ---------- */}
      <section id="cortesia">
        <div className="wrap">
          <div className="sec-head">
            <div className="sec-eye">Lo que nos diferencia</div>
            <h2>Primero corregir. Multar cuando corresponde.</h2>
            <p>El objetivo de una comunidad no es recaudar, es que la gente sepa que hay una norma.
              Quien la incumple por primera vez casi siempre corrige con el aviso.</p>
          </div>

          <div className="semaforo">
            {SEMAFORO.map((s) => (
              <div key={s.nivel} className={`sem ${s.color}`}>
                <i className={`punto ${s.color}`} />
                <h3>{s.nivel}</h3>
                <p>{s.que}</p>
              </div>
            ))}
          </div>

          <div className="escalera">
            <div className="esc-paso"><Bell size={18} /><b>1a vez</b><span>Aviso, sin cobro</span></div>
            <ArrowRight size={16} className="esc-flecha" />
            <div className="esc-paso"><Bell size={18} /><b>2a vez</b><span>Aviso, sin cobro</span></div>
            <ArrowRight size={16} className="esc-flecha" />
            <div className="esc-paso esc-multa"><AlertTriangle size={18} /><b>3a vez</b><span>Ahora si, multa</span></div>
          </div>

          <p className="frase-grande">El sistema recuerda lo que las personas suelen olvidar.</p>
        </div>
      </section>

      {/* ---------- 5. LA IA, CON LIMITES ---------- */}
      <section className="band">
        <div className="wrap">
          <div className="caja-confianza">
            <div className="cc-icono"><Sparkles size={28} strokeWidth={1.8} /></div>
            <div>
              <h2>La inteligencia artificial analiza y propone. El sistema aplica las reglas.</h2>
              <p>
                No inventa multas. Trabaja sobre un catalogo que tu comunidad reviso y aprobo antes,
                y si propone algo que no esta en ese catalogo, se descarta.
              </p>
              <div className="cc-puntos">
                <div><ScrollText size={16} /><span><b>Lee tus documentos y la ley.</b> El reglamento de tu comunidad, los instructivos, las actas de asamblea y la normativa chilena vigente.</span></div>
                <div><Camera size={16} /><span><b>Mira la evidencia.</b> Analiza las fotos y los videos del reporte. Tiene prohibido describir personas.</span></div>
                <div><CheckCircle2 size={16} /><span><b>Todo nace como borrador.</b> Ninguna regla se puede aplicar hasta que una persona la revisa y la aprueba.</span></div>
                <div><AlertTriangle size={16} /><span><b>Si no esta segura, no actua.</b> Mientras mas grave sea la falta, mas certeza se le exige antes de notificar sin que alguien la revise.</span></div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ---------- 6. NOTIFICAR NO ES ENVIAR ---------- */}
      <section id="notificacion">
        <div className="wrap">
          <div className="sec-head">
            <div className="sec-eye">Debido proceso</div>
            <h2>Notificar no es solo mandar un mensaje</h2>
            <p>El plazo para apelar empieza cuando el residente confirma que recibio la notificacion.
              No cuando el sistema la envio. Nadie pierde su defensa por un correo que nunca vio.</p>
          </div>

          <div className="cadena">
            <div className="cad-paso"><Mail size={18} /><b>Se notifica</b><span>Correo y WhatsApp</span></div>
            <ArrowRight size={16} className="cad-flecha" />
            <div className="cad-paso"><Bell size={18} /><b>Se reintenta</b><span>Hasta 3 veces</span></div>
            <ArrowRight size={16} className="cad-flecha" />
            <div className="cad-paso"><CheckCircle2 size={18} /><b>Confirma</b><span>O queda constancia</span></div>
            <ArrowRight size={16} className="cad-flecha" />
            <div className="cad-paso cad-final"><Scale size={18} /><b>Ahi corre el plazo</b><span>5 dias para apelar</span></div>
          </div>

          <div className="dos-cajas">
            <div className="dc">
              <Inbox size={20} />
              <h3>El residente tiene su propio buzon</h3>
              <p>Sin crear cuenta ni recordar contraseñas. Entra por el enlace del correo o del
                WhatsApp y ahi encuentra su caso, la norma que se le aplico, la evidencia, el documento
                para descargar cuando quiera, y el formulario para apelar.</p>
            </div>
            <div className="dc">
              <ShieldCheck size={20} />
              <h3>Y una proteccion antes del cobro</h3>
              <p>Si hay señales de que la persona pudo no haberse podido defender —nunca confirmo que
                recibio el aviso, o figura con una condicion que se lo impide— el cobro se detiene y
                alguien tiene que confirmarlo antes de emitirse.</p>
            </div>
          </div>
        </div>
      </section>

      {/* ---------- 7. EL EXPEDIENTE ---------- */}
      <section id="expediente" className="band">
        <div className="wrap">
          <div className="sec-head">
            <div className="sec-eye">El respaldo</div>
            <h2>Todo termina en un expediente completo</h2>
            <p>Cada paso queda registrado y sellado. Si el caso se discute meses despues, la respuesta
              esta entera y se puede demostrar que nadie la modifico.</p>
          </div>

          <div className="expediente">
            {EXPEDIENTE.map((item, i) => (
              <div key={item} className="exp-item">
                <span className="exp-num">{String(i + 1).padStart(2, '0')}</span>
                {item}
              </div>
            ))}
          </div>

          <p className="frase-grande">
            Si mañana alguien pregunta que paso, la respuesta esta completa.
          </p>
        </div>
      </section>

      {/* ---------- 8. QUIEN GANA QUE ---------- */}
      <section id="beneficios">
        <div className="wrap">
          <div className="sec-head">
            <div className="sec-eye">Para todos</div>
            <h2>Un proceso claro le sirve a los tres lados</h2>
          </div>

          <div className="actores-grid">
            {ACTORES.map((a) => (
              <div key={a.nombre} className="actor-col">
                <span className="actor-ico"><a.Icon size={22} strokeWidth={1.9} /></span>
                <h3>{a.nombre}</h3>
                <ul>
                  {a.puntos.map((p) => (
                    <li key={p}><Check size={14} strokeWidth={3} /> {p}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ---------- CTA ---------- */}
      <section id="demo" className="cta">
        <div className="wrap cta-in">
          <div>
            <h2>Las reglas de tu comunidad ya existen.<br />Ahora puedes aplicarlas mejor.</h2>
            <p>Cuentanos de tu condominio y te mostramos el ciclo completo con un caso real:
              desde el reporte hasta el expediente.</p>
            <p className="cta-cierre">Reglas claras. Procesos justos. Comunidades mas ordenadas.</p>
          </div>

          {enviado ? (
            <div className="form-ok">
              <CheckCircle2 size={30} />
              <h3>Gracias, {form.nombre || 'que bueno tenerte'}.</h3>
              <p>Te escribimos a {form.correo} para coordinar la demostracion.</p>
            </div>
          ) : (
            <form onSubmit={enviar} className="cta-form">
              <label>
                Tu nombre
                <input required value={form.nombre} onChange={(e) => setForm({ ...form, nombre: e.target.value })} />
              </label>
              <label>
                Correo
                <input required type="email" value={form.correo} onChange={(e) => setForm({ ...form, correo: e.target.value })} />
              </label>
              <label>
                Condominio o administradora
                <input value={form.empresa} onChange={(e) => setForm({ ...form, empresa: e.target.value })} />
              </label>
              <button className="btn btn-cyan" type="submit">Solicitar demostracion</button>
            </form>
          )}
        </div>
      </section>

      <footer>
        <div className="wrap foot-in">
          <div className="brand"><BrandMark size={30} /><span className="wordmark"><b>VIVE</b><b>PIOLA</b></span></div>
          <span>Gestion de convivencia y cumplimiento normativo para condominios en Chile.</span>
        </div>
      </footer>
    </div>
  );
}
