import { Clock3 } from 'lucide-react';

/**
 * Cuenta regresiva reutilizable. `cola` es el sufijo de accion
 * ("para presentar descargos", "para que esta delegacion venza"...).
 * urgente < 2 dias. Sin icono si `plano`.
 */
export default function CuentaRegresiva({ fechaLimite, cola = '', vencidoTexto = 'Plazo vencido', plano = false }) {
  const restante = new Date(fechaLimite).getTime() - Date.now();
  if (restante <= 0) {
    return <span className={`countdown urgente${plano ? ' plano' : ''}`}>{!plano && <Clock3 size={15} />} {vencidoTexto}</span>;
  }
  const dias = Math.floor(restante / 86400000);
  const horas = Math.floor((restante % 86400000) / 3600000);
  const urgente = dias < 2;
  const cuerpo = dias > 0
    ? `${dias} dia${dias === 1 ? '' : 's'} y ${horas} h`
    : `${horas} h`;
  return (
    <span className={`countdown ${urgente ? 'urgente' : 'normal'}${plano ? ' plano' : ''}`}>
      {!plano && <Clock3 size={15} />}
      {cola ? `${cuerpo} ${cola}` : cuerpo}
    </span>
  );
}
