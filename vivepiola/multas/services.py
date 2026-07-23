import io
from datetime import timedelta
from decimal import Decimal

import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.utils import timezone
from xhtml2pdf import pisa

from condominios.vocab import frase, termino

from .models import Descargo, EstadoMulta, HistorialMulta, TipoActo
from .sellado import sellar_acto


def registrar_historial(multa, estado_anterior, estado_nuevo, usuario, comentario=''):
    HistorialMulta.objects.create(
        multa=multa,
        estado_anterior=estado_anterior,
        estado_nuevo=estado_nuevo,
        usuario=usuario,
        comentario=comentario,
    )


def verificar_reincidencia(unidad, infraccion, ventana_meses=None):
    """
    Ley 21.442: existe reincidencia cuando se comete la misma infraccion
    dentro de los N meses siguientes a la fecha de la primera sancion
    (N configurable, por defecto settings.REINCIDENCIA_VENTANA_MESES).
    """
    ventana_meses = ventana_meses or settings.REINCIDENCIA_VENTANA_MESES
    limite = timezone.now() - timedelta(days=30 * ventana_meses)

    from .models import Multa  # import local para evitar ciclos

    primera_sancion = (
        Multa.objects.filter(
            unidad=unidad,
            infraccion=infraccion,
            estado__in=[
                EstadoMulta.APROBADA, EstadoMulta.NOTIFICADA,
                EstadoMulta.CON_DESCARGO, EstadoMulta.FIRME, EstadoMulta.EXPORTADA,
            ],
            fecha_aprobacion__gte=limite,
        )
        .order_by('fecha_aprobacion')
        .first()
    )

    if not primera_sancion:
        return False, None, ''

    agravante = (
        f'Reincidencia: misma infraccion "{infraccion.codigo}" ya sancionada el '
        f'{primera_sancion.fecha_aprobacion:%d-%m-%Y} (multa #{primera_sancion.id}), '
        f'dentro de los {ventana_meses} meses que establece la ley. '
        'Se sugiere al Comite aplicar el agravante correspondiente de su reglamento.'
    )
    return True, primera_sancion, agravante


def _contexto_vocab_notificacion(multa):
    """
    Terminos y frases del vertical, resueltos para el PDF. Se exponen como
    claves planas (no lambdas) porque el motor de plantillas de Django no puede
    invocar funciones con argumentos.
    """
    c = multa.condominio
    fecha_limite = multa.fecha_limite_descargo.strftime('%d-%m-%Y') if multa.fecha_limite_descargo else ''
    dias = multa.plazo_descargo_dias or c.plazo_descargo_dias
    return {
        'termino_unidad_cap': termino(c, 'unidad_cap'),
        'termino_sujeto_cap': termino(c, 'sujeto_cap'),
        'termino_organo': termino(c, 'organo_sancionador'),
        'aviso_descargo': frase(c, 'pdf_aviso_descargo', dias=dias, fecha_limite=fecha_limite),
        'multa_num': frase(c, 'pdf_titulo', numero=multa.id),
    }


def generar_pdf_notificacion(multa):
    """
    Genera el PDF de notificacion (xhtml2pdf). Plantilla 100% determinista:
    los datos se inyectan desde el expediente, el marco legal y el vocabulario
    vienen de la configuracion del vertical de la organizacion — cero IA.
    """
    html = render_to_string('multas/notificacion_pdf.html', {
        'multa': multa,
        'marco_legal': multa.condominio.marco_legal_texto,
        'voc': _contexto_vocab_notificacion(multa),
    })
    buffer = io.BytesIO()
    resultado = pisa.CreatePDF(src=html, dest=buffer)
    if resultado.err:
        raise RuntimeError('No se pudo generar el PDF de notificacion.')
    buffer.seek(0)
    return buffer.read()


