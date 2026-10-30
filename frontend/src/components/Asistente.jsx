import { Fragment, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowUp, Sparkles, Trash2, X } from 'lucide-react';
import client from '../api/client';
import { useAuth } from '../context/AuthContext';

/**
 * Asistente de consulta. Responde sobre el reglamento, la ley y los casos que
 * la persona ya puede ver; no hace tramites. Cuando hay que actuar, lleva al
 * caso ("caso #12" se vuelve enlace) y el acto ocurre en su pantalla, con su
 * sello, como siempre.
 *
 * La conversacion vive en sessionStorage: sobrevive a cambiar de seccion,
 * pero no queda guardada en el telefono despues de cerrar la app.
 */

const SUGERENCIAS = {
  RESIDENTE: ['¿Tengo multas pendientes?', '¿Hasta cuándo puedo apelar?', '¿Qué dice el reglamento sobre mascotas?'],
  COMITE: ['¿Qué casos tengo por resolver?', '¿Hay apelaciones por vencer?', '¿Qué dice la ley sobre la reincidencia?'],
  ADMINISTRADOR: ['¿Qué multas están listas para cobrar?', '¿Qué casos faltan por notificar?', '¿Cómo se notifica una multa?'],
  FISCALIZADOR: ['¿En qué quedaron mis reportes?', '¿Qué infracciones hay por ruidos?', '¿Qué tiene que llevar un buen reporte?'],
};
const SUGERENCIAS_GENERALES = ['¿Cómo funciona una multa de principio a fin?', '¿Qué dice la Ley 21.442 sobre las multas?'];

const clave = (usuario) => `asistente:${usuario?.username || ''}`;

function leerGuardado(usuario) {
  try {
    return JSON.parse(sessionStorage.getItem(clave(usuario))) || [];
  } catch {
    return [];
  }
}

