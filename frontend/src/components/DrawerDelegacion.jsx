import { useEffect, useState } from 'react';
import { Lock, X } from 'lucide-react';
import client from '../api/client';
import CuentaRegresiva from './CuentaRegresiva';

const horasDesdeAhora = (h) => {
  const d = new Date(Date.now() + h * 3600000);
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
};

/**
 * Drawer para otorgar y monitorear delegaciones tacticas. El vencimiento es
 * el protagonista visual (no un campo enterrado): al elegir la ventana, se ve
 * la cuenta regresiva en grande — refuerza que la delegacion es acotada, no
 * estructural. GRAVISIMA aparece bloqueada: el riesgo vital no se delega.
 */
export default function DrawerDelegacion({ usuarioActual, onClose, onCambio }) {
  const [delegaciones, setDelegaciones] = useState([]);
  const [usuarios, setUsuarios] = useState([]);
  const [form, setForm] = useState({ delegado_id: '', tope_gravedad: 'GRAVE', vigencia_hasta: horasDesdeAhora(24), motivo: '' });
  const [mensaje, setMensaje] = useState('');

  const cargar = () => {
    client.get('/delegaciones/').then((res) => setDelegaciones(res.data.results || res.data));
  };

  useEffect(() => {
    cargar();
    client.get('/delegaciones/candidatos/').then((res) => setUsuarios(res.data)).catch(() => setUsuarios([]));
  }, []);

  const otorgar = async (e) => {
    e.preventDefault();
    setMensaje('');
    try {
      await client.post('/delegaciones/', {
        delegado_id: Number(form.delegado_id),
        acciones: ['RATIFICAR_CONTENCION'],
        tope_gravedad: form.tope_gravedad,
        vigencia_desde: new Date().toISOString(),
        vigencia_hasta: new Date(form.vigencia_hasta).toISOString(),
        motivo: form.motivo,
      });
      setMensaje('Delegacion otorgada y sellada con su hash de contenido.');
      setForm({ ...form, delegado_id: '', motivo: '' });
      cargar();
      onCambio && onCambio();
    } catch (err) {
      setMensaje(err.response?.data?.detail || 'No se pudo otorgar la delegacion.');
    }
  };

  const revocar = async (id) => {
    await client.post(`/delegaciones/${id}/revocar/`);
    cargar();
    onCambio && onCambio();
  };

  const misVigentes = delegaciones.filter(
    (d) => d.estado === 'VIGENTE' && d.delegante === usuarioActual?.id,
  );

  return (
    <div className="drawer-overlay" onClick={onClose}>
      <aside className="drawer" onClick={(e) => e.stopPropagation()}>
        <div className="drawer-header">
          <h3>Delegar mi facultad de ratificar</h3>
          <button className="drawer-cerrar" onClick={onClose} aria-label="Cerrar"><X size={18} /></button>
        </div>
        <div className="drawer-body">
          <p className="texto-secundario">
            Traspaso tactico y acotado: alguien firma la ratificacion en tu nombre mientras no estas
            en terreno. Queda sellado; se revoca cuando quieras.
          </p>

          <form className="formulario" onSubmit={otorgar}>
            <label>
              Delegar en
              <select value={form.delegado_id} onChange={(e) => setForm({ ...form, delegado_id: e.target.value })} required>
                <option value="">Seleccione...</option>
                {usuarios.map((u) => (
                  <option key={u.id} value={u.id}>{u.nombre} · {u.rol}</option>
                ))}
              </select>
            </label>

            <label>
              Vence el
              <input type="datetime-local" value={form.vigencia_hasta} onChange={(e) => setForm({ ...form, vigencia_hasta: e.target.value })} required />
            </label>

            {form.vigencia_hasta && (
              <div className="deleg-vencimiento">
                <div className="cuenta"><CuentaRegresiva fechaLimite={form.vigencia_hasta} cola="hasta vencer" plano /></div>
                <div className="nota">Una delegacion es tactica, no permanente: siempre tiene fin.</div>
              </div>
            )}

            <label>
              Techo de gravedad
              <select value={form.tope_gravedad} onChange={(e) => setForm({ ...form, tope_gravedad: e.target.value })}>
                <option value="LEVE">Leve</option>
                <option value="GRAVE">Grave</option>
                <option value="GRAVISIMA" disabled>Gravisima (no delegable)</option>
              </select>
            </label>
            <div className="deleg-techo-vital"><Lock size={13} /> El riesgo vital (gravisima) no se delega ad-hoc.</div>

            <label>
              Motivo (opcional)
              <input value={form.motivo} onChange={(e) => setForm({ ...form, motivo: e.target.value })} placeholder="Ej: viaje a faena Antofagasta" />
            </label>

            {mensaje && <div className="mensaje-info">{mensaje}</div>}
            <button className="btn btn-primario" type="submit" style={{ alignSelf: 'flex-start' }}>Otorgar delegacion</button>
          </form>

          {misVigentes.length > 0 && (
            <div>
              <h2 style={{ fontSize: '0.9rem', marginTop: 8 }}>Mis delegaciones vigentes</h2>
              <ul className="deleg-lista">
                {misVigentes.map((d) => (
                  <li key={d.id} className="deleg-item">
                    <div className="deleg-quien">{d.delegado_nombre} · techo {d.tope_gravedad}</div>
                    <div className="deleg-meta">
                      <CuentaRegresiva fechaLimite={d.vigencia_hasta} cola="hasta vencer" plano />
                      {d.motivo ? ` · ${d.motivo}` : ''}
                    </div>
                    <button className="btn btn-peligro" style={{ marginTop: 8 }} onClick={() => revocar(d.id)}>Revocar</button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </aside>
    </div>
  );
}
