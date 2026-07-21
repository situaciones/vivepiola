import { useMemo } from 'react';
import { useAuth } from './context/AuthContext';

/**
 * La "piel" multi-nicho: el backend entrega el vocabulario del vertical de la
 * organizacion en /auth/me/ (campo `vocabulario`); este helper lo consume con
 * defaults del nicho original (copropiedad). Una clave ausente en el vertical
 * cae al default — nunca se muestra una clave cruda al usuario.
 *
 * Convencion: sustantivos sueltos en minuscula (para incrustar) o con su forma
 * de titulo cuando encabezan; frases completas cuando el genero/numero importa
 * (i18n clave-por-frase), nunca concatenacion de palabras dentro de una oracion.
 */
export const VOCAB_DEFAULTS = {
  // --- Terminos base ---
  organizacion: 'Condominio',
  unidad: 'Unidad',
  multa: 'Multa',
  multa_min: 'multa',
  multa_plural: 'Multas',
  reporte_corto: 'Nuevo reporte',
  nuevo_reporte: 'Nuevo reporte de fiscalizacion',
  persona_reportada: 'Persona reportada',
  residente: 'Residente',
  descargo: 'Descargo',
  descargo_min: 'descargo',
  catalogo: 'Catalogo de infracciones',
  infraccion: 'Infraccion',
  contencion: 'Contencion',
  contencion_titulo: 'Contencion inmediata',
  contenciones: 'Contenciones',
  destino_cobro: 'gastos comunes',
  rol_FISCALIZADOR: 'Fiscalizador (Conserje)',
  rol_COMITE: 'Comite de Administracion',
  rol_ADMINISTRADOR: 'Administrador',
  rol_RESIDENTE: 'Residente',
  rol_SUPERADMIN: 'Administrador del sistema',

  // --- Portal del infractor (Residente) ---
  panel_residente: 'Mi Panel de Residente',
  mis_multas: 'Mis multas',
  mis_multas_sub: 'Consulta tus multas con su evidencia y presenta descargos dentro del plazo legal.',
  presentar_descargo: 'Presentar descargo',
  descargo_placeholder: 'Escribe tu descargo...',
  tu_descargo: 'Tu descargo:',
  ver_notificacion_pdf: 'Ver documento de notificacion (PDF)',
  por_que_falta: '¿Por que es una falta?',
  por_que_falta_texto: 'El reglamento de copropiedad la tipifica como infraccion',
  semaforo_verde_titulo: 'Convivencia al dia',
  semaforo_verde_detalle: 'No registras multas activas. ¡Gracias por cuidar la comunidad!',
  semaforo_ambar_titulo: 'Tienes un proceso en curso',
  semaforo_ambar_detalle: 'Hay una multa en tramite o con plazo de descargo abierto. Revisa los detalles mas abajo.',
  semaforo_rojo_titulo: 'Tienes multas firmes',
  semaforo_rojo_detalle: 'Una o mas multas quedaron firmes y seran cargadas a tus gastos comunes.',
  countdown_texto: 'para presentar descargos',
  countdown_vencido: 'Plazo de descargo vencido',

  // --- Gestion (Administrador) ---
  panel_administrador: 'Panel del Administrador',
  notificar_titulo: 'Notificar multas aprobadas',
  notificar_sub: 'Genera el PDF formal y lo envia al correo registrado del residente: ese envio es el canal legal de notificacion.',
  notificar_accion: 'Notificar al residente',
  notificar_pendientes: 'Multas aprobadas pendientes de notificar',
  registro_titulo: 'Registro de copropietarios',
  registro_sub: 'Individualiza propietarios, arrendatarios y ocupantes con su correo legal de notificacion.',
  registro_importar: 'Importar registro (.xlsx / .csv)',
  gastos_titulo: 'Integracion a gastos comunes',
  gastos_sub: 'Exporta las multas firmes (sin apelaciones pendientes) al aviso de cobro mensual.',
  gastos_exportar: 'Exportar multas firmes del periodo',
};

export const crearVocab = (vocabulario) => (clave) =>
  (vocabulario && vocabulario[clave]) || VOCAB_DEFAULTS[clave] || clave;

export function useVocab() {
  const { usuario } = useAuth();
  // Memoizado por el diccionario de la sesion: evita recrear `t` en cada render
  // y romper la memoizacion de hijos cuando se pasa como prop en listas pesadas.
  return useMemo(() => crearVocab(usuario?.vocabulario), [usuario?.vocabulario]);
}
