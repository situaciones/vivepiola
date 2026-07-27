/**
 * Service worker de VIVE PIOLA.
 *
 * Regla que manda sobre todas las demas: LA API NUNCA SE CACHEA.
 *
 * Este sistema muestra plazos legales, estados de expedientes y montos. Una
 * respuesta guardada puede decir que un descargo sigue abierto cuando ya
 * vencio, o mostrar un monto anterior a una rebaja. En un producto que se
 * vende como prueba, mostrar datos viejos es peor que no mostrar nada: por
 * eso /api y /media van siempre a la red y, sin conexion, fallan a la vista.
 *
 * Lo que si se guarda es la cascara (HTML, JS, CSS): asi la app abre estando
 * sin señal y puede decir con claridad que no hay conexion, en vez de dejar
 * al conserje frente a una pantalla en blanco.
 */

const VERSION = 'vivepiola-v1';
const CASCARA = `${VERSION}-cascara`;
const RUTA_APP = '/index.html';

self.addEventListener('install', (evento) => {
  evento.waitUntil(
    caches.open(CASCARA).then((cache) => cache.addAll([RUTA_APP])).then(() => self.skipWaiting()),
  );
});

self.addEventListener('activate', (evento) => {
  evento.waitUntil(
    caches.keys()
      .then((claves) => Promise.all(
        claves.filter((c) => !c.startsWith(VERSION)).map((c) => caches.delete(c)),
      ))
      .then(() => self.clients.claim()),
  );
});

function esDatoVivo(url) {
  return url.pathname.startsWith('/api/') || url.pathname.startsWith('/media/');
}

self.addEventListener('fetch', (evento) => {
  const solicitud = evento.request;
  if (solicitud.method !== 'GET') return;

  const url = new URL(solicitud.url);
  if (url.origin !== self.location.origin) return;

  // Datos del expediente: siempre a la red, nunca guardados.
  if (esDatoVivo(url)) return;

  // Navegacion: se intenta la red y, sin conexion, se abre la cascara guardada.
  if (solicitud.mode === 'navigate') {
    evento.respondWith(
      fetch(solicitud).catch(() => caches.match(RUTA_APP)),
    );
    return;
  }

  // Recursos estaticos (con hash en el nombre): se sirven del cache y se
  // refrescan en segundo plano.
  evento.respondWith(
    caches.match(solicitud).then((guardado) => {
      const desdeRed = fetch(solicitud)
        .then((respuesta) => {
          if (respuesta && respuesta.ok) {
            const copia = respuesta.clone();
            caches.open(CASCARA).then((cache) => cache.put(solicitud, copia));
          }
          return respuesta;
        })
        .catch(() => guardado);
      return guardado || desdeRed;
    }),
  );
});
