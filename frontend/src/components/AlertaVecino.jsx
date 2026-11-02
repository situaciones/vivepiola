import { useEffect, useState } from 'react';
import { Camera, CarFront, ParkingSquare, Siren } from 'lucide-react';
import client from '../api/client';
import EstadoBadge from './EstadoBadge';

/**
 * El vecino avisa algo que no puede esperar. Llega al momento a los guardias
 * de turno, a la administracion y, si la patente esta registrada, a la unidad
 * duena del auto. Ademas queda un reporte normal sobre esa unidad: la multa,
 * si corresponde, sigue su curso como cualquier otra.
 */

const TIPOS = [
  { valor: 'SALIDA_BLOQUEADA', texto: 'Me bloquean la salida', icono: CarFront },
  { valor: 'ESTACIONAMIENTO_OCUPADO', texto: 'Ocupan mi estacionamiento', icono: ParkingSquare },
  { valor: 'OTRA', texto: 'Otra urgencia', icono: Siren },
];

const VACIO = { tipo: 'SALIDA_BLOQUEADA', patente: '', descripcion: '', foto: null };

export default function AlertaVecino() {
  const [form, setForm] = useState(VACIO);
  const [alertas, setAlertas] = useState([]);
  const [error, setError] = useState('');
  const [mensaje, setMensaje] = useState('');
  const [enviando, setEnviando] = useState(false);

  const cargar = () => client.get('/alertas/').then((r) => setAlertas(r.data.results || r.data)).catch(() => {});
  useEffect(() => { cargar(); }, []);

  const enviar = async (e) => {
    e.preventDefault();
    setError('');
    setMensaje('');
    const datos = new FormData();
    datos.append('tipo', form.tipo);
    datos.append('patente', form.patente);
    datos.append('descripcion', form.descripcion);
    if (form.foto) datos.append('foto', form.foto);
    setEnviando(true);
    try {
      const { data } = await client.post('/alertas/', datos, { headers: { 'Content-Type': 'multipart/form-data' } });
      setMensaje(
        data.unidad_vehiculo_identificador
          ? `Alerta enviada. Avisamos a los guardias de turno y a ${data.unidad_vehiculo_identificador}, duena del vehiculo.`
          : 'Alerta enviada a los guardias de turno y a la administracion.',
      );
      setForm(VACIO);
      cargar();
    } catch (err) {
      const d = err.response?.data;
      setError(
        err.response?.status === 429
          ? 'Enviaste muchas alertas seguidas. Si es urgente, llama a conserjeria.'
          : d?.detail || d?.patente || d?.descripcion || 'No se pudo enviar la alerta.',
      );
    } finally {
      setEnviando(false);
    }
  };

  const conVehiculo = form.tipo !== 'OTRA';

  return (
    <div>
      <form className="tarjeta formulario" onSubmit={enviar}>
        <strong>¿Que pasa?</strong>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 10 }}>
          {TIPOS.map(({ valor, texto, icono: Icono }) => (
            <button
              key={valor} type="button"
              className={`btn ${form.tipo === valor ? 'btn-primario' : 'btn-secundario'}`}
              style={{ minHeight: 64, flexDirection: 'column', gap: 6 }}
              onClick={() => setForm({ ...form, tipo: valor })}
              aria-pressed={form.tipo === valor}
            >
              <Icono size={22} /> {texto}
            </button>
          ))}
        </div>

        {conVehiculo && (
          <label>
            Patente del vehiculo
            <input
              value={form.patente} placeholder="Ej: ABCD12" autoCapitalize="characters" autoComplete="off"
              onChange={(e) => setForm({ ...form, patente: e.target.value.toUpperCase() })}
            />
          </label>
        )}
        <label className="btn btn-secundario subir-evidencia" style={{ alignSelf: 'flex-start' }}>
          <Camera size={16} /> {form.foto ? `Foto: ${form.foto.name}` : 'Tomar foto (recomendado)'}
          <input
            type="file" accept="image/*" capture="environment" hidden
            onChange={(e) => setForm({ ...form, foto: e.target.files[0] || null })}
          />
        </label>
        <label>
          {conVehiculo ? 'Detalle (opcional)' : 'Cuenta brevemente que pasa'}
          <textarea
            rows={2} value={form.descripcion} maxLength={500}
            onChange={(e) => setForm({ ...form, descripcion: e.target.value })}
            placeholder={conVehiculo ? 'Ej: auto gris frente a mi porton, no puedo salir' : ''}
          />
        </label>

        {error && <div className="mensaje-error">{error}</div>}
        {mensaje && <div className="mensaje-info">{mensaje}</div>}
        <button className="btn btn-primario" type="submit" disabled={enviando} style={{ minHeight: 52 }}>
          <Siren size={18} /> {enviando ? 'Enviando...' : 'Enviar alerta ahora'}
        </button>
        <p className="texto-secundario" style={{ margin: 0 }}>
          Llega al instante a los guardias de turno. Si la patente esta registrada, tambien al dueno del auto.
          El hecho queda registrado y la administracion puede aplicar la multa que corresponda.
        </p>
      </form>

      {alertas.length > 0 && (
        <div className="tarjeta" style={{ marginTop: 14 }}>
          <strong>Mis alertas</strong>
          {alertas.map((a) => (
            <div key={a.id} style={{ display: 'flex', justifyContent: 'space-between', gap: 10, padding: '10px 0', borderTop: '1px solid var(--borde, #e7e7f0)', flexWrap: 'wrap' }}>
              <span>
                {a.tipo_nombre}{a.patente ? ` · ${a.patente}` : ''}
                <br />
                <span className="texto-secundario">
                  {new Date(a.creada_en).toLocaleString('es-CL')}
                  {a.atendida_por_nombre ? ` · atendida por ${a.atendida_por_nombre}` : ''}
                  {a.nota_atencion ? `: ${a.nota_atencion}` : ''}
                </span>
              </span>
              <EstadoBadge estado={a.estado === 'ABIERTA' ? 'ALERTA_ABIERTA' : 'ALERTA_ATENDIDA'} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
