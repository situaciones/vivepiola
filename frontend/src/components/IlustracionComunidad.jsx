/**
 * Ilustracion del login: dos vecinos con un problema, el edificio al medio y
 * el visto de la marca arriba. Se lee de izquierda a derecha: el aviso (!)
 * recorre un camino ordenado y llega resuelto (visto verde).
 * Es un SVG propio para que pese poco y se vea nitida en cualquier pantalla.
 */

// Ventanas del edificio: [columna, fila, color]. Las vacias quedan apagadas.
const LUZ = '#e9c46a';
const VENTANAS = [
  [0, 0, LUZ], [1, 0, null], [2, 0, null],
  [0, 1, null], [1, 1, LUZ], [2, 1, LUZ],
  [0, 2, null], [1, 2, null], [2, 2, LUZ],
  [0, 3, LUZ], [1, 3, null], [2, 3, null],
];

function Vecino({ x, color, cabello }) {
  return (
    <g transform={`translate(${x} 0)`}>
      <path d="M-20 196 C-20 166 -12 154 0 154 C12 154 20 166 20 196 Z" fill={color} />
      <circle cx="0" cy="138" r="13" fill="#f1d3bd" />
      <path d={cabello} fill="#2c2a55" />
    </g>
  );
}

export default function IlustracionComunidad({ className = '' }) {
  return (
    <svg
      className={`ilustracion-comunidad ${className}`.trim()}
      viewBox="0 0 360 210"
      role="img"
      aria-label="Dos vecinos con un problema que se resuelve por un camino ordenado"
    >
      <line x1="20" y1="198" x2="340" y2="198" stroke="rgba(150,140,235,.3)" strokeWidth="1.5" />

      {/* Edificio */}
      <rect x="128" y="64" width="104" height="134" rx="4" fill="#1f1d3c" />
      <rect x="120" y="58" width="120" height="8" rx="2" fill="#2c2a55" />
      {VENTANAS.map(([c, f, color]) => (
        <rect
          key={`${c}-${f}`}
          x={142 + c * 28} y={78 + f * 24} width="20" height="14" rx="3"
          fill={color || 'rgba(255,255,255,.07)'} opacity={color ? 0.85 : 1}
        />
      ))}
      <rect x="168" y="172" width="24" height="26" rx="4" fill="#0b0b14" stroke="rgba(150,140,235,.35)" />

      {/* Camino del aviso: sale del vecino de la izquierda y llega al de la derecha */}
      <path
        d="M70 104 C 96 30, 150 18, 180 22 C 210 18, 264 30, 290 104"
        fill="none" stroke="#5b5a8a" strokeWidth="2" strokeLinecap="round" strokeDasharray="4 6"
      />

      {/* Al centro, el paso por el Comite */}
      <g transform="translate(180 22)">
        <circle r="19" fill="#131320" stroke="rgba(150,140,235,.45)" strokeWidth="1.5" />
        <path d="M-8 -2 L-2 7 L9 -9" fill="none" stroke="#3b82f6" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="-8" cy="-2" r="2.6" fill="#a855f7" />
        <circle cx="9" cy="-9" r="2.6" fill="#10b981" />
      </g>

      {/* Burbuja con el problema */}
      <g transform="translate(70 104)">
        <rect x="-17" y="-17" width="34" height="30" rx="10" fill="#a855f7" />
        <path d="M-4 12 L0 20 L5 12 Z" fill="#a855f7" />
        <rect x="-2" y="-10" width="4" height="12" rx="2" fill="white" />
        <circle cx="0" cy="7" r="2.3" fill="white" />
      </g>

      {/* Burbuja resuelta */}
      <g transform="translate(290 104)">
        <rect x="-17" y="-17" width="34" height="30" rx="10" fill="#10b981" />
        <path d="M-5 12 L0 20 L4 12 Z" fill="#10b981" />
        <path d="M-7 -2 L-2 4 L8 -7" fill="none" stroke="white" strokeWidth="3.4" strokeLinecap="round" strokeLinejoin="round" />
      </g>

      <Vecino x={70} color="#6d4bd8" cabello="M-13 136 C-13 122 13 122 13 136 C8 129 -6 128 -13 136 Z" />
      <Vecino x={290} color="#2f6fe0" cabello="M-13 138 C-15 120 15 120 13 138 C13 128 4 126 -2 129 C-7 131 -11 133 -13 138 Z" />
    </svg>
  );
}
