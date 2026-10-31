"""
Asistente de consulta de SINCONFLICTO.

Responde preguntas sobre el reglamento de la comunidad, la ley chilena y los
casos que la persona ya puede ver en su pantalla. Es un asistente de CONSULTA,
no de tramite: no tiene ninguna herramienta que cambie algo. Aprobar, apelar,
notificar o resolver son actos que quedan sellados con la identidad de quien
los hace, y por eso ocurren en sus pantallas, nunca en el chat. El asistente
explica y lleva hasta ahi.

Las herramientas reciben al usuario por cierre, no como parametro del modelo:
el modelo no puede pedir los casos de otra persona porque ni siquiera tiene
como nombrarla. Todo pasa por multas_visibles, la misma regla de la API.
"""

import json
import logging
import re
import unicodedata

from django.conf import settings
from django.utils import timezone

from accounts.models import Rol
from multas.models import EstadoMulta, ResolucionDescargo
from multas.views import multas_visibles
from reglamentos.models import EstadoInfraccion, InfraccionCatalogo, Reglamento

logger = logging.getLogger(__name__)

# Topes de cada conversacion: el chat no es un canal para pegar documentos y
# cada vuelta del ciclo de herramientas es una llamada pagada.
MAX_MENSAJES = 20
MAX_CARACTERES_MENSAJE = 2000
MAX_VUELTAS_HERRAMIENTAS = 6

SISTEMA = """Eres el asistente de SINCONFLICTO, la plataforma de convivencia y multas \
de condominios en Chile (Ley 21.442 de Copropiedad Inmobiliaria).

Tu trabajo es responder dudas. Puedes:
- Explicar el estado de los casos que la persona puede ver, sus plazos y que le toca hacer.
- Buscar en el reglamento de su comunidad y en la normativa chilena, citando el articulo.
- Explicar como funciona el procedimiento: reporte, notificacion, acuse, apelacion y cobro.

No puedes hacer tramites. No apruebas, rechazas, apelas, notificas ni cambias nada, y no \
tienes como hacerlo. Si la persona quiere actuar, dile en que pantalla de la app se hace \
(por ejemplo: "abre el caso #12 y usa Apelar"). Tampoco decides si una multa es justa ni \
como deberia resolverse una apelacion: eso lo decide el Comite. Puedes explicar que dice \
la norma y que argumentos suelen considerarse, sin anticipar el resultado.

Reglas:
- Usa las herramientas antes de afirmar algo sobre un caso, un plazo o una norma. Nunca \
inventes articulos, montos ni fechas. Si la busqueda no encuentra nada, dilo.
- Cita la fuente cuando te apoyes en una norma: el articulo del reglamento o la referencia \
legal que entrega la herramienta.
- Para nombrar un caso escribe siempre "caso #" seguido del numero (ej: caso #12): la app \
lo convierte en un enlace.
- Solo conoces los casos que la herramienta te entrega para esta persona. Si pregunta por \
otra persona o unidad, explica que solo ves lo suyo.
- Esto es orientacion, no asesoria legal. Si la situacion es delicada o la persona va a \
judicializar, sugiere consultar a un abogado.
- Escribe en espanol de Chile, claro y breve: parrafos cortos o listas con guiones. Sin \
tablas ni encabezados. Tutea."""