// "caso #12" lleva al caso; **texto** queda en negrita. Nada mas: el modelo
// tiene instruccion de escribir sin tablas ni encabezados.
function Enriquecido({ texto, casos, onCaso }) {
  const partes = texto.split(/(\*\*[^*]+\*\*|caso\s*#\d+)/gi);
  return partes.map((parte, i) => {
    const caso = parte.match(/^caso\s*#(\d+)$/i);
    if (caso && casos.includes(Number(caso[1]))) {
      return (
        <button key={i} type="button" className="asistente-caso" onClick={() => onCaso(Number(caso[1]))}>
          {parte}
        </button>
      );
    }
    if (/^\*\*[^*]+\*\*$/.test(parte)) return <strong key={i}>{parte.slice(2, -2)}</strong>;
    return <Fragment key={i}>{parte}</Fragment>;
  });
}

function Respuesta({ mensaje, onCaso }) {
  const casos = mensaje.casos || [];
  const bloques = mensaje.texto.split(/\n{2,}/);
  return bloques.map((bloque, i) => {
    const lineas = bloque.split('\n');
    if (lineas.every((l) => /^\s*[-•*]\s+/.test(l))) {
      return (
        <ul key={i}>
          {lineas.map((l, j) => (
            <li key={j}><Enriquecido texto={l.replace(/^\s*[-•*]\s+/, '')} casos={casos} onCaso={onCaso} /></li>
          ))}
        </ul>
      );
    }
    return (
      <p key={i}>
        {lineas.map((l, j) => (
          <Fragment key={j}>
            {j > 0 && <br />}
            <Enriquecido texto={l} casos={casos} onCaso={onCaso} />
          </Fragment>
        ))}
      </p>
    );
  });
}

export default function Asistente({ abierto, onAbrir, onCerrar }) {
  const { usuario } = useAuth();
  const navigate = useNavigate();
  const [mensajes, setMensajes] = useState(() => leerGuardado(usuario));
  const [texto, setTexto] = useState('');
  const [pensando, setPensando] = useState(false);
  const [error, setError] = useState('');
  const listaRef = useRef(null);
  const entradaRef = useRef(null);

  useEffect(() => {
    try {
      sessionStorage.setItem(clave(usuario), JSON.stringify(mensajes));
    } catch {
      // Sin almacenamiento (modo privado) la conversacion vive solo en memoria.
    }
  }, [mensajes, usuario]);

  useEffect(() => {
    if (!abierto) return undefined;
    // Se baja la lista, no la pagina: scrollIntoView tambien desplazaba el
    // panel entero y escondia la cabecera.
    const lista = listaRef.current;
    if (lista) lista.scrollTop = lista.scrollHeight;
    const alEscape = (e) => e.key === 'Escape' && onCerrar();
    window.addEventListener('keydown', alEscape);
    return () => window.removeEventListener('keydown', alEscape);
  }, [abierto, mensajes, pensando, onCerrar]);

  useEffect(() => {
    if (abierto && window.matchMedia('(min-width: 861px)').matches) entradaRef.current?.focus();
  }, [abierto]);

  const enviar = async (pregunta) => {
    const limpia = pregunta.trim();
    if (!limpia || pensando) return;
    const conversacion = [...mensajes, { rol: 'usuario', texto: limpia }];
    setMensajes(conversacion);
    setTexto('');
    setError('');
    setPensando(true);
    try {
      const { data } = await client.post('/asistente/', {
        mensajes: conversacion.map(({ rol, texto: t }) => ({ rol, texto: t })),
      });
      setMensajes([...conversacion, { rol: 'asistente', texto: data.respuesta, casos: data.casos }]);
    } catch (err) {
      const estado = err.response?.status;
      setError(
        estado === 429
          ? 'Hiciste muchas preguntas seguidas. Espera un rato y vuelve a intentar.'
          : err.response?.data?.detail || 'No se pudo conectar con el asistente. Revisa tu conexión.',
      );
      // La pregunta vuelve al cuadro para no tener que escribirla de nuevo.
      setMensajes(mensajes);
      setTexto(limpia);
    } finally {
      setPensando(false);
    }
  };

  const abrirCaso = (id) => {
    onCerrar();
    navigate(`/m/${id}`);
  };

  const sugerencias = [...(SUGERENCIAS[usuario?.rol] || []), ...SUGERENCIAS_GENERALES].slice(0, 4);

  if (!abierto) {
    return (
      <button type="button" className="asistente-fab" onClick={onAbrir} aria-label="Abrir asistente">
        <Sparkles size={22} />
      </button>
    );
  }

  return (
    <div className="asistente-capa" onClick={onCerrar}>
      <section
        className="asistente"
        role="dialog"
        aria-modal="true"
        aria-label="Asistente"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="asistente-cabecera">
          <span className="asistente-icono"><Sparkles size={17} /></span>
          <div>
            <strong>Asistente</strong>
            <span>Reglamento, ley y tus casos</span>
          </div>
          {mensajes.length > 0 && (
            <button
              type="button" className="btn-icono" onClick={() => { setMensajes([]); setError(''); }}
              title="Nueva conversación" aria-label="Nueva conversación"
            >
              <Trash2 size={16} />
            </button>
          )}
          <button type="button" className="btn-icono" onClick={onCerrar} aria-label="Cerrar asistente">
            <X size={18} />
          </button>
        </header>

        <div className="asistente-mensajes" ref={listaRef} aria-live="polite">
          {mensajes.length === 0 && (
            <div className="asistente-bienvenida">
              <p>
                Pregúntame por tus casos, sus plazos o lo que dice el reglamento de tu
                comunidad. Te explico y te llevo a la pantalla donde se hace cada trámite.
              </p>
              <div className="asistente-sugerencias">
                {sugerencias.map((s) => (
                  <button key={s} type="button" onClick={() => enviar(s)}>{s}</button>
                ))}
              </div>
            </div>
          )}

          {mensajes.map((m, i) => (
            <div key={i} className={`asistente-burbuja de-${m.rol}`}>
              {m.rol === 'asistente' ? <Respuesta mensaje={m} onCaso={abrirCaso} /> : m.texto}
            </div>
          ))}

          {pensando && (
            <div className="asistente-burbuja de-asistente pensando" aria-label="Pensando">
              <span /><span /><span />
            </div>
          )}
          {error && <p className="asistente-error">{error}</p>}
        </div>

        <form className="asistente-entrada" onSubmit={(e) => { e.preventDefault(); enviar(texto); }}>
          <textarea
            ref={entradaRef}
            rows={1}
            value={texto}
            maxLength={2000}
            placeholder="Escribe tu pregunta"
            onChange={(e) => setTexto(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                enviar(texto);
              }
            }}
          />
          <button type="submit" disabled={!texto.trim() || pensando} aria-label="Enviar">
            <ArrowUp size={18} />
          </button>
        </form>
        <p className="asistente-aviso">Orientación, no asesoría legal. Las decisiones las toma el Comité.</p>
      </section>
    </div>
  );
}
