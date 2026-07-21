import { useVocab } from '../vocab';

export default function Semaforo({ nivel }) {
  const t = useVocab();
  const info = {
    verde: { titulo: t('semaforo_verde_titulo'), detalle: t('semaforo_verde_detalle') },
    ambar: { titulo: t('semaforo_ambar_titulo'), detalle: t('semaforo_ambar_detalle') },
    rojo: { titulo: t('semaforo_rojo_titulo'), detalle: t('semaforo_rojo_detalle') },
  }[nivel] || { titulo: t('semaforo_verde_titulo'), detalle: t('semaforo_verde_detalle') };

  return (
    <div className={`semaforo ${nivel}`} role="status">
      <div className="semaforo-luces" aria-hidden="true">
        <span className={nivel === 'rojo' ? 'activa' : ''} />
        <span className={nivel === 'ambar' ? 'activa' : ''} />
        <span className={nivel === 'verde' ? 'activa' : ''} />
      </div>
      <div>
        <p className="estado-titulo">{info.titulo}</p>
        <p className="estado-detalle">{info.detalle}</p>
      </div>
    </div>
  );
}
