import { useEffect, useState } from 'react';
import { KeyRound, PenLine } from 'lucide-react';
import client from '../api/client';
import { useAuth } from '../context/AuthContext';
import QuorumBar from './QuorumBar';
import HoldToConfirm from './HoldToConfirm';
import EmptyState from './EmptyState';
import CuentaRegresiva from './CuentaRegresiva';

/**
 * Superficie de firma para el DELEGADO (un jefe de area que no es Comite pero
 * recibio la facultad de ratificar). Cierra el ciclo de la delegacion: quien
 * recibio la firma puede aportarla desde su propio panel, con el banner que
 * refleja bajo que autoridad actua — el mismo dato que quedara sellado.
 */
export default function PanelFirmasDelegadas() {
  const { usuario } = useAuth();
  const [delegaciones, setDelegaciones] = useState([]);
  const [medidas, setMedidas] = useState([]);
  const [mensaje, setMensaje] = useState('');

  const cargar = () => {
    client.get('/delegaciones/').then((r) => {
      const mias = (r.data.results || r.data).filter(
        (d) => d.estado === 'VIGENTE' && d.delegado === usuario?.id,
      );
      setDelegaciones(mias);
    });
    client.get('/medidas-inmediatas/').then((r) => setMedidas(r.data.results || r.data));
  };

  useEffect(cargar, []);

  const firmables = medidas.filter(
    (m) => (m.estado === 'EJECUTADA' || m.estado === 'EN_ESCALAMIENTO') && !m.ya_vote,
  );

  const firmar = async (id) => {
    try {
      const res = await client.post(`/medidas-inmediatas/${id}/ratificar/`);
      const m = res.data;
      setMensaje(
        m.estado === 'RATIFICADA'
          ? `Firma registrada. Quorum completo (${m.votos_emitidos}/${m.quorum_requerido}): contencion ratificada.`
          : `Tu firma quedo sellada. Faltan ${m.quorum_requerido - m.votos_emitidos} firma(s) para completar el quorum.`,
      );
      cargar();
    } catch (err) {
      setMensaje(err.response?.data?.detail || 'No pudiste registrar tu firma.');
    }
  };

  if (delegaciones.length === 0) {
    return (
      <EmptyState
        icon={KeyRound}
        mensaje="No tienes delegaciones vigentes. Cuando alguien te delegue su firma, las paralizaciones por ratificar apareceran aqui."
      />
    );
  }

  return (
    <>
      {mensaje && <div className="mensaje-info">{mensaje}</div>}

      {delegaciones.map((d) => (
        <div className="banner-delegacion" key={d.id}>
          <KeyRound size={16} />
          <span>
            Actuas por delegacion de <strong>{d.delegante_nombre}</strong> ·{' '}
            techo {d.tope_gravedad} ·{' '}
            <CuentaRegresiva fechaLimite={d.vigencia_hasta} cola="hasta vencer" plano />
          </span>
        </div>
      ))}

      <div className="lista-tarjetas" style={{ marginTop: 12 }}>
        {firmables.map((m) => (
          <div key={m.id} className="tarjeta">
            <div className="tarjeta-header">
              <strong>Medida #{m.id} · {m.unidad_identificador} · {m.hallazgo_codigo}</strong>
            </div>
            <p>{m.hallazgo_descripcion}</p>
            <p className="texto-secundario">
              Ejecutada por {m.ejecutada_por_nombre} · {new Date(m.ejecutada_en).toLocaleString()}
              {m.nivel_escalamiento > 0 && ` · escalamiento N${m.nivel_escalamiento}`}
            </p>
            <QuorumBar medida={m} />
            <div className="acciones">
              <HoldToConfirm
                label="Mantener para AGREGAR MI FIRMA"
                className="btn btn-exito"
                onConfirm={() => firmar(m.id)}
              />
            </div>
          </div>
        ))}
        {firmables.length === 0 && (
          <EmptyState icon={PenLine} mensaje="No hay paralizaciones esperando tu firma en este momento." />
        )}
      </div>
    </>
  );
}
