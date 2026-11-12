import { useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, ArrowLeft, Camera, FileText } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { LogoSinConflicto } from '../components/Marca';
import './Landing.css';
import './LandingMinimal.css';
import './ComoFunciona.css';

/**
 * El proceso, para recorrerlo en vez de leerlo.
 *
 * Antes esto eran diez bloques de prosa y nueve mil pixeles de scroll. Nadie
 * lee nueve mil pixeles para entender un producto que todavia no compro. Ahora
 * son siete pasos que se tocan: cada uno cabe en una frase y trae el unico
 * numero que importa.
 *
 * LAS CIFRAS SALEN DEL CODIGO, NO DE LO QUE SUENA BIEN:
 *   65 / 80 / 90 -> settings.CURSE_CONFIANZA_MINIMA
 *   2 cortesias  -> Condominio.cortesias_antes_de_multar
 *   10 dias      -> Condominio.plazo_descargo_dias (habiles)
 *   15 dias      -> Condominio.plazo_resolucion_dias
 * Son los valores por defecto y cada comunidad los ajusta. Si cambian en el
 * backend tienen que cambiar aca: una pagina publica que promete cinco dias
 * cuando el sistema da tres no es una errata, es un problema legal.
 */

const PASOS = [
  {
    n: '01',
    tab: 'Configuracion',
    titulo: 'Todo cargado antes de empezar',
    frase: 'Nuestro equipo legal mantiene al dia la normativa de Chile. Tu comunidad sube la suya: reglamento de copropiedad, reglamento interno y actas.',
    dato: { valor: '0', pie: 'reglas escribe el software' },
    nota: 'El catalogo de infracciones sale de tus documentos, y lo aprueba una persona.',
  },
  {
    n: '02',
    tab: 'Infraccion',
    titulo: 'La infraccion no es la multa',
    // La distincion que ordena todo lo demas. Si el visitante se lleva una
    // sola idea de esta pagina, ojala sea esta. Va con un caso concreto
    // porque en abstracto suena a leguleyada y con un auto sobre la rampa
    // se entiende sin explicacion.
    frase: 'La IA mira las fotos y el video. Con el hecho respaldado, recien ahi se califica segun tu reglamento.',
    contraste: {
      // El hecho va con un caso concreto porque es un ejemplo cualquiera y no
      // afirma nada. El otro lado va descrito y no citado: el articulo, la
      // gravedad y el monto los pone el reglamento de cada comunidad, asi que
      // inventar "Art. 24, 0,5 UF" seria dar por cierta una cifra que no
      // existe y que ademas cambia en cada condominio.
      hecho: { et: 'La infraccion', titulo: 'El hecho', texto: 'Un auto estacionado sobre la rampa de acceso.' },
      multa: { et: 'La multa', titulo: 'La consecuencia', texto: 'El articulo que lo prohibe, su gravedad y el monto.' },
    },
    nota: 'Un hecho sin respaldo suficiente no se acredita. Y lo que no se acredita no se multa.',
  },
  {
    n: '03',
    tab: 'Comunicacion',
    titulo: 'Se avisa hasta que confirme',
    // Los canales son los que el sistema despacha hoy. La app existe, pero no
    // manda notificaciones: ponerla como canal seria prometer un aviso que
    // nunca llega.
    frase: 'Correo y WhatsApp, con reintentos. Va el hecho, el articulo y el monto. Si nadie confirma, queda la constancia en el buzon de la unidad.',
    dato: { valor: '3', pie: 'canales, hasta que alguien confirme' },
    nota: 'El plazo corre desde el acuse y no desde el envio: un correo en spam no puede costarle a nadie su defensa.',
  },
  {
    n: '04',
    tab: 'Apelacion',
    titulo: 'Puede apelar, y con pruebas',
    frase: 'Un formulario para sus descargos y para subir el material que lo respalde. Si prefiere hablarlo, agenda una reunion en linea o presencial.',
    dato: { valor: '10', pie: 'dias habiles para apelar, desde el acuse' },
    nota: 'Lo que aporte entra al expediente, y el comite lo tiene que mirar.',
  },
  {
    n: '05',
    tab: 'Resolucion',
    titulo: 'Resuelve el comite',
    frase: 'El sistema le pone las salidas sobre la mesa, cada una con su fundamento: cortesia, rebajar un porcentaje o anular. El comite vota segun sus reglas.',
    dato: { valor: '15', pie: 'dias tiene el comite para resolver' },
    nota: 'Propone. No decide. Quien firma sigue siendo el comite.',
  },
  {
    n: '06',
    tab: 'Cobro',
    titulo: 'Recien ahora se cobra',
    frase: 'Con la resolucion firme, la multa pasa al administrador y entra al proximo cobro de gastos comunes.',
    dato: { valor: '1', pie: 'cobro, y solo al final del proceso' },
    nota: 'Nada se cobra mientras el caso siga abierto.',
  },
  {
    n: '07',
    tab: 'Registro',
    titulo: 'Todo queda escrito',
    frase: 'Cada paso con su fecha, su hora y quien lo hizo: pruebas, cita del articulo, acuse, descargos, votos y resolucion. Si la falta se repite, queda el historial.',
    dato: { valor: '0', pie: 'pasos se pueden borrar' },
    nota: 'Se cierra sellado en cadena: alterar un paso pasado la rompe entera y se nota.',
  },
];

