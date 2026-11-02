import { useEffect, useState } from 'react';
import { FileText, Landmark, Send } from 'lucide-react';
import client from '../api/client';

/**
 * El Comite de Administracion como lo designo la asamblea: el acta, el
 * mandato y los miembros elegidos desde el registro de copropietarios.
 *
 * No se invita a nadie a mano: al registrar la designacion, quien ya tiene
 * cuenta pasa a Comite y quien no recibe el enlace para activar su acceso.
 * Las reglas (minimo de miembros, quien es elegible, duracion maxima) las
 * aplica el backend (condominios/comite.py) y aqui solo se muestran.
 */

const fecha = (iso) => (iso ? String(iso).slice(0, 10).split('-').reverse().join('-') : '');

const ESTADOS = {
  ACTIVO: { texto: 'Acceso activo', color: 'var(--verde, #1f8a5b)' },
  INVITADO: { texto: 'Enlace enviado', color: 'var(--ambar, #b46d00)' },
  SIN_ACTIVAR: { texto: 'Sin activar (enlace vencido)', color: 'var(--rojo, #c0362c)' },
};

const VACIO = { acta: null, fecha_asamblea: '', vigente_hasta: '', personas: [], cargos: {} };

export default function PanelComite() {
  const [estado, setEstado] = useState(null);
  const [elegibles, setElegibles] = useState([]);
  const [abierto, setAbierto] = useState(false);
  const [form, setForm] = useState(VACIO);
  const [error, setError] = useState('');
  const [mensaje, setMensaje] = useState('');
  const [enviando, setEnviando] = useState(false);

  const cargar = () => client.get('/comite/').then((r) => setEstado(r.data)).catch(() => {});
  useEffect(() => { cargar(); }, []);

  const abrir = async () => {
    setError('');
    setMensaje('');
    const { data } = await client.get('/comite/elegibles/');
    setElegibles(data);
    // Al cambiar de Comite se parte de los miembros actuales.
    setForm({ ...VACIO, personas: (estado?.miembros || []).map((m) => m.persona_id) });
    setAbierto(true);
  };

  const alternar = (id) => setForm({
    ...form,
    personas: form.personas.includes(id) ? form.personas.filter((x) => x !== id) : [...form.personas, id],
  });

  const guardar = async (e) => {
    e.preventDefault();
    setError('');
    if (!form.acta) {
      setError('Adjunta el acta de la asamblea en PDF.');
      return;
    }
    const datos = new FormData();
    datos.append('acta', form.acta);
    datos.append('fecha_asamblea', form.fecha_asamblea);
    datos.append('vigente_hasta', form.vigente_hasta);
    form.personas.forEach((id) => datos.append('personas', id));
    const cargos = Object.fromEntries(form.personas.filter((id) => form.cargos[id]).map((id) => [id, form.cargos[id]]));
    datos.append('cargos', JSON.stringify(cargos));
    setEnviando(true);
    try {
      const { data } = await client.post('/comite/designar/', datos, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setEstado(data);
      setAbierto(false);
      const enviados = data.miembros.filter((m) => m.estado === 'INVITADO').length;
      setMensaje(
        enviados
          ? `Comite registrado. ${enviados} ${enviados === 1 ? 'miembro recibio' : 'miembros recibieron'} por correo el enlace para activar su acceso.`
          : 'Comite registrado. Todos sus miembros ya tenian cuenta y tienen acceso.',
      );
    } catch (err) {
      const d = err.response?.data;
      setError(d?.detail || d?.acta || d?.personas || 'No se pudo registrar el Comite.');
    } finally {
      setEnviando(false);
    }
  };

  const reenviar = async (m) => {
    setMensaje('');
    try {
      const { data } = await client.post(`/comite/miembros/${m.id}/reenviar/`);
      setEstado(data);
      setMensaje(`Se envio un nuevo enlace a ${m.nombre}.`);
    } catch (err) {
      setMensaje(err.response?.data?.detail || 'No se pudo reenviar.');
    }
  };

  if (!estado) return null;
  const d = estado.designacion;
  const elegidos = form.personas.length;

  return (
    <div className="tarjeta" style={{ marginBottom: 18 }}>
      <strong><Landmark size={15} style={{ verticalAlign: 'middle', marginRight: 6 }} />Comite de Administracion</strong>
      <p className="texto-secundario" style={{ margin: '6px 0 0' }}>
        Lo elige la asamblea. Registra el acta y marca a sus miembros desde el registro de
        copropietarios: solo ellos pueden decidir como Comite, y solo mientras dure su mandato.
      </p>

      {mensaje && <div className="mensaje-info" style={{ marginTop: 10 }}>{mensaje}</div>}
      {estado.alertas.map((a) => (
        <div key={a} className={estado.vigente && !estado.sin_designacion ? 'mensaje-info' : 'mensaje-error'} style={{ marginTop: 10 }}>{a}</div>
      ))}

      {d && (
        <div style={{ marginTop: 12 }}>
          <p style={{ margin: 0 }}>
            Elegido en asamblea del <strong>{fecha(d.fecha_asamblea)}</strong>, mandato hasta el{' '}
            <strong>{fecha(d.vigente_hasta)}</strong>
            {d.acta && (
              <> · <a href={d.acta} target="_blank" rel="noreferrer"><FileText size={13} style={{ verticalAlign: 'middle' }} /> Ver acta</a></>
            )}
          </p>
          <p className="texto-secundario" style={{ margin: '4px 0 0' }}>
            {estado.activos} de {estado.miembros.length} con acceso activo · quorum para resolver: {estado.quorum}
          </p>
          {estado.miembros.map((m) => (
            <div key={m.id} className="fila-formulario" style={{ alignItems: 'center', flexWrap: 'wrap', marginTop: 10, paddingTop: 10, borderTop: '1px solid var(--borde, #e7e7f0)' }}>
              <span style={{ minWidth: 220, flex: 1 }}>
                <strong>{m.nombre}</strong>{m.cargo ? ` · ${m.cargo}` : ''}
                <br />
                <span className="texto-secundario">{m.unidad}{m.correo ? ` · ${m.correo}` : ''}</span>
              </span>
              <span style={{ color: ESTADOS[m.estado].color, fontWeight: 600, fontSize: '0.85rem' }}>
                {ESTADOS[m.estado].texto}
                {m.estado === 'INVITADO' && m.invitacion_vence ? ` (vence ${fecha(m.invitacion_vence)})` : ''}
              </span>
              {m.estado !== 'ACTIVO' && (
                <button className="btn btn-secundario" type="button" onClick={() => reenviar(m)}>
                  <Send size={14} /> Reenviar enlace
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {!abierto && (
        <button className="btn btn-primario" type="button" style={{ marginTop: 14 }} onClick={abrir}>
          {d ? 'Registrar nueva designacion (cambio de Comite)' : 'Registrar el Comite'}
        </button>
      )}

      {abierto && (
        <form className="formulario" onSubmit={guardar} style={{ marginTop: 14 }}>
          <div className="fila-formulario" style={{ flexWrap: 'wrap' }}>
            <label>
              Fecha de la asamblea
              <input type="date" required value={form.fecha_asamblea} onChange={(e) => setForm({ ...form, fecha_asamblea: e.target.value })} />
            </label>
            <label>
              Mandato hasta
              <input type="date" required value={form.vigente_hasta} onChange={(e) => setForm({ ...form, vigente_hasta: e.target.value })} />
            </label>
          </div>
          <label className="btn btn-secundario subir-evidencia" style={{ alignSelf: 'flex-start' }}>
            {form.acta ? `Acta: ${form.acta.name}` : 'Adjuntar acta de la asamblea (PDF)'}
            <input type="file" accept="application/pdf" hidden onChange={(e) => setForm({ ...form, acta: e.target.files[0] || null })} />
          </label>

          <div>
            <strong style={{ fontSize: '0.9rem' }}>
              Miembros elegidos ({elegidos}{estado.minimo ? `, minimo ${estado.minimo}` : ''})
            </strong>
            <p className="texto-secundario" style={{ margin: '4px 0 8px' }}>
              Pueden integrarlo los propietarios y su conyuge o conviviente civil, con correo en el registro.
            </p>
            <div style={{ maxHeight: 320, overflowY: 'auto', border: '1px solid var(--borde, #e7e7f0)', borderRadius: 10, padding: '4px 10px' }}>
              {elegibles.length === 0 && <p className="texto-secundario">Primero carga el registro de copropietarios.</p>}
              {elegibles.map((p) => {
                const marcado = form.personas.includes(p.id);
                return (
                  <div key={p.id} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '7px 0', borderBottom: '1px solid var(--borde, #f0f0f6)', opacity: p.motivo_no_elegible ? 0.55 : 1, flexWrap: 'wrap' }}>
                    <input
                      type="checkbox" style={{ width: 'auto', minHeight: 0 }} checked={marcado}
                      disabled={Boolean(p.motivo_no_elegible)} onChange={() => alternar(p.id)}
                      aria-label={p.nombre}
                    />
                    <span style={{ flex: 1, minWidth: 180 }}>
                      {p.nombre} <span className="texto-secundario">· {p.unidad} · {p.rol_ocupacion}</span>
                      {p.motivo_no_elegible && <><br /><span className="texto-secundario">No elegible: {p.motivo_no_elegible}</span></>}
                    </span>
                    {marcado && (
                      <input
                        placeholder="Cargo (opcional)" value={form.cargos[p.id] || ''} style={{ maxWidth: 170 }}
                        onChange={(e) => setForm({ ...form, cargos: { ...form.cargos, [p.id]: e.target.value } })}
                      />
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {error && <div className="mensaje-error">{error}</div>}
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <button className="btn btn-primario" type="submit" disabled={enviando}>
              {enviando ? 'Registrando...' : 'Registrar Comite y dar acceso'}
            </button>
            <button className="btn btn-secundario" type="button" onClick={() => setAbierto(false)}>Cancelar</button>
          </div>
          {d && (
            <p className="texto-secundario" style={{ margin: 0 }}>
              La designacion actual queda en el historial. Quien no siga en el Comite vuelve a ser Residente.
            </p>
          )}
        </form>
      )}
    </div>
  );
}
