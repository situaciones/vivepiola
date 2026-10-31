import { useEffect, useState } from 'react';
import { ShieldCheck } from 'lucide-react';
import client from '../api/client';

export const DIAS = ['Lun', 'Mar', 'Mie', 'Jue', 'Vie', 'Sab', 'Dom'];

const fecha = (iso) => iso.split('-').reverse().join('-');

// Una linea legible con los limites de un permiso; null = sin limites.
export function resumenPermiso(p) {
  if (!p) return 'Sin limites: puede reportar siempre y en toda la comunidad.';
  if (p.suspendido) return 'Suspendido: no puede reportar.';
  const partes = [];
  if (p.vigente_desde || p.vigente_hasta) {
    partes.push(
      [p.vigente_desde && `desde el ${fecha(p.vigente_desde)}`, p.vigente_hasta && `hasta el ${fecha(p.vigente_hasta)}`]
        .filter(Boolean).join(' '),
    );
  }
  if (p.dias?.length) partes.push(p.dias.map((d) => DIAS[d]).join(', '));
  if (p.hora_desde && p.hora_hasta) partes.push(`de ${p.hora_desde.slice(0, 5)} a ${p.hora_hasta.slice(0, 5)}`);
  if (p.unidades_identificadores?.length) partes.push(`solo en ${p.unidades_identificadores.join(', ')}`);
  return partes.length ? partes.join(' · ') : 'Sin limites: puede reportar siempre y en toda la comunidad.';
}

const VACIO = {
  suspendido: false, vigente_desde: '', vigente_hasta: '', dias: [], hora_desde: '', hora_hasta: '',
  unidades: [], notas: '',
};

function desdePermiso(p) {
  if (!p) return VACIO;
  return {
    suspendido: p.suspendido,
    vigente_desde: p.vigente_desde || '',
    vigente_hasta: p.vigente_hasta || '',
    dias: p.dias || [],
    hora_desde: p.hora_desde?.slice(0, 5) || '',
    hora_hasta: p.hora_hasta?.slice(0, 5) || '',
    unidades: p.unidades || [],
    notas: p.notas || '',
  };
}

function primerError(data) {
  if (!data) return 'No se pudo guardar.';
  if (data.detail) return data.detail;
  const valor = Object.values(data)[0];
  return Array.isArray(valor) ? valor[0] : String(valor);
}

