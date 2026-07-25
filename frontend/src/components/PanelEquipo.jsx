import { useEffect, useState } from 'react';
import { Copy, MailPlus, UserCheck } from 'lucide-react';
import client from '../api/client';

const ROLES = [
  { valor: 'RESIDENTE', etiqueta: 'Residente' },
  { valor: 'FISCALIZADOR', etiqueta: 'Fiscalizador (Conserje)' },
  { valor: 'COMITE', etiqueta: 'Comite de Administracion' },
];

export default function PanelEquipo() {
  const [invitaciones, setInvitaciones] = useState([]);
  const [pendientes, setPendientes] = useState([]);
  const [unidades, setUnidades] = useState([]);
  const [codigoComunidad, setCodigoComunidad] = useState(null);
  const [form, setForm] = useState({ correo: '', unidad: '', rol_sugerido: 'RESIDENTE' });
  const [rolesElegidos, setRolesElegidos] = useState({});
  const [mensaje, setMensaje] = useState('');

  const cargar = () => {
    client.get('/invitaciones/').then((r) => setInvitaciones(r.data.results || r.data)).catch(() => {});
    client.get('/usuarios/pendientes/').then((r) => setPendientes(r.data)).catch(() => {});
    client.get('/unidades/').then((r) => setUnidades(r.data.results || r.data)).catch(() => {});
    client.get('/condominios/').then((r) => {
      const lista = r.data.results || r.data;
      if (lista.length) setCodigoComunidad(lista[0].codigo_comunidad);
    }).catch(() => {});
  };

  useEffect(cargar, []);

  const invitar = async (e) => {
    e.preventDefault();
    setMensaje('');
    try {
      const payload = { correo: form.correo, rol_sugerido: form.rol_sugerido };
      if (form.unidad) payload.unidad = form.unidad;
      const { data } = await client.post('/invitaciones/', payload);
      setMensaje(`Invitacion enviada a ${data.correo}. Codigo: ${data.codigo}`);
      setForm({ correo: '', unidad: '', rol_sugerido: 'RESIDENTE' });
      cargar();
    } catch (err) {
      const detalle = err.response?.data;
      setMensaje(
        detalle?.detail || detalle?.correo?.[0] || detalle?.rol_sugerido?.[0] || 'Error al invitar.',
      );
    }
  };

  const revocar = async (id) => {
    await client.post(`/invitaciones/${id}/revocar/`);
    cargar();
  };

  const confirmarRol = async (usuarioId) => {
    const rol = rolesElegidos[usuarioId] || 'RESIDENTE';
    setMensaje('');
    try {
      await client.post(`/usuarios/${usuarioId}/asignar-rol/`, { rol });
      setMensaje('Rol asignado. La persona ya puede usar la plataforma.');
      cargar();
    } catch (err) {
      setMensaje(err.response?.data?.detail || 'Error al asignar el rol.');
    }
  };

  const copiarCodigo = () => {
    if (!codigoComunidad) return;
    navigator.clipboard?.writeText(codigoComunidad);
    setMensaje('Codigo de comunidad copiado.');
  };

  const invitacionesPendientes = invitaciones.filter((i) => i.estado === 'PENDIENTE');

  return (
    <div>
      {mensaje && <div className="mensaje-info">{mensaje}</div>}

      {codigoComunidad && (
        <div className="tarjeta" style={{ marginBottom: 18 }}>
          <strong>Codigo Unico de Comunidad</strong>
          <p className="texto-secundario" style={{ margin: '6px 0 10px' }}>
            Compartelo con tus vecinos: entran con Google + este codigo y te llegan aqui
            para confirmarles su rol.
          </p>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <code style={{ fontSize: '1.15rem', letterSpacing: '0.12em' }}>{codigoComunidad}</code>
            <button className="btn btn-secundario" type="button" onClick={copiarCodigo}>
              <Copy size={14} /> Copiar
            </button>
          </div>
        </div>
      )}

      <form className="tarjeta formulario" onSubmit={invitar} style={{ marginBottom: 18 }}>
        <strong><MailPlus size={15} style={{ verticalAlign: 'middle', marginRight: 6 }} />Invitar a una persona</strong>
        <div className="fila-formulario" style={{ alignItems: 'flex-end', flexWrap: 'wrap' }}>
          <label>
            Correo (cuenta Google)
            <input
              type="email" required value={form.correo}
              onChange={(e) => setForm({ ...form, correo: e.target.value })}
            />
          </label>
          <label>
            Unidad (opcional)
            <select value={form.unidad} onChange={(e) => setForm({ ...form, unidad: e.target.value })}>
              <option value="">Sin unidad</option>
              {unidades.map((u) => (
                <option key={u.id} value={u.id}>{u.identificador}</option>
              ))}
            </select>
          </label>
          <label>
            Rol sugerido
            <select
              value={form.rol_sugerido}
              onChange={(e) => setForm({ ...form, rol_sugerido: e.target.value })}
            >
              {ROLES.map((r) => <option key={r.valor} value={r.valor}>{r.etiqueta}</option>)}
            </select>
          </label>
          <button className="btn btn-primario" type="submit">Enviar invitacion</button>
        </div>
      </form>

      <div className="tarjeta" style={{ marginBottom: 18 }}>
        <strong><UserCheck size={15} style={{ verticalAlign: 'middle', marginRight: 6 }} />Cuentas por confirmar ({pendientes.length})</strong>
        {pendientes.length === 0 && (
          <p className="texto-secundario" style={{ marginTop: 8 }}>
            Nadie espera asignacion de rol por ahora.
          </p>
        )}
        {pendientes.map((p) => (
          <div key={p.id} className="fila-formulario" style={{ alignItems: 'center', marginTop: 10, flexWrap: 'wrap' }}>
            <span style={{ minWidth: 220 }}>{p.nombre} · {p.email}</span>
            <select
              value={rolesElegidos[p.id] || 'RESIDENTE'}
              onChange={(e) => setRolesElegidos({ ...rolesElegidos, [p.id]: e.target.value })}
            >
              {ROLES.map((r) => <option key={r.valor} value={r.valor}>{r.etiqueta}</option>)}
            </select>
            <button className="btn btn-primario" type="button" onClick={() => confirmarRol(p.id)}>
              Confirmar rol
            </button>
          </div>
        ))}
      </div>

      <div className="tarjeta">
        <strong>Invitaciones pendientes ({invitacionesPendientes.length})</strong>
        {invitacionesPendientes.length === 0 && (
          <p className="texto-secundario" style={{ marginTop: 8 }}>Sin invitaciones abiertas.</p>
        )}
        {invitacionesPendientes.map((i) => (
          <div key={i.id} className="fila-formulario" style={{ alignItems: 'center', marginTop: 10, flexWrap: 'wrap' }}>
            <span style={{ minWidth: 220 }}>{i.correo} · {i.rol_sugerido}{i.unidad_identificador ? ` · ${i.unidad_identificador}` : ''}</span>
            <code>{i.codigo}</code>
            <button className="btn btn-secundario" type="button" onClick={() => revocar(i.id)}>
              Revocar
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