HERRAMIENTAS = [
    {
        'name': 'mis_casos',
        'description': (
            'Lista los casos (multas y avisos) que esta persona puede ver, del mas reciente al '
            'mas antiguo, con su estado, monto y plazo. Un residente ve los suyos; el comite y '
            'la administracion, los de su comunidad; un denunciante, los que reporto.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'estado': {
                    'type': 'string',
                    'enum': [''] + list(EstadoMulta.values),
                    'description': 'Filtra por estado. Cadena vacia para todos.',
                },
            },
            'required': ['estado'],
            'additionalProperties': False,
        },
        'strict': True,
    },
    {
        'name': 'detalle_caso',
        'description': (
            'Detalle de un caso: que se reporto, la infraccion y su articulo, el monto, las '
            'fechas de notificacion y acuse, el plazo para apelar y el estado de la apelacion.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {'caso': {'type': 'integer', 'description': 'Numero del caso.'}},
            'required': ['caso'],
            'additionalProperties': False,
        },
        'strict': True,
    },
    {
        'name': 'buscar_reglamento',
        'description': (
            'Busca en el reglamento de copropiedad, reglamento interno y actas de esta '
            'comunidad, y en su catalogo de infracciones con montos. Usala para preguntas '
            'como "que pasa si hago ruido de noche" o "cuanto es la multa por mascotas".'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'consulta': {'type': 'string', 'description': 'Palabras clave del tema.'},
            },
            'required': ['consulta'],
            'additionalProperties': False,
        },
        'strict': True,
    },
    {
        'name': 'buscar_ley',
        'description': (
            'Busca en la normativa general de Chile cargada en el sistema (Ley 21.442, su '
            'reglamento y normas relacionadas). Devuelve fragmentos con su cita.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'consulta': {'type': 'string', 'description': 'La pregunta o el tema.'},
            },
            'required': ['consulta'],
            'additionalProperties': False,
        },
        'strict': True,
    },
]


class AsistenteNoConfigurado(Exception):
    pass


class AsistenteNoDisponible(Exception):
    pass


# -- Herramientas -------------------------------------------------------

def _fecha(valor):
    return timezone.localtime(valor).strftime('%d-%m-%Y %H:%M') if valor else None


def _monto(multa):
    if multa.monto is None:
        return None
    unidad = multa.infraccion.unidad_monto if multa.infraccion else ''
    return f'{multa.monto} {unidad}'.strip()


def mis_casos(usuario, estado=''):
    qs = multas_visibles(usuario).select_related('unidad', 'infraccion').order_by('-fecha_creacion')
    if estado:
        qs = qs.filter(estado=estado)
    total = qs.count()
    casos = [
        {
            'caso': m.id,
            'unidad': m.unidad.identificador,
            'infraccion': m.infraccion.descripcion if m.infraccion else 'Sin tipificar',
            'estado': m.get_estado_display(),
            'monto': _monto(m),
            'plazo_para_apelar_hasta': _fecha(m.fecha_limite_descargo),
            'creado': _fecha(m.fecha_creacion),
        }
        for m in qs[:20]
    ]
    return {'total': total, 'mostrados': len(casos), 'casos': casos}


def detalle_caso(usuario, caso):
    multa = (
        multas_visibles(usuario)
        .select_related('unidad', 'infraccion', 'ticket', 'infraccion__reglamento')
        .filter(id=caso).first()
    )
    if not multa:
        return {'error': f'No existe el caso #{caso} o esta persona no tiene acceso a el.'}

    infraccion = multa.infraccion
    detalle = {
        'caso': multa.id,
        'unidad': multa.unidad.identificador,
        'estado': multa.get_estado_display(),
        'lo_reportado': multa.ticket.descripcion[:1500],
        'fecha_del_hecho': _fecha(getattr(multa.ticket, 'fecha_hecho', None)),
        'infraccion': infraccion.descripcion if infraccion else 'Sin tipificar todavia',
        'articulo': infraccion.articulo_referencia if infraccion else None,
        'fuente': infraccion.reglamento.referencia_citable if infraccion and infraccion.reglamento else None,
        'monto': _monto(multa),
        'es_aviso_de_cortesia': multa.es_aviso_de_cortesia,
        'es_reincidencia': multa.es_reincidencia,
        'notificada': _fecha(multa.fecha_notificacion),
        'acuse_de_recibo': _fecha(multa.fecha_acuse),
        'plazo_para_apelar_hasta': _fecha(multa.fecha_limite_descargo),
        'firme_desde': _fecha(multa.fecha_firme),
    }
    descargo = getattr(multa, 'descargo', None)
    if descargo:
        detalle['apelacion'] = {
            'presentada': _fecha(descargo.fecha_presentacion),
            'resolucion': descargo.get_resolucion_display(),
            'el_comite_debe_responder_hasta': (
                _fecha(descargo.fecha_limite_resolucion)
                if descargo.resolucion == ResolucionDescargo.PENDIENTE else None
            ),
            'comentario_del_comite': descargo.comentario_resolucion or None,
        }
    if multa.estado == EstadoMulta.RECHAZADA and multa.motivo_rechazo:
        detalle['motivo_rechazo'] = multa.motivo_rechazo
    return detalle