export default function PanelDenunciantes({ unidades }) {
  const [denunciantes, setDenunciantes] = useState([]);
  const [editando, setEditando] = useState(null);
  const [form, setForm] = useState(VACIO);
  const [error, setError] = useState('');

  const cargar = () => client.get('/usuarios/denunciantes/').then((r) => setDenunciantes(r.data)).catch(() => {});
  useEffect(() => { cargar(); }, []);

  const abrir = (f) => {
    setEditando(f.id);
    setForm(desdePermiso(f.permiso));
    setError('');
  };

  const alternarDia = (d) => setForm({
    ...form, dias: form.dias.includes(d) ? form.dias.filter((x) => x !== d) : [...form.dias, d],
  });

  const guardar = async (e) => {
    e.preventDefault();
    setError('');
    try {
      await client.put(`/usuarios/${editando}/permiso-denuncia/`, {
        ...form,
        vigente_desde: form.vigente_desde || null,
        vigente_hasta: form.vigente_hasta || null,
        hora_desde: form.hora_desde || null,
        hora_hasta: form.hora_hasta || null,
      });
      setEditando(null);
      cargar();
    } catch (err) {
      setError(primerError(err.response?.data));
    }
  };

  const quitarLimites = async () => {
    await client.delete(`/usuarios/${editando}/permiso-denuncia/`);
    setEditando(null);
    cargar();
  };

  return (
    <div className="tarjeta" style={{ marginBottom: 18 }}>
      <strong><ShieldCheck size={15} style={{ verticalAlign: 'middle', marginRight: 6 }} />Denunciantes y sus limites ({denunciantes.length})</strong>
      <p className="texto-secundario" style={{ margin: '6px 0 0' }}>
        Acota cuando y donde reporta cada Denunciante. Fuera de esos limites la app no le deja reportar.
        Comite y residentes reportan siempre: la ley les da ese derecho.
      </p>
      {denunciantes.length === 0 && (
        <p className="texto-secundario" style={{ marginTop: 8 }}>
          Aun no hay Denunciantes. Invita a uno con el rol Denunciante.
        </p>
      )}
      {denunciantes.map((f) => (
        <div key={f.id} style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid var(--borde, #e7e7f0)' }}>
          <div className="fila-formulario" style={{ alignItems: 'center', flexWrap: 'wrap' }}>
            <span style={{ minWidth: 220 }}>
              <strong>{f.nombre}</strong>{f.email ? ` · ${f.email}` : ''}
              <br />
              <span className="texto-secundario">{resumenPermiso(f.permiso)}</span>
            </span>
            {editando !== f.id && (
              <button className="btn btn-secundario" type="button" onClick={() => abrir(f)}>
                Editar limites
              </button>
            )}
          </div>

          {editando === f.id && (
            <form className="formulario" onSubmit={guardar} style={{ marginTop: 10 }}>
              {error && <div className="mensaje-error">{error}</div>}
              <label style={{ display: 'flex', flexDirection: 'row', gap: 8, alignItems: 'center', justifyContent: 'flex-start' }}>
                <input
                  type="checkbox" checked={form.suspendido}
                  onChange={(e) => setForm({ ...form, suspendido: e.target.checked })}
                  style={{ width: 'auto' }}
                />
                Suspender (no puede reportar hasta que lo reactives)
              </label>
              <div className="fila-formulario" style={{ flexWrap: 'wrap' }}>
                <label>
                  Desde (opcional)
                  <input type="date" value={form.vigente_desde} onChange={(e) => setForm({ ...form, vigente_desde: e.target.value })} />
                </label>
                <label>
                  Hasta (opcional)
                  <input type="date" value={form.vigente_hasta} onChange={(e) => setForm({ ...form, vigente_hasta: e.target.value })} />
                </label>
                <label>
                  Hora de inicio
                  <input type="time" value={form.hora_desde} onChange={(e) => setForm({ ...form, hora_desde: e.target.value })} />
                </label>
                <label>
                  Hora de termino
                  <input type="time" value={form.hora_hasta} onChange={(e) => setForm({ ...form, hora_hasta: e.target.value })} />
                </label>
              </div>
              <p className="texto-secundario" style={{ margin: '0 0 6px' }}>
                Si la hora de termino es menor que la de inicio, el turno cruza la medianoche (ej. 22:00 a 06:00).
              </p>
              <div>
                <span>Dias (ninguno marcado = todos)</span>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 6 }}>
                  {DIAS.map((d, i) => (
                    <button
                      key={d} type="button"
                      className={`btn ${form.dias.includes(i) ? 'btn-primario' : 'btn-secundario'}`}
                      onClick={() => alternarDia(i)}
                    >
                      {d}
                    </button>
                  ))}
                </div>
              </div>
              <label>
                Unidades sobre las que puede reportar (ninguna marcada = todas)
                <select
                  multiple value={form.unidades.map(String)} size={Math.min(6, Math.max(3, unidades.length))}
                  onChange={(e) => setForm({ ...form, unidades: [...e.target.selectedOptions].map((o) => Number(o.value)) })}
                >
                  {unidades.map((u) => <option key={u.id} value={u.id}>{u.identificador}</option>)}
                </select>
              </label>
              <label>
                Nota (opcional)
                <input value={form.notas} maxLength={255} placeholder="Ej: guardia turno noche"
                  onChange={(e) => setForm({ ...form, notas: e.target.value })} />
              </label>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <button className="btn btn-primario" type="submit">Guardar limites</button>
                {f.permiso && (
                  <button className="btn btn-secundario" type="button" onClick={quitarLimites}>Quitar todos los limites</button>
                )}
                <button className="btn btn-secundario" type="button" onClick={() => setEditando(null)}>Cancelar</button>
              </div>
            </form>
          )}
        </div>
      ))}
    </div>
  );
}
