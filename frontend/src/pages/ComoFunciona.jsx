import { useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, ArrowLeft } from 'lucide-react';
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
    tab: 'Reporte',
    titulo: 'Alguien reporta',
    frase: 'Un vecino, el conserje o el comite. Con fotos o video, y tambien de forma anonima.',
    dato: { valor: '1', pie: 'hecho, aunque lo reporten cinco personas' },
    nota: 'El sistema reconoce cuando varios reportes hablan de lo mismo.',
  },
  {
    n: '02',
    tab: 'Regla',
    titulo: 'Aparece la regla',
    frase: 'Se busca en tu reglamento de copropiedad, en las actas de asamblea y en la normativa de Chile.',
    dato: { valor: 'Art.', pie: 'la cita exacta, no un resumen' },
    nota: 'Ninguna regla la escribe el software.',
  },
  {
    n: '03',
    tab: 'Certeza',
    titulo: 'Se mide la certeza',
    frase: 'Un expediente solo avanza solo si la propuesta supera el umbral que corresponde al peso de la falta.',
    umbrales: [
      { grado: 'Leve', valor: 65 },
      { grado: 'Grave', valor: 80 },
      { grado: 'Gravisima', valor: 90 },
    ],
    nota: 'Debajo del umbral no se descarta: lo revisa una persona.',
  },
  {
    n: '04',
    tab: 'Aviso',
    titulo: 'Aviso o multa',
    frase: 'Las primeras faltas de una unidad se avisan sin cobro. La falta queda en el registro, el monto va en cero.',
    dato: { valor: '2', pie: 'cortesias antes de empezar a cobrar' },
    nota: 'Las gravisimas y las de riesgo no esperan.',
  },
  {
    n: '05',
    tab: 'Notificacion',
    titulo: 'Se notifica',
    frase: 'Correo y WhatsApp, con reintentos. Si nadie confirma, queda la constancia en el buzon de la unidad.',
    dato: { valor: '3', pie: 'canales, hasta que alguien confirme' },
    nota: 'El enlace abre sin cuenta ni contraseña.',
  },
  {
    n: '06',
    tab: 'Plazo',
    titulo: 'Corre el plazo',
    frase: 'Empieza cuando la persona confirma que recibio. No cuando el sistema envio.',
    dato: { valor: '5', pie: 'dias para apelar, desde el acuse' },
    nota: 'Si corriera desde el envio, un correo en spam costaria la defensa.',
  },
  {
    n: '07',
    tab: 'Resolucion',
    titulo: 'Resuelve el comite',
    frase: 'Puede acoger, rechazar o rebajar el monto. Si no hubo apelacion, la multa queda firme.',
    dato: { valor: '15', pie: 'dias tiene el comite para responder' },
    nota: 'El plazo tambien corre para quien resuelve.',
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

            {p.umbrales && (
              <div className="umbrales">
                {p.umbrales.map((u) => (
                  <div key={u.grado} className={`umbral u-${u.grado.toLowerCase()}`}>
                    <b>{u.valor}</b>
                    <span>{u.grado}</span>
                  </div>
                ))}
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
        <h1>Del reclamo<br /><span className="acento">al expediente.</span></h1>
        <p>Siete pasos. Tocalos para verlos.</p>
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
