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


def copropietario_en_copia(multa):
    """
    Devuelve al copropietario cuando la notificacion debe llegarle en copia,
    o None cuando basta con notificar al infractor.

    La Ley 21.442 hace al copropietario el obligado principal al pago, asi que
    tiene interes legitimo en toda multa de su unidad. Pero copiarlo siempre
    seria excesivo: se hace solo cuando el infractor podria no estar para
    ejercer su defensa, o cuando ocupa la unidad precisamente por el vinculo
    con el dueño.

    - TRANSITORIO: puede haberse ido antes de que corra el plazo de descargo
      (hospedaje turistico, estadia corta). Sin copia al dueño, el expediente
      arriesga quedarse sin notificado valido.
    - Ocupa por vinculo con el copropietario (conyuge, conviviente civil,
      familiar): su titulo de ocupacion depende de ese vinculo.

    Nunca se copia al propio infractor ni a quien no tenga correo registrado.
    """
    from condominios.models import Permanencia, VinculoCopropietario

    infractor = multa.persona_infractor
    if not infractor or not multa.unidad:
        return None

    corresponde = (
        infractor.permanencia == Permanencia.TRANSITORIO
        or infractor.vinculo_copropietario in (
            VinculoCopropietario.CONYUGE,
            VinculoCopropietario.CONVIVIENTE_CIVIL,
            VinculoCopropietario.FAMILIAR,
        )
    )
    if not corresponde:
        return None

    propietario = multa.unidad.propietario
    if not propietario or propietario.id == infractor.id or not propietario.correo_electronico:
        return None
    if propietario.correo_electronico == infractor.correo_electronico:
        return None
    return propietario


def enviar_notificacion_email(multa, pdf_bytes):
    """
    Envia la notificacion legal al correo registrado del sujeto responsable:
    este es EL canal legal de notificacion exigido para el debido proceso.
    Asunto y cuerpo se componen por frases completas del vertical (i18n
    clave-por-frase), no por concatenacion de palabras sueltas.

    Devuelve la lista de correos que recibieron copia (ver copropietario_en_copia),
    para que quede sellada en el acta quien fue notificado realmente.
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
    copia = copropietario_en_copia(multa)
    copias = [copia.correo_electronico] if copia else []
    if copia:
        cuerpo += '\n\n' + frase(
            c, 'notificacion_copia_copropietario',
            nombre=copia.nombre_completo, unidad_id=multa.unidad.identificador,
        )

    email = EmailMessage(
        subject=asunto,
        body=cuerpo,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[persona.correo_electronico],
        cc=copias,
    )
    email.attach(f'notificacion_{multa.id}.pdf', pdf_bytes, 'application/pdf')
    email.send(fail_silently=False)
    return copias


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
    limite = multa.fecha_limite_descargo.strftime('%d-%m-%Y') if multa.fecha_limite_descargo else ''
    # Link directo al expediente: el aviso sirve para actuar, no solo para
    # enterarse. No lleva sesion en la URL a proposito (los mensajes se
    # reenvian): al abrirlo se pide identificarse y recien ahi se muestra.
    enlace = f'{settings.FRONTEND_URL.rstrip("/")}/m/{multa.id}'
    cuerpo = (
        f'{c.nombre}: se registro una multa (#{multa.id}) para la unidad '
        f'{multa.unidad.identificador}. La notificacion formal, con su documento, '
        f'esta en su correo registrado.\n\n'
        f'Tiene {dias} dias corridos para presentar su descargo'
        f'{f" (hasta el {limite})" if limite else ""}.\n\n'
        f'Ver el detalle y responder: {enlace}'
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
    Analiza el reporte y propone la infraccion del catalogo ACTIVO que
    corresponde, con su fundamento.

    Es una PROPUESTA: la multa nace EN_REVISION y el Comite confirma o cambia
    antes de aprobar. Intenta primero el clasificador con IA y, si no hay clave
    o la llamada falla, cae al respaldo determinista por coincidencia de
    terminos: el debido proceso nunca queda a merced de un servicio externo.

    Devuelve (infraccion|None, origen, confianza, fundamento).
    """
    from reglamentos.models import EstadoInfraccion, InfraccionCatalogo

    from .clasificador import (
        ORIGEN_COINCIDENCIA, ORIGEN_IA, clasificar_con_ia, clasificar_por_coincidencia,
    )

    activos = list(InfraccionCatalogo.objects.filter(
        condominio=ticket.condominio, estado=EstadoInfraccion.ACTIVA,
    ))
    if not activos:
        return None, '', 0, ''

    if settings.ANTHROPIC_API_KEY:
        try:
            infraccion, confianza, fundamento = clasificar_con_ia(ticket, activos)
            if infraccion is not None:
                return infraccion, ORIGEN_IA, confianza, fundamento
            if fundamento:
                # La IA respondio que ninguna encaja: se conserva el porque.
                return None, ORIGEN_IA, confianza, fundamento
        except Exception:
            pass  # cualquier fallo del servicio cae al respaldo determinista

    infraccion, confianza, fundamento = clasificar_por_coincidencia(ticket, activos)
    if infraccion is None:
        return None, '', 0, ''
    return infraccion, ORIGEN_COINCIDENCIA, confianza, fundamento