def _sin_tildes(texto):
    return ''.join(
        c for c in unicodedata.normalize('NFD', texto.lower()) if unicodedata.category(c) != 'Mn'
    )


def _palabras(consulta):
    # Las palabras cortas ("de", "la", "por") encuentran todo y no aportan.
    return [p for p in re.findall(r'\w+', _sin_tildes(consulta)) if len(p) > 3]


def buscar_reglamento(usuario, consulta):
    if not usuario.condominio_id:
        return {'error': 'Esta cuenta no pertenece a una comunidad.'}
    palabras = _palabras(consulta)
    if not palabras:
        return {'error': 'Indica al menos una palabra clave de mas de 3 letras.'}

    infracciones = []
    for inf in InfraccionCatalogo.objects.filter(
        condominio_id=usuario.condominio_id, estado=EstadoInfraccion.ACTIVA,
    ).select_related('reglamento'):
        texto = _sin_tildes(f'{inf.codigo} {inf.descripcion} {inf.articulo_referencia}')
        puntaje = sum(p in texto for p in palabras)
        if puntaje:
            infracciones.append((puntaje, {
                'infraccion': inf.descripcion,
                'articulo': inf.articulo_referencia or None,
                'fuente': inf.reglamento.referencia_citable if inf.reglamento else None,
                'monto': f'{inf.monto} {inf.unidad_monto}',
                'gravedad': inf.get_gravedad_display(),
                'factor_reincidencia': str(inf.factor_reincidencia),
            }))
    infracciones.sort(key=lambda par: -par[0])

    # Del texto de los documentos se entregan los parrafos con mas
    # coincidencias, no el documento entero.
    fragmentos = []
    for reglamento in Reglamento.objects.filter(
        condominio_id=usuario.condominio_id, vigente=True,
    ).exclude(texto_extraido=''):
        for parrafo in re.split(r'\n\s*\n', reglamento.texto_extraido):
            parrafo = parrafo.strip()
            if len(parrafo) < 40:
                continue
            puntaje = sum(p in _sin_tildes(parrafo) for p in palabras)
            if puntaje:
                fragmentos.append((puntaje, {
                    'fuente': reglamento.referencia_citable,
                    'texto': parrafo[:1200],
                }))
    fragmentos.sort(key=lambda par: -par[0])

    if not infracciones and not fragmentos:
        return {'resultado': 'No se encontro nada sobre eso en los documentos de esta comunidad.'}
    return {
        'infracciones_del_catalogo': [i for _, i in infracciones[:6]],
        'fragmentos_de_documentos': [f for _, f in fragmentos[:4]],
    }


def buscar_ley(consulta):
    from reglamentos.normativa import buscar_normativa

    resultados = buscar_normativa(consulta)
    if not resultados:
        return {'resultado': 'No hay normativa cargada que responda a eso.'}
    return {'fragmentos': [{'cita': r['cita'], 'texto': r['texto']} for r in resultados]}


def _ejecutar(usuario, nombre, entrada):
    if nombre == 'mis_casos':
        return mis_casos(usuario, entrada.get('estado', ''))
    if nombre == 'detalle_caso':
        return detalle_caso(usuario, int(entrada['caso']))
    if nombre == 'buscar_reglamento':
        return buscar_reglamento(usuario, entrada['consulta'])
    if nombre == 'buscar_ley':
        return buscar_ley(entrada['consulta'])
    return {'error': f'Herramienta desconocida: {nombre}'}


# -- Conversacion -------------------------------------------------------

def _contexto(usuario):
    """Quien pregunta. Va despues del sistema estable para no romper su cache."""
    rol = Rol(usuario.rol).label
    nombre = usuario.get_full_name() or usuario.username
    comunidad = usuario.condominio.nombre if usuario.condominio_id else 'ninguna (administrador del sistema)'
    hoy = timezone.localdate().strftime('%d-%m-%Y')
    return f'Hablas con {nombre}, rol {rol}, de la comunidad {comunidad}. Hoy es {hoy}.'


