import { useEffect, useState } from 'react';
import { Camera, ClipboardList, ListChecks, Siren } from 'lucide-react';
import client, { MEDIA_BASE } from '../../api/client';
import EstadoBadge from '../../components/EstadoBadge';
import EmptyState from '../../components/EmptyState';
import HoldToConfirm from '../../components/HoldToConfirm';
import PageHeader from '../../components/PageHeader';
import AppShell from '../../components/AppShell';
import { useVocab } from '../../vocab';

// Timestamp local prellenado: el guardia reporta "ahora" salvo que corrija.
const ahoraLocal = () =>
  new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 16);

export default function FiscalizadorDashboard() {
  const t = useVocab();
  const [tab, setTab] = useState('nuevo');
  const [unidades, setUnidades] = useState([]);
  const [personas, setPersonas] = useState([]);
  const [tickets, setTickets] = useState([]);
  const [form, setForm] = useState({ unidad: '', persona_reportada: '', descripcion: '', fecha_hecho: ahoraLocal(), ubicacion: '' });
  const [mensaje, setMensaje] = useState('');
  const [subiendoEvidencia, setSubiendoEvidencia] = useState(null);

  // Carril de contencion
  const [multas, setMultas] = useState([]);
  const [medidas, setMedidas] = useState([]);
  const [hallazgosCriticos, setHallazgosCriticos] = useState([]);
  const [formContencion, setFormContencion] = useState({ expediente_id: '', hallazgo_codigo: '', descripcion: '' });

  const cargarTickets = () => client.get('/tickets/').then((res) => setTickets(res.data.results || res.data));
  const cargarContencion = () => {
    client.get('/multas/').then((res) => setMultas(res.data.results || res.data));
    client.get('/medidas-inmediatas/').then((res) => setMedidas(res.data.results || res.data));
    client.get('/infracciones/?estado=ACTIVA').then((res) => {
      const activos = (res.data.results || res.data).filter((i) => i.conlleva_contencion);
      setHallazgosCriticos(activos);
    });
  };

  useEffect(() => {
    client.get('/unidades/').then((res) => setUnidades(res.data.results || res.data));
    cargarTickets();
    cargarContencion();
  }, []);

  const ejecutarContencion = async () => {
    if (!formContencion.expediente_id || !formContencion.hallazgo_codigo) {
      setMensaje('Selecciona el caso y el hallazgo critico antes de ejecutar.');
      return;
    }
    try {
      await client.post('/medidas-inmediatas/', {
        expediente_id: Number(formContencion.expediente_id),
        hallazgo_codigo: formContencion.hallazgo_codigo,
        evidencia_ids: [],
        descripcion: formContencion.descripcion,
        auth_metodo: 'hold_to_confirm_1400ms+jwt',
      });
      setMensaje('Contencion ejecutada y sellada. Los adjudicadores fueron notificados; la medida queda activa hasta que la ratifiquen o levanten.');
      setFormContencion({ expediente_id: '', hallazgo_codigo: '', descripcion: '' });
      cargarContencion();
    } catch (err) {
      setMensaje(err.response?.data?.detail || 'No se pudo ejecutar la contencion.');
    }
  };

  useEffect(() => {
    if (form.unidad) {
      client.get(`/personas/?unidad=${form.unidad}`).then((res) => setPersonas(res.data.results || res.data));
    } else {
      setPersonas([]);
    }
  }, [form.unidad]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setMensaje('');
    try {
      await client.post('/tickets/', {
        unidad: Number(form.unidad),
        persona_reportada: form.persona_reportada ? Number(form.persona_reportada) : null,
        descripcion: form.descripcion,
        fecha_hecho: new Date(form.fecha_hecho).toISOString(),
        ubicacion: form.ubicacion,
      });
      setMensaje('Ticket creado. El Comite ya puede revisarlo.');
      setForm({ unidad: '', persona_reportada: '', descripcion: '', fecha_hecho: ahoraLocal(), ubicacion: '' });
      cargarTickets();
    } catch (err) {
      setMensaje(err.response?.data?.detail || 'Error al crear el ticket.');
    }
  };

  const subirEvidencia = async (ticketId, archivo) => {
    const formData = new FormData();
    formData.append('imagen', archivo);
    setSubiendoEvidencia(ticketId);
    try {
      await client.post(`/tickets/${ticketId}/evidencia/`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      cargarTickets();
    } finally {
      setSubiendoEvidencia(null);
    }
  };

  const pendientesRevision = tickets.filter((t) => t.estado === 'PENDIENTE').length;

  const medidasActivas = medidas.filter((m) => m.activa);

  return (
    <AppShell
      dark
      tabs={[
        { id: 'nuevo', label: t('reporte_corto'), icon: Camera },
        { id: 'contencion', label: t('contencion'), icon: Siren, badge: medidasActivas.length },
        { id: 'tickets', label: 'Mis tickets', icon: ListChecks, badge: tickets.length },
      ]}
      active={tab}
      onChange={setTab}
    >
      <div className="contenedor">
        {tab === 'nuevo' && (
          <>
            <PageHeader
              titulo={t('nuevo_reporte')}
              subtitulo={`Modo nocturno para terreno. La fecha y hora quedan prellenadas automaticamente. El monto y la aprobacion son responsabilidad exclusiva de ${t('rol_COMITE')}.`}
              stats={[
                { label: 'Reportes creados', valor: tickets.length },
                { label: `Convertidos en ${t('multa').toLowerCase()}`, valor: tickets.filter((tk) => tk.estado === 'CONVERTIDO').length },
                { label: 'Pendientes de revision', valor: pendientesRevision },
              ]}
            />

            <form className="tarjeta formulario" onSubmit={handleSubmit} style={{ marginTop: 24 }}>
              <div className="fila-formulario">
                <label>
                  {t('unidad')}
                  <select value={form.unidad} onChange={(e) => setForm({ ...form, unidad: e.target.value, persona_reportada: '' })} required>
                    <option value="">Seleccione...</option>
                    {unidades.map((u) => (
                      <option key={u.id} value={u.id}>{u.identificador}</option>
                    ))}
                  </select>
                </label>
                <label>
                  {t('persona_reportada')} (necesaria para poder aprobar)
                  <select value={form.persona_reportada} onChange={(e) => setForm({ ...form, persona_reportada: e.target.value })}>
                    <option value="">Sin especificar</option>
                    {personas.map((p) => (
                      <option key={p.id} value={p.id}>{p.nombre_completo} ({p.rol_ocupacion})</option>
                    ))}
                  </select>
                </label>
              </div>
              <div className="fila-formulario">
                <label>
                  Fecha y hora del hecho
                  <input type="datetime-local" value={form.fecha_hecho} onChange={(e) => setForm({ ...form, fecha_hecho: e.target.value })} required />
                </label>
                <label>
                  Ubicacion
                  <input value={form.ubicacion} onChange={(e) => setForm({ ...form, ubicacion: e.target.value })} placeholder="Ej: Piscina, hall de acceso" />
                </label>
              </div>
              <label>
                Descripcion del hecho
                <textarea rows={3} value={form.descripcion} onChange={(e) => setForm({ ...form, descripcion: e.target.value })} required />
              </label>
              {mensaje && <div className="mensaje-info">{mensaje}</div>}
              <button className="btn btn-primario" type="submit">Crear ticket</button>
            </form>
          </>
        )}

        {tab === 'contencion' && (
          <>
            <PageHeader
              titulo={t('contencion_titulo')}
              subtitulo="Para hallazgos que el catalogo califica como criticos. Tu no decides la calificacion juridica: seleccionas el hallazgo, el sistema hace el resto. La medida queda activa y sellada hasta que un facultado la ratifique o levante."
              stats={[
                { label: `${t('contenciones')} activas`, valor: medidasActivas.length, alerta: medidasActivas.length > 0 },
                { label: 'Hallazgos criticos en catalogo', valor: hallazgosCriticos.length },
              ]}
            />

            {mensaje && <div className="mensaje-info">{mensaje}</div>}

            <div className="tarjeta formulario" style={{ marginTop: 24 }}>
              <div className="fila-formulario">
                <label>
                  Caso (expediente)
                  <select
                    value={formContencion.expediente_id}
                    onChange={(e) => setFormContencion({ ...formContencion, expediente_id: e.target.value })}
                  >
                    <option value="">Seleccione...</option>
                    {multas.map((m) => (
                      <option key={m.id} value={m.id}>
                        #{m.id} · {m.unidad_identificador} · {m.ticket_detalle?.descripcion?.slice(0, 40)}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Hallazgo critico (segun catalogo)
                  <select
                    value={formContencion.hallazgo_codigo}
                    onChange={(e) => setFormContencion({ ...formContencion, hallazgo_codigo: e.target.value })}
                  >
                    <option value="">Seleccione...</option>
                    {hallazgosCriticos.map((h) => (
                      <option key={h.id} value={h.codigo}>
                        {h.codigo} · {h.descripcion} (ratificacion en {h.plazo_ratificacion_horas}h)
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <label>
                Observacion (opcional)
                <input
                  value={formContencion.descripcion}
                  onChange={(e) => setFormContencion({ ...formContencion, descripcion: e.target.value })}
                  placeholder="Ej: tablero electrico expuesto junto a zona humeda"
                />
              </label>
              <HoldToConfirm
                label="Mantener presionado para EJECUTAR CONTENCION"
                onConfirm={ejecutarContencion}
                disabled={!formContencion.expediente_id || !formContencion.hallazgo_codigo}
              />
              <p className="texto-secundario">
                Esta accion notifica de inmediato a la cadena de escalamiento y queda sellada
                criptograficamente con tu nombre. No se puede deshacer, solo ratificar o levantar
                con fundamento.
              </p>
            </div>

            <h2>Medidas de esta comunidad</h2>
            <div className="lista-tarjetas">
              {medidas.map((m) => (
                <div key={m.id} className="tarjeta">
                  <div className="tarjeta-header">
                    <strong>Medida #{m.id} · {m.unidad_identificador} · {m.hallazgo_codigo}</strong>
                    <EstadoBadge estado={m.estado} />
                  </div>
                  <p className="texto-secundario">
                    Ejecutada por {m.ejecutada_por_nombre} el {new Date(m.ejecutada_en).toLocaleString()}
                    {m.nivel_escalamiento > 0 && ` · escalamiento N${m.nivel_escalamiento}`}
                    {m.activa && ` · proxima revision ${new Date(m.proxima_revision).toLocaleString()}`}
                  </p>
                </div>
              ))}
              {medidas.length === 0 && <EmptyState icon={Siren} mensaje="Sin medidas de contencion registradas." />}
            </div>
          </>
        )}

        {tab === 'tickets' && (
          <>
            <PageHeader titulo="Mis tickets" subtitulo="Historial de reportes creados por ti, con su estado y evidencia adjunta." />
            <div className="lista-tarjetas" style={{ marginTop: 24 }}>
              {tickets.map((t) => (
                <div key={t.id} className="tarjeta">
                  <div className="tarjeta-header">
                    <strong>Ticket #{t.id} - {t.unidad_identificador}</strong>
                    <EstadoBadge estado={t.estado} />
                  </div>
                  <p>{t.descripcion}</p>
                  <p className="texto-secundario">{t.ubicacion} - {new Date(t.fecha_hecho).toLocaleString()}</p>

                  <div className="evidencias-grid">
                    {t.evidencias.map((ev) => (
                      <img key={ev.id} src={`${MEDIA_BASE}${ev.imagen}`} alt="evidencia" />
                    ))}
                  </div>

                  <label className="btn btn-secundario subir-evidencia">
                    {subiendoEvidencia === t.id ? 'Subiendo...' : 'Agregar foto de evidencia'}
                    <input
                      type="file"
                      accept="image/*"
                      hidden
                      onChange={(e) => e.target.files[0] && subirEvidencia(t.id, e.target.files[0])}
                    />
                  </label>
                </div>
              ))}
              {tickets.length === 0 && <EmptyState icon={ClipboardList} mensaje="Aun no has creado tickets." />}
            </div>
          </>
        )}
      </div>
    </AppShell>
  );
}
