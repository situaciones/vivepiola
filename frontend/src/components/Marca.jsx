/**
 * Identidad de marca VIVE PIOLA, en un solo lugar.
 *
 * El simbolo es un visto de cumplimiento con los tres colores de la marca:
 * arranca en morado (#A855F7), traza en azul (#3B82F6) y remata en verde
 * (#10B981). Se usa igual en la landing publica y dentro de la aplicacion,
 * para que nadie vea dos marcas distintas del mismo producto.
 */

export function LogoVivePiola({ size = 32, className = 'logo-mark' }) {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 100 100"
      aria-hidden="true"
    >
      <rect width="100" height="100" rx="24" fill="#131320" stroke="rgba(150,140,235,.22)" strokeWidth="1.5" />
      <path
        d="M32 40 L48 66 L74 26"
        fill="none"
        stroke="#3B82F6"
        strokeWidth="10"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="32" cy="40" r="6.5" fill="#A855F7" />
      <circle cx="74" cy="26" r="6.5" fill="#10B981" />
    </svg>
  );
}

/** Logo + wordmark apilado (VIVE regular sobre PIOLA en negra). */
export default function Marca({ size = 32, className = '' }) {
  return (
    <span className={`marca-vp ${className}`.trim()}>
      <LogoVivePiola size={size} />
      <span className="marca-wordmark">
        <b>VIVE</b>
        <b>PIOLA</b>
      </span>
    </span>
  );
}
