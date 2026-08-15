import { Link } from 'react-router-dom';
import { ArrowRight, ArrowLeft } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { LogoVivePiola } from '../components/Marca';
import './Landing.css';
import './LandingMinimal.css';
import './ComoFunciona.css';

/**
 * La pagina que explica el proceso completo.
 *
 * Existe porque la landing tiene que entenderse en diez segundos y esto no
 * cabe ahi. Aqui si se puede entrar en detalle, y por eso se entra con
 * numeros concretos: los plazos, los umbrales y los cupos que el sistema usa
 * de verdad, no adjetivos.
 *
 * TODAS LAS CIFRAS DE ESTA PAGINA SALEN DEL CODIGO:
 *   umbrales 65/80/90 -> settings.CURSE_CONFIANZA_MINIMA
 *   2 cortesias       -> Condominio.cortesias_antes_de_multar
 *   5 dias apelacion  -> Condominio.plazo_descargo_dias
 *   15 dias resolver  -> Condominio.plazo_resolucion_dias
 *   6 meses ventana   -> settings.REINCIDENCIA_VENTANA_MESES
 * Son los valores por defecto y cada comunidad los ajusta. Si alguno cambia
 * en el backend, tiene que cambiar aca: una pagina que promete cinco dias
 * cuando el sistema da tres es un problema legal, no una errata.
 */

const PASOS = [
  {
    n: '01',
    titulo: 'Alguien reporta',
    texto: 'Un vecino, el conserje o el comite. Con fotos o video. Tambien de forma anonima.',
  },
  {
    n: '02',
    titulo: 'Se busca la regla',
    texto: 'En el reglamento de la comunidad, en sus actas y en la normativa de Chile. El sistema devuelve el articulo, con su cita.',
  },
  {
    n: '03',
    titulo: 'Se mide la certeza',
    texto: 'Si no alcanza para el peso de la falta, el expediente para y lo revisa una persona. Nada avanza a medias.',
  },
  {
    n: '04',
    titulo: 'Aviso o multa',
    texto: 'Las primeras faltas de una unidad se avisan sin cobro. Las graves no esperan.',
  },
  {
    n: '05',
    titulo: 'Se notifica',
    texto: 'Correo y WhatsApp, con reintentos. Si nadie confirma, queda la constancia en el buzon de la unidad.',
  },
  {
    n: '06',
    titulo: 'Corre el plazo',
    texto: 'Desde que la persona confirma que recibio. No desde que el sistema envio.',
  },
  {
    n: '07',
    titulo: 'Resuelve el comite',
    texto: 'Si hubo apelacion, la ve el comite y vota. Si no la hubo, la multa queda firme.',
  },
];

const UMBRALES = [
  { grado: 'Leve', valor: 65, nota: 'Un aviso mal puesto se corrige con una disculpa.' },
  { grado: 'Grave', valor: 80, nota: 'Ya hay un cobro de por medio.' },
  { grado: 'Gravisima', valor: 90, nota: 'Cobro inmediato y sin cortesia. El error sale caro.' },
];

const CANALES = [
  { titulo: 'Correo', texto: 'Con el expediente en PDF adjunto y el enlace al buzon.' },
  { titulo: 'WhatsApp', texto: 'El mismo enlace, que abre sin cuenta ni contraseña.' },
  { titulo: 'Buzon de la unidad', texto: 'Constancia impresa cuando nadie confirma por los otros dos.' },
];

/**
 * Banda panoramica a todo el ancho.
 *
 * Son el respiro de una pagina larga: contra una columna de 760px de texto,
 * una imagen de borde a borde corta la lectura sin pedir que la interpreten.
 * Por eso van sin pie ni titulo.
 */
function Banda({ imagen, alt, tono }) {
  return (
    <div className={`banda ${tono}`}>
      <img
        src={`/img/${imagen}.webp`}
        alt={alt}
        width={1800}
        height={771}
        loading="lazy"
        decoding="async"
      />
    </div>
  );
}