/*
 * LA IA, CONTADA DESDE SUS FUENTES.
 *
 * La unidad base es el caso, y cada capa dice de donde sale. Dos reglas:
 *  - "Agente" solo para el asistente, que elige que herramienta usar. Las
 *    demas funciones son consultas guiadas; llamarlas agentes coordinados
 *    seria prometer algo que el producto no hace.
 *  - Mientras la IA no este activa en produccion (VITE_IA_ACTIVA distinto de
 *    'true'), la seccion lo dice: cada caso llega ordenado al Comite.
 */
const IA_ACTIVA = import.meta.env.VITE_IA_ACTIVA === 'true';

const CAPAS = [
  { nombre: 'Ley', aporta: 'Plazos, derecho a defensa y quien decide.', fuente: 'Ley 21.442 y su reglamento' },
  { nombre: 'Reglamento', aporta: 'Que conductas son falta en su comunidad.', fuente: 'Reglamento de copropiedad inscrito' },
  { nombre: 'Catalogo de faltas', aporta: 'Montos, gravedad y cortesia.', fuente: 'Catalogo confirmado por el Comite' },
  { nombre: 'Evidencia', aporta: 'Fotos y videos con huella digital.', fuente: 'Lo que sube quien reporta' },
  { nombre: 'Historial', aporta: 'Cortesias usadas y faltas previas de la unidad.', fuente: 'Casos cerrados de la comunidad' },
];

// Ficha de ejemplo: datos inventados a proposito, y rotulados como tales.
// Nunca una captura de un caso real.
const FICHA = [
  { et: 'Hecho', valor: 'Auto estacionado sobre la rampa de acceso, con foto', fuente: 'Reporte del conserje' },
  { et: 'Falta propuesta', valor: 'Obstruir accesos comunes', fuente: 'Reglamento, art. 24 (ejemplo)' },
  { et: 'Consecuencia', valor: 'Aviso de cortesia, sin cobro', fuente: 'Catalogo: primera falta en 6 meses' },
  { et: 'Plazo para apelar', valor: '10 dias habiles desde que confirma', fuente: 'Ley 21.442 y regla de la comunidad' },
  { et: 'Decision', valor: 'Pendiente: 1 de 2 votos necesarios', fuente: 'Votos del Comite, registrados' },
];

const FUNCIONES = [
  { titulo: 'Propone la regla que aplica', texto: 'Lee el reporte sin datos personales y propone una falta del catalogo, con su articulo.' },
  { titulo: 'Lee la evidencia', texto: 'Describe lo que se ve en fotos y video. No identifica personas.' },
  { titulo: 'Arma el primer catalogo', texto: 'Extrae posibles faltas de su reglamento. Su Comite las revisa y confirma.' },
  { titulo: 'Un agente que responde', texto: 'El asistente busca en sus casos, su reglamento y la ley, y responde solo con lo que usted puede ver.' },
];