def generar_audit_trail_pdf(multa, solicitante):
    """
    La Prueba Maestra: certificado imprimible de integridad del expediente.

    100% determinista: recalcula la cadena completa (verificar_expediente)
    en el momento de la emision e inyecta los resultados en una plantilla
    rigida. Cero IA. Si el recalculo detecta alteraciones, el certificado
    NO las oculta: emite el sello de alerta con el punto exacto del quiebre
    — un certificado que solo supiera decir "todo bien" no valdria nada.
    """
    from .sellado import verificar_expediente

    informe = verificar_expediente(multa)
    if not informe['sellado']:
        raise ValueError(
            'El expediente no tiene actos sellados (legacy V1): no existe cadena criptografica que certificar.'
        )

    actas = {a.indice: a for a in multa.actas_selladas.order_by('indice')}
    filas = []
    for r in informe['actas']:
        acta = actas[r['indice']]
        actor_manifiesto = acta.manifiesto.get('actor') or {}
        extra = acta.manifiesto.get('extra') or {}
        hitos = []
        if extra.get('ratificacion_tardia'):
            hitos.append('RATIFICACION TARDIA')
        if extra.get('tope_alcanzado'):
            hitos.append('TOPE DE CADENA ALCANZADO')
        filas.append({
            'indice': r['indice'],
            'tipo': acta.get_tipo_acto_display() + (f" [{' / '.join(hitos)}]" if hitos else ''),
            'tipo_manifiesto': acta.manifiesto.get('tipo_manifiesto', 'SANCION'),
            'actor': r['actor'],
            'rol': actor_manifiesto.get('rol', 'SISTEMA'),
            'ts': acta.ts,
            'auth': acta.auth_metodo,
            'hash_previo': acta.hash_previo[:12],
            'hash_acto': acta.hash_acto[:12],
            'ok': r['integra'],
        })

    evidencias_obj = {ev.id: ev for ev in multa.ticket.evidencias.all()}
    evidencias = []
    for r in informe['evidencias']:
        ev = evidencias_obj.get(r['id'])
        evidencias.append({
            'id': r['id'],
            'archivo': r['archivo'],
            'subida': ev.subida_en if ev else None,
            'sha256_corto': (ev.sha256[:24] + '...') if ev and ev.sha256 else 'sin hash (pre-epoca)',
            'anclaje': ev.anclaje_fisico if ev else False,
            'ok': r['integra'],
        })

    hash_raiz = multa.actas_selladas.order_by('-indice').first().hash_acto

    html = render_to_string('multas/audit_trail_pdf.html', {
        'multa': multa,
        'integra': informe['integra'],
        'total_actas': informe['total_actas'],
        'filas': filas,
        'evidencias': evidencias,
        'hash_raiz': hash_raiz,
        'generado_en': timezone.now(),
        'solicitante': solicitante.get_full_name() or solicitante.username,
        'marco_legal_nombre': multa.condominio.marco_legal_nombre,
        'marco_legal_texto': multa.condominio.marco_legal_texto,
    })
    buffer = io.BytesIO()
    resultado = pisa.CreatePDF(src=html, dest=buffer)
    if resultado.err:
        raise RuntimeError('No se pudo generar el certificado de integridad.')
    buffer.seek(0)
    return buffer.read()


def enviar_notificacion_email(multa, pdf_bytes):
    """
    Envia la notificacion legal al correo registrado del sujeto responsable:
    este es EL canal legal de notificacion exigido para el debido proceso.
    Asunto y cuerpo se componen por frases completas del vertical (i18n
    clave-por-frase), no por concatenacion de palabras sueltas.
    """
    persona = multa.persona_infractor
    if not persona or not persona.correo_electronico:
        raise ValueError('El sujeto responsable no tiene correo electronico registrado.')

    c = multa.condominio
    inf = multa.infraccion
    fecha_limite = multa.fecha_limite_descargo.strftime('%d-%m-%Y') if multa.fecha_limite_descargo else ''
    dias = multa.plazo_descargo_dias or c.plazo_descargo_dias

    asunto = frase(c, 'notificacion_asunto', numero=multa.id, org_nombre=c.nombre)
    cuerpo = '\n\n'.join([
        frase(c, 'notificacion_saludo', nombre=persona.nombre_completo),
        frase(
            c, 'notificacion_cuerpo',
            org_nombre=c.nombre,
            unidad_id=multa.unidad.identificador,
            infraccion=inf.descripcion,
            articulo=inf.articulo_referencia,
        ),
        frase(c, 'notificacion_monto', monto=multa.monto, unidad_monto=inf.unidad_monto),
        frase(c, 'notificacion_plazo', dias=dias, fecha_limite=fecha_limite),
        frase(c, 'notificacion_canal_legal'),
    ])
    email = EmailMessage(
        subject=asunto,
        body=cuerpo,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[persona.correo_electronico],
    )
    email.attach(f'notificacion_{multa.id}.pdf', pdf_bytes, 'application/pdf')
    email.send(fail_silently=False)


