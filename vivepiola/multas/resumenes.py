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
    por_vencer = _apelaciones_por_vencer(condominio)
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
    if por_vencer:
        puntos.append(_linea_por_vencer(por_vencer, 'Si no las resuelves, quedan firmes y se cobran en gastos comunes.'))
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
        'urgente': bool(contenciones or vencidos or por_vencer),
        'total': en_revision + descargos + contenciones + por_confirmar,
    }


def _apelaciones_por_vencer(condominio):
    """Apelaciones sin resolver cuyo plazo del Comite vence en los proximos dias."""
    ahora = timezone.now()
    return list(Multa.objects.filter(
        condominio=condominio, estado=EstadoMulta.CON_DESCARGO,
        descargo__resolucion=ResolucionDescargo.PENDIENTE,
        descargo__fecha_limite_resolucion__gte=ahora,
        descargo__fecha_limite_resolucion__lte=ahora + timedelta(days=DIAS_URGENCIA),
    ).select_related('descargo').order_by('descargo__fecha_limite_resolucion'))


def _linea_por_vencer(multas, consecuencia):
    casos = ', '.join(
        f'#{m.id} vence el {timezone.localtime(m.descargo.fecha_limite_resolucion):%d-%m}' for m in multas
    )
    return (
        f'URGENTE: {_linea(len(multas), "apelacion vence", "apelaciones vencen")} en menos de '
        f'{DIAS_URGENCIA} dias ({casos}). {consecuencia}'
    )


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

    por_vencer = _apelaciones_por_vencer(condominio)

    puntos = []
    if por_vencer:
        puntos.append(_linea_por_vencer(
            por_vencer, 'Recuerdaselo al Comite: si no las resuelve, quedan firmes y se cobran.',
        ))
    if apelaciones_vencidas:
        puntos.append(
            f'{_linea(apelaciones_vencidas, "apelacion", "apelaciones")} que el Comite '
            f'no ha respondido dentro del plazo: recuerdaselo'
        )
    if por_notificar:
        puntos.append(f'{_linea(por_notificar, "multa aprobada", "multas aprobadas")} por notificar')
    if urgentes:
        puntos.append(
            f'{_linea(urgentes, "reclamo", "reclamos")} de Solicitudes y reclamos '
            f'con el plazo de respuesta por vencer'
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
        'urgente': bool(urgentes or apelaciones_vencidas or por_vencer),
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


def _enviar_whatsapp(telefono, texto, condominio, resumen):
    """Best-effort, igual que el aviso de multa: si no hay canal, se omite."""
    from .services import enviar_whatsapp

    # Variables de la plantilla "resumen_pendientes" (ver PUESTA_EN_MARCHA.md, 1.5).
    variables = (
        condominio.nombre,
        '; '.join(resumen['puntos']),
        f'{settings.FRONTEND_URL.rstrip("/")}/app',
    )
    return enviar_whatsapp(telefono, texto, settings.TWILIO_PLANTILLA_RESUMEN, variables)


def enviar_resumen(condominio, resumen, destinatarios):
    """Envia el resumen a cada destinatario por sus canales disponibles."""
    if not resumen['puntos'] or not destinatarios:
        return 0

    from .correo_html import correo_con_html, html_correo

    texto = redactar_mensaje(condominio, resumen)
    asunto = f'{condominio.nombre}: {resumen["total"]} pendientes en SINCONFLICTO'
    html = html_correo(
        comunidad=condominio.nombre,
        titulo='Urgente: tienes pendientes' if resumen['urgente'] else 'Tienes pendientes',
        parrafos=[
            'Esto es lo que espera de ti en tu comunidad:',
            '\n'.join(f'- {p}' for p in resumen['puntos']),
        ],
        boton=('Entrar a resolverlo', f'{settings.FRONTEND_URL.rstrip("/")}/app'),
        pie='Recibes un solo resumen al dia, y solo cuando hay algo pendiente.',
    )
    enviados = 0

    for usuario in destinatarios:
        if usuario.email:
            try:
                correo_con_html(
                    asunto=asunto, texto=texto, html=html,
                    from_email=settings.DEFAULT_FROM_EMAIL, to=[usuario.email],
                ).send(fail_silently=True)
                enviados += 1
            except Exception:
                pass
        try:
            _enviar_whatsapp(usuario.telefono, texto, condominio, resumen)
        except Exception:
            pass  # el resumen es un recordatorio: su fallo nunca frena nada
    return enviados
