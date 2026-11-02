import { Capacitor } from '@capacitor/core';

/**
 * Insignias de App Store y Google Play.
 *
 * Los enlaces se configuran al publicar la app en cada tienda
 * (VITE_URL_APP_STORE y VITE_URL_GOOGLE_PLAY). Mientras no existan, la
 * insignia se muestra como "Muy pronto" y no lleva a ninguna parte: un enlace
 * a una ficha que no existe es peor que no tener enlace.
 */
const URL_APP_STORE = import.meta.env.VITE_URL_APP_STORE || '';
const URL_GOOGLE_PLAY = import.meta.env.VITE_URL_GOOGLE_PLAY || '';

function LogoApple() {
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
      <path
        fill="currentColor"
        d="M12.152 6.896c-.948 0-2.415-1.078-3.96-1.04-2.04.027-3.91 1.183-4.961 3.014-2.117 3.675-.546 9.103 1.519 12.09 1.013 1.454 2.208 3.09 3.792 3.039 1.52-.065 2.09-.987 3.935-.987 1.831 0 2.35.987 3.96.948 1.637-.026 2.676-1.48 3.676-2.948 1.156-1.688 1.636-3.325 1.662-3.415-.039-.013-3.182-1.221-3.22-4.857-.026-3.04 2.48-4.494 2.597-4.559-1.429-2.09-3.623-2.324-4.39-2.376-2-.156-3.675 1.09-4.61 1.09zM15.53 3.83c.843-1.012 1.4-2.427 1.245-3.83-1.207.052-2.662.805-3.532 1.818-.78.896-1.454 2.338-1.273 3.714 1.338.104 2.715-.688 3.559-1.701"
      />
    </svg>
  );
}

function LogoGooglePlay() {
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
      <path fill="#00a0ff" d="M3.6 1.8 13.4 12 3.6 22.2c-.4-.2-.6-.7-.6-1.2V3c0-.5.2-1 .6-1.2Z" />
      <path fill="#00e176" d="M3.6 1.8c.4-.2.9-.2 1.4.1l11.5 6.6-3.1 3.5L3.6 1.8Z" />
      <path fill="#ff3a44" d="M3.6 22.2 13.4 12l3.1 3.5L5 22.1c-.5.3-1 .3-1.4.1Z" />
      <path fill="#ffd500" d="m16.5 8.5 3.6 2.1c1 .6 1 2.2 0 2.8l-3.6 2.1-3.1-3.5 3.1-3.5Z" />
    </svg>
  );
}

function Insignia({ url, logo, arriba, abajo }) {
  const contenido = (
    <>
      {logo}
      <span className="insignia-texto">
        <small>{url ? arriba : 'Muy pronto en'}</small>
        <b>{abajo}</b>
      </span>
    </>
  );
  if (!url) {
    return <span className="insignia-tienda insignia-pronto" aria-label={`Muy pronto en ${abajo}`}>{contenido}</span>;
  }
  return (
    <a className="insignia-tienda" href={url} target="_blank" rel="noopener noreferrer">{contenido}</a>
  );
}

export default function DescargarApp() {
  // Dentro de la app instalada no tiene sentido ofrecer descargarla.
  if (Capacitor.isNativePlatform()) return null;
  return (
    <div className="descargar-app">
      <p>Descarga la app y recibe cada aviso al instante en tu celular.</p>
      <div className="descargar-app-insignias">
        <Insignia url={URL_APP_STORE} logo={<LogoApple />} arriba="Descárgalo en el" abajo="App Store" />
        <Insignia url={URL_GOOGLE_PLAY} logo={<LogoGooglePlay />} arriba="Disponible en" abajo="Google Play" />
      </div>
    </div>
  );
}
