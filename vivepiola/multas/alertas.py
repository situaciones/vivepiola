"""
Alerta inmediata: un vecino avisa algo que no puede esperar (un auto que le
bloquea la salida) y se entera al mismo tiempo:

  - los guardias de turno, para que actuen ya;
  - la administracion;
  - la unidad duena del vehiculo, si la patente esta registrada, para que lo
    mueva.

Ademas queda un reporte normal sobre la unidad del vehiculo, asi la falta
sigue el procedimiento de siempre y la multa le llega a quien corresponde.
Los avisos son best-effort: si un canal falla, la alerta igual queda creada y
visible en la app de los guardias.
"""

import logging

from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone

from accounts.models import Rol, Usuario, motivo_fuera_de_permiso
from condominios.models import Persona, Vehiculo, normalizar_patente

from .models import AlertaInmediata, EstadoAlerta, EstadoTicket, EvidenciaFoto, Ticket, TipoAlerta

logger = logging.getLogger(__name__)

QUE_HACE = {
    TipoAlerta.SALIDA_BLOQUEADA: 'esta bloqueando la salida de vehiculos',
    TipoAlerta.ESTACIONAMIENTO_OCUPADO: 'esta ocupando un estacionamiento ajeno',
}


def guardias_de_turno(condominio, momento=None):
    """
    Denunciantes activos cuyo horario cubre este momento. Si ninguno esta de
    turno se avisa a todos: una alerta que no le llega a nadie es peor que
    una que le llega a alguien que no esta trabajando.
    """
    momento = momento or timezone.now()
    todos = list(Usuario.objects.filter(condominio=condominio, rol=Rol.FISCALIZADOR, is_active=True))
    de_turno = []
    for guardia in todos:
        try:
            permiso = guardia.permiso_denuncia
        except Exception:
            de_turno.append(guardia)
            continue
        if permiso.motivo_rechazo(momento) is None:
            de_turno.append(guardia)
    return de_turno or todos


def _enviar(destino, asunto, texto, condominio, correo='', telefono='', boton=None):
    from .correo_html import correo_con_html, html_correo
    from .services import enviar_whatsapp

    canales = []
    if correo:
        try:
            correo_con_html(
                asunto=asunto, texto=texto,
                html=html_correo(comunidad=condominio.nombre, titulo=asunto, parrafos=texto.split('\n\n'), boton=boton),
                from_email=settings.DEFAULT_FROM_EMAIL, to=[correo],
            ).send(fail_silently=False)
            canales.append('correo')
        except Exception:
            logger.exception('No se pudo enviar el correo de alerta a %s', correo)
    if telefono:
        try:
            if enviar_whatsapp(telefono, f'{asunto}\n\n{texto}'):
                canales.append('whatsapp')
        except Exception:
            logger.exception('No se pudo enviar el WhatsApp de alerta a %s', telefono)
    return {'a': destino, 'canales': canales}


def crear_alerta(usuario, *, tipo=TipoAlerta.SALIDA_BLOQUEADA, patente='', descripcion='', foto=None):
    condominio = usuario.condominio
    patente = normalizar_patente(patente)
    vehiculo = Vehiculo.objects.filter(condominio=condominio, patente=patente).select_related('unidad').first() if patente else None
    unidad_afectada = usuario.persona.unidad if usuario.persona_id else None

    alerta = AlertaInmediata.objects.create(
        condominio=condominio, tipo=tipo, creada_por=usuario, unidad_afectada=unidad_afectada,
        patente=patente, unidad_vehiculo=vehiculo.unidad if vehiculo else None,
        descripcion=(descripcion or '')[:500], foto=foto,
    )
    alerta.avisados = _avisar(alerta)
    alerta.ticket = _reporte_de_la_alerta(alerta, usuario)
    alerta.save(update_fields=['avisados', 'ticket'])
    return alerta


def _texto_situacion(alerta):
    lugar = f' (afecta a {alerta.unidad_afectada.identificador})' if alerta.unidad_afectada else ''
    if alerta.tipo in QUE_HACE:
        vehiculo = f'El vehiculo patente {alerta.patente}' if alerta.patente else 'Un vehiculo'
        frase = f'{vehiculo} {QUE_HACE[alerta.tipo]}{lugar}.'
    else:
        frase = f'Urgencia reportada{lugar}.'
    if alerta.descripcion:
        frase += f' "{alerta.descripcion}"'
    return frase


