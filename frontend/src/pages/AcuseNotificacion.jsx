import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import axios from 'axios';
import { API_URL } from '../api/client';
import { LogoVivePiola } from '../components/Marca';
import './AcuseNotificacion.css';

/**
 * Confirmacion de recepcion de una notificacion de multa, SIN iniciar sesion.
 *
 * Quien mas necesita esta pagina es quien no tiene la app ni recuerda una
 * contraseña, asi que no se le pide nada: llega por el enlace del correo, ve
 * de que se trata y confirma con un boton. Ese clic es lo que hace correr el
 * plazo para defenderse, asi que la pagina lo dice con todas sus letras.
 *
 * Se usa axios directo y no el cliente de la app a proposito: el cliente
 * adjunta el token guardado y, si esta vencido, redirige al login. Aqui no
 * puede haber login de por medio.
 */
export default function AcuseNotificacion() {
  const { token } = useParams();
  const [datos, setDatos] = useState(null);
  const [error, setError] = useState('');
  const [enviando, setEnviando] = useState(false);

  const url = `${API_URL.replace(/\/$/, '')}/notificaciones/acuse/${token}/`;

  useEffect(() => {
    axios.get(url)
      .then((res) => setDatos(res.data))
      .catch((err) => setError(
        err.response?.data?.detail
        || 'No pudimos abrir esta notificacion. Revisa el enlace del correo.',
      ));
  }, [url]);

  const confirmar = async () => {
    setEnviando(true);
    try {
      const res = await axios.post(url);
      setDatos(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'No pudimos registrar la confirmacion.');
    }
    setEnviando(false);
  };

  const fecha = (valor) => (valor
    ? new Date(valor).toLocaleDateString('es-CL', { day: '2-digit', month: 'long', year: 'numeric' })
    : '');

  return (
    <div className="acuse">
      <div className="acuse-caja">
        <LogoVivePiola size={44} />

        {error && <p className="acuse-error">{error}</p>}

        {!datos && !error && <p className="acuse-cargando">Abriendo la notificacion...</p>}

        {datos && !datos.ya_acusada && (
          <>
            <h1>Confirma que recibiste esta notificacion</h1>
            <dl className="acuse-detalle">
              <div><dt>Comunidad</dt><dd>{datos.organizacion}</dd></div>
              <div><dt>Unidad</dt><dd>{datos.unidad}</dd></div>
              <div><dt>Motivo</dt><dd>{datos.infraccion} {datos.articulo && `(${datos.articulo})`}</dd></div>
              {datos.monto && (
                <div><dt>Monto</dt><dd>{datos.monto} {datos.unidad_monto}</dd></div>
              )}
            </dl>
            <p className="acuse-aviso">
              Al confirmar empiezan a correr tus <b>{datos.plazo_dias} dias</b> para apelar si no estas
              de acuerdo. Antes de que confirmes, el plazo no corre: nadie pierde su defensa por un
              correo que llego tarde.
            </p>
            <button className="acuse-boton" onClick={confirmar} disabled={enviando}>
              {enviando ? 'Confirmando...' : 'Confirmo que la recibi'}
            </button>
          </>
        )}

        {datos && datos.ya_acusada && (
          <>
            <h1>Recepcion confirmada</h1>
            <p className="acuse-ok">
              Quedo registrado que recibiste la notificacion de la multa
              {' '}#{datos.multa_id} de {datos.organizacion}.
            </p>
            {datos.fecha_limite_descargo && (
              <p className="acuse-aviso">
                Tienes hasta el <b>{fecha(datos.fecha_limite_descargo)}</b> para presentar tu apelacion.
              </p>
            )}
            <p className="acuse-pie">
              Para apelar, entra a la aplicacion de tu comunidad. Si no puedes hacerlo por este medio,
              avisale a la administracion: tu derecho a defenderte no depende de la app.
            </p>
          </>
        )}
      </div>
    </div>
  );
}
