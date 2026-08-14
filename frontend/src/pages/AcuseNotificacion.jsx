import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import axios from 'axios';
import { API_URL } from '../api/client';
import { LogoVivePiola } from '../components/Marca';
import './AcuseNotificacion.css';

/**
 * El buzon del residente: su caso completo, SIN iniciar sesion.
 *
 * Aqui aterriza venga del correo, del WhatsApp o de la app, porque los tres
 * canales llevan el mismo enlace firmado. Puede confirmar que recibio la
 * notificacion, leer la norma que le aplican, ver la evidencia, descargar el
 * documento las veces que quiera y apelar.
 *
 * No se le pide cuenta a proposito: quien mas necesita esta puerta es quien no
 * tiene la app ni recuerda una contraseña, y el derecho a defenderse no puede
 * depender de saber usar un software.
 *
 * Se usa axios directo y no el cliente de la app: ese adjunta el token guardado
 * y, si esta vencido, redirige al login. Aqui no puede haber login de por medio.
 */
export default function AcuseNotificacion() {
  const { token } = useParams();
  const [datos, setDatos] = useState(null);
  const [error, setError] = useState('');
  const [enviando, setEnviando] = useState(false);
  const [textoApelacion, setTextoApelacion] = useState('');
  const [abrirApelacion, setAbrirApelacion] = useState(false);

  const base = `${API_URL.replace(/\/$/, '')}/notificaciones`;
  const url = `${base}/acuse/${token}/`;

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

  const apelar = async () => {
    if (!textoApelacion.trim()) return;
    setEnviando(true);
    try {
      const res = await axios.post(`${base}/apelar/${token}/`, { texto: textoApelacion });
      setDatos(res.data);
      setAbrirApelacion(false);
    } catch (err) {
      setError(err.response?.data?.detail || 'No pudimos registrar tu apelacion.');
    }
    setEnviando(false);
  };

  const fecha = (valor) => (valor
    ? new Date(valor).toLocaleDateString('es-CL', { day: '2-digit', month: 'long', year: 'numeric' })
    : '');

  const acciones = datos?.acciones || {};

  return (
    <div className="acuse">
      <div className="acuse-caja">
        <LogoVivePiola size={44} />

        {error && <p className="acuse-error">{error}</p>}
        {!datos && !error && <p className="acuse-cargando">Abriendo tu caso...</p>}

        {datos && (
          <>
            <h1>
              {datos.es_aviso_de_cortesia
                ? 'Aviso de tu comunidad'
                : `Multa #${datos.multa_id}`}
            </h1>

            <dl className="acuse-detalle">
              <div><dt>Comunidad</dt><dd>{datos.organizacion}</dd></div>
              <div><dt>Unidad</dt><dd>{datos.unidad}</dd></div>
              <div><dt>Motivo</dt><dd>{datos.infraccion} {datos.articulo && `(${datos.articulo})`}</dd></div>
              {datos.hecho && <div><dt>Lo reportado</dt><dd>{datos.hecho}</dd></div>}
              {datos.texto_norma && (
                <div><dt>La norma</dt><dd className="acuse-norma">{datos.texto_norma}</dd></div>
              )}
              {datos.evidencias?.length > 0 && (
                <div>
                  <dt>Evidencia</dt>
                  <dd>
                    {datos.evidencias.filter((e) => e.es_video).length} video(s) y
                    {' '}{datos.evidencias.filter((e) => !e.es_video).length} foto(s) en el expediente
                  </dd>
                </div>
              )}
              {datos.es_aviso_de_cortesia ? (
                <div>
                  <dt>Cobro</dt>
                  <dd><b>Sin cobro.</b> Si se repite, la sancion es de {datos.monto_sin_cortesia}.</dd>
                </div>
              ) : (
                datos.monto && (
                  <div><dt>Monto</dt><dd>{datos.monto} {datos.unidad_monto}</dd></div>
                )
              )}
            </dl>

            {acciones.tiene_documento && (
              <a
                className="acuse-documento"
                href={`${base}/documento/${token}/`}
                target="_blank"
                rel="noreferrer"
              >
                Ver o descargar el documento oficial
              </a>
            )}

            {acciones.puede_acusar && (
              <>
                <p className="acuse-aviso">
                  Al confirmar empiezan a correr tus <b>{datos.plazo_dias} dias</b> para apelar si no
                  estas de acuerdo. Antes de que confirmes, el plazo no corre: nadie pierde su
                  defensa por un correo que llego tarde.
                </p>
                <button className="acuse-boton" onClick={confirmar} disabled={enviando}>
                  {enviando ? 'Confirmando...' : 'Confirmo que la recibi'}
                </button>
              </>
            )}

            {datos.ya_acusada && !datos.apelacion && (
              <p className="acuse-aviso">
                Recepcion confirmada.
                {datos.fecha_limite_descargo && (
                  <> Tienes hasta el <b>{fecha(datos.fecha_limite_descargo)}</b> para apelar.</>
                )}
              </p>
            )}

            {datos.apelacion ? (
              <div className="acuse-apelacion-hecha">
                <strong>Tu apelacion quedo registrada</strong>
                <p>{datos.apelacion.texto}</p>
                <p className="acuse-pie">
                  {datos.apelacion.resolucion === 'PENDIENTE'
                    ? 'El comite la esta revisando. Te avisaremos su resolucion.'
                    : `Resolucion: ${datos.apelacion.resolucion}. ${datos.apelacion.comentario || ''}`}
                </p>
              </div>
            ) : acciones.puede_apelar && (
              abrirApelacion ? (
                <div className="acuse-apelacion">
                  <label htmlFor="apelacion">Cuentanos tu version</label>
                  <textarea
                    id="apelacion"
                    rows={5}
                    value={textoApelacion}
                    placeholder="Explica lo que pasó. Si tienes algo que lo respalde, mencionalo."
                    onChange={(e) => setTextoApelacion(e.target.value)}
                  />
                  <button
                    className="acuse-boton"
                    onClick={apelar}
                    disabled={enviando || !textoApelacion.trim()}
                  >
                    {enviando ? 'Enviando...' : 'Enviar mi apelacion'}
                  </button>
                </div>
              ) : (
                <button
                  className="acuse-boton acuse-boton-secundario"
                  onClick={() => setAbrirApelacion(true)}
                >
                  No estoy de acuerdo, quiero apelar
                </button>
              )
            )}

            <p className="acuse-pie">
              Puedes volver a este enlace cuando quieras: aqui queda tu caso, el documento y el
              estado de tu apelacion. Si no puedes usar este medio, avisale a la administracion:
              tu derecho a defenderte no depende de la app.
            </p>
          </>
        )}
      </div>
    </div>
  );
}
