import { useEffect, useRef, useState } from 'react';
import { CheckCircle2, Siren } from 'lucide-react';
import client, { MEDIA_BASE } from '../api/client';
import EmptyState from './EmptyState';

/**
 * Las alertas de los vecinos, para quien esta en terreno. Se refresca solo
 * cada pocos segundos y suena y vibra cuando llega una nueva, porque una
 * alerta que se descubre al recargar la pantalla ya llego tarde.
 *
 * `onCantidad` informa cuantas hay abiertas (para el numerito de la pestana).
 */

const CADA_MS = 15000;

function sonar() {
  try {
    navigator.vibrate?.([300, 120, 300]);
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return;
    const ctx = new Ctx();
    [0, 0.35].forEach((retraso) => {
      const osc = ctx.createOscillator();
      const vol = ctx.createGain();
      osc.frequency.value = 880;
      vol.gain.value = 0.15;
      osc.connect(vol).connect(ctx.destination);
      osc.start(ctx.currentTime + retraso);
      osc.stop(ctx.currentTime + retraso + 0.22);
    });
  } catch {
    // El navegador puede bloquear el sonido hasta que la persona toque la pantalla.
  }
}

const urlFoto = (foto) => (!foto ? null : foto.startsWith('http') ? foto : `${MEDIA_BASE}${foto}`);

export default function PanelAlertas({ onCantidad }) {
  const [alertas, setAlertas] = useState([]);
  const [mensaje, setMensaje] = useState('');
  const conocidas = useRef(null);

  const cargar = () => client.get('/alertas/', { params: { estado: 'ABIERTA' } })
    .then((r) => {
      const lista = r.data.results || r.data;
      const ids = new Set(lista.map((a) => a.id));
      if (conocidas.current && lista.some((a) => !conocidas.current.has(a.id))) sonar();
      conocidas.current = ids;
      setAlertas(lista);
      onCantidad?.(lista.length);
    })
    .catch(() => {});

  useEffect(() => {
    cargar();
    const intervalo = setInterval(cargar, CADA_MS);
    return () => clearInterval(intervalo);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const atender = async (a) => {
    const nota = window.prompt('¿Como se resolvio? (opcional, le llega a quien aviso)') ?? null;
    if (nota === null) return;
    try {
      await client.post(`/alertas/${a.id}/atender/`, { nota });
      setMensaje(`Alerta #${a.id} marcada como atendida.`);
      cargar();
    } catch (err) {
      setMensaje(err.response?.data?.detail || 'No se pudo marcar como atendida.');
    }
  };

  return (
    <div>
      {mensaje && <div className="mensaje-info">{mensaje}</div>}
      {alertas.length === 0 && (
        <EmptyState icon={Siren} mensaje="No hay alertas abiertas. Esta pantalla se actualiza sola y suena cuando llega una." />
      )}
      {alertas.map((a) => (
        <div key={a.id} className="tarjeta" style={{ borderColor: 'var(--rojo, #c0362c)', marginBottom: 12 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, flexWrap: 'wrap' }}>
            <strong style={{ color: 'var(--rojo, #c0362c)' }}><Siren size={16} style={{ verticalAlign: 'middle' }} /> {a.tipo_nombre}</strong>
            <span className="texto-secundario">{new Date(a.creada_en).toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit' })}</span>
          </div>
          <p style={{ margin: '8px 0 4px' }}>
            {a.patente && <>Patente <strong>{a.patente}</strong> · </>}
            {a.unidad_vehiculo_identificador
              ? <>vehiculo de <strong>{a.unidad_vehiculo_identificador}</strong> (ya se le aviso)</>
              : a.patente ? 'patente no registrada: ubicar al dueno en terreno' : 'sin patente'}
          </p>
          <p className="texto-secundario" style={{ margin: 0 }}>
            Avisa {a.creada_por_nombre}{a.unidad_afectada_identificador ? `, ${a.unidad_afectada_identificador}` : ''}
          </p>
          {a.descripcion && <p style={{ margin: '6px 0 0' }}>"{a.descripcion}"</p>}
          {urlFoto(a.foto) && (
            <a href={urlFoto(a.foto)} target="_blank" rel="noreferrer">
              <img src={urlFoto(a.foto)} alt="Foto de la alerta" style={{ marginTop: 8, maxWidth: '100%', maxHeight: 220, borderRadius: 10 }} />
            </a>
          )}
          <button className="btn btn-exito" type="button" style={{ marginTop: 10 }} onClick={() => atender(a)}>
            <CheckCircle2 size={16} /> Marcar como atendida
          </button>
        </div>
      ))}
    </div>
  );
}
