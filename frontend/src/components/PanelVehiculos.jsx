import { useEffect, useState } from 'react';
import { CarFront, Trash2 } from 'lucide-react';
import client from '../api/client';

/**
 * Patentes de cada unidad. Con ellas una alerta de "me bloquean la salida"
 * llega directo al dueno del auto. Tambien se cargan con la columna
 * "patentes" del Excel del registro.
 */
export default function PanelVehiculos() {
  const [vehiculos, setVehiculos] = useState([]);
  const [unidades, setUnidades] = useState([]);
  const [form, setForm] = useState({ unidad: '', patente: '', descripcion: '' });
  const [error, setError] = useState('');

  const cargar = () => client.get('/vehiculos/').then((r) => setVehiculos(r.data.results || r.data)).catch(() => {});
  useEffect(() => {
    cargar();
    client.get('/unidades/').then((r) => setUnidades(r.data.results || r.data)).catch(() => {});
  }, []);

  const agregar = async (e) => {
    e.preventDefault();
    setError('');
    try {
      await client.post('/vehiculos/', form);
      setForm({ ...form, patente: '', descripcion: '' });
      cargar();
    } catch (err) {
      const d = err.response?.data;
      setError(d?.patente?.[0] || d?.patente || d?.unidad?.[0] || d?.detail || 'No se pudo agregar.');
    }
  };

  const quitar = async (v) => {
    if (!window.confirm(`¿Quitar la patente ${v.patente} de ${v.unidad_identificador}?`)) return;
    await client.delete(`/vehiculos/${v.id}/`);
    cargar();
  };

  return (
    <div className="tarjeta formulario" style={{ marginTop: 18 }}>
      <strong><CarFront size={15} style={{ verticalAlign: 'middle', marginRight: 6 }} />Vehiculos de la comunidad ({vehiculos.length})</strong>
      <p className="texto-secundario" style={{ margin: 0 }}>
        Con la patente, una alerta de "me bloquean la salida" le llega directo al dueno del auto.
        Solo tu ves esta lista. Tambien puedes cargarlas con la columna <code>patentes</code> del Excel.
      </p>
      <form className="fila-formulario" onSubmit={agregar} style={{ alignItems: 'flex-end', flexWrap: 'wrap' }}>
        <label>
          Unidad
          <select required value={form.unidad} onChange={(e) => setForm({ ...form, unidad: e.target.value })}>
            <option value="">Elige</option>
            {unidades.map((u) => <option key={u.id} value={u.id}>{u.identificador}</option>)}
          </select>
        </label>
        <label>
          Patente
          <input required value={form.patente} placeholder="ABCD12" onChange={(e) => setForm({ ...form, patente: e.target.value.toUpperCase() })} />
        </label>
        <label>
          Descripcion (opcional)
          <input value={form.descripcion} placeholder="Toyota gris" onChange={(e) => setForm({ ...form, descripcion: e.target.value })} />
        </label>
        <button className="btn btn-primario" type="submit">Agregar</button>
      </form>
      {error && <div className="mensaje-error">{error}</div>}
      {vehiculos.map((v) => (
        <div key={v.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, padding: '8px 0', borderTop: '1px solid var(--borde, #e7e7f0)' }}>
          <span><strong>{v.patente}</strong> · {v.unidad_identificador}{v.descripcion ? ` · ${v.descripcion}` : ''}</span>
          <button className="btn btn-fantasma" type="button" onClick={() => quitar(v)} aria-label={`Quitar ${v.patente}`}>
            <Trash2 size={15} />
          </button>
        </div>
      ))}
    </div>
  );
}
