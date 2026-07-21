import { Check, X } from 'lucide-react';

const PASOS_BASE = [
  { id: 'reportado', label: 'Reportado', quien: 'Fiscalizador' },
  { id: 'revision', label: 'En revision', quien: 'Comite' },
  { id: 'notificacion', label: 'Notificacion', quien: 'Administrador' },
  { id: 'descargo', label: 'Descargo', quien: 'Residente' },
  { id: 'resolucion', label: 'Resolucion', quien: 'Comite' },
  { id: 'cobro', label: 'Cobro', quien: 'Administrador' },
];

const fmt = (fecha) => (fecha ? new Date(fecha).toLocaleDateString('es-CL', { day: '2-digit', month: 'short' }) : null);

/**
 * Deriva el estado de cada paso del proceso legal a partir del estado real de
 * la multa. Los estados terminales (RECHAZADA, ANULADA) cortan la linea de
 * tiempo en el paso donde ocurrieron, en vez de mostrar pasos futuros que
 * nunca sucederan.
 */
function construirPasos(multa) {
  const pasos = PASOS_BASE.map((p) => ({ ...p, estado: 'pendiente', fecha: null }));
  const completar = (hasta) => {
    for (let i = 0; i <= hasta; i += 1) pasos[i].estado = 'completado';
  };

  pasos[0].fecha = fmt(multa.ticket_detalle?.fecha_creacion);

  switch (multa.estado) {
    case 'EN_REVISION':
      completar(0);
      pasos[1].estado = 'actual';
      return { pasos: pasos.slice(0, 6), detenido: null };
    case 'RECHAZADA':
      completar(0);
      pasos[1].estado = 'rechazado';
      return { pasos: pasos.slice(0, 2), detenido: 'El Comite rechazo el reporte: el proceso termina aqui.' };
    case 'APROBADA':
      completar(1);
      pasos[1].fecha = fmt(multa.fecha_aprobacion);
      pasos[2].estado = 'actual';
      return { pasos, detenido: null };
    case 'NOTIFICADA':
      completar(2);
      pasos[1].fecha = fmt(multa.fecha_aprobacion);
      pasos[2].fecha = fmt(multa.fecha_notificacion);
      pasos[3].estado = 'actual';
      return { pasos, detenido: null };
    case 'CON_DESCARGO':
      completar(3);
      pasos[1].fecha = fmt(multa.fecha_aprobacion);
      pasos[2].fecha = fmt(multa.fecha_notificacion);
      pasos[3].fecha = fmt(multa.descargo?.fecha_presentacion);
      pasos[4].estado = 'actual';
      return { pasos, detenido: null };
    case 'FIRME':
      completar(4);
      pasos[1].fecha = fmt(multa.fecha_aprobacion);
      pasos[2].fecha = fmt(multa.fecha_notificacion);
      pasos[3].fecha = fmt(multa.descargo?.fecha_presentacion);
      pasos[4].fecha = fmt(multa.descargo?.fecha_resolucion);
      pasos[5].estado = 'actual';
      return { pasos, detenido: null };
    case 'EXPORTADA':
      completar(5);
      pasos[1].fecha = fmt(multa.fecha_aprobacion);
      pasos[2].fecha = fmt(multa.fecha_notificacion);
      pasos[3].fecha = fmt(multa.descargo?.fecha_presentacion);
      pasos[4].fecha = fmt(multa.descargo?.fecha_resolucion);
      return { pasos, detenido: null };
    case 'ANULADA':
      completar(3);
      pasos[1].fecha = fmt(multa.fecha_aprobacion);
      pasos[2].fecha = fmt(multa.fecha_notificacion);
      pasos[3].fecha = fmt(multa.descargo?.fecha_presentacion);
      pasos[4].estado = 'anulado';
      return { pasos: pasos.slice(0, 5), detenido: 'El Comite acepto el descargo: la multa fue anulada.' };
    default:
      return { pasos, detenido: null };
  }
}

export default function ProcesoTimeline({ multa }) {
  const { pasos, detenido } = construirPasos(multa);

  return (
    <div className="timeline">
      <h4>Estado del proceso</h4>
      <ol className="timeline-lista">
        {pasos.map((p) => (
          <li key={p.id} className={`timeline-paso ${p.estado}`}>
            <span className="timeline-marca">
              {p.estado === 'completado' && <Check size={12} strokeWidth={3} />}
              {p.estado === 'rechazado' || p.estado === 'anulado' ? <X size={12} strokeWidth={3} /> : null}
            </span>
            <span className="timeline-texto">
              <span className="timeline-label">{p.label}</span>
              <span className="timeline-quien">
                {p.quien}{p.fecha ? ` · ${p.fecha}` : p.estado === 'actual' ? ' · ahora' : ''}
              </span>
            </span>
          </li>
        ))}
      </ol>
      {detenido && <p className="timeline-detenido">{detenido}</p>}
    </div>
  );
}
