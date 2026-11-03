import { useEffect, useState } from 'react';
import { AlertTriangle, ArrowLeft, BookMarked, CheckCircle2, Inbox, PenLine, ShieldCheck, Siren, Sparkles, UserPlus } from 'lucide-react';
import client, { MEDIA_BASE } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import EstadoBadge from '../../components/EstadoBadge';
import EmptyState from '../../components/EmptyState';
import PageHeader from '../../components/PageHeader';
import AppShell from '../../components/AppShell';
import ProcesoTimeline from '../../components/ProcesoTimeline';
import QuorumBar from '../../components/QuorumBar';
import HoldToConfirm from '../../components/HoldToConfirm';
import DrawerDelegacion from '../../components/DrawerDelegacion';
import { useVocab } from '../../vocab';

const REINCIDENCIA_MESES = 6;
// Un parte de cortesia tambien cuenta: su sentido es avisar que la proxima vez
// se cobra. Debe coincidir con verificar_reincidencia del backend.
const ESTADOS_SANCIONADOS = [
  'APROBADA', 'NOTIFICADA', 'CON_DESCARGO', 'FIRME', 'EXPORTADA', 'CORTESIA',
];

/**
 * Vista previa de reincidencia en el cliente, calculada al vuelo mientras el
 * Comite todavia esta decidiendo (antes de aprobar). El backend vuelve a
 * calcularla de forma autoritativa al momento de aprobar; esto es solo para
 * que el Comite vea la alerta y pueda ajustar el monto antes de confirmar.
 */
function buscarReincidenciaPreview(multaActiva, infraccionId, todasLasMultas) {
  if (!infraccionId) return null;
  const limite = Date.now() - REINCIDENCIA_MESES * 30 * 86400000;
  const candidatas = todasLasMultas.filter((m) =>
    m.id !== multaActiva.id &&
    m.unidad === multaActiva.unidad &&
    m.infraccion === Number(infraccionId) &&
    ESTADOS_SANCIONADOS.includes(m.estado) &&
    // Las multas que se cursan solas no tienen fecha_aprobacion, porque nadie
    // las aprobo. Mirar solo esa fecha las dejaba fuera del conteo.
    (m.fecha_aprobacion || m.fecha_notificacion) &&
    new Date(m.fecha_aprobacion || m.fecha_notificacion).getTime() >= limite,
  );
  if (candidatas.length === 0) return null;
  const cuando = (m) => new Date(m.fecha_aprobacion || m.fecha_notificacion);
  candidatas.sort((a, b) => cuando(a) - cuando(b));
  return candidatas[0];
}

