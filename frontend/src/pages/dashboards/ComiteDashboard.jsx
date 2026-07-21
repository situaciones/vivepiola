import { useEffect, useState } from 'react';
import { AlertTriangle, BookMarked, CheckCircle2, Inbox, PenLine, ShieldCheck, Siren, Sparkles, UserPlus } from 'lucide-react';
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
const ESTADOS_SANCIONADOS = ['APROBADA', 'NOTIFICADA', 'CON_DESCARGO', 'FIRME', 'EXPORTADA'];

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
    m.fecha_aprobacion &&
    new Date(m.fecha_aprobacion).getTime() >= limite,
  );
  if (candidatas.length === 0) return null;
  candidatas.sort((a, b) => new Date(a.fecha_aprobacion) - new Date(b.fecha_aprobacion));
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
  const [seleccionId, setSeleccionId] = useState(null);
  const [decision, setDecision] = useState({}); // { [multaId]: { infraccion_id, monto, revisado } }
  const [verificacion, setVerificacion] = useState(null); // { multaId, data }
  const [mensaje, setMensaje] = useState('');
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
  const pendientes = [...enRevision, ...conDescargo];

  const activa = pendientes.find((m) => m.id === seleccionId) || pendientes[0] || null;
  const datosActiva = activa ? decision[activa.id] || {} : {};
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

  const aplicarAgravante = () => {
    if (!infraccionElegida) return;
    const sugerido = (Number(infraccionElegida.monto) * 1.5).toFixed(2);
    setDatoActiva('monto', sugerido);
  };

  const aprobar = async () => {
    if (!datosActiva.infraccion_id) {
      setMensaje('Selecciona una infraccion del catalogo antes de aprobar.');
      return;
    }
    try {
      await client.post(`/multas/${activa.id}/aprobar/`, {
        infraccion_id: Number(datosActiva.infraccion_id),
        ...(datosActiva.monto ? { monto: datosActiva.monto } : {}),
      });
      setMensaje(`Multa #${activa.id} aprobada. Pasa al Administrador para su notificacion legal.`);
      setSeleccionId(null);
      cargarTodo();
    } catch (err) {
      setMensaje(err.response?.data?.detail || 'No se pudo aprobar la multa.');
    }
  };

  const rechazar = async () => {
    const motivo = prompt('Motivo del rechazo (queda en el historial):');
    if (!motivo) return;
    await client.post(`/multas/${activa.id}/rechazar/`, { motivo });
    setSeleccionId(null);
    cargarTodo();
  };

  const resolverDescargo = async (resolucion) => {
    const comentario = prompt(`Comentario de la resolucion (${resolucion}):`) || '';
    await client.post(`/multas/${activa.id}/resolver-descargo/`, { resolucion, comentario });
    setMensaje(`Descargo de multa #${activa.id} resuelto: ${resolucion}.`);
    setSeleccionId(null);
    cargarTodo();
  };

  const confirmarInfraccion = async (id) => {
    await client.post(`/infracciones/${id}/confirmar/`);
    cargarTodo();
  };

  const rechazarInfraccion = async (id) => {
    await client.post(`/infracciones/${id}/rechazar/`);
    cargarTodo();
  };

  const crearInfraccion = async (e) => {
    e.preventDefault();
    await client.post('/infracciones/', { ...formInfraccion, estado: 'ACTIVA' });
    setFormInfraccion({ codigo: '', descripcion: '', articulo_referencia: '', monto: '', unidad_monto: 'UF', gravedad: 'LEVE', conlleva_contencion: false, plazo_ratificacion_horas: 24 });
    cargarTodo();
  };

  return (
    <AppShell
      tabs={[
        { id: 'bandeja', label: 'Bandeja de decision', icon: Inbox, badge: pendientes.length },
        { id: 'contenciones', label: t('contenciones'), icon: Siren, badge: medidas.filter((m) => m.estado === 'EJECUTADA' || m.estado === 'EN_ESCALAMIENTO').length },
        { id: 'borradores', label: 'Borradores IA', icon: Sparkles, badge: borradores.length },
        { id: 'catalogo', label: t('catalogo'), icon: BookMarked },
      ]}
      active={tab}
      onChange={setTab}
    >
      <div className="contenedor">
        {mensaje && <div className="mensaje-info">{mensaje}</div>}

        {tab === 'bandeja' && (
          <>
            <PageHeader
              titulo="Bandeja de decision"
              subtitulo="Unico organo facultado para imponer las multas del reglamento de copropiedad. Compara la evidencia con el articulo aplicable antes de decidir."
              stats={[
                { label: 'En revision', valor: enRevision.length, alerta: enRevision.length > 0 },
                { label: 'Descargos por resolver', valor: conDescargo.length, alerta: conDescargo.length > 0 },
                { label: 'Infracciones activas', valor: infracciones.length },
              ]}
            />

            {pendientes.length === 0 ? (
              <div style={{ marginTop: 24 }}>
                <EmptyState icon={CheckCircle2} mensaje="No hay casos pendientes de decision. La bandeja esta al dia." />
              </div>
            ) : (
              <div className="split" style={{ marginTop: 24 }}>
                <div className="split-lista">
                  {pendientes.map((m) => (
                    <button
                      key={m.id}
                      type="button"
                      className={`split-item${activa?.id === m.id ? ' activo' : ''}`}
                      onClick={() => setSeleccionId(m.id)}
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
                          Sin persona reportada: pide al conserje identificar al infractor antes de aprobar.
                        </p>
                      )}

                      <blockquote className="cita-reporte">
                        "{activa.ticket_detalle?.descripcion}"
                        <footer>— {activa.ticket_detalle?.creado_por_nombre || 'Fiscalizador'}, reporte de fiscalizacion</footer>
                      </blockquote>

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
                                <span className="descripcion">{i.descripcion} · Art. {i.articulo_referencia || 's/n'}</span>
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
                                dentro de los {REINCIDENCIA_MESES} meses que establece la ley.
                              </p>
                              <button type="button" className="btn btn-secundario" onClick={aplicarAgravante}>
                                Aplicar agravante (+50% sugerido)
                              </button>
                            </div>
                          )}

                          <label>
                            Monto a aplicar (opcional, sobreescribe el del catalogo)
                            <input
                              type="number"
                              step="0.01"
                              min="0.01"
                              value={datosActiva.monto || ''}
                              onChange={(e) => setDatoActiva('monto', e.target.value)}
                            />
                          </label>

                          <label className="check-gate">
                            <input
                              type="checkbox"
                              checked={Boolean(datosActiva.revisado)}
                              onChange={(e) => setDatoActiva('revisado', e.target.checked)}
                            />
                            Confirmo que he revisado la evidencia fotografica y el articulo del reglamento
                            aplicable antes de emitir una decision.
                          </label>

                          <div className="acciones">
                            <button
                              className="btn btn-exito"
                              onClick={aprobar}
                              disabled={!datosActiva.revisado || !datosActiva.infraccion_id || !activa.persona_nombre}
                            >
                              Aprobar multa
                            </button>
                            <button className="btn btn-peligro" onClick={rechazar}>Rechazar reporte</button>
                          </div>
                        </>
                      )}

                      {activa.estado === 'CON_DESCARGO' && (
                        <>
                          <div className="panel-comparacion">
                            <div className="panel-evidencia">
                              <h4>Descargo del residente</h4>
                              <p>{activa.descargo?.texto}</p>
                              {activa.descargo?.archivo_adjunto && (
                                <a href={`${MEDIA_BASE}${activa.descargo.archivo_adjunto}`} target="_blank" rel="noreferrer">
                                  Ver documento adjunto
                                </a>
                              )}
                            </div>
                            <div className="panel-articulo">
                              <h4>Multa impugnada</h4>
                              <p><strong>{activa.infraccion_codigo}</strong> · {activa.infraccion_articulo}</p>
                              <p>{activa.infraccion_descripcion}</p>
                              <p><strong>Monto:</strong> {activa.monto}</p>
                              {activa.es_reincidencia && <p className="alerta-reincidencia">{activa.agravante_sugerido}</p>}
                            </div>
                          </div>

                          <div className="acciones">
                            <button className="btn btn-exito" onClick={() => resolverDescargo('ACEPTADO')}>
                              Aceptar descargo (anula la multa)
                            </button>
                            <button className="btn btn-peligro" onClick={() => resolverDescargo('RECHAZADO')}>
                              Rechazar descargo (multa firme)
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
                            Aun sin actos de decision sellados (los sellos se crean al aprobar, notificar o resolver).
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
                  <p className="texto-secundario">Art. {b.articulo_referencia} · {b.monto} {b.unidad_monto} · {b.gravedad}</p>
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
            <PageHeader titulo="Catalogo de infracciones activas" subtitulo="Base legal que el Comite puede invocar al aprobar una multa." />

            <form className="tarjeta formulario" onSubmit={crearInfraccion} style={{ marginTop: 24 }}>
              <div className="fila-formulario">
                <label>
                  Codigo
                  <input value={formInfraccion.codigo} onChange={(e) => setFormInfraccion({ ...formInfraccion, codigo: e.target.value })} required />
                </label>
                <label>
                  Articulo del reglamento
                  <input value={formInfraccion.articulo_referencia} onChange={(e) => setFormInfraccion({ ...formInfraccion, articulo_referencia: e.target.value })} />
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
                        <td>{i.monto} {i.unidad_monto}</td>
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