def _avisar(alerta):
    condominio = alerta.condominio
    situacion = _texto_situacion(alerta)
    enlace_app = f'{settings.FRONTEND_URL.rstrip("/")}/app'
    avisados = []

    dueno = (
        f'Unidad del vehiculo: {alerta.unidad_vehiculo.identificador} (ya se le aviso).'
        if alerta.unidad_vehiculo else
        'La patente no esta registrada: hay que ubicar al dueno en terreno.'
    )
    texto_equipo = f'{situacion}\n\n{dueno}\n\nAvisa: {_quien(alerta)}.'
    asunto_equipo = f'ALERTA {condominio.nombre}: {alerta.get_tipo_display()}'
    for guardia in guardias_de_turno(condominio):
        avisados.append(_enviar(
            f'guardia:{guardia.username}', asunto_equipo,
            texto_equipo + '\n\nMarcala como atendida en la app cuando este resuelta.',
            condominio, correo=guardia.email, telefono=guardia.telefono,
            boton=('Abrir la app', enlace_app),
        ))
    for admin in Usuario.objects.filter(condominio=condominio, rol=Rol.ADMINISTRADOR, is_active=True):
        avisados.append(_enviar(
            f'administracion:{admin.username}', asunto_equipo, texto_equipo, condominio,
            correo=admin.email, boton=('Abrir la app', enlace_app),
        ))

    if alerta.unidad_vehiculo:
        texto_dueno = (
            f'{situacion}\n\nPor favor muevalo de inmediato.\n\n'
            'El hecho queda registrado y la comunidad puede aplicar la multa que corresponda '
            'segun su reglamento; si es asi, le llegara la notificacion con su derecho a apelar.'
        )
        for persona in Persona.objects.filter(unidad=alerta.unidad_vehiculo, activo=True):
            avisados.append(_enviar(
                f'unidad:{alerta.unidad_vehiculo.identificador}', f'{condominio.nombre}: mueva su vehiculo',
                texto_dueno, condominio, correo=persona.correo_electronico, telefono=persona.telefono,
            ))
    return avisados


def _quien(alerta):
    usuario = alerta.creada_por
    nombre = usuario.get_full_name() or usuario.username if usuario else 'un usuario'
    if alerta.unidad_afectada:
        return f'{nombre}, {alerta.unidad_afectada.identificador}'
    return nombre


def _responsable_del_vehiculo(unidad):
    """
    A quien se dirige el reporte de una alerta. Si en la unidad del auto hay
    una sola persona registrada, es ella. Con varias no se puede saber quien
    lo dejo ahi: el caso queda para que alguien identifique al responsable.
    """
    personas = list(
        Persona.objects.filter(unidad=unidad, activo=True)
        .exclude(condicion_especial='FALLECIDO')[:2]
    )
    return personas[0] if len(personas) == 1 else None


def _reporte_de_la_alerta(alerta, usuario):
    """
    El reporte para el procedimiento normal, sobre la unidad del vehiculo.
    Sin patente registrada no hay unidad a quien dirigirlo: el guardia que la
    atienda puede levantarlo despues, cuando sepa de quien es el auto.
    """
    from .sellado import procesar_evidencia
    from .services import reevaluar_con_evidencia
    from .views import procesar_reporte_nuevo

    unidad = alerta.unidad_vehiculo
    if unidad is None:
        return None
    if motivo_fuera_de_permiso(usuario, unidad):
        return None  # un guardia fuera de sus limites avisa, pero no denuncia
    ticket = Ticket.objects.create(
        condominio=alerta.condominio, unidad=unidad, creado_por=usuario,
        persona_reportada=_responsable_del_vehiculo(unidad),
        descripcion=f'Alerta inmediata: {_texto_situacion(alerta)}',
        fecha_hecho=alerta.creada_en, estado=EstadoTicket.CONVERTIDO,
    )
    # Mismo orden que el reporte normal: primero se procesa el reporte y
    # despues la foto, que se vuelve a mirar si el caso aun no se curso.
    procesar_reporte_nuevo(ticket, usuario)
    if alerta.foto:
        alerta.foto.open('rb')
        contenido = alerta.foto.read()
        alerta.foto.seek(0)
        digest, metadatos, anclaje = procesar_evidencia(alerta.foto)
        EvidenciaFoto.objects.create(
            ticket=ticket, imagen=ContentFile(contenido, name=alerta.foto.name.rsplit('/', 1)[-1]),
            descripcion='Foto de la alerta inmediata',
            sha256=digest, metadatos_origen=metadatos, anclaje_fisico=anclaje,
        )
        reevaluar_con_evidencia(ticket, usuario)
    return ticket


def atender_alerta(alerta, usuario, nota=''):
    if alerta.estado != EstadoAlerta.ABIERTA:
        raise ValueError('Esta alerta ya fue atendida.')
    alerta.estado = EstadoAlerta.ATENDIDA
    alerta.atendida_por = usuario
    alerta.atendida_en = timezone.now()
    alerta.nota_atencion = (nota or '')[:500]
    alerta.save(update_fields=['estado', 'atendida_por', 'atendida_en', 'nota_atencion'])
    autor = alerta.creada_por
    if autor and autor.email and autor != usuario:
        _enviar(
            f'autor:{autor.username}', f'{alerta.condominio.nombre}: su alerta fue atendida',
            f'Un guardia atendio su alerta "{alerta.get_tipo_display()}".'
            + (f'\n\nNota: {alerta.nota_atencion}' if alerta.nota_atencion else ''),
            alerta.condominio, correo=autor.email,
        )
    return alerta
