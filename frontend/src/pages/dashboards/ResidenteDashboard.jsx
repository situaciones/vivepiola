import { useEffect, useState } from 'react';
import { Clock3, MessageSquareText, ShieldCheck } from 'lucide-react';
import client, { MEDIA_BASE } from '../../api/client';
import EstadoBadge from '../../components/EstadoBadge';
import EmptyState from '../../components/EmptyState';
import PageHeader from '../../components/PageHeader';
import Semaforo from '../../components/Semaforo';
import AppShell from '../../components/AppShell';
import ProcesoTimeline from '../../components/ProcesoTimeline';
import { useVocab } from '../../vocab';

function CuentaRegresiva({ fechaLimite, t }) {
  const restante = new Date(fechaLimite).getTime() - Date.now();
  if (restante <= 0) {
    return <span className="countdown urgente"><Clock3 size={15} /> {t('countdown_vencido')}</span>;
  }
  const dias = Math.floor(restante / 86400000);
  const horas = Math.floor((restante % 86400000) / 3600000);
  const urgente = dias < 2;
  const cola = t('countdown_texto');
  return (
    <span className={`countdown ${urgente ? 'urgente' : 'normal'}`}>
      <Clock3 size={15} />
      {dias > 0 ? `Quedan ${dias} dia${dias === 1 ? '' : 's'} y ${horas} h ${cola}` : `¡Quedan solo ${horas} horas ${cola}!`}
    </span>
  );
}

