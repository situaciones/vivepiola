import { Link } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { LogoSinConflicto } from '../components/Marca';
import './Landing.css';
import './LandingMinimal.css';
import './ComoFunciona.css';
import './Privacidad.css';

/**
 * Politica de privacidad. La exigen Apple y Google Play, y la tienen que
 * poder leer sin cuenta: por eso es publica y tambien se abre desde la app.
 *
 * LO QUE DICE AQUI TIENE QUE SER VERDAD EN EL CODIGO. Si se agrega un
 * proveedor (por ejemplo WhatsApp) o cambia lo que hace "Eliminar mi cuenta"
 * (Usuario.eliminar_cuenta), esta pagina se actualiza en el mismo cambio.
 */

const CORREO = 'soporte@sinconflicto.cl';
const ACTUALIZADA = '31 de octubre de 2026';

export default function Privacidad() {
  return (
    <div className="vp vp-min vp-doc">
      <nav>
        <div className="nav-in">
          <Link to="/" className="brand">
            <LogoSinConflicto size={34} className="mk" />
            <span className="wordmark"><b>SIN</b><b>CONFLICTO</b></span>
          </Link>
        </div>
      </nav>

      <header className="doc-portada">
        <Link to="/" className="volver"><ArrowLeft size={15} /> Volver</Link>
        <h1>Politica de<br /><span className="acento">privacidad.</span></h1>
        <p>Actualizada el {ACTUALIZADA}.</p>
      </header>

      <article className="privacidad">
        <section>
          <h2>Quien trata tus datos</h2>
          <p>
            SinConflicto (sinconflicto.cl) es una plataforma que usan las comunidades de
            condominios de Chile para llevar el procedimiento de infracciones y multas de la
            Ley 21.442. Cada comunidad, por medio de su administracion, decide a quien da
            acceso y que datos de su registro de copropietarios carga. SinConflicto guarda y
            procesa esos datos por encargo de la comunidad y solo para ese fin.
          </p>
          <p>Para cualquier consulta sobre tus datos escribenos a <a href={`mailto:${CORREO}`}>{CORREO}</a>.</p>
        </section>

        <section>
          <h2>Que datos guardamos</h2>
          <ul>
            <li>
              <b>Tu cuenta:</b> nombre, correo, telefono si lo agregas, tu rol y tu comunidad.
              Si entras con Google, recibimos de Google tu nombre y tu correo; nunca tu contrasena.
            </li>
            <li>
              <b>Registro de copropietarios:</b> nombre, cedula de identidad, domicilio, correo,
              telefono y unidad de propietarios, arrendatarios y ocupantes. Lo carga la
              administracion porque la ley le exige llevarlo.
            </li>
            <li>
              <b>Denuncias y pruebas:</b> la descripcion del hecho, la fecha, la unidad y las fotos
              o videos que adjuntes. Las fotos pueden traer la fecha y la ubicacion en que se
              tomaron; las usamos para acreditar cuando y donde ocurrio el hecho.
            </li>
            <li>
              <b>Descargos y resoluciones:</b> lo que presentas para defenderte, los votos y las
              actas del procedimiento.
            </li>
            <li>
              <b>Notificaciones:</b> a que correo se envio cada aviso, cuando se envio y cuando se
              confirmo su recepcion.
            </li>
            <li>
              <b>Solicitudes de demo:</b> nombre, correo y comunidad de quien la pide en la portada.
            </li>
          </ul>
        </section>

        <section>
          <h2>Para que los usamos</h2>
          <p>
            Solo para que tu comunidad lleve el procedimiento: recibir denuncias, notificar a
            la persona afectada, recibir sus descargos, resolver y dejar constancia de cada
            paso. Tambien para que puedas entrar a tu cuenta y para responder tus consultas.
          </p>
          <p>No vendemos tus datos, no los usamos para publicidad y no te rastreamos fuera de la plataforma.</p>
        </section>

        <section>
          <h2>Con quien los compartimos</h2>
          <p>Dentro de tu comunidad, cada persona ve solo lo que su rol le permite. Fuera de ella, trabajamos con estos proveedores:</p>
          <ul>
            <li><b>Google Cloud:</b> aloja la plataforma y sus archivos, en servidores en Santiago de Chile.</li>
            <li><b>Google:</b> el ingreso con tu cuenta de Google y el analisis de las fotos y videos de una denuncia para describir lo que se ve.</li>
            <li><b>Anthropic:</b> la lectura del texto de las denuncias y de los reglamentos para proponer que norma aplica.</li>
            <li><b>Brevo:</b> el envio de los correos de aviso y notificacion.</li>
          </ul>
          <p>
            Estos proveedores procesan los datos solo para prestar ese servicio. La inteligencia
            artificial no identifica personas en las imagenes ni decide multas: eso lo hacen
            personas de tu comunidad. Tambien entregaremos datos si un tribunal u otra
            autoridad competente lo exige conforme a la ley.
          </p>
        </section>

        <section>
          <h2>Permisos del celular</h2>
          <p>
            La app pide acceso a la camara, al microfono y a tus fotos solo cuando adjuntas una
            prueba a una denuncia o a un descargo. No accede a ellos en ningun otro momento.
          </p>
        </section>

        <section>
          <h2>Cuanto tiempo los guardamos</h2>
          <p>
            Los datos de tu cuenta, mientras la tengas. Las denuncias, pruebas, descargos y
            actas son registros del procedimiento de tu comunidad: se conservan mientras la
            comunidad los necesite para respaldar sus decisiones o la ley lo exija, aunque
            elimines tu cuenta.
          </p>
        </section>

        <section id="eliminar-cuenta">
          <h2>Eliminar tu cuenta</h2>
          <p>
            Puedes eliminarla tu mismo desde la app: entra, toca <b>Mi cuenta</b> y luego
            <b> Eliminar mi cuenta</b>. Tambien puedes pedirlo escribiendo a{' '}
            <a href={`mailto:${CORREO}`}>{CORREO}</a> desde el correo de tu cuenta.
          </p>
          <p>
            Al eliminarla borramos tu nombre, correo y telefono, y la cuenta deja de poder
            entrar. Las denuncias y actuaciones que hiciste quedan en los expedientes de tu
            comunidad, firmadas como "Cuenta eliminada". Tu ficha en el registro de
            copropietarios no se borra, porque la administracion esta obligada a llevarlo;
            para corregirla o darla de baja, habla con tu administracion.
          </p>
        </section>

        <section>
          <h2>Tus derechos</h2>
          <p>
            Conforme a la ley chilena de proteccion de datos personales, puedes pedir acceso a
            tus datos, corregirlos, eliminarlos, oponerte a su tratamiento y recibir una copia.
            Escribenos a <a href={`mailto:${CORREO}`}>{CORREO}</a> y te responderemos dentro de
            los plazos legales. Si se trata de datos del registro de copropietarios, tambien
            puedes dirigirte a la administracion de tu comunidad.
          </p>
        </section>

        <section>
          <h2>Seguridad</h2>
          <p>
            Toda la comunicacion viaja cifrada. El acceso a cada dato depende de tu rol y tu
            comunidad, y las actas del procedimiento quedan selladas para detectar cualquier
            alteracion.
          </p>
        </section>

        <section>
          <h2>Menores de edad</h2>
          <p>La plataforma esta pensada para personas mayores de 18 anos y no esta dirigida a menores.</p>
        </section>

        <section>
          <h2>Cambios a esta politica</h2>
          <p>
            Si la cambiamos, publicaremos la nueva version en esta pagina con su fecha. Si el
            cambio es importante, lo avisaremos tambien dentro de la plataforma.
          </p>
        </section>
      </article>

      <footer>
        <div className="foot-min">
          <LogoSinConflicto size={26} className="mk" />
          <span>Condominios de Chile · Ley 21.442</span>
        </div>
      </footer>
    </div>
  );
}