# Estados en los que el expediente sigue vivo: un reporte nuevo sobre el mismo
# hecho debe sumarse a el. Si fue RECHAZADA o ANULADA, el hecho quedo sin
# sancion y un reporte posterior si merece expediente propio.
ESTADOS_EXPEDIENTE_ABIERTO = (
    EstadoMulta.EN_REVISION, EstadoMulta.APROBADA, EstadoMulta.NOTIFICADA,
    EstadoMulta.CON_DESCARGO, EstadoMulta.FIRME, EstadoMulta.EXPORTADA,
)

# Como se le explica el estado a quien reporta. Se describe la ETAPA, nunca el
# monto, la infraccion ni la persona: el vecino que reporta no tiene por que
# conocer la sancion de otra unidad.
ETAPA_PARA_DENUNCIANTE = {
    EstadoMulta.EN_REVISION: 'Ya fue reportado y esta en revision del comite.',
    EstadoMulta.APROBADA: 'Ya fue reportado, el comite lo resolvio y esta por notificarse.',
    EstadoMulta.NOTIFICADA: 'Ya fue reportado y el residente ya fue notificado.',
    EstadoMulta.CON_DESCARGO: 'Ya fue reportado y el residente presento su descargo.',
    EstadoMulta.FIRME: 'Ya fue reportado y el caso quedo cerrado.',
    EstadoMulta.EXPORTADA: 'Ya fue reportado y el caso quedo cerrado.',
}


def buscar_expediente_abierto(condominio, unidad, fecha_hecho, infraccion_propuesta=None):
    """
    Busca un expediente vivo sobre la misma unidad referido al mismo hecho.

    Criterio: misma unidad + el hecho ocurrio dentro de la ventana que definio
    la comunidad. Si ambos reportes traen una infraccion propuesta y son
    distintas, se entienden hechos distintos (ruido y mascota suelta la misma
    noche son dos cosas) y cada uno abre su expediente.
    """
    from .models import Multa

    horas = condominio.ventana_duplicados_horas or 0
    if not horas:
        return None

    ventana = timedelta(hours=horas)
    candidatas = Multa.objects.filter(
        condominio=condominio,
        unidad=unidad,
        estado__in=ESTADOS_EXPEDIENTE_ABIERTO,
        ticket__fecha_hecho__gte=fecha_hecho - ventana,
        ticket__fecha_hecho__lte=fecha_hecho + ventana,
    ).order_by('fecha_creacion')

    for candidata in candidatas:
        if (
            infraccion_propuesta is not None
            and candidata.infraccion_id is not None
            and candidata.infraccion_id != infraccion_propuesta.id
        ):
            continue  # otro tipo de hecho: merece expediente propio
        return candidata
    return None


def notificar_multa(multa, usuario):
    """Orquesta: genera PDF, calcula plazo de descargo, envia correo (+WhatsApp) y actualiza estado."""
    estado_anterior = multa.estado
    pdf_bytes = generar_pdf_notificacion(multa)

    multa.plazo_descargo_dias = multa.plazo_descargo_dias or multa.condominio.plazo_descargo_dias
    multa.fecha_limite_descargo = timezone.now() + timedelta(days=multa.plazo_descargo_dias)
    multa.pdf_notificacion.save(f'notificacion_multa_{multa.id}.pdf', ContentFile(pdf_bytes), save=False)

    copias = enviar_notificacion_email(multa, pdf_bytes)

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
        # Quien recibio copia queda sellado: si mañana se discute si el
        # copropietario fue notificado, el acta lo prueba.
        'copias_copropietario': sorted(copias),
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
