import { useRef, useState } from 'react';

/**
 * Boton de accion volitiva e inequivoca: exige mantener presionado durante
 * holdMs para disparar onConfirm. Un toque accidental no ejecuta nada; la
 * barra de progreso comunica que la accion es deliberada y esta por ocurrir.
 */
export default function HoldToConfirm({ label, holdMs = 1400, onConfirm, disabled = false, className = 'btn btn-peligro' }) {
  const [holding, setHolding] = useState(false);
  const timer = useRef(null);

  const iniciar = () => {
    if (disabled || timer.current) return;
    setHolding(true);
    timer.current = setTimeout(() => {
      timer.current = null;
      setHolding(false);
      onConfirm();
    }, holdMs);
  };

  const cancelar = () => {
    if (timer.current) {
      clearTimeout(timer.current);
      timer.current = null;
    }
    setHolding(false);
  };

  return (
    <button
      type="button"
      disabled={disabled}
      className={`${className} btn-hold${holding ? ' holding' : ''}`}
      style={{ '--hold-ms': `${holdMs}ms` }}
      onMouseDown={iniciar}
      onMouseUp={cancelar}
      onMouseLeave={cancelar}
      onTouchStart={iniciar}
      onTouchEnd={cancelar}
      onTouchCancel={cancelar}
      onContextMenu={(e) => e.preventDefault()}
    >
      <span className="hold-progress" aria-hidden="true" />
      <span className="hold-label">{holding ? 'Manten presionado...' : label}</span>
    </button>
  );
}