export default function ResidenteDashboard() {
  const t = useVocab();
  const [tab, setTab] = useState('multas');
  const [multas, setMultas] = useState([]);
  const [novedades, setNovedades] = useState([]);
  const [textoDescargo, setTextoDescargo] = useState({});
  const [mensaje, setMensaje] = useState('');
  const [nuevaNovedad, setNuevaNovedad] = useState({ tipo: 'RECLAMO', texto: '' });

  const cargarTodo = () => {
    client.get('/multas/').then((res) => setMultas(res.data.results || res.data));
    client.get('/novedades/').then((res) => setNovedades(res.data.results || res.data));
  };

  useEffect(cargarTodo, []);

  // Refresca cada minuto para que la cuenta regresiva del plazo sea dinamica.
  const [, setTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), 60000);
    return () => clearInterval(id);
  }, []);

  const presentarDescargo = async (multaId) => {
    const texto = textoDescargo[multaId];
    if (!texto) {
      setMensaje(`Escribe tu ${t('descargo_min')} antes de enviarlo.`);
      return;
    }
    const formData = new FormData();
    formData.append('texto', texto);
    try {
      await client.post(`/multas/${multaId}/descargo/`, formData, { headers: { 'Content-Type': 'multipart/form-data' } });
      setMensaje(`${t('descargo')} presentado correctamente.`);
      cargarTodo();
    } catch (err) {
      setMensaje(err.response?.data?.detail || `No se pudo presentar el ${t('descargo_min')}.`);
    }
  };

  const crearNovedad = async (e) => {
    e.preventDefault();
    await client.post('/novedades/', nuevaNovedad);
    setNuevaNovedad({ tipo: 'RECLAMO', texto: '' });
    cargarTodo();
  };

  const activas = multas.filter((m) => !['ANULADA', 'RECHAZADA'].includes(m.estado));
  const conPlazoAbierto = multas.filter((m) => m.estado === 'NOTIFICADA' && !m.descargo);
  const novedadesPendientes = novedades.filter((n) => n.estado !== 'RESPONDIDA');

  const nivelSemaforo = multas.some((m) => ['FIRME', 'EXPORTADA'].includes(m.estado))
    ? 'rojo'
    : activas.length > 0
      ? 'ambar'
      : 'verde';

  return (
    <AppShell
      tabs={[
        { id: 'multas', label: t('mis_multas'), icon: ShieldCheck, badge: activas.length },
        { id: 'novedades', label: 'Libro de Novedades', icon: MessageSquareText, badge: novedadesPendientes.length },
      ]}
      active={tab}
      onChange={setTab}
    >
      <div className="contenedor">
        {tab === 'multas' && (
          <>
            <PageHeader
              titulo={t('mis_multas')}
              subtitulo={t('mis_multas_sub')}
              stats={[
                { label: `${t('multa_plural')} activas`, valor: activas.length },
                { label: `Con plazo de ${t('descargo_min')} abierto`, valor: conPlazoAbierto.length, alerta: conPlazoAbierto.length > 0 },
              ]}
            />

            <Semaforo nivel={nivelSemaforo} />

            {mensaje && <div className="mensaje-info">{mensaje}</div>}

            <div className="lista-tarjetas">
              {multas.map((m) => (
                <div key={m.id} className="tarjeta">
                  <div className="tarjeta-header">
                    <strong>{t('multa')} #{m.id} - {m.unidad_identificador}</strong>
                    <EstadoBadge estado={m.estado} />
                  </div>

                  {!['RECHAZADA'].includes(m.estado) && (
                    <div style={{ maxWidth: 340, marginBottom: 12 }}>
                      <ProcesoTimeline multa={m} />
                    </div>
                  )}

                  <p>{m.infraccion_descripcion}</p>
                  {m.monto && <p><strong>Monto:</strong> {m.monto}</p>}
                  {m.infraccion && (
                    <div className="explicacion-ia">
                      <strong>{t('por_que_falta')}</strong> {t('por_que_falta_texto')}
                      {' '}<strong>{m.infraccion_codigo}</strong>
                      {m.infraccion_articulo && <> ({m.infraccion_articulo})</>}.
                      {m.infraccion_texto_fuente && <> Texto de la norma: <em>"{m.infraccion_texto_fuente}"</em></>}
                    </div>
                  )}
                  {m.es_reincidencia && <p className="alerta-reincidencia">{m.agravante_sugerido}</p>}

                  <div className="evidencias-grid">
                    {m.ticket_detalle?.evidencias.map((ev) => (
                      <img key={ev.id} src={`${MEDIA_BASE}${ev.imagen}`} alt="evidencia" />
                    ))}
                  </div>

                  {m.pdf_notificacion && (
                    <a href={`${MEDIA_BASE}${m.pdf_notificacion}`} target="_blank" rel="noreferrer">{t('ver_notificacion_pdf')}</a>
                  )}

                  {m.estado === 'NOTIFICADA' && !m.descargo && (
                    <div className="formulario" style={{ marginTop: 12 }}>
                      <CuentaRegresiva fechaLimite={m.fecha_limite_descargo} t={t} />
                      <textarea
                        rows={2}
                        placeholder={t('descargo_placeholder')}
                        value={textoDescargo[m.id] || ''}
                        onChange={(e) => setTextoDescargo({ ...textoDescargo, [m.id]: e.target.value })}
                      />
                      <button className="btn btn-primario" onClick={() => presentarDescargo(m.id)}>{t('presentar_descargo')}</button>
                    </div>
                  )}

                  {m.descargo && (
                    <div className="resultado-importacion" style={{ marginTop: 12 }}>
                      <p><strong>{t('tu_descargo')}</strong> {m.descargo.texto}</p>
                      <p><strong>Resolucion:</strong> <EstadoBadge estado={m.descargo.resolucion} /> {m.descargo.comentario_resolucion}</p>
                    </div>
                  )}
                </div>
              ))}
              {multas.length === 0 && <EmptyState icon={ShieldCheck} mensaje={`No tienes ${t('multa_plural').toLowerCase()} registradas. ¡Sigue asi!`} />}
            </div>
          </>
        )}

        {tab === 'novedades' && (
          <>
            <PageHeader titulo="Libro de Novedades" subtitulo="Reclamos y solicitudes dirigidos a la administracion, con respuesta garantizada dentro de 20 dias corridos." />

            <form className="tarjeta formulario" onSubmit={crearNovedad} style={{ marginTop: 24 }}>
              <div className="fila-formulario">
                <label>
                  Tipo
                  <select value={nuevaNovedad.tipo} onChange={(e) => setNuevaNovedad({ ...nuevaNovedad, tipo: e.target.value })}>
                    <option value="RECLAMO">Reclamo</option>
                    <option value="SOLICITUD">Solicitud</option>
                    <option value="OBSERVACION">Observacion</option>
                  </select>
                </label>
              </div>
              <label>
                Descripcion
                <textarea rows={2} value={nuevaNovedad.texto} onChange={(e) => setNuevaNovedad({ ...nuevaNovedad, texto: e.target.value })} required />
              </label>
              <button className="btn btn-primario" type="submit" style={{ alignSelf: 'flex-start' }}>Enviar a la administracion</button>
            </form>

            <div className="lista-tarjetas">
              {novedades.map((n) => (
                <div key={n.id} className="tarjeta">
                  <div className="tarjeta-header">
                    <strong>{n.tipo}</strong>
                    <EstadoBadge estado={n.estado} />
                  </div>
                  <p>{n.texto}</p>
                  {n.estado === 'RESPONDIDA' ? (
                    <p><strong>Respuesta:</strong> {n.respuesta_texto}</p>
                  ) : (
                    <p className="texto-secundario">Plazo legal de respuesta: {n.dias_restantes} dias restantes.</p>
                  )}
                </div>
              ))}
              {novedades.length === 0 && <EmptyState icon={MessageSquareText} mensaje="Aun no has enviado novedades." />}
            </div>
          </>
        )}
      </div>
    </AppShell>
  );
}
