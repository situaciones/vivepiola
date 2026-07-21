import { Check } from 'lucide-react';

/**
 * Barra segmentada de quorum: K casillas, una por firma requerida. Se lee de
 * un vistazo ("falta gente" vs "completo"), no como fraccion. Cada casilla
 * llena muestra quien firmo y EN QUE CALIDAD (el activo probatorio es quien,
 * no cuantos). Ambar mientras falte una firma; verde al completar.
 *
 * No se renderiza para quorum simple (1): esa medida se ve como antes.
 */
export default function QuorumBar({ medida }) {
  const requerido = medida.quorum_requerido || 1;
  if (requerido <= 1) return null;

  const votos = medida.votos || [];
  const completo = votos.length >= requerido;

  return (
    <div className="quorum">
      <div className="quorum-header">
        <span className="quorum-titulo">Quorum de firmas</span>
        <span className={`quorum-conteo${completo ? ' completo' : ''}`}>
          {votos.length} / {requerido}
        </span>
      </div>
      <div className="quorum-barra">
        {Array.from({ length: requerido }).map((_, i) => (
          <span key={i} className={`quorum-seg${i < votos.length ? (completo ? ' llena completo' : ' llena') : ''}`}>
            {i < votos.length && <Check size={12} strokeWidth={3} />}
          </span>
        ))}
      </div>
      <ul className="quorum-firmas">
        {votos.map((v) => (
          <li key={v.id}>
            <Check size={13} className="firma-ok" />
            <strong>{v.actor_nombre}</strong>
            <span className="firma-calidad">
              {v.en_calidad_de === 'DELEGADO'
                ? `delegado de ${v.delegante_nombre}`
                : 'titular'}
            </span>
          </li>
        ))}
        {!completo && (
          <li className="firma-pendiente">
            Falta {requerido - votos.length} firma{requerido - votos.length === 1 ? '' : 's'} facultada{requerido - votos.length === 1 ? '' : 's'}
          </li>
        )}
      </ul>
    </div>
  );
}