function ComoFuncionaIA() {
  return (
    <section className="doc-ia" aria-labelledby="ia-titulo">
      <div className="doc-ia-in">
        <span className="ia-et">Como funciona la IA</span>
        <h2 id="ia-titulo">Cada caso, cruzado<br /><span className="acento">con las reglas de su comunidad.</span></h2>
        <p className="ia-bajada">
          La IA lee el reporte y lo compara con la ley, su reglamento y el catalogo
          que aprobo su Comite. Cada propuesta muestra la regla de donde sale.
        </p>
        {!IA_ACTIVA && (
          <p className="ia-aviso">
            Estamos activando la IA por etapas. Mientras tanto, cada caso llega
            ordenado al Comite, que decide.
          </p>
        )}

        <h3 className="ia-sub">Nuestra unidad base: el caso</h3>
        <div className="capas">
          {CAPAS.map((c) => (
            <div className="capa" key={c.nombre}>
              <b>{c.nombre}</b>
              <span>{c.aporta}</span>
              <small>Fuente: {c.fuente}</small>
            </div>
          ))}
        </div>

        <figure className="ficha">
          <div className="ficha-cab">
            <span>Caso de ejemplo</span>
            <b>Unidad 402 · Estacionamientos</b>
          </div>
          <dl>
            {FICHA.map((f) => (
              <div className="ficha-fila" key={f.et}>
                <dt>{f.et}</dt>
                <dd>{f.valor}<small>{f.fuente}</small></dd>
              </div>
            ))}
          </dl>
          <figcaption>Caso ficticio. Cada valor muestra la regla o el documento que lo respalda.</figcaption>
        </figure>

        <h3 className="ia-sub">Que hace la IA</h3>
        <div className="funciones">
          {FUNCIONES.map((f) => (
            <div className="funcion" key={f.titulo}>
              <b>{f.titulo}</b>
              <span>{f.texto}</span>
            </div>
          ))}
        </div>

        <div className="dos-col">
          <div>
            <span className="col-et">Respaldo trazable</span>
            <ul>
              <li><b>Con fuente:</b> cada propuesta cita el articulo y su texto.</li>
              <li><b>Sin datos personales:</b> el relato llega a la IA sin nombres, RUT, correos, telefonos ni patentes.</li>
              <li><b>Con decision humana:</b> ninguna multa con cobro se aplica sin la mayoria del Comite.</li>
            </ul>
          </div>
          <div>
            <span className="col-et">No hace</span>
            <ul>
              <li>No inventa reglas ni montos.</li>
              <li>No identifica personas en las imagenes.</li>
              <li>No resuelve apelaciones.</li>
              <li>No cobra.</li>
            </ul>
          </div>
        </div>

        <div className="ia-faq">
          <h3>¿Por que confiar en la IA?</h3>
          <p>
            Porque no decide sola ni inventa reglas. Solo puede proponer faltas que
            existen en el catalogo confirmado por su Comite, y siempre muestra el
            articulo en que se apoya. Si la propuesta no calza, el Comite la corrige
            o la rechaza antes de que alguien sea notificado.
          </p>
        </div>
      </div>
    </section>
  );
}

function Banda({ imagen, alt, tono }) {
  return (
    <div className={`banda ${tono}`}>
      <img src={`/img/${imagen}.webp`} alt={alt} width={1800} height={771}
           loading="lazy" decoding="async" />
    </div>
  );
}