function Bloque({ id, sobre, titulo, children, ancho }) {
  return (
    <section id={id} className={`bloque ${ancho ? 'bloque-ancho' : ''}`}>
      <div className="bloque-in">
        {sobre && <span className="sobre">{sobre}</span>}
        <h2>{titulo}</h2>
        {children}
      </div>
    </section>
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

      {/* ---------- Portada ---------- */}
      <header className="doc-portada">
        <Link to="/" className="volver"><ArrowLeft size={15} /> Volver</Link>
        <h1>El proceso,<br /><span className="acento">paso por paso.</span></h1>
        <p>
          Desde que alguien reporta algo hasta que el expediente queda cerrado.
          Con los plazos y los numeros que el sistema usa de verdad.
        </p>
      </header>

      <Banda
        imagen="pasillo"
        tono="tono-pasillo"
        alt="Pasillo vacio de un edificio residencial de noche, alejandose hacia la oscuridad."
      />

      {/* ---------- 1. De donde salen las reglas ---------- */}
      <Bloque sobre="Antes de todo" titulo="De donde salen las reglas">
        <p className="parrafo">
          El sistema no trae un catalogo de faltas propio. Trabaja con tres cosas
          que ya existen, y solo con esas:
        </p>
        <ol className="lista-num">
          <li>
            <b>El reglamento de copropiedad de tu comunidad.</b> Se sube y queda
            como catalogo: cada infraccion con su articulo, su gravedad y su monto.
          </li>
          <li>
            <b>Las actas y acuerdos de asamblea.</b> Lo que la comunidad decidio
            despues del reglamento y tambien obliga.
          </li>
          <li>
            <b>La normativa de Chile.</b> Un corpus comun a todas las comunidades,
            cargado y mantenido por abogados de copropiedad inmobiliaria: la ley,
            su reglamento, circulares y dictamenes.
          </li>
        </ol>
        <p className="parrafo">
          Cuando hay que fundar algo, se busca el pasaje pertinente en esos textos
          y se cita. Ninguna regla la escribe el software.
        </p>
      </Bloque>

      {/* ---------- 2. El ciclo ---------- */}
      <Bloque sobre="El ciclo" titulo="Siete pasos" ancho>
        <ol className="pasos">
          {PASOS.map((p) => (
            <li key={p.n}>
              <span className="paso-n">{p.n}</span>
              <div>
                <h3>{p.titulo}</h3>
                <p>{p.texto}</p>
              </div>
            </li>
          ))}
        </ol>
      </Bloque>

      {/* ---------- 3. La certeza ---------- */}
      <Bloque sobre="Paso 03" titulo="Cuanta certeza se exige" ancho>
        <p className="parrafo">
          Un expediente solo avanza sin revision humana si la propuesta supera el
          umbral que corresponde al peso de la falta. La exigencia sube con lo que
          cuesta equivocarse:
        </p>
        <div className="umbrales">
          {UMBRALES.map((u) => (
            <div key={u.grado} className={`umbral u-${u.grado.toLowerCase()}`}>
              <span className="u-num">{u.valor}</span>
              <b>{u.grado}</b>
              <p>{u.nota}</p>
            </div>
          ))}
        </div>
        <p className="parrafo nota">
          Debajo del umbral el expediente no se descarta: queda <b>en revision</b>,
          y lo tipifica una persona. Tampoco avanza solo si falta el reglamento,
          si no hay un responsable identificado, o si no hay como notificarlo:
          sin notificacion no hay plazo, y sin plazo no hay defensa posible.
        </p>
      </Bloque>

      {/* ---------- 4. Cortesias ---------- */}
      <Bloque sobre="Paso 04" titulo="Primero corregir">
        <p className="cifra"><b>2</b> primeras faltas se avisan sin cobro.</p>
        <p className="parrafo">
          El objetivo de una comunidad no es recaudar: es que la gente sepa que hay
          una norma. Quien la incumple por primera vez casi siempre corrige con el
          aviso. La falta queda igual en el registro —y consume el cupo—, pero el
          monto va en cero.
        </p>
        <p className="parrafo">
          <b>Dos casos nunca admiten cortesia</b>, por muy primera vez que sea: las
          faltas gravisimas, y las que obligan a contener algo porque paraliza el
          edificio o pone a alguien en riesgo. Avisar sin consecuencia frente a un
          riesgo real manda el mensaje contrario.
        </p>
        <p className="parrafo nota">
          Cada comunidad fija su cupo. Con cero, se multa desde la primera.
        </p>
      </Bloque>

      {/* ---------- 5. Notificacion ---------- */}
      <Bloque sobre="Paso 05" titulo="Notificar no es enviar" ancho>
        <p className="parrafo">
          Un correo que se envio y nadie abrio no notifico a nadie. Por eso se
          insiste por tres vias, en este orden:
        </p>
        <div className="canales">
          {CANALES.map((c, i) => (
            <div key={c.titulo} className="canal">
              <span className="canal-n">{i + 1}</span>
              <b>{c.titulo}</b>
              <p>{c.texto}</p>
            </div>
          ))}
        </div>
        <p className="parrafo">
          El enlace lleva a un <b>buzon del residente que abre sin cuenta ni
          contraseña</b>. Ahi esta el expediente completo, el PDF descargable
          cuantas veces quiera, y el boton para apelar. Sin ese detalle, la
          notificacion por WhatsApp excluiria justo a quien no tiene la app.
        </p>
      </Bloque>

      <Banda
        imagen="buzones"
        tono="tono-buzones"
        alt="Fila de buzones metalicos en un hall a oscuras, uno entreabierto con un sobre."
      />

      {/* ---------- 6. El plazo ---------- */}
      <Bloque sobre="Paso 06" titulo="El plazo corre desde el acuse">
        <p className="cifra"><b>5</b> dias para apelar, desde que la persona confirma.</p>
        <p className="parrafo">
          No desde que el sistema envio el mensaje. Si el plazo corriera desde el
          envio, bastaria con que un correo cayera en spam para que alguien
          perdiera su derecho a defenderse sin haberse enterado nunca.
        </p>
        <p className="parrafo">
          Confirmar el recibo y apelar son dos actos distintos, y quedan
          registrados por separado con su fecha, su hora y el canal por el que
          ocurrieron.
        </p>
      </Bloque>

      {/* ---------- 7. La resolucion ---------- */}
      <Bloque sobre="Paso 07" titulo="Quien resuelve">
        <p className="cifra"><b>15</b> dias tiene el comite para responder una apelacion.</p>
        <p className="parrafo">
          El plazo tambien corre para quien resuelve. Sin el, una apelacion puede
          quedar meses sin respuesta y el residente sin saber en que esta.
        </p>
        <p className="parrafo">
          El comite puede convocar una reunion con el residente, dejar el acta y
          votar. Segun el quorum que fije la comunidad, resuelve el primero que
          entre o se acumulan los votos hasta reunir acuerdo. Puede acoger, rechazar
          o rebajar el monto.
        </p>
      </Bloque>

      {/* ---------- 8. Confirmacion previa ---------- */}
      <Bloque sobre="Antes de cobrar" titulo="Cuando alguien mira aunque no haya apelacion">
        <p className="parrafo">
          Revisar todas las multas no apeladas devolveria al comite al papel de
          cuello de botella. Se detienen solo aquellas donde hay una señal concreta
          de que la persona pudo no haber podido defenderse:
        </p>
        <ul className="lista-marca">
          <li>
            El residente figura en el registro con una <b>condicion especial</b>
            —fallecido, con discapacidad, o que requiere apoyo.
          </li>
          <li>
            La notificacion <b>nunca fue confirmada</b> y se perfecciono dejando la
            constancia en el buzon. Pudo estar de viaje, hospitalizado, o
            simplemente no verla.
          </li>
        </ul>
        <p className="parrafo nota">
          En esos dos casos el expediente queda por confirmar y no se cobra hasta
          que una persona lo mira.
        </p>
      </Bloque>

      {/* ---------- 9. Reincidencia ---------- */}
      <Bloque sobre="Sobre el monto" titulo="La reincidencia pesa, pero no para siempre">
        <p className="cifra"><b>6</b> meses es la ventana que se mira hacia atras.</p>
        <p className="parrafo">
          Repetir la misma falta dentro de ese periodo agrava el monto. Fuera de
          la ventana, no: tres faltas de hace cinco años no deberian costarle a
          nadie ni el agravante ni su cortesia.
        </p>
      </Bloque>

      {/* ---------- 10. El expediente ---------- */}
      <Bloque sobre="Al cerrar" titulo="Todo queda escrito">
        <p className="parrafo">
          Cada acto —el reporte, la evidencia, la regla citada, la notificacion,
          el acuse, la apelacion, el acta, cada voto, la resolucion— se registra
          con su fecha, su hora y quien lo hizo.
        </p>
        <p className="parrafo">
          El expediente se cierra <b>sellado en cadena</b>: cada acta lleva la
          huella de la anterior, de modo que alterar un paso pasado rompe la cadena
          entera y se nota. La base de datos misma impide modificarlos.
        </p>
        <p className="parrafo nota">
          Si mañana alguien pregunta por que se cobro esa multa, la respuesta no
          depende de la memoria de nadie.
        </p>
      </Bloque>

      {/* ---------- 11. La IA ---------- */}
      <section className="doc-cierre-ia">
        <div className="doc-cierre-in">
          <h2>Que hace la IA<br /><span className="acento">y que no hace.</span></h2>
          <div className="dos-col">
            <div>
              <span className="col-et">Hace</span>
              <ul>
                <li>Lee el reglamento y propone el catalogo de infracciones, que despues aprueba una persona.</li>
                <li>Busca en las fuentes el pasaje que corresponde y lo cita.</li>
                <li>Describe lo que se ve en las fotos y en el video.</li>
                <li>Reconoce cuando dos reportes hablan del mismo hecho.</li>
              </ul>
            </div>
            <div>
              <span className="col-et">No hace</span>
              <ul>
                <li>No inventa reglas ni montos: los toma del reglamento aprobado.</li>
                <li>No identifica personas en las imagenes ni describe rasgos que permitan reconocerlas.</li>
                <li>No resuelve apelaciones.</li>
                <li>No cobra: eso lo confirma el comite.</li>
              </ul>
            </div>
          </div>
          <p className="frase-final">El sistema no decide. Aplica lo que ya estaba escrito.</p>
        </div>
      </section>

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
