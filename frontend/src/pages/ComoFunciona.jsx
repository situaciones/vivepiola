import { useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, ArrowLeft, Camera, FileText } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { LogoVivePiola } from '../components/Marca';
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
 *   5 dias       -> Condominio.plazo_descargo_dias
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
    dato: { valor: '5', pie: 'dias para apelar, desde el acuse' },
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
            <LogoVivePiola size={34} className="mk" />
            <span className="wordmark"><b>VIVE</b><b>PIOLA</b></span>
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

      {/* ---------- Que hace y que no hace la IA ---------- */}
      <section className="doc-ia">
        <div className="doc-ia-in">
          <h2>Que hace la IA<br /><span className="acento">y que no hace.</span></h2>
          <div className="dos-col">
            <div>
              <span className="col-et">Hace</span>
              <ul>
                <li>Lee el reglamento y propone el catalogo, que aprueba una persona.</li>
                <li>Busca el pasaje que corresponde y lo cita.</li>
                <li>Describe lo que se ve en fotos y video.</li>
                <li>Reconoce dos reportes del mismo hecho.</li>
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
          <p className="frase-final">El sistema no decide. Aplica lo que ya estaba escrito.</p>
        </div>
      </section>

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
          <LogoVivePiola size={26} className="mk" />
          <span>Condominios de Chile · Ley 21.442</span>
        </div>
      </footer>
    </div>
  );
}