def enviar_notificacion_whatsapp(multa):
    """
    Aviso COMPLEMENTARIO por WhatsApp (Twilio). El canal legal de la
    notificacion sigue siendo el correo; este solo avisa que hay una multa que
    revisar. Best-effort: si el canal no esta configurado o falla, se omite sin
    interrumpir el debido proceso. Devuelve True solo si el mensaje se envio.
    """
    sid = settings.TWILIO_ACCOUNT_SID
    token = settings.TWILIO_AUTH_TOKEN
    emisor = settings.TWILIO_WHATSAPP_FROM
    if not (sid and token and emisor):
        return False

    persona = multa.persona_infractor
    telefono = ((getattr(persona, 'telefono', '') or '').strip()) if persona else ''
    if not telefono:
        return False

    c = multa.condominio
    dias = multa.plazo_descargo_dias or c.plazo_descargo_dias
    cuerpo = (
        f'{c.nombre}: se registro una multa (#{multa.id}) para la unidad '
        f'{multa.unidad.identificador}. El detalle formal esta en su correo. '
        f'Tiene {dias} dias corridos para presentar su descargo.'
    )
    destino = telefono if telefono.startswith('whatsapp:') else f'whatsapp:{telefono}'
    resp = requests.post(
        f'https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json',
        auth=(sid, token),
        data={'From': emisor, 'To': destino, 'Body': cuerpo},
        timeout=10,
    )
    return resp.status_code in (200, 201)


def proponer_infraccion(ticket):
    """
    Analisis automatico del reporte: sugiere la infraccion del catalogo ACTIVO
    que mejor calza con la descripcion (coincidencia por palabras clave del
    codigo y la descripcion de cada infraccion). Es una PROPUESTA — el Comite
    siempre confirma o cambia antes de aprobar; nunca sanciona sola.
    """
    from reglamentos.models import EstadoInfraccion, InfraccionCatalogo

    activos = list(InfraccionCatalogo.objects.filter(
        condominio=ticket.condominio, estado=EstadoInfraccion.ACTIVA,
    ))
    if not activos:
        return None

    texto = (ticket.descripcion or '').lower()
    mejor, mejor_score = None, 0
    for inf in activos:
        tokens = {t for t in f'{inf.codigo} {inf.descripcion}'.lower().replace('-', ' ').split() if len(t) >= 4}
        score = sum(1 for t in tokens if t in texto)
        if score > mejor_score:
            mejor, mejor_score = inf, score
    return mejor if mejor_score > 0 else None


def notificar_multa(multa, usuario):
    """Orquesta: genera PDF, calcula plazo de descargo, envia correo (+WhatsApp) y actualiza estado."""
    estado_anterior = multa.estado
    pdf_bytes = generar_pdf_notificacion(multa)

    multa.plazo_descargo_dias = multa.plazo_descargo_dias or multa.condominio.plazo_descargo_dias
    multa.fecha_limite_descargo = timezone.now() + timedelta(days=multa.plazo_descargo_dias)
    multa.pdf_notificacion.save(f'notificacion_multa_{multa.id}.pdf', ContentFile(pdf_bytes), save=False)

    enviar_notificacion_email(multa, pdf_bytes)

    multa.estado = EstadoMulta.NOTIFICADA
    multa.notificada_por = usuario
    multa.fecha_notificacion = timezone.now()
    multa.save()

    # Aviso complementario por WhatsApp: nunca bloquea el flujo legal.
    try:
        whatsapp_enviado = enviar_notificacion_whatsapp(multa)
    except Exception:
        whatsapp_enviado = False

    registrar_historial(multa, estado_anterior, multa.estado, usuario, 'Notificacion enviada al correo registrado.')
    sellar_acto(multa, TipoActo.NOTIFICACION, usuario, extra={
        'correo_destino': multa.persona_infractor.correo_electronico,
        'whatsapp_enviado': whatsapp_enviado,
        'plazo_descargo_dias': multa.plazo_descargo_dias,
        'fecha_limite_descargo': multa.fecha_limite_descargo.isoformat(),
        'pdf_notificacion': multa.pdf_notificacion.name,
    })
    return multa