def normalizar_historial(mensajes):
    """
    Valida lo que manda el cliente: solo texto, roles alternados que empiezan
    y terminan en el usuario, y con topes. El historial viaja desde el
    navegador, asi que nunca se confia en su forma.
    """
    if not isinstance(mensajes, list) or not mensajes:
        raise ValueError('Envia al menos un mensaje.')
    limpios = []
    for m in mensajes[-MAX_MENSAJES:]:
        if not isinstance(m, dict) or m.get('rol') not in ('usuario', 'asistente'):
            raise ValueError('Cada mensaje necesita rol "usuario" o "asistente".')
        texto = str(m.get('texto', '')).strip()
        if not texto:
            continue
        if len(texto) > MAX_CARACTERES_MENSAJE:
            raise ValueError(f'Cada mensaje puede tener hasta {MAX_CARACTERES_MENSAJE} caracteres.')
        rol = 'user' if m['rol'] == 'usuario' else 'assistant'
        if limpios and limpios[-1]['role'] == rol:
            limpios[-1]['content'] += '\n\n' + texto
        else:
            limpios.append({'role': rol, 'content': texto})
    while limpios and limpios[0]['role'] != 'user':
        limpios.pop(0)
    if not limpios or limpios[-1]['role'] != 'user':
        raise ValueError('El ultimo mensaje debe ser de la persona.')
    return limpios


def _cliente():
    import anthropic

    return anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


def responder(usuario, mensajes):
    """Devuelve {'respuesta': texto, 'casos': [ids citados]}."""
    if not settings.ANTHROPIC_API_KEY:
        raise AsistenteNoConfigurado()

    import anthropic

    historial = normalizar_historial(mensajes)
    cliente = _cliente()
    sistema = [
        {'type': 'text', 'text': SISTEMA, 'cache_control': {'type': 'ephemeral'}},
        {'type': 'text', 'text': _contexto(usuario)},
    ]

    respuesta = None
    for _ in range(MAX_VUELTAS_HERRAMIENTAS):
        try:
            respuesta = cliente.beta.messages.create(
                model=settings.ASISTENTE_MODELO,
                max_tokens=8000,
                system=sistema,
                tools=HERRAMIENTAS,
                messages=historial,
                output_config={'effort': settings.ASISTENTE_ESFUERZO},
                # Si el modelo declina por una politica de seguridad, la API
                # reintenta en el modelo de respaldo dentro de la misma llamada.
                betas=['server-side-fallback-2026-07-01'],
                fallbacks='default',
            )
        except anthropic.APIStatusError as e:
            logger.warning('Asistente: la API respondio %s (%s)', e.status_code, e.message)
            raise AsistenteNoDisponible() from e
        except anthropic.APIConnectionError as e:
            logger.warning('Asistente: sin conexion con la API (%s)', e)
            raise AsistenteNoDisponible() from e

        if respuesta.stop_reason != 'tool_use':
            break

        historial.append({'role': 'assistant', 'content': respuesta.content})
        resultados = []
        for bloque in respuesta.content:
            if bloque.type != 'tool_use':
                continue
            try:
                salida = _ejecutar(usuario, bloque.name, bloque.input)
                resultados.append({
                    'type': 'tool_result', 'tool_use_id': bloque.id,
                    'content': json.dumps(salida, ensure_ascii=False, default=str),
                })
            except Exception:
                logger.exception('Asistente: fallo la herramienta %s', bloque.name)
                resultados.append({
                    'type': 'tool_result', 'tool_use_id': bloque.id, 'is_error': True,
                    'content': 'La consulta fallo. Dile a la persona que intente de nuevo.',
                })
        historial.append({'role': 'user', 'content': resultados})

    if respuesta is None or respuesta.stop_reason == 'refusal':
        texto = 'No puedo ayudarte con eso. Si es sobre tu comunidad, intenta preguntarlo de otra forma.'
    else:
        texto = '\n\n'.join(b.text for b in respuesta.content if b.type == 'text').strip()
        if respuesta.stop_reason == 'tool_use' or not texto:
            texto = texto or 'No alcance a terminar de revisar. Intenta con una pregunta mas acotada.'

    casos = sorted({int(n) for n in re.findall(r'caso\s*#(\d+)', texto, re.IGNORECASE)})
    visibles = set(multas_visibles(usuario).filter(id__in=casos).values_list('id', flat=True))
    return {'respuesta': texto, 'casos': [c for c in casos if c in visibles]}