/** Los siete pasos, uno a la vez. */
function Recorrido() {
  const [activo, setActivo] = useState(0);
  const tabs = useRef([]);
  const paso = PASOS[activo];

  // Flechas para moverse sin mouse. Un recorrido que solo responde al click
  // deja fuera a quien navega con teclado, y son siete pasos: se recorren
  // mucho mas rapido con las flechas que apuntando a cada numero.
  const porTeclado = (e) => {
    const salto = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
    const destino = salto
      ? (activo + salto + PASOS.length) % PASOS.length
      : { Home: 0, End: PASOS.length - 1 }[e.key];
    if (destino === undefined) return;
    e.preventDefault();
    setActivo(destino);
    tabs.current[destino]?.focus();
  };

  return (
    <div className="recorrido">
      <div className="pista" role="tablist" aria-label="Pasos del proceso" onKeyDown={porTeclado}>
        {PASOS.map((p, i) => (
          <button
            key={p.n}
            ref={(el) => { tabs.current[i] = el; }}
            role="tab"
            id={`tab-${p.n}`}
            aria-selected={i === activo}
            aria-controls={`panel-${p.n}`}
            tabIndex={i === activo ? 0 : -1}
            className={`pista-paso ${i === activo ? 'activo' : ''} ${i < activo ? 'hecho' : ''}`}
            onClick={() => setActivo(i)}
          >
            <span className="pp-n">{p.n}</span>
            <span className="pp-t">{p.tab}</span>
          </button>
        ))}
      </div>

      {/*
        Los siete paneles van montados a la vez, apilados en la misma celda de
        la grilla, y solo se muestra el activo. Renderizar uno solo hacia que
        la caja midiera distinto en cada paso —37px entre el mas corto y el
        mas largo— y la pagina brincaba bajo el dedo al recorrerla. Asi el
        contenedor siempre mide lo del mas alto, a cualquier ancho y sin
        numero magico. De paso, los siete pasos quedan en el HTML.
      */}
      <div className="paneles">
        {PASOS.map((p, i) => (
          <div
            key={p.n}
            id={`panel-${p.n}`}
            role="tabpanel"
            aria-labelledby={`tab-${p.n}`}
            className={`panel ${i === activo ? 'visible' : ''}`}
          >
            <span className="panel-n">{p.n}</span>
            <h3>{p.titulo}</h3>
            <p className="panel-frase">{p.frase}</p>

            {p.dato && (
              <div className="dato">
                <b>{p.dato.valor}</b>
                <span>{p.dato.pie}</span>
              </div>
            )}

            {p.contraste && (
              <div className="contraste">
                <div className="lado lado-hecho">
                  <Camera size={19} />
                  <span className="lado-et">{p.contraste.hecho.et}</span>
                  <b>{p.contraste.hecho.titulo}</b>
                  <span className="lado-txt">{p.contraste.hecho.texto}</span>
                </div>
                <ArrowRight className="contraste-flecha" size={20} aria-hidden="true" />
                <div className="lado lado-multa">
                  <FileText size={19} />
                  <span className="lado-et">{p.contraste.multa.et}</span>
                  <b>{p.contraste.multa.titulo}</b>
                  <span className="lado-txt">{p.contraste.multa.texto}</span>
                </div>
              </div>
            )}

            <p className="panel-nota">{p.nota}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function ComoFunciona() {
  const { usuario } = useAuth();

  return (
    <div className="vp vp-min vp-doc">
      <nav>
        <div className="nav-in">
          <Link to="/" className="brand">
            <LogoSinConflicto size={34} className="mk" />
            <span className="wordmark"><b>SIN</b><b>CONFLICTO</b></span>
          </Link>
          <div className="nav-right">
            <Link to={usuario ? '/app' : '/login'} className="nav-login">Entrar</Link>
            <Link to="/#demo" className="btn btn-cyan">Ver una demo</Link>
          </div>
        </div>
      </nav>

      <header className="doc-portada">
        <Link to="/" className="volver"><ArrowLeft size={15} /> Volver</Link>
        <h1>Del hecho<br /><span className="acento">al expediente.</span></h1>
        <p>Siete etapas. Tocalas para verlas.</p>
      </header>

      <Recorrido />

      <Banda
        imagen="buzones"
        tono="tono-buzones"
        alt="Fila de buzones metalicos en un hall a oscuras, uno entreabierto con un sobre."
      />

      <ComoFuncionaIA />

      <Banda
        imagen="pasillo"
        tono="tono-pasillo"
        alt="Pasillo vacio de un edificio residencial de noche, alejandose hacia la oscuridad."
      />

      <section className="cierre">
        <div className="cierre-in">
          <h2>Empieza por ver<br /><span className="acento">un caso real.</span></h2>
          <Link to="/#demo" className="btn btn-cyan btn-grande" style={{ marginTop: 34 }}>
            Solicitar una demo <ArrowRight size={18} />
          </Link>
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
