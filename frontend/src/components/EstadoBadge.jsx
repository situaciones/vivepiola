const ESTILOS = {
  PENDIENTE: { color: '#475569', fondo: '#f1f5f9', etiqueta: 'Pendiente' },
  CONVERTIDO: { color: '#475569', fondo: '#f1f5f9', etiqueta: 'Convertido en multa' },
  DESCARTADO: { color: '#475569', fondo: '#f1f5f9', etiqueta: 'Descartado' },
  EN_REVISION: { color: '#92400e', fondo: '#fffbeb', etiqueta: 'En revision' },
  RECHAZADA: { color: '#b91c1c', fondo: '#fef2f2', etiqueta: 'Rechazada' },
  APROBADA: { color: '#3730a3', fondo: '#eef2ff', etiqueta: 'Aprobada' },
  NOTIFICADA: { color: '#6d28d9', fondo: '#f5f3ff', etiqueta: 'Notificada' },
  CON_DESCARGO: { color: '#9a3412', fondo: '#fff7ed', etiqueta: 'Con descargo' },
  FIRME: { color: '#065f46', fondo: '#ecfdf5', etiqueta: 'Firme' },
  ANULADA: { color: '#475569', fondo: '#f1f5f9', etiqueta: 'Anulada' },
  EXPORTADA: { color: '#065f46', fondo: '#ecfdf5', etiqueta: 'Exportada a GGCC' },
  BORRADOR: { color: '#92400e', fondo: '#fffbeb', etiqueta: 'Borrador IA' },
  ACTIVA: { color: '#065f46', fondo: '#ecfdf5', etiqueta: 'Activa' },
  INACTIVA: { color: '#475569', fondo: '#f1f5f9', etiqueta: 'Inactiva' },
  RESPONDIDA: { color: '#065f46', fondo: '#ecfdf5', etiqueta: 'Respondida' },
  VENCIDA: { color: '#b91c1c', fondo: '#fef2f2', etiqueta: 'Vencida' },
  ACEPTADO: { color: '#065f46', fondo: '#ecfdf5', etiqueta: 'Aceptado' },
  RECHAZADO: { color: '#b91c1c', fondo: '#fef2f2', etiqueta: 'Rechazado' },
  EJECUTADA: { color: '#b91c1c', fondo: '#fef2f2', etiqueta: 'Contencion activa' },
  RATIFICADA: { color: '#9a3412', fondo: '#fff7ed', etiqueta: 'Ratificada · activa' },
  EN_ESCALAMIENTO: { color: '#b91c1c', fondo: '#fef2f2', etiqueta: 'En escalamiento · ACTIVA' },
  LEVANTADA: { color: '#065f46', fondo: '#ecfdf5', etiqueta: 'Levantada' },
};

export default function EstadoBadge({ estado }) {
  const estilo = ESTILOS[estado] || { color: '#334155', fondo: '#f1f5f9', etiqueta: estado };
  return (
    <span
      className="badge"
      style={{
        color: estilo.color,
        backgroundColor: estilo.fondo,
        border: `1px solid ${estilo.color}33`,
      }}
    >
      <span className="badge-dot" />
      {estilo.etiqueta}
    </span>
  );
}
