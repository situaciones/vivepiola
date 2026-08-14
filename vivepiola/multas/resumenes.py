"""
Resumen agrupado de lo pendiente en cada comunidad.

Un aviso por cada cosa que pasa satura y termina silenciado: el comite no
quiere ocho mensajes, quiere uno que diga "tienes tres casos". Por eso aqui se
arma UN resumen por rol y por dia, y solo si hay algo que hacer.

Cada rol recibe lo suyo, respetando la separacion de funciones de la ley:
el comite lo que debe decidir, la administracion lo que debe ejecutar.
"""

from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMessage
from django.utils import timezone

from accounts.models import Rol

from .models import EstadoMedida, EstadoMulta, MedidaInmediata, Multa, ResolucionDescargo

# Un plazo que vence dentro de estos dias se marca como urgente en el resumen.
DIAS_URGENCIA = 3


def _linea(cantidad, singular, plural):
    return f'{cantidad} {singular if cantidad == 1 else plural}'


def resumen_para_comite(condominio):
    """Lo que solo el comite puede resolver."""
    en_revision = Multa.objects.filter(
        condominio=condominio, estado=EstadoMulta.EN_REVISION,
    ).count()
    descargos_qs = Multa.objects.filter(condominio=condominio, estado=EstadoMulta.CON_DESCARGO)
    descargos = descargos_qs.count()
    # El plazo tambien obliga al Comite: una apelacion sin responder deja al
    # residente sin saber en que esta su caso.
    vencidos = descargos_qs.filter(
        descargo__resolucion=ResolucionDescargo.PENDIENTE,
        descargo__fecha_limite_resolucion__lt=timezone.now(),
    ).count()
    por_confirmar = Multa.objects.filter(
        condominio=condominio, estado=EstadoMulta.POR_CONFIRMAR,
    ).count()
    contenciones = MedidaInmediata.objects.filter(
        multa__condominio=condominio,
        estado__in=(EstadoMedida.EJECUTADA, EstadoMedida.EN_ESCALAMIENTO),
    ).count()

    puntos = []
    if contenciones:
        # Va primero: una contencion sin ratificar sigue activa sobre alguien.
        puntos.append(f'{_linea(contenciones, "paralizacion", "paralizaciones")} esperando tu ratificacion')
    if vencidos:
        puntos.append(
            f'{_linea(vencidos, "apelacion", "apelaciones")} con el plazo de respuesta VENCIDO'
        )
    if en_revision:
        puntos.append(f'{_linea(en_revision, "caso", "casos")} por revisar')
    if descargos:
        puntos.append(f'{_linea(descargos, "apelacion", "apelaciones")} por resolver')
    if por_confirmar:
        puntos.append(
            f'{_linea(por_confirmar, "cobro detenido", "cobros detenidos")} esperando tu confirmacion'
        )

    return {
        'rol': Rol.COMITE,
        'puntos': puntos,
        'urgente': bool(contenciones or vencidos),
        'total': en_revision + descargos + contenciones + por_confirmar,
    }


def resumen_para_administracion(condominio):
    """Lo que la administracion debe ejecutar: notificar, responder y cobrar."""
    from novedades.models import EstadoNovedad, NovedadLibro

    por_notificar = Multa.objects.filter(
        condominio=condominio, estado=EstadoMulta.APROBADA,
    ).count()
    firmes = Multa.objects.filter(
        condominio=condominio, estado=EstadoMulta.FIRME,
    ).count()

    novedades = NovedadLibro.objects.filter(condominio=condominio, estado=EstadoNovedad.PENDIENTE)
    por_responder = novedades.count()
    limite_urgente = timezone.now() + timedelta(days=DIAS_URGENCIA)
    urgentes = novedades.filter(fecha_limite_respuesta__lte=limite_urgente).count()

    # Las apelaciones que el Comite dejo vencer tambien se le avisan a la
    # administracion: si el organo que decide no responde, alguien tiene que
    # empujarlo. Una apelacion sin respuesta no se resuelve sola.
    apelaciones_vencidas = Multa.objects.filter(
        condominio=condominio, estado=EstadoMulta.CON_DESCARGO,
        descargo__resolucion=ResolucionDescargo.PENDIENTE,
        descargo__fecha_limite_resolucion__lt=timezone.now(),
    ).count()

    puntos = []
    if apelaciones_vencidas:
        puntos.append(
            f'{_linea(apelaciones_vencidas, "apelacion", "apelaciones")} que el Comite '
            f'no ha respondido dentro del plazo: recuerdaselo'
        )
    if por_notificar:
        puntos.append(f'{_linea(por_notificar, "multa aprobada", "multas aprobadas")} por notificar')
    if urgentes:
        puntos.append(
            f'{_linea(urgentes, "reclamo", "reclamos")} del Libro de Novedades '
            f'con el plazo legal por vencer'
        )
    elif por_responder:
        puntos.append(f'{_linea(por_responder, "reclamo", "reclamos")} por responder')
    if firmes:
        puntos.append(
            f'{_linea(firmes, "multa firme lista", "multas firmes listas")} para el cobro'
        )

    return {
        'rol': Rol.ADMINISTRADOR,
        'puntos': puntos,
        'urgente': bool(urgentes or apelaciones_vencidas),
        'total': por_notificar + por_responder + firmes + apelaciones_vencidas,
    }


def redactar_mensaje(condominio, resumen):
    """
    Texto corto, con el enlace para entrar a resolverlo. Sin emojis: el mismo
    texto viaja a WhatsApp, a un correo y a una consola, y no todas hablan
    el mismo juego de caracteres.
    """
    encabezado = 'URGENTE - ' if resumen['urgente'] else ''
    cuerpo = f'{encabezado}{condominio.nombre}: tienes pendientes.\n\n'
    cuerpo += '\n'.join(f'- {p}' for p in resumen['puntos'])
    cuerpo += f'\n\nEntrar: {settings.FRONTEND_URL.rstrip("/")}/app'
    return cuerpo


def _enviar_whatsapp(telefono, texto):
    """Best-effort, igual que el aviso de multa: si no hay canal, se omite."""
    import requests

    sid, token, emisor = (
        settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN, settings.TWILIO_WHATSAPP_FROM,
    )
    telefono = (telefono or '').strip()
    if not (sid and token and emisor and telefono):
        return False
    destino = telefono if telefono.startswith('whatsapp:') else f'whatsapp:{telefono}'
    respuesta = requests.post(
        f'https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json',
        auth=(sid, token),
        data={'From': emisor, 'To': destino, 'Body': texto},
        timeout=10,
    )
    return respuesta.status_code in (200, 201)


def enviar_resumen(condominio, resumen, destinatarios):
    """Envia el resumen a cada destinatario por sus canales disponibles."""
    if not resumen['puntos'] or not destinatarios:
        return 0

    texto = redactar_mensaje(condominio, resumen)
    asunto = f'{condominio.nombre}: {resumen["total"]} pendientes en VIVEPIOLA'
    enviados = 0

    for usuario in destinatarios:
        if usuario.email:
            try:
                EmailMessage(
                    subject=asunto, body=texto,
                    from_email=settings.DEFAULT_FROM_EMAIL, to=[usuario.email],
                ).send(fail_silently=True)
                enviados += 1
            except Exception:
                pass
        try:
            _enviar_whatsapp(usuario.telefono, texto)
        except Exception:
            pass  # el resumen es un recordatorio: su fallo nunca frena nada
    return enviados