def actualizar_multas_vencidas(condominio=None):
    """
    Marca como FIRME las multas notificadas cuyo plazo de descargo vencio sin
    que el residente presentara defensa. Se ejecuta de forma perezosa (al
    listar) para no depender de un scheduler externo tipo Celery.
    """
    from .models import Multa

    qs = Multa.objects.filter(estado=EstadoMulta.NOTIFICADA, fecha_limite_descargo__lt=timezone.now())
    if condominio is not None:
        qs = qs.filter(condominio=condominio)

    for multa in qs:
        multa.estado = EstadoMulta.FIRME
        multa.fecha_firme = timezone.now()
        multa.save(update_fields=['estado', 'fecha_firme'])
        registrar_historial(
            multa, EstadoMulta.NOTIFICADA, EstadoMulta.FIRME, None,
            'Firme automaticamente: vencio el plazo de descargo sin presentacion.',
        )
        sellar_acto(multa, TipoActo.FIRMEZA_AUTOMATICA, None, auth_metodo='sistema', extra={
            'fecha_limite_vencida': multa.fecha_limite_descargo.isoformat(),
        })


def resolver_descargo(descargo, resolucion, usuario, comentario='', porcentaje_descuento=None):
    """
    El Comite resuelve la apelacion con tres desenlaces posibles (Ley 21.442):
      - ACEPTADO  -> se anula la multa (monto a cero, expediente ANULADA).
      - RECHAZADO -> la multa se mantiene firme por su monto original.
      - DESCUENTO -> la multa queda firme pero con una rebaja porcentual del
        monto. El monto previo se congela en el descargo para trazabilidad.
    """
    from .models import ResolucionDescargo

    multa = descargo.multa
    estado_anterior = multa.estado

    descargo.resolucion = resolucion
    descargo.resuelto_por = usuario
    descargo.comentario_resolucion = comentario
    descargo.fecha_resolucion = timezone.now()

    monto_final = multa.monto
    if resolucion == ResolucionDescargo.ACEPTADO:
        multa.estado = EstadoMulta.ANULADA
    elif resolucion == ResolucionDescargo.DESCUENTO:
        pct = int(porcentaje_descuento or 0)
        descargo.monto_original = multa.monto
        descargo.porcentaje_descuento = pct
        factor = (Decimal(100) - Decimal(pct)) / Decimal(100)
        monto_final = (multa.monto * factor).quantize(Decimal('0.01'))
        multa.monto = monto_final
        multa.estado = EstadoMulta.FIRME
        multa.fecha_firme = timezone.now()
    else:  # RECHAZADO
        multa.estado = EstadoMulta.FIRME
        multa.fecha_firme = timezone.now()

    descargo.save()
    multa.save()

    detalle = f'Descargo resuelto: {resolucion}.'
    if resolucion == ResolucionDescargo.DESCUENTO:
        detalle = f'Descargo resuelto: DESCUENTO {porcentaje_descuento}% (monto {descargo.monto_original} -> {monto_final}).'
    registrar_historial(multa, estado_anterior, multa.estado, usuario, f'{detalle} {comentario}'.strip())
    sellar_acto(multa, TipoActo.RESOLUCION_DESCARGO, usuario, extra={
        'resolucion': resolucion,
        'comentario': comentario,
        'porcentaje_descuento': porcentaje_descuento,
        'monto_original': str(descargo.monto_original) if descargo.monto_original is not None else None,
        'monto_final': str(monto_final) if monto_final is not None else None,
        'texto_descargo': descargo.texto,
        'descargo_presentado_en': descargo.fecha_presentacion.isoformat(),
    })
    return multa