export default function ComiteDashboard() {
  const t = useVocab();
  const { usuario } = useAuth();
  const [drawerAbierto, setDrawerAbierto] = useState(false);
  const [tab, setTab] = useState('bandeja');
  const [multas, setMultas] = useState([]);
  const [infracciones, setInfracciones] = useState([]);
  const [borradores, setBorradores] = useState([]);
  // Opciones que sugiere el sistema para el caso abierto, con su fundamento.
  const [propuestas, setPropuestas] = useState([]);
  // /app?multa=12 llega desde el link del aviso: se abre ese expediente.
  const [seleccionId, setSeleccionId] = useState(() => {
    const pedida = new URLSearchParams(window.location.search).get('multa');
    return pedida ? Number(pedida) : null;
  });
  const [decision, setDecision] = useState({}); // { [multaId]: { infraccion_id, monto, revisado } }
  const [verificacion, setVerificacion] = useState(null); // { multaId, data }
  const [mensaje, setMensaje] = useState('');
  // Si el mandato vencio o falta el acta, se avisa arriba: las decisiones las rechaza el backend.
  const [comite, setComite] = useState(null);
  const [formInfraccion, setFormInfraccion] = useState({ codigo: '', descripcion: '', articulo_referencia: '', monto: '', unidad_monto: 'UF', gravedad: 'LEVE', conlleva_contencion: false, plazo_ratificacion_horas: 24 });

  const [medidas, setMedidas] = useState([]);
  const [levantamiento, setLevantamiento] = useState({}); // { [medidaId]: { causal, fundamento } }

  const cargarTodo = () => {
    client.get('/multas/').then((res) => setMultas(res.data.results || res.data));
    client.get('/infracciones/?estado=ACTIVA').then((res) => setInfracciones(res.data.results || res.data));
    client.get('/infracciones/?estado=BORRADOR').then((res) => setBorradores(res.data.results || res.data));
    client.get('/medidas-inmediatas/').then((res) => setMedidas(res.data.results || res.data));
  };

  useEffect(cargarTodo, []);
  useEffect(() => { client.get('/comite/').then((r) => setComite(r.data)).catch(() => {}); }, []);

  // Las propuestas se piden por caso: dependen del historial de esa unidad.
  useEffect(() => {
    const caso = [...multas].find((m) => m.id === seleccionId) || null;
    if (!caso || caso.estado !== 'CON_DESCARGO') {
      setPropuestas([]);
      return;
    }
    client.get(`/multas/${caso.id}/propuestas-resolucion/`)
      .then((res) => setPropuestas(res.data.opciones || []))
      .catch(() => setPropuestas([]));
  }, [seleccionId, multas]);

  const ratificarMedida = async (id) => {
    try {
      const res = await client.post(`/medidas-inmediatas/${id}/ratificar/`);
      const m = res.data;
      if (m.estado === 'RATIFICADA') {
        setMensaje(`Firma registrada. Quorum completo (${m.votos_emitidos}/${m.quorum_requerido}): contencion ratificada.`);
      } else {
        setMensaje(`Tu firma quedo sellada. Faltan ${m.quorum_requerido - m.votos_emitidos} firma(s) para completar el quorum.`);
      }
      cargarTodo();
    } catch (err) {
      setMensaje(err.response?.data?.detail || 'No se pudo registrar tu firma.');
    }
  };

  const levantarMedida = async (id) => {
    const datos = levantamiento[id] || {};
    if (!datos.causal || !datos.fundamento?.trim()) {
      setMensaje('Levantar una contencion exige causal y fundamento escrito.');
      return;
    }
    try {
      await client.post(`/medidas-inmediatas/${id}/levantar/`, datos);
      setMensaje(`Medida #${id} levantada con causal ${datos.causal}. Queda sellada con tu nombre.`);
      cargarTodo();
    } catch (err) {
      setMensaje(err.response?.data?.detail || 'No se pudo levantar la medida.');
    }
  };

  const enRevision = multas.filter((m) => m.estado === 'EN_REVISION');
  const conDescargo = multas.filter((m) => m.estado === 'CON_DESCARGO');
  // Vencieron sin apelacion, pero traian una señal de que la persona pudo no
  // haber podido defenderse. Solo hay que confirmar, no volver a estudiarlas.
  const porConfirmar = multas.filter((m) => m.estado === 'POR_CONFIRMAR');
  const pendientes = [...enRevision, ...conDescargo, ...porConfirmar];

  const activa = pendientes.find((m) => m.id === seleccionId) || pendientes[0] || null;
  // Si el sistema ya encuadro el caso, la infraccion propuesta viene marcada:
  // el Comite solo la revisa y vota.
  const datosActiva = activa
    ? { infraccion_id: activa.estado === 'EN_REVISION' ? activa.infraccion || '' : '', ...(decision[activa.id] || {}) }
    : {};
  const votacion = activa?.aprobacion_comite;
  const infraccionElegida = infracciones.find((i) => i.id === Number(datosActiva.infraccion_id));
  const reincidenciaPreview = activa && infraccionElegida
    ? buscarReincidenciaPreview(activa, datosActiva.infraccion_id, multas)
    : null;

  const setDatoActiva = (campo, valor) => {
    setDecision({ ...decision, [activa.id]: { ...datosActiva, [campo]: valor } });
  };

  const verificarIntegridad = async () => {
    try {
      const res = await client.get(`/multas/${activa.id}/verificar-integridad/`);
      setVerificacion({ multaId: activa.id, data: res.data });
    } catch {
      setMensaje('No se pudo ejecutar la verificacion de integridad.');
    }
  };

  const descargarAuditTrail = async () => {
    try {
      const res = await client.get(`/multas/${activa.id}/audit-trail/`, { responseType: 'blob' });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = `audit_trail_expediente_${activa.id}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setMensaje('El expediente aun no tiene actos sellados que certificar.');
    }
  };

  const aprobar = async () => {
    if (!datosActiva.infraccion_id) {
      setMensaje('Selecciona una infraccion del catalogo antes de cursar.');
      return;
    }
    try {
      const res = await client.post(`/multas/${activa.id}/aprobar/`, {
        infraccion_id: Number(datosActiva.infraccion_id),
        ...(datosActiva.monto ? { monto: datosActiva.monto } : {}),
      });
      if (res.data.resultado_votacion === 'APROBADA') {
        setMensaje(`Multa #${activa.id} aprobada por mayoria del Comite. Pasa a la administracion para notificarla.`);
        setSeleccionId(null);
      } else {
        const faltan = res.data.votos_requeridos - res.data.votos;
        setMensaje(`Tu voto quedo sellado. Faltan ${faltan} voto(s) iguales del Comite para aplicar la multa.`);
      }
      cargarTodo();
    } catch (err) {
      setMensaje(err.response?.data?.detail || 'No se pudo cursar el expediente.');
    }
  };

  // Un posible duplicado se decide antes de tipificar: unirlo al caso
  // original (mismo hecho) o dejarlo seguir (hecho distinto).
  const resolverDuplicado = async (mismoHecho) => {
    try {
      await client.post(`/multas/${activa.id}/resolver-duplicado/`, { mismo_hecho: mismoHecho });
      setMensaje(mismoHecho
        ? `Expediente #${activa.id} unido al #${activa.posible_duplicado.id} como el mismo hecho.`
        : `Expediente #${activa.id} sigue como un hecho distinto: ya puedes tipificarlo.`);
      if (mismoHecho) setSeleccionId(null);
      cargarTodo();
    } catch (err) {
      setMensaje(err.response?.data?.detail || 'No se pudo registrar la decision.');
    }
  };

  const rechazar = async () => {
    const motivo = prompt('Motivo para no aplicar la multa (queda en el historial):');
    if (!motivo) return;
    try {
      const res = await client.post(`/multas/${activa.id}/rechazar/`, { motivo });
      if (res.data.resultado_votacion === 'RECHAZADA') {
        setMensaje(`Expediente #${activa.id} descartado por mayoria del Comite.`);
        setSeleccionId(null);
      } else {
        setMensaje(`Tu voto quedo sellado. Faltan ${res.data.votos_requeridos - res.data.votos} voto(s) para descartarlo.`);
      }
      cargarTodo();
    } catch (err) {
      setMensaje(err.response?.data?.detail || 'No se pudo registrar tu voto.');
    }
  };

  const resolverDescargo = async (resolucion, porcentaje_descuento = null) => {
    const comentario = prompt(`Comentario de la resolucion (${resolucion}):`) || '';
    const cuerpo = { resolucion, comentario };
    if (porcentaje_descuento) cuerpo.porcentaje_descuento = porcentaje_descuento;
    const res = await client.post(`/multas/${activa.id}/resolver-descargo/`, cuerpo);

    // 202 = el voto quedo sellado pero la comunidad exige acuerdo y todavia no
    // se reune. El caso sigue abierto, asi que no se cierra el panel.
    if (res.status === 202) {
      setMensaje(res.data.detail);
      cargarTodo();
      return;
    }

    setMensaje(
      // eslint-disable-next-line no-nested-ternary
      porcentaje_descuento
        ? `Descargo de multa #${activa.id} resuelto con ${porcentaje_descuento}% de descuento.`
        : resolucion === 'CORTESIA'
          ? `Multa #${activa.id} resuelta como parte de cortesia: la falta queda en el registro, sin cobro.`
          : `Descargo de multa #${activa.id} resuelto: ${resolucion}.`,
    );
    setSeleccionId(null);
    cargarTodo();
  };

  // Un formulario no siempre alcanza: hay explicaciones que se entienden
  // hablando. Citar extiende el plazo que tiene el Comite para resolver.
  const convocarReunion = async (modalidad) => {
    const fecha = prompt('Fecha y hora de la reunion (AAAA-MM-DD HH:MM):');
    if (!fecha) return;
    const lugar = prompt(
      modalidad === 'ONLINE' ? 'Enlace de la videollamada:' : 'Lugar de la reunion:',
    );
    if (!lugar) return;
    try {
      await client.post(`/multas/${activa.id}/convocar-reunion/`, {
        modalidad,
        fecha_propuesta: new Date(fecha.replace(' ', 'T')).toISOString(),
        lugar_o_enlace: lugar,
      });
      setMensaje('Reunion convocada. El plazo para resolver se extendio hasta despues de la cita.');
      cargarTodo();
    } catch (err) {
      setMensaje(err.response?.data?.detail || 'No se pudo convocar la reunion.');
    }
  };

  const registrarActa = async () => {
    const acta = prompt('Que se expuso en la reunion:');
    if (!acta) return;
    try {
      await client.post(`/multas/${activa.id}/acta-reunion/`, { acta });
      setMensaje('Acta registrada: lo conversado quedo en el expediente.');
      cargarTodo();
    } catch (err) {
      setMensaje(err.response?.data?.detail || 'No se pudo registrar el acta.');
    }
  };

  // Ultima confirmacion antes del cobro. No se reabre el fondo del caso: se
  // pregunta solo si corresponde cobrarle a alguien que quiza no pudo defenderse.
  const confirmarCobro = async (dar_cortesia) => {
    const comentario = prompt(
      dar_cortesia
        ? 'Motivo para dar parte de cortesia:'
        : 'Comentario (opcional) para confirmar el cobro:',
    );
    if (dar_cortesia && !comentario) return;
    await client.post(`/multas/${activa.id}/confirmar-cobro/`, { dar_cortesia, comentario: comentario || '' });
    setMensaje(
      dar_cortesia
        ? `Multa #${activa.id} convertida en parte de cortesia: no se cobra.`
        : `Cobro de la multa #${activa.id} confirmado.`,
    );
    setSeleccionId(null);
    cargarTodo();
  };

  // Descuento parcial: la multa queda firme, pero con el monto rebajado.
  const resolverConDescuento = async () => {
    const ingresado = prompt('Porcentaje de descuento a aplicar (1-99):', '30');
    if (!ingresado) return;
    const porcentaje = parseInt(ingresado, 10);
    if (Number.isNaN(porcentaje) || porcentaje < 1 || porcentaje > 99) {
      setMensaje('El descuento debe ser un numero entre 1 y 99.');
      return;
    }
    await resolverDescargo('DESCUENTO', porcentaje);
  };

  const confirmarInfraccion = async (id) => {
    try {
      await client.post(`/infracciones/${id}/confirmar/`);
    } catch (err) {
      setMensaje(err.response?.data?.detail || 'No se pudo confirmar la infraccion.');
      return;
    }
    cargarTodo();
  };

  const rechazarInfraccion = async (id) => {
    await client.post(`/infracciones/${id}/rechazar/`);
    cargarTodo();
  };

  const crearInfraccion = async (e) => {
    e.preventDefault();
    const datos = { ...formInfraccion, estado: 'ACTIVA' };
    if (!datos.monto_minimo) delete datos.monto_minimo;
    if (!datos.monto_maximo) delete datos.monto_maximo;
    try {
      await client.post('/infracciones/', datos);
    } catch (err) {
      const d = err.response?.data || {};
      setMensaje(d.detail || d.articulo_referencia?.[0] || d.monto_minimo?.[0] || d.monto_maximo?.[0] || 'No se pudo agregar la infraccion.');
      return;
    }
    setFormInfraccion({ codigo: '', descripcion: '', articulo_referencia: '', monto: '', unidad_monto: 'UF', gravedad: 'LEVE', conlleva_contencion: false, plazo_ratificacion_horas: 24 });
    cargarTodo();
  };

  // En el telefono el expediente es su propia pantalla: volver lo cierra y
  // muestra la bandeja. Devuelve true si atendio el "atras" de Android.
  const volverABandeja = () => {
    if (tab !== 'bandeja' || seleccionId == null) return false;
    setSeleccionId(null);
    window.scrollTo({ top: 0 });
    return true;
  };

  return (
    <AppShell
      tabs={[
        { id: 'bandeja', corto: 'Bandeja', label: 'Bandeja de decision', icon: Inbox, badge: pendientes.length },
        { id: 'contenciones', corto: 'Medidas', label: t('contenciones'), icon: Siren, badge: medidas.filter((m) => m.estado === 'EJECUTADA' || m.estado === 'EN_ESCALAMIENTO').length },
        { id: 'borradores', corto: 'Borradores', label: 'Borradores IA', icon: Sparkles, badge: borradores.length },
        { id: 'catalogo', corto: 'Catalogo', label: t('catalogo'), icon: BookMarked },
      ]}
      active={tab}
      onChange={setTab}
      onAtras={volverABandeja}
    >
      <div className="contenedor">
        {comite && !comite.vigente && !comite.sin_designacion && (
          <div className="mensaje-error">{comite.motivo} Mientras tanto el Comite no puede tomar decisiones en la plataforma.</div>
        )}
        {comite?.sin_designacion && (
          <div className="mensaje-info">El Comite aun no tiene registrada el acta de la asamblea que lo eligio. Pidele al Administrador que la registre en Equipo y accesos.</div>
        )}
        {mensaje && <div className="mensaje-info">{mensaje}</div>}

        {tab === 'bandeja' && (
          <>
            <PageHeader
              titulo="Bandeja de decision"
              subtitulo="Aqui llegan las apelaciones de los residentes y los casos que el sistema no pudo tipificar solo. Compara la evidencia con el articulo aplicable antes de decidir."
              stats={[
                { label: 'Sin tipificar', valor: enRevision.length, alerta: enRevision.length > 0 },
                { label: 'Apelaciones por resolver', valor: conDescargo.length, alerta: conDescargo.length > 0 },
                { label: 'Por confirmar antes del cobro', valor: porConfirmar.length, alerta: porConfirmar.length > 0 },
                { label: 'Infracciones activas', valor: infracciones.length },
              ]}
            />

            {pendientes.length === 0 ? (
              <div style={{ marginTop: 24 }}>
                <EmptyState icon={CheckCircle2} mensaje="No hay casos pendientes de decision. La bandeja esta al dia." />
              </div>
            ) : (
              <div className={`split${seleccionId != null ? ' con-detalle' : ''}`} style={{ marginTop: 24 }}>
                <div className="split-lista">
                  {pendientes.map((m) => (
                    <button
                      key={m.id}
                      type="button"
                      className={`split-item${activa?.id === m.id ? ' activo' : ''}`}
                      onClick={() => {
                        setSeleccionId(m.id);
                        window.scrollTo({ top: 0 });
                      }}
                    >
                      <span className="titulo">
                        {t('multa')} #{m.id} · {m.unidad_identificador}
                        <EstadoBadge estado={m.estado} />
                      </span>
                      <span className="resumen">{m.ticket_detalle?.descripcion}</span>
                    </button>
                  ))}
                </div>

                {activa && (
                  <div className="split-detalle">
                    <button type="button" className="btn btn-fantasma volver-bandeja" onClick={volverABandeja}>
                      <ArrowLeft size={18} /> Bandeja
                    </button>
                    <div className="tarjeta">
                      <div className="tarjeta-header">
                        <strong>{t('multa')} #{activa.id} - {activa.unidad_identificador}</strong>
                        <EstadoBadge estado={activa.estado} />
                      </div>

                      <dl className="metadatos-caso">
                        <div>
                          <dt>{t('unidad')}</dt>
                          <dd>{activa.unidad_identificador}</dd>
                        </div>
                        <div>
                          <dt>{t('residente')}</dt>
                          <dd>{activa.persona_nombre || 'Sin identificar'}</dd>
                        </div>
                        <div>
                          <dt>Reportado por</dt>
                          <dd>{activa.ticket_detalle?.creado_por_nombre || '—'}</dd>
                        </div>
                        <div>
                          <dt>Fecha / hora</dt>
                          <dd>{new Date(activa.ticket_detalle?.fecha_hecho).toLocaleString('es-CL', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}</dd>
                        </div>
                      </dl>

                      {!activa.persona_nombre && (
                        <p className="alerta-reincidencia">
                          Sin persona reportada: pide al denunciante identificar al infractor antes de cursar.
                        </p>
                      )}

                      <blockquote className="cita-reporte">
                        "{activa.ticket_detalle?.descripcion}"
                        <footer>— {activa.ticket_detalle?.creado_por_nombre || 'Denunciante'}, denuncia</footer>
                      </blockquote>

                      {activa.estado === 'EN_REVISION' && activa.posible_duplicado && !activa.duplicado_revisado && (
                        <div className="tarjeta" style={{ borderColor: 'var(--ambar, #b46d00)', background: '#fff8ec' }}>
                          <strong>¿Es el mismo hecho del expediente #{activa.posible_duplicado.id}?</strong>
                          <p className="texto-secundario" style={{ margin: '6px 0 10px' }}>
                            Es de la misma unidad y cercano en el tiempo, pero no calza lo bastante para juntarlos solo.
                            Decide antes de tipificar: unirlos evita sancionar dos veces; separarlos evita dejar una falta sin sancion.
                          </p>
                          <blockquote className="cita-reporte" style={{ margin: '0 0 10px' }}>
                            "{activa.posible_duplicado.descripcion}"
                            <footer>
                              — expediente #{activa.posible_duplicado.id}
                              {activa.posible_duplicado.fecha_hecho ? `, ${new Date(activa.posible_duplicado.fecha_hecho).toLocaleString('es-CL')}` : ''}
                              {activa.posible_duplicado.infraccion_descripcion ? ` · ${activa.posible_duplicado.infraccion_descripcion}` : ''}
                              {activa.posible_duplicado.reportes > 1 ? ` · ${activa.posible_duplicado.reportes} reportes` : ''}
                            </footer>
                          </blockquote>
                          <p className="texto-secundario" style={{ margin: '0 0 10px' }}>
                            Este reporte: {activa.ticket_detalle?.fecha_hecho ? new Date(activa.ticket_detalle.fecha_hecho).toLocaleString('es-CL') : ''}
                          </p>
                          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                            <button className="btn btn-primario" type="button" onClick={() => resolverDuplicado(true)}>
                              Es el mismo hecho: unir
                            </button>
                            <button className="btn btn-secundario" type="button" onClick={() => resolverDuplicado(false)}>
                              Es otro hecho: seguir por separado
                            </button>
                          </div>
                        </div>
                      )}

                      {activa.estado === 'EN_REVISION' && activa.propuesta_fundamento && (
                        <div className="propuesta-automatica">
                          <div className="propuesta-cabecera">
                            <Sparkles size={14} />
                            <strong>
                              {activa.propuesta_origen === 'IA'
                                ? 'Analisis automatico'
                                : 'Coincidencia de terminos'}
                            </strong>
                            {activa.propuesta_confianza > 0 && (
                              <span className="propuesta-confianza">
                                {activa.propuesta_confianza}% de confianza
                              </span>
                            )}
                          </div>
                          <p>{activa.propuesta_fundamento}</p>
                          <span className="propuesta-nota">
                            Es una propuesta: la decision es tuya. Puedes cambiar la infraccion o rechazar el reporte.
                          </span>
                        </div>
                      )}

                      {activa.estado === 'EN_REVISION' && (
                        <>
                          <div className="panel-comparacion">
                            <div className="panel-evidencia">
                              <h4>Evidencia del hecho</h4>
                              <p className="texto-secundario">
                                {activa.ticket_detalle?.ubicacion}
                              </p>
                              <div className="evidencias-grid">
                                {activa.ticket_detalle?.evidencias.map((ev) => (
                                  <img key={ev.id} src={`${MEDIA_BASE}${ev.imagen}`} alt="evidencia" />
                                ))}
                              </div>
                              {activa.ticket_detalle?.evidencias.length === 0 && (
                                <p className="texto-secundario">Sin fotografias adjuntas.</p>
                              )}
                            </div>
                            <div className="panel-articulo">
                              <h4>Articulo del reglamento</h4>
                              {infraccionElegida ? (
                                <>
                                  <p><strong>{infraccionElegida.codigo}</strong> · {infraccionElegida.articulo_referencia || 'Sin articulo asociado'}</p>
                                  <p>{infraccionElegida.descripcion}</p>
                                  {infraccionElegida.texto_fuente && (
                                    <blockquote className="cita-fuente">"{infraccionElegida.texto_fuente}"</blockquote>
                                  )}
                                  <p><strong>Multa base:</strong> {infraccionElegida.monto} {infraccionElegida.unidad_monto} · {infraccionElegida.gravedad}</p>
                                </>
                              ) : (
                                <p className="texto-secundario">Selecciona una infraccion para ver el articulo aplicable y compararlo con la evidencia.</p>
                              )}
                            </div>
                          </div>

                          <label style={{ marginBottom: 4 }}>Selecciona la infraccion del catalogo</label>
                          <div className="catalogo-opciones">
                            {infracciones.map((i) => (
                              <label key={i.id} className={`catalogo-opcion${Number(datosActiva.infraccion_id) === i.id ? ' seleccionada' : ''}`}>
                                <input
                                  type="radio"
                                  name={`infraccion-${activa.id}`}
                                  checked={Number(datosActiva.infraccion_id) === i.id}
                                  onChange={() => setDatoActiva('infraccion_id', i.id)}
                                />
                                <span className="codigo">{i.codigo}</span>
                                <span className="descripcion">{i.descripcion} · {i.articulo_referencia || 'sin articulo'}</span>
                                <span className="monto">{i.monto} {i.unidad_monto}</span>
                              </label>
                            ))}
                          </div>

                          {reincidenciaPreview && (
                            <div className="reincidencia-aviso">
                              <AlertTriangle size={20} className="icono" />
                              <p className="texto">
                                <strong>Reincidencia detectada</strong>
                                La unidad {activa.unidad_identificador} ya fue sancionada por esta misma infraccion
                                el {new Date(reincidenciaPreview.fecha_aprobacion).toLocaleDateString('es-CL')} (multa #{reincidenciaPreview.id}),
                                dentro de los {REINCIDENCIA_MESES} meses que establece la ley. El agravante del
                                catalogo (x{infraccionElegida.factor_reincidencia}, como maximo el doble) se aplica solo.
                              </p>
                            </div>
                          )}

                          {infraccionElegida && (infraccionElegida.monto_minimo || infraccionElegida.monto_maximo) ? (
                            <label>
                              Graduar el monto dentro del rango del reglamento
                              ({infraccionElegida.monto_minimo || infraccionElegida.monto} a {infraccionElegida.monto_maximo || infraccionElegida.monto} {infraccionElegida.unidad_monto})
                              <input
                                type="number"
                                step="0.01"
                                min={infraccionElegida.monto_minimo || infraccionElegida.monto}
                                max={infraccionElegida.monto_maximo || infraccionElegida.monto}
                                value={datosActiva.monto || ''}
                                placeholder={String(infraccionElegida.monto)}
                                onChange={(e) => setDatoActiva('monto', e.target.value)}
                              />
                            </label>
                          ) : infraccionElegida && (
                            <p className="texto-secundario" style={{ margin: 0 }}>
                              El reglamento fija {infraccionElegida.monto} {infraccionElegida.unidad_monto} para esta falta.
                            </p>
                          )}

                          <label className="check-gate">
                            <input
                              type="checkbox"
                              checked={Boolean(datosActiva.revisado)}
                              onChange={(e) => setDatoActiva('revisado', e.target.checked)}
                            />
                            Confirmo que he revisado la evidencia fotografica y el articulo del reglamento
                            aplicable antes de emitir una decision.
                          </label>

                          {votacion && (
                            <p className="texto-secundario" style={{ margin: 0 }}>
                              Para aplicar la multa hacen falta {votacion.requeridos} voto(s) iguales del Comite
                              (mayoria de sus integrantes). Van {votacion.votos_aprobar} a favor
                              {votacion.votos_rechazar ? ` y ${votacion.votos_rechazar} en contra` : ''}.
                              {votacion.mi_voto && ` Tu voto: ${votacion.mi_voto === 'APROBAR' ? 'aplicarla' : 'no aplicarla'}.`}
                            </p>
                          )}
                          <div className="acciones">
                            <button
                              className="btn btn-exito"
                              onClick={aprobar}
                              disabled={
                                Boolean(votacion?.mi_voto) || !datosActiva.revisado
                                || !datosActiva.infraccion_id || !activa.persona_nombre
                              }
                            >
                              Votar por aplicar la multa
                            </button>
                            <button className="btn btn-peligro" onClick={rechazar} disabled={Boolean(votacion?.mi_voto)}>
                              Votar por no aplicarla
                            </button>
                          </div>
                        </>
                      )}

                      {activa.estado === 'CON_DESCARGO' && (
                        <>
                          <div className="panel-comparacion">
                            <div className="panel-evidencia">
                              <h4>Descargo del residente</h4>
                              {activa.descargo?.resolucion_vencida && (
                                <p className="alerta-reincidencia">
                                  El plazo para responder esta apelacion ya vencio. El cobro queda suspendido
                                  hasta que el Comite la resuelva.
                                </p>
                              )}
                              <p>{activa.descargo?.texto}</p>
                              {activa.descargo?.archivo_adjunto && (
                                <a href={`${MEDIA_BASE}${activa.descargo.archivo_adjunto}`} target="_blank" rel="noreferrer">
                                  Ver documento adjunto
                                </a>
                              )}
                              {activa.descargo?.antecedentes?.length > 0 && (
                                <>
                                  <h4 style={{ marginTop: 14 }}>
                                    Antecedentes sumados despues ({activa.descargo.antecedentes.length})
                                  </h4>
                                  <ul className="lista-antecedentes">
                                    {activa.descargo.antecedentes.map((a) => (
                                      <li key={a.id}>
                                        {a.texto}
                                        {a.archivo_adjunto && (
                                          <>
                                            {' '}
                                            <a href={`${MEDIA_BASE}${a.archivo_adjunto}`} target="_blank" rel="noreferrer">
                                              (ver adjunto)
                                            </a>
                                          </>
                                        )}
                                      </li>
                                    ))}
                                  </ul>
                                </>
                              )}
                            </div>
                            <div className="panel-articulo">
                              <h4>Multa impugnada</h4>
                              <p><strong>{activa.infraccion_codigo}</strong> · {activa.infraccion_articulo}</p>
                              <p>{activa.infraccion_descripcion}</p>
                              <p><strong>Monto:</strong> {activa.monto} {activa.infraccion_unidad_monto}</p>
                              {activa.es_reincidencia && <p className="alerta-reincidencia">{activa.agravante_sugerido}</p>}
                            </div>
                          </div>

                          {propuestas.length > 0 && (
                            <div className="propuestas-resolucion">
                              <h4>Lo que sugiere el sistema</h4>
                              <p className="propuestas-nota">
                                Son sugerencias con su fundamento a la vista. Quien resuelve es el Comite.
                              </p>
                              <ul>
                                {propuestas.map((o) => (
                                  <li key={`${o.resolucion}-${o.porcentaje_descuento || ''}`}>
                                    <b>{o.etiqueta}</b>
                                    <span>{o.fundamento}</span>
                                  </li>
                                ))}
                              </ul>
                            </div>
                          )}

                          {activa.descargo?.reuniones?.length > 0 && (
                            <div className="propuestas-resolucion">
                              <h4>Reuniones con el residente</h4>
                              <ul>
                                {activa.descargo.reuniones.map((r) => (
                                  <li key={r.id}>
                                    <b>
                                      {r.modalidad === 'ONLINE' ? 'En linea' : 'Presencial'}
                                      {' · '}
                                      {new Date(r.fecha_propuesta).toLocaleString('es-CL')}
                                      {' · '}{r.estado}
                                    </b>
                                    <span>{r.acta || r.lugar_o_enlace}</span>
                                  </li>
                                ))}
                              </ul>
                            </div>
                          )}

                          <div className="acciones">
                            <button className="btn btn-secundario" onClick={() => convocarReunion('ONLINE')}>
                              Citar a reunion en linea
                            </button>
                            <button className="btn btn-secundario" onClick={() => convocarReunion('PRESENCIAL')}>
                              Citar a reunion presencial
                            </button>
                            {activa.descargo?.reuniones?.some((r) => r.estado !== 'REALIZADA') && (
                              <button className="btn btn-secundario" onClick={registrarActa}>
                                Registrar acta de la reunion
                              </button>
                            )}
                          </div>

                          <div className="acciones">
                            <button className="btn btn-exito" onClick={() => resolverDescargo('ACEPTADO')}>
                              Aceptar descargo (anula la multa)
                            </button>
                            <button className="btn btn-secundario" onClick={resolverConDescuento}>
                              Aplicar descuento (multa firme, monto rebajado)
                            </button>
                            <button className="btn btn-secundario" onClick={() => resolverDescargo('CORTESIA')}>
                              Parte de cortesia (sin cobro, queda en el registro)
                            </button>
                            <button className="btn btn-peligro" onClick={() => resolverDescargo('RECHAZADO')}>
                              Rechazar descargo (multa firme)
                            </button>
                          </div>
                        </>
                      )}

                      {activa.estado === 'POR_CONFIRMAR' && (
                        <>
                          <div className="propuestas-resolucion">
                            <h4>Este cobro se detuvo antes de emitirse</h4>
                            <p className="propuestas-nota">
                              Nadie apelo dentro del plazo, pero hay una señal de que esta persona
                              pudo no haber podido defenderse. No hay que estudiar el caso de nuevo:
                              solo decidir si corresponde cobrarlo igual.
                            </p>
                            <ul>
                              <li>
                                <b>Por que se detuvo</b>
                                <span>{activa.motivo_confirmacion}</span>
                              </li>
                              <li>
                                <b>Multa</b>
                                <span>
                                  {activa.infraccion_codigo} · {activa.infraccion_descripcion}
                                  {' '}— {activa.monto} {activa.infraccion_unidad_monto}
                                </span>
                              </li>
                            </ul>
                          </div>

                          <div className="acciones">
                            <button className="btn btn-secundario" onClick={() => confirmarCobro(true)}>
                              Dar parte de cortesia (no se cobra)
                            </button>
                            <button className="btn btn-peligro" onClick={() => confirmarCobro(false)}>
                              Confirmar el cobro
                            </button>
                          </div>
                        </>
                      )}
                    </div>
                  </div>
                )}

                {activa && (
                  <div className="split-timeline">
                    <ProcesoTimeline multa={activa} />

                    <div className="tarjeta" style={{ marginTop: 12, padding: 14 }}>
                      <button className="btn btn-secundario" style={{ width: '100%' }} onClick={verificarIntegridad}>
                        <ShieldCheck size={16} /> Verificar integridad
                      </button>
                      <button className="btn btn-primario" style={{ width: '100%', marginTop: 8 }} onClick={descargarAuditTrail}>
                        Descargar certificado (PDF)
                      </button>
                      {verificacion?.multaId === activa.id && (
                        verificacion.data.sellado ? (
                          <p
                            className={verificacion.data.integra ? 'texto-secundario' : 'mensaje-error'}
                            style={{ marginTop: 10, fontWeight: 600, color: verificacion.data.integra ? '#2f7d4f' : undefined }}
                          >
                            {verificacion.data.integra
                              ? `Expediente integro: ${verificacion.data.total_actas} acto(s) sellado(s), cadena y evidencia verificadas.`
                              : 'ALERTA: la verificacion criptografica detecto alteraciones en este expediente.'}
                          </p>
                        ) : (
                          <p className="texto-secundario" style={{ marginTop: 10 }}>
                            Aun sin actos de decision sellados (los sellos se crean al cursar, notificar o resolver).
                          </p>
                        )
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}
          </>
        )}

        {tab === 'contenciones' && (
          <>
            <PageHeader
              titulo={`Medidas de ${t('contencion').toLowerCase()}`}
              subtitulo="Las contenciones ejecutadas en terreno permanecen ACTIVAS hasta que reunan su quorum de firmas o se levanten con fundamento. La omision escala y queda sellada con tu nombre entre los notificados."
              stats={[
                { label: 'Pendientes de firma', valor: medidas.filter((m) => m.estado === 'EJECUTADA' || m.estado === 'EN_ESCALAMIENTO').length, alerta: medidas.some((m) => m.estado === 'EJECUTADA' || m.estado === 'EN_ESCALAMIENTO') },
                { label: 'En escalamiento', valor: medidas.filter((m) => m.estado === 'EN_ESCALAMIENTO').length, alerta: medidas.some((m) => m.estado === 'EN_ESCALAMIENTO') },
                { label: 'Activas en total', valor: medidas.filter((m) => m.activa).length },
              ]}
            />

            <div style={{ marginTop: 16 }}>
              <button className="btn btn-secundario" onClick={() => setDrawerAbierto(true)}>
                <UserPlus size={16} /> Estoy fuera de terreno · delegar
              </button>
            </div>

            <div className="lista-tarjetas" style={{ marginTop: 16 }}>
              {medidas.map((m) => (
                <div key={m.id} className="tarjeta">
                  <div className="tarjeta-header">
                    <strong>Medida #{m.id} · {m.unidad_identificador} · {m.hallazgo_codigo}</strong>
                    <EstadoBadge estado={m.estado} />
                  </div>
                  <p>{m.hallazgo_descripcion}</p>
                  {m.descripcion && <p className="texto-secundario">Observacion de terreno: {m.descripcion}</p>}
                  <p className="texto-secundario">
                    Ejecutada por {m.ejecutada_por_nombre} · {new Date(m.ejecutada_en).toLocaleString()}
                    {' '}(auth: {m.auth_metodo_ejecucion})
                    {m.nivel_escalamiento > 0 && ` · escalamiento N${m.nivel_escalamiento}`}
                  </p>

                  <QuorumBar medida={m} />

                  {m.estado === 'LEVANTADA' && (
                    <p className="texto-secundario">
                      Levantada con causal {m.causal_levantamiento}: {m.fundamento_levantamiento}
                    </p>
                  )}

                  {m.activa && (
                    <>
                      {(m.estado === 'EJECUTADA' || m.estado === 'EN_ESCALAMIENTO') && (
                        m.ya_vote ? (
                          <span className="ya-firmaste"><CheckCircle2 size={16} /> Ya firmaste · esperando el resto del quorum</span>
                        ) : (
                          <div className="acciones">
                            <HoldToConfirm
                              label={m.quorum_requerido > 1 ? 'Mantener para AGREGAR MI FIRMA' : 'Mantener para RATIFICAR'}
                              className="btn btn-exito"
                              onConfirm={() => ratificarMedida(m.id)}
                            />
                          </div>
                        )
                      )}
                      <div className="fila-formulario" style={{ marginTop: 12, alignItems: 'flex-end' }}>
                        <label>
                          Causal de levantamiento
                          <select
                            value={levantamiento[m.id]?.causal || ''}
                            onChange={(e) => setLevantamiento({ ...levantamiento, [m.id]: { ...levantamiento[m.id], causal: e.target.value } })}
                          >
                            <option value="">Seleccione...</option>
                            <option value="CORREGIDA">Hallazgo corregido (con evidencia)</option>
                            <option value="DESESTIMADA">Hallazgo desestimado (con fundamento)</option>
                          </select>
                        </label>
                        <label style={{ flex: 2 }}>
                          Fundamento (obligatorio, queda sellado)
                          <input
                            value={levantamiento[m.id]?.fundamento || ''}
                            onChange={(e) => setLevantamiento({ ...levantamiento, [m.id]: { ...levantamiento[m.id], fundamento: e.target.value } })}
                            placeholder="Ej: tablero normalizado, evidencia adjunta al expediente"
                          />
                        </label>
                        <button className="btn btn-peligro" onClick={() => levantarMedida(m.id)}>
                          Levantar
                        </button>
                      </div>
                    </>
                  )}
                </div>
              ))}
              {medidas.length === 0 && <EmptyState icon={Siren} mensaje="No hay medidas de contencion registradas." />}
            </div>
          </>
        )}

        {tab === 'borradores' && (
          <>
            <PageHeader
              titulo="Borradores de infracciones sugeridos por IA"
              subtitulo="Revisa y confirma antes de que puedan usarse para fundar una multa. Ninguna sancion puede fundarse en un borrador sin revision humana."
            />
            <div className="lista-tarjetas" style={{ marginTop: 24 }}>
              {borradores.map((b) => (
                <div key={b.id} className="tarjeta">
                  <div className="tarjeta-header">
                    <strong>{b.codigo}</strong>
                    <EstadoBadge estado={b.estado} />
                  </div>
                  <p>{b.descripcion}</p>
                  <p className="texto-secundario">{b.articulo_referencia || 'sin articulo'} · {b.monto} {b.unidad_monto} · {b.gravedad}</p>
                  {b.texto_fuente && <blockquote className="cita-fuente">"{b.texto_fuente}"</blockquote>}
                  <div className="acciones">
                    <button className="btn btn-exito" onClick={() => confirmarInfraccion(b.id)}>Confirmar</button>
                    <button className="btn btn-peligro" onClick={() => rechazarInfraccion(b.id)}>Descartar</button>
                  </div>
                </div>
              ))}
              {borradores.length === 0 && (
                <EmptyState icon={Sparkles} mensaje="No hay borradores pendientes. Sube un reglamento desde el panel del Administrador para generar sugerencias." />
              )}
            </div>
          </>
        )}

        {tab === 'catalogo' && (
          <>
            <PageHeader titulo="Catalogo de infracciones activas" subtitulo="Base legal con la que se tipifican las multas, automaticamente o a mano." />

            <form className="tarjeta formulario" onSubmit={crearInfraccion} style={{ marginTop: 24 }}>
              <div className="fila-formulario">
                <label>
                  Codigo
                  <input value={formInfraccion.codigo} onChange={(e) => setFormInfraccion({ ...formInfraccion, codigo: e.target.value })} required />
                </label>
                <label>
                  Articulo del reglamento de copropiedad (o de la ley)
                  <input value={formInfraccion.articulo_referencia} onChange={(e) => setFormInfraccion({ ...formInfraccion, articulo_referencia: e.target.value })} required />
                </label>
              </div>
              <label>
                Descripcion
                <input value={formInfraccion.descripcion} onChange={(e) => setFormInfraccion({ ...formInfraccion, descripcion: e.target.value })} required />
              </label>
              <div className="fila-formulario">
                <label>
                  Monto
                  <input type="number" step="0.01" value={formInfraccion.monto} onChange={(e) => setFormInfraccion({ ...formInfraccion, monto: e.target.value })} required />
                </label>
                <label>
                  Minimo del reglamento (opcional)
                  <input type="number" step="0.01" value={formInfraccion.monto_minimo || ''} onChange={(e) => setFormInfraccion({ ...formInfraccion, monto_minimo: e.target.value })} />
                </label>
                <label>
                  Maximo del reglamento (opcional)
                  <input type="number" step="0.01" value={formInfraccion.monto_maximo || ''} onChange={(e) => setFormInfraccion({ ...formInfraccion, monto_maximo: e.target.value })} />
                </label>
                <label>
                  Unidad
                  <select value={formInfraccion.unidad_monto} onChange={(e) => setFormInfraccion({ ...formInfraccion, unidad_monto: e.target.value })}>
                    <option value="UF">UF</option>
                    <option value="UTM">UTM</option>
                    <option value="CLP">CLP</option>
                  </select>
                </label>
                <label>
                  Gravedad
                  <select value={formInfraccion.gravedad} onChange={(e) => setFormInfraccion({ ...formInfraccion, gravedad: e.target.value })}>
                    <option value="LEVE">Leve</option>
                    <option value="GRAVE">Grave</option>
                    <option value="GRAVISIMA">Gravisima</option>
                  </select>
                </label>
              </div>
              <div className="fila-formulario" style={{ alignItems: 'flex-end' }}>
                <label className="check-gate" style={{ flex: 2 }}>
                  <input
                    type="checkbox"
                    checked={formInfraccion.conlleva_contencion}
                    onChange={(e) => setFormInfraccion({ ...formInfraccion, conlleva_contencion: e.target.checked })}
                  />
                  Hallazgo critico: reportarlo detona una medida de contencion inmediata
                  (la calificacion juridica se decide aqui, en frio — nunca en terreno).
                </label>
                {formInfraccion.conlleva_contencion && (
                  <label>
                    Plazo de ratificacion (horas)
                    <input
                      type="number"
                      min="1"
                      value={formInfraccion.plazo_ratificacion_horas}
                      onChange={(e) => setFormInfraccion({ ...formInfraccion, plazo_ratificacion_horas: e.target.value })}
                    />
                  </label>
                )}
              </div>
              <button className="btn btn-primario" type="submit" style={{ alignSelf: 'flex-start' }}>Agregar al catalogo</button>
            </form>

            {infracciones.length > 0 ? (
              <div className="tabla-wrap">
                <table className="tabla">
                  <thead>
                    <tr>
                      <th>Codigo</th>
                      <th>Descripcion</th>
                      <th>Articulo</th>
                      <th>Monto</th>
                      <th>Gravedad</th>
                      <th>Contencion</th>
                    </tr>
                  </thead>
                  <tbody>
                    {infracciones.map((i) => (
                      <tr key={i.id}>
                        <td><strong>{i.codigo}</strong></td>
                        <td>{i.descripcion}</td>
                        <td>{i.articulo_referencia || '—'}</td>
                        <td>
                          {i.monto} {i.unidad_monto}
                          {(i.monto_minimo || i.monto_maximo) && ` (${i.monto_minimo || i.monto} a ${i.monto_maximo || i.monto})`}
                        </td>
                        <td>{i.gravedad}</td>
                        <td>{i.conlleva_contencion ? `Si (${i.plazo_ratificacion_horas}h)` : '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <EmptyState icon={BookMarked} mensaje="Aun no hay infracciones activas en el catalogo." />
            )}
          </>
        )}
      </div>

      {drawerAbierto && (
        <DrawerDelegacion
          usuarioActual={usuario}
          onClose={() => setDrawerAbierto(false)}
          onCambio={cargarTodo}
        />
      )}
    </AppShell>
  );
}
