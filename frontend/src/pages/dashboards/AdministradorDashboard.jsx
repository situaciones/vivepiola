import { useEffect, useState } from 'react';
import { BellRing, FileText, KeyRound, MessageSquareText, Users, Wallet } from 'lucide-react';
import client, { MEDIA_BASE } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import EstadoBadge from '../../components/EstadoBadge';
import EmptyState from '../../components/EmptyState';
import PageHeader from '../../components/PageHeader';
import AppShell from '../../components/AppShell';
import PanelFirmasDelegadas from '../../components/PanelFirmasDelegadas';
import { useVocab } from '../../vocab';

export default function AdministradorDashboard() {
  const t = useVocab();
  const { usuario } = useAuth();
  const [tab, setTab] = useState('notificar');
  const [multas, setMultas] = useState([]);
  const [novedades, setNovedades] = useState([]);
  const [reglamentos, setReglamentos] = useState([]);
  const [tieneDelegacion, setTieneDelegacion] = useState(false);
  const [firmasPendientes, setFirmasPendientes] = useState(0);
  const [mensaje, setMensaje] = useState('');
  const [resultadoImportacion, setResultadoImportacion] = useState(null);
  const [periodo, setPeriodo] = useState(() => new Date().toISOString().slice(0, 7));
  const [lote, setLote] = useState(null);

  const cargarTodo = () => {
    client.get('/multas/').then((res) => setMultas(res.data.results || res.data));
    client.get('/novedades/').then((res) => setNovedades(res.data.results || res.data));
    client.get('/reglamentos/').then((res) => setReglamentos(res.data.results || res.data));
    // ¿Tengo delegaciones vigentes? Define si aparece la pestaña de firmas.
    client.get('/delegaciones/').then((res) => {
      const vigentes = (res.data.results || res.data).filter(
        (d) => d.estado === 'VIGENTE' && d.delegado === usuario?.id,
      );
      setTieneDelegacion(vigentes.length > 0);
      if (vigentes.length === 0) { setFirmasPendientes(0); return; }
      client.get('/medidas-inmediatas/').then((r) => {
        const pend = (r.data.results || r.data).filter(
          (m) => (m.estado === 'EJECUTADA' || m.estado === 'EN_ESCALAMIENTO') && !m.ya_vote,
        );
        setFirmasPendientes(pend.length);
      });
    }).catch(() => { setTieneDelegacion(false); setFirmasPendientes(0); });
  };

  useEffect(cargarTodo, []);

  const aprobadas = multas.filter((m) => m.estado === 'APROBADA');
  const novedadesPendientes = novedades.filter((n) => n.estado !== 'RESPONDIDA');

  const notificar = async (multaId) => {
    setMensaje('Enviando notificacion...');
    try {
      await client.post(`/multas/${multaId}/notificar/`);
      setMensaje(`${t('multa')} #${multaId} notificada al correo registrado del ${t('residente').toLowerCase()}.`);
      cargarTodo();
    } catch (err) {
      setMensaje(err.response?.data?.detail || 'Error al notificar.');
    }
  };

  const descargarPlantilla = async () => {
    const res = await client.get('/registro/plantilla/', { responseType: 'blob' });
    const url = URL.createObjectURL(res.data);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'plantilla_registro_copropietarios.xlsx';
    a.click();
    URL.revokeObjectURL(url);
  };

  const importarRegistro = async (e) => {
    const archivo = e.target.files[0];
    if (!archivo) return;
    const formData = new FormData();
    formData.append('archivo', archivo);
    try {
      const res = await client.post('/registro/importar/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setResultadoImportacion(res.data);
    } catch (err) {
      setMensaje(err.response?.data?.detail || 'Error al importar el registro.');
    }
    e.target.value = '';
  };

  const subirReglamento = async (e) => {
    const archivo = e.target.files[0];
    if (!archivo) return;
    const formData = new FormData();
    formData.append('archivo_pdf', archivo);
    setMensaje('Subiendo reglamento y extrayendo texto...');
    try {
      await client.post('/reglamentos/', formData, { headers: { 'Content-Type': 'multipart/form-data' } });
      setMensaje('Reglamento cargado.');
      cargarTodo();
    } catch {
      setMensaje('Error al subir el reglamento.');
    }
    e.target.value = '';
  };

  const generarBorradoresIA = async (reglamentoId) => {
    setMensaje('Consultando IA para sugerir infracciones (esto puede tardar unos segundos)...');
    try {
      const res = await client.post(`/reglamentos/${reglamentoId}/generar-borradores-ia/`);
      const omitidas = res.data.omitidas?.length
        ? ` Se omitieron ${res.data.omitidas.length} codigos ya confirmados: ${res.data.omitidas.join(', ')}.`
        : '';
      setMensaje(
        `${res.data.borradores.length} infracciones sugeridas como borrador. ` +
        `El Comite debe confirmarlas en su panel.${omitidas}`,
      );
    } catch (err) {
      setMensaje(err.response?.data?.detail || 'Error consultando el modelo de IA.');
    }
  };

  const responderNovedad = async (id) => {
    const respuesta_texto = prompt(`Respuesta para el ${t('residente').toLowerCase()}:`);
    if (!respuesta_texto) return;
    await client.post(`/novedades/${id}/responder/`, { respuesta_texto });
    cargarTodo();
  };

  const exportarGastosComunes = async (e) => {
    e.preventDefault();
    try {
      const res = await client.post('/gastos-comunes/exportar/', { periodo });
      setLote(res.data);
      setMensaje(`Lote generado: ${res.data.cargos.length} ${t('multa_plural').toLowerCase()} exportadas por un total de ${res.data.total_monto}.`);
    } catch (err) {
      setMensaje(err.response?.data?.detail || `No hay ${t('multa_plural').toLowerCase()} firmes para exportar.`);
    }
  };

  return (
    <AppShell
      tabs={[
        { id: 'notificar', label: `Notificar ${t('multa_plural').toLowerCase()}`, icon: BellRing, badge: aprobadas.length },
        ...(tieneDelegacion ? [{ id: 'firmas', label: 'Firmas por delegacion', icon: KeyRound, badge: firmasPendientes }] : []),
        { id: 'registro', label: t('registro_titulo'), icon: Users },
        { id: 'reglamento', label: `${t('infraccion')} y reglamento`, icon: FileText },
        { id: 'novedades', label: 'Libro de Novedades', icon: MessageSquareText, badge: novedadesPendientes.length },
        { id: 'gastos', label: t('destino_cobro').charAt(0).toUpperCase() + t('destino_cobro').slice(1), icon: Wallet },
      ]}
      active={tab}
      onChange={setTab}
    >
      <div className="contenedor">
        {mensaje && <div className="mensaje-info">{mensaje}</div>}

        {tab === 'notificar' && (
          <>
            <PageHeader
              titulo={`Notificar ${t('multa_plural').toLowerCase()} aprobadas`}
              subtitulo={`Genera el PDF formal y lo envia al correo registrado del ${t('residente').toLowerCase()}: ese envio es el canal legal de notificacion.`}
              stats={[{ label: 'Pendientes de notificar', valor: aprobadas.length, alerta: aprobadas.length > 0 }]}
            />
            <div className="lista-tarjetas" style={{ marginTop: 24 }}>
              {aprobadas.map((m) => (
                <div key={m.id} className="tarjeta">
                  <div className="tarjeta-header">
                    <strong>{t('multa')} #{m.id} - {m.unidad_identificador}</strong>
                    <EstadoBadge estado={m.estado} />
                  </div>
                  <p>{m.infraccion_descripcion} - {m.monto}</p>
                  {m.es_reincidencia && <p className="alerta-reincidencia">Reincidencia: {m.agravante_sugerido}</p>}
                  <button className="btn btn-primario" onClick={() => notificar(m.id)} style={{ marginTop: 10 }}>
                    Notificar al {t('residente').toLowerCase()}
                  </button>
                </div>
              ))}
              {aprobadas.length === 0 && <EmptyState icon={BellRing} mensaje={`No hay ${t('multa_plural').toLowerCase()} aprobadas pendientes de notificar.`} />}
            </div>
          </>
        )}

        {tab === 'firmas' && (
          <>
            <PageHeader
              titulo="Firmas por delegacion"
              subtitulo="El Comite te delego su facultad de ratificar mientras no esta en terreno. Aporta tu firma a las paralizaciones que reunen quorum. Cada firma queda sellada indicando bajo que delegacion actuaste."
            />
            <div style={{ marginTop: 24 }}>
              <PanelFirmasDelegadas />
            </div>
          </>
        )}

        {tab === 'registro' && (
          <>
            <PageHeader titulo={t('registro_titulo')} subtitulo={t('registro_sub')} />
            <div className="tarjeta formulario" style={{ marginTop: 24 }}>
              <div className="acciones">
                <button className="btn btn-secundario" onClick={descargarPlantilla}>Descargar plantilla Excel</button>
                <label className="btn btn-primario subir-evidencia">
                  Importar registro (.xlsx / .csv)
                  <input type="file" accept=".xlsx,.csv" hidden onChange={importarRegistro} />
                </label>
              </div>
              {resultadoImportacion && (
                <div className="resultado-importacion">
                  <p>
                    Filas totales: {resultadoImportacion.filas_totales} - OK: {resultadoImportacion.filas_ok} - Con error: {resultadoImportacion.filas_error}
                  </p>
                  {resultadoImportacion.detalle_errores?.length > 0 && (
                    <ul>
                      {resultadoImportacion.detalle_errores.map((e, idx) => (
                        <li key={idx}>Fila {e.fila}: {e.errores.join(', ')}</li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
            </div>
          </>
        )}

        {tab === 'reglamento' && (
          <>
            <PageHeader titulo="Reglamento e infracciones" subtitulo="Sube el PDF vigente; la IA sugiere infracciones como borrador para que el Comite las confirme." />
            <div className="tarjeta formulario" style={{ marginTop: 24 }}>
              <label className="btn btn-secundario subir-evidencia" style={{ alignSelf: 'flex-start' }}>
                Subir PDF del reglamento
                <input type="file" accept="application/pdf" hidden onChange={subirReglamento} />
              </label>
            </div>
            <div className="lista-tarjetas">
              {reglamentos.map((r) => (
                <div key={r.id} className="tarjeta tarjeta-compacta">
                  <span>Reglamento #{r.id} {r.procesado_ia ? '(IA ya proceso este documento)' : ''}</span>
                  <button className="btn btn-primario" onClick={() => generarBorradoresIA(r.id)}>
                    Extraer infracciones con IA
                  </button>
                </div>
              ))}
              {reglamentos.length === 0 && <EmptyState icon={FileText} mensaje="Sube el PDF del reglamento para digitalizar el catalogo." />}
            </div>
          </>
        )}

        {tab === 'novedades' && (
          <>
            <PageHeader
              titulo="Libro de Novedades - pendientes de respuesta"
              subtitulo="Toda solicitud o reclamo dirigido a la administracion debe responderse dentro del plazo legal de 20 dias corridos."
              stats={[{ label: 'Pendientes', valor: novedadesPendientes.length, alerta: novedadesPendientes.length > 0 }]}
            />
            <div className="lista-tarjetas" style={{ marginTop: 24 }}>
              {novedadesPendientes.map((n) => (
                <div key={n.id} className="tarjeta">
                  <div className="tarjeta-header">
                    <strong>{n.tipo}</strong>
                    <EstadoBadge estado={n.estado} />
                  </div>
                  <p>{n.texto}</p>
                  <p className="texto-secundario">Dias restantes para responder (plazo legal 20 dias): {n.dias_restantes}</p>
                  <button className="btn btn-primario" onClick={() => responderNovedad(n.id)} style={{ marginTop: 10 }}>
                    Responder
                  </button>
                </div>
              ))}
              {novedadesPendientes.length === 0 && (
                <EmptyState icon={MessageSquareText} mensaje="No hay novedades pendientes de respuesta." />
              )}
            </div>
          </>
        )}

        {tab === 'gastos' && (
          <>
            <PageHeader titulo={`Integracion a ${t('destino_cobro')}`} subtitulo={`Exporta las ${t('multa_plural').toLowerCase()} firmes (sin apelaciones pendientes) al aviso de cobro mensual.`} />
            <form className="tarjeta formulario" onSubmit={exportarGastosComunes} style={{ marginTop: 24 }}>
              <div className="fila-formulario" style={{ alignItems: 'flex-end' }}>
                <label>
                  Periodo (AAAA-MM)
                  <input value={periodo} onChange={(e) => setPeriodo(e.target.value)} pattern="\d{4}-\d{2}" required />
                </label>
                <button className="btn btn-primario" type="submit">Exportar {t('multa_plural').toLowerCase()} firmes del periodo</button>
              </div>
            </form>
            {lote && (
              <div className="resultado-importacion">
                <p>Lote {lote.periodo}: {lote.cargos.length} cargos, total {lote.total_monto}</p>
                {lote.archivo_csv && (
                  <a href={`${MEDIA_BASE}${lote.archivo_csv}`} target="_blank" rel="noreferrer">
                    Descargar CSV
                  </a>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </AppShell>
  );
}
