import io
from datetime import timedelta
from decimal import Decimal

import requests
from django.conf import settings
from django.core import signing
from django.core.files.base import ContentFile
from django.core.mail import EmailMessage
from django.db.models.functions import Coalesce
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
                # El parte de cortesia cuenta: su sentido es avisar que la
                # proxima vez se cobra. Si no contara, se podria pedir cortesia
                # indefinidamente por la misma falta.
                EstadoMulta.CORTESIA,
            ],
        )
        # Las multas que se cursan solas no tienen fecha_aprobacion, porque
        # nadie las aprobo. Tomar solo esa fecha las dejaba fuera del conteo y
        # la reincidencia dejaba de detectarse justo en el camino normal.
        .annotate(fecha_sancion=Coalesce('fecha_aprobacion', 'fecha_notificacion'))
        .filter(fecha_sancion__gte=limite)
        .order_by('fecha_sancion')
        .first()
    )

    if not primera_sancion:
        return False, None, ''

    fecha_previa = primera_sancion.fecha_aprobacion or primera_sancion.fecha_notificacion
    tipo_previo = (
        'ya advertida con parte de cortesia'
        if primera_sancion.estado == EstadoMulta.CORTESIA else 'ya sancionada'
    )
    agravante = (
        f'Reincidencia: misma infraccion "{infraccion.codigo}" {tipo_previo} el '
        f'{fecha_previa:%d-%m-%Y} (multa #{primera_sancion.id}), '
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
        # El PDF no puede atribuirle al organo sancionador una aprobacion que
        # no existio: sin aprobada_por, la multa se curso automaticamente.
        'label_origen': termino(
            c, 'pdf_label_organo' if multa.aprobada_por_id else 'pdf_label_organo_automatica',
        ),
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


SAL_ACUSE = 'vivepiola-acuse-notificacion'
# Un enlace de acuse no puede servir para siempre: pasado este plazo el
# expediente ya se resolvio por otra via y el enlace deja de tener sentido.
ACUSE_VIGENCIA_SEGUNDOS = 90 * 24 * 3600


def token_acuse(multa):
    """Token firmado que identifica la multa sin exponer nada mas."""
    return signing.dumps({'multa': multa.id}, salt=SAL_ACUSE)


def multa_desde_token_acuse(token):
    """Devuelve la multa del token, o None si es invalido o vencido."""
    from .models import Multa

    try:
        datos = signing.loads(token, salt=SAL_ACUSE, max_age=ACUSE_VIGENCIA_SEGUNDOS)
    except signing.BadSignature:
        return None
    return Multa.objects.filter(id=datos.get('multa')).first()


def enlace_acuse(multa):
    return f'{settings.FRONTEND_URL.rstrip("/")}/acuse/{token_acuse(multa)}'


def puntos_de_contacto(multa):
    """
    Canales por los que se puede alcanzar al residente, en orden legal.

    El correo es el canal legal; WhatsApp acompaña. Se devuelven juntos porque
    la notificacion se despacha por TODOS a la vez: alcanzar a la persona
    importa mas que ahorrarse un mensaje.
    """
    from .models import CanalNotificacion

    persona = multa.persona_infractor
    if not persona:
        return []

    puntos = []
    if persona.correo_electronico:
        puntos.append((CanalNotificacion.EMAIL, persona.correo_electronico))
    if persona.telefono:
        puntos.append((CanalNotificacion.WHATSAPP, persona.telefono))
    return puntos


def registrar_acuse(multa, canal, usuario=None, destino='', detalle=''):
    """
    Deja constancia de que el residente recibio la notificacion y arranca el
    plazo de apelacion.

    Es idempotente: el primer acuse manda. Que despues abra el enlace otras
    diez veces no reabre ni recorta el plazo.
    """
    from .models import CanalNotificacion, EstadoEntrega, EstadoMulta, TipoActo

    if multa.fecha_acuse:
        return False

    ahora = timezone.now()
    dias = multa.plazo_descargo_dias or multa.condominio.plazo_descargo_dias

    multa.fecha_acuse = ahora
    multa.canal_acuse = canal
    multa.fecha_limite_descargo = ahora + timedelta(days=dias)
    multa.save(update_fields=['fecha_acuse', 'canal_acuse', 'fecha_limite_descargo'])

    entrega = multa.entregas.filter(canal=canal).order_by('-enviada_en').first()
    if entrega is None:
        entrega = multa.entregas.create(
            multa=multa, canal=canal, destino=destino or '', intento=0,
            registrada_por=usuario, detalle=detalle,
        )
    entrega.estado = EstadoEntrega.ACUSADA
    entrega.acusada_en = ahora
    if usuario and entrega.registrada_por_id is None:
        entrega.registrada_por = usuario
    entrega.save(update_fields=['estado', 'acusada_en', 'registrada_por'])

    etiqueta = CanalNotificacion(canal).label if canal in CanalNotificacion.values else canal
    registrar_historial(
        multa, multa.estado, multa.estado, usuario,
        f'Notificacion recepcionada por {etiqueta}. El plazo de apelacion vence el '
        f'{multa.fecha_limite_descargo.strftime("%d-%m-%Y")}.',
    )
    sellar_acto(
        multa, TipoActo.ACUSE_RECIBO, usuario,
        auth_metodo='sistema' if usuario is None else 'sesion',
        extra={
            'canal': canal,
            'destino': destino or '',
            'fecha_limite_descargo': multa.fecha_limite_descargo.isoformat(),
            'plazo_descargo_dias': dias,
        },
    )
    return True


def despachar_notificacion(multa, pdf_bytes=None, intento=1):
    """
    Envia la notificacion por todos los puntos de contacto y registra cada
    intento, haya funcionado o no.

    Un canal caido no puede impedir los otros: si el correo falla se registra
    el fallo y se sigue con WhatsApp.

    Devuelve (envios_exitosos, correos_en_copia).
    """
    from .models import CanalNotificacion, EstadoEntrega

    if pdf_bytes is None:
        pdf_bytes = generar_pdf_notificacion(multa)

    enviados = 0
    copias = []
    for canal, destino in puntos_de_contacto(multa):
        try:
            if canal == CanalNotificacion.EMAIL:
                copias = enviar_notificacion_email(multa, pdf_bytes)
            elif not enviar_notificacion_whatsapp(multa):
                continue  # canal no configurado: no es un fallo que registrar
            multa.entregas.create(
                multa=multa, canal=canal, destino=destino, intento=intento,
                estado=EstadoEntrega.ENVIADA,
            )
            enviados += 1
        except Exception as exc:
            multa.entregas.create(
                multa=multa, canal=canal, destino=destino, intento=intento,
                estado=EstadoEntrega.FALLIDA, detalle=str(exc)[:500],
            )
    return enviados, copias


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

    es_cortesia = multa.es_aviso_de_cortesia
    asunto = (
        frase(c, 'notificacion_asunto_cortesia', numero=multa.id, org_nombre=c.nombre)
        if es_cortesia
        else frase(c, 'notificacion_asunto', numero=multa.id, org_nombre=c.nombre)
    )
    # Sin aprobacion humana previa no se puede decir que el organo sancionador
    # aprobo: se usa la redaccion del curse automatico.
    if es_cortesia:
        clave_cuerpo = 'notificacion_cuerpo_cortesia'
    elif multa.aprobada_por_id:
        clave_cuerpo = 'notificacion_cuerpo'
    else:
        clave_cuerpo = 'notificacion_cuerpo_automatica'
    cuerpo = '\n\n'.join([
        frase(c, 'notificacion_saludo', nombre=persona.nombre_completo),
        frase(
            c, clave_cuerpo,
            org_nombre=c.nombre,
            unidad_id=multa.unidad.identificador,
            infraccion=inf.descripcion,
            articulo=inf.articulo_referencia,
        ),
        # En un aviso de cortesia decir "Monto: 0.00" seria absurdo: lo que hay
        # que decir es que no se cobra y cuanto se habria cobrado.
        frase(
            c, 'notificacion_cortesia_sin_cobro',
            monto_evitado=multa.monto_sin_cortesia, unidad_monto=inf.unidad_monto,
        )
        if es_cortesia
        else frase(c, 'notificacion_monto', monto=multa.monto, unidad_monto=inf.unidad_monto),
        # Antes del acuse no hay fecha de vencimiento que anunciar: prometer una
        # que todavia no existe seria confundir a quien lee.
        frase(c, 'notificacion_plazo', dias=dias, fecha_limite=fecha_limite)
        if multa.fecha_limite_descargo
        else frase(c, 'notificacion_plazo_sin_acuse', dias=dias),
        # El acuse es lo que hace correr el plazo, asi que la instruccion va
        # antes del cierre legal y no perdida al final.
        frase(c, 'notificacion_pide_acuse', enlace=enlace_acuse(multa)),
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


def aplicar_monto_con_reincidencia(multa, infraccion, monto_base=None):
    """
    Fija infraccion y monto en el expediente, aplicando el agravante por
    reincidencia de la Ley 21.442 si el catalogo define un factor mayor a 1.

    Devuelve el factor efectivamente aplicado, para dejarlo sellado en el acta.
    """
    es_reincidencia, primera_sancion, agravante = verificar_reincidencia(multa.unidad, infraccion)

    monto = monto_base if monto_base is not None else infraccion.monto
    factor = infraccion.factor_reincidencia or Decimal('1.00')
    factor_aplicado = Decimal('1.00')
    if es_reincidencia and factor > Decimal('1.00'):
        factor_aplicado = factor
        monto = (monto * factor).quantize(Decimal('0.01'))

    multa.infraccion = infraccion
    multa.monto = monto
    multa.es_reincidencia = es_reincidencia
    multa.multa_primera_sancion = primera_sancion
    multa.agravante_sugerido = agravante
    return factor_aplicado


def confianza_minima_para(infraccion):
    """
    Cuanta certeza se exige para cursar sin revision, segun lo que pesa la falta.

    Mientras mas caro sea el error, mas seguro hay que estar antes de actuar
    solo: una leve termina en un aviso sin cobro, una gravisima en un cobro
    inmediato sin cortesia.
    """
    from reglamentos.models import Gravedad

    gravedad = getattr(infraccion, 'gravedad', None) or Gravedad.GRAVE
    return settings.CURSE_CONFIANZA_MINIMA.get(
        gravedad, settings.CURSE_CONFIANZA_MINIMA['GRAVE'],
    )


def puede_cursarse_sola(multa, confianza):
    """
    Decide si el expediente puede notificarse sin que un humano lo tipifique.

    El ciclo ya no tiene un filtro previo del comite: la denuncia va directo al
    residente, que se defiende apelando. Para que eso sea legitimo se exige:

    - una infraccion del catalogo vigente,
    - un sujeto responsable identificado y con correo (sin contacto no hay
      notificacion valida, y sin notificacion no hay plazo de apelacion),
    - que la propuesta venga del analisis con IA y no del respaldo por
      terminos,
    - confianza sobre el umbral que corresponda a la gravedad de la falta.

    Lo que no pasa este filtro no se pierde: queda EN_REVISION para que lo
    tipifique una persona.
    """
    from .clasificador import ORIGEN_IA

    if multa.infraccion is None:
        return False, 'el reporte no calza con ninguna infraccion del catalogo vigente'
    persona = multa.persona_infractor
    if persona is None:
        return False, 'no hay un sujeto responsable identificado'
    if not persona.correo_electronico:
        return False, 'el sujeto responsable no tiene correo registrado'

    # El respaldo por coincidencia de terminos existe para que el sistema no se
    # caiga sin IA, no para sancionar a alguien por calzar palabras sueltas.
    # Se bloquea por ORIGEN y no por umbral: antes la garantia dependia de que
    # ese respaldo topara en 60 y el umbral fuera 70, o sea de una coincidencia
    # numerica que se rompia en silencio si alguien bajaba el umbral.
    if multa.propuesta_origen != ORIGEN_IA:
        return False, (
            'la propuesta salio del respaldo por coincidencia de terminos, que no '
            'sanciona por si solo'
        )

    minimo = confianza_minima_para(multa.infraccion)
    if (confianza or 0) < minimo:
        return False, (
            f'la propuesta automatica quedo en {confianza or 0} de confianza y una falta '
            f'{multa.infraccion.gravedad.lower()} exige al menos {minimo} para cursar sin revision'
        )
    return True, ''


# Estados en que la falta se dio por ocurrida. Son los que cuentan para saber
# si a esta unidad todavia le quedan cortesias.
ESTADOS_FALTA_ACREDITADA = (
    EstadoMulta.APROBADA, EstadoMulta.NOTIFICADA, EstadoMulta.CON_DESCARGO,
    EstadoMulta.POR_CONFIRMAR, EstadoMulta.FIRME, EstadoMulta.EXPORTADA,
    EstadoMulta.CORTESIA,
)


def corresponde_cortesia(multa):
    """
    Decide si esta falta se avisa sin cobrar por ser de las primeras.

    El objetivo de una comunidad no es recaudar sino que la gente sepa que hay
    una norma, y quien la incumple por primera vez casi siempre corrige con el
    aviso. Por eso las primeras faltas de una unidad se notifican sin monto: la
    falta queda igual en el registro, y es ella misma la que consume el cupo.

    Dos cosas nunca admiten cortesia, por muy primera vez que sea:
    - una falta GRAVISIMA, y
    - una que conlleva contencion (paraliza algo o pone a alguien en riesgo).
    Avisar sin consecuencia frente a un riesgo real seria el mensaje contrario.

    Devuelve (corresponde, motivo).
    """
    from reglamentos.models import Gravedad
    from .models import Multa

    infraccion = multa.infraccion
    if infraccion is None or multa.unidad is None:
        return False, ''

    cupo = multa.condominio.cortesias_antes_de_multar
    if cupo <= 0:
        return False, ''

    if infraccion.gravedad == Gravedad.GRAVISIMA:
        return False, 'la falta es gravisima: no admite cortesia'
    if infraccion.conlleva_contencion:
        return False, 'la falta conlleva contencion: no admite cortesia'

    # Se cuentan las faltas previas de la unidad, de cualquier tipo, dentro de
    # la misma ventana que la ley usa para la reincidencia: tres faltas de hace
    # cinco años no deberian costarle la cortesia a nadie.
    limite = timezone.now() - timedelta(days=30 * settings.REINCIDENCIA_VENTANA_MESES)
    previas = (
        Multa.objects
        .filter(unidad=multa.unidad, estado__in=ESTADOS_FALTA_ACREDITADA)
        .exclude(id=multa.id)
        .annotate(fecha_falta=Coalesce('fecha_aprobacion', 'fecha_notificacion', 'fecha_creacion'))
        .filter(fecha_falta__gte=limite)
        .count()
    )
    if previas >= cupo:
        return False, f'la unidad ya acumula {previas} falta(s): corresponde multa'

    restantes = cupo - previas - 1
    return True, (
        f'Es la falta numero {previas + 1} de esta unidad y la comunidad avisa sin cobrar '
        f'las primeras {cupo}. '
        + (
            f'Le queda {restantes} aviso mas antes de que se empiece a cobrar.'
            if restantes == 1 else
            f'Le quedan {restantes} avisos mas antes de que se empiece a cobrar.'
            if restantes > 1 else
            'La proxima falta ya se cobra.'
        )
    )


def cursar_multa_automatica(multa, confianza):
    """
    Tipifica y notifica el expediente sin intervencion humana previa.

    Si algo falla al notificar (correo caido, PDF, etc.) el expediente queda
    EN_REVISION con el motivo registrado: una falla tecnica no puede hacer
    desaparecer una denuncia ni dejar a alguien sancionado sin enterarse.

    Devuelve True solo si el residente quedo efectivamente notificado.
    """
    procede, motivo = puede_cursarse_sola(multa, confianza)
    if not procede:
        registrar_historial(
            multa, multa.estado, multa.estado, None,
            f'Requiere tipificacion humana: {motivo}.',
        )
        return False

    factor = aplicar_monto_con_reincidencia(multa, multa.infraccion)

    # Las primeras faltas de la unidad se avisan sin cobrar. El monto calculado
    # arriba se conserva en monto_sin_cortesia: sirve para decirle al residente
    # cuanto se le habria cobrado, que es lo que le da sentido al aviso.
    es_cortesia, motivo_cortesia = corresponde_cortesia(multa)
    if es_cortesia:
        multa.monto_sin_cortesia = multa.monto
        multa.monto = Decimal('0.00')
    multa.save()

    try:
        notificar_multa(multa, usuario=None)
    except Exception as exc:
        registrar_historial(
            multa, multa.estado, multa.estado, None,
            f'No se pudo notificar automaticamente: {exc}. Queda para revision.',
        )
        return False

    sellar_acto(multa, TipoActo.CURSE_AUTOMATICO, None, auth_metodo='sistema', extra={
        'monto_aplicado': str(multa.monto),
        'es_cortesia': es_cortesia,
        'motivo_cortesia': motivo_cortesia,
        'monto_sin_cortesia': str(multa.monto_sin_cortesia) if es_cortesia else None,
        'factor_reincidencia_aplicado': str(factor),
        'confianza_propuesta': confianza or 0,
        'origen_propuesta': multa.propuesta_origen,
        'agravante_sugerido': multa.agravante_sugerido,
        'multa_primera_sancion_id': multa.multa_primera_sancion_id,
    })
    if es_cortesia:
        registrar_historial(multa, multa.estado, multa.estado, None, motivo_cortesia)
    return True


def reevaluar_con_evidencia(ticket, usuario=None):
    """
    Analiza la evidencia recien subida y, si el expediente todavia no se curso,
    lo vuelve a evaluar con lo que se ve en ella.

    Hace falta por un problema de orden: el reporte se ingresa primero y las
    fotos llegan por otra llamada, segundos despues. Sin esto, una foto que
    prueba el hecho llegaba tarde para influir en la clasificacion y solo
    servia cuando una persona abria el caso.

    Si el expediente ya se notifico no se reabre —no se puede cambiar una
    sancion ya comunicada— pero el analisis igual queda guardado para quien
    tenga que resolver despues.
    """
    from .models import EstadoMulta, Multa
    from .vision import analizar_evidencias

    descripcion, piezas = analizar_evidencias(ticket)
    if not descripcion:
        return False

    ticket.analisis_evidencia = descripcion
    ticket.save(update_fields=['analisis_evidencia'])

    multa = Multa.objects.filter(ticket=ticket).first()
    if multa is None or multa.estado != EstadoMulta.EN_REVISION:
        return False

    # Con la evidencia a la vista el encuadre puede cambiar, y con el la
    # confianza: lo que antes no alcanzaba el umbral ahora puede alcanzarlo.
    sugerida, origen, confianza, fundamento = proponer_infraccion(ticket)
    multa.infraccion = sugerida
    multa.monto = sugerida.monto if sugerida else None
    multa.propuesta_origen = origen
    multa.propuesta_confianza = confianza
    multa.propuesta_fundamento = fundamento
    multa.save(update_fields=[
        'infraccion', 'monto', 'propuesta_origen', 'propuesta_confianza', 'propuesta_fundamento',
    ])

    registrar_historial(
        multa, multa.estado, multa.estado, usuario,
        f'Se analizo la evidencia adjunta ({piezas} pieza[s]) y se reevaluo el encuadre.',
    )
    return cursar_multa_automatica(multa, confianza)


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
    EstadoMulta.EN_REVISION: 'Ya fue reportado y esta pendiente de tipificacion.',
    EstadoMulta.APROBADA: 'Ya fue reportado y esta por notificarse.',
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
    """
    Despacha la notificacion por todos los puntos de contacto y deja el
    expediente NOTIFICADA.

    Ojo con lo que este paso NO hace: no arranca el plazo de apelacion. Haber
    enviado no es haber notificado. El plazo empieza cuando hay acuse de
    recibo (ver registrar_acuse) o cuando se deja constancia en el buzon de la
    unidad. Mientras tanto la multa no puede quedar firme sola, que es
    exactamente la proteccion que necesita alguien que no revisa su correo.
    """
    estado_anterior = multa.estado
    pdf_bytes = generar_pdf_notificacion(multa)

    multa.plazo_descargo_dias = multa.plazo_descargo_dias or multa.condominio.plazo_descargo_dias

    # Primero se despacha y despues se marca NOTIFICADA. Al reves, un envio que
    # falla por completo dejaba el expediente como notificado sin que saliera
    # un solo mensaje: alguien sancionado sin enterarse jamas.
    enviados, copias = despachar_notificacion(multa, pdf_bytes, intento=1)
    if enviados == 0:
        raise ValueError('No se pudo despachar la notificacion por ningun canal.')

    multa.pdf_notificacion.save(f'notificacion_multa_{multa.id}.pdf', ContentFile(pdf_bytes), save=False)
    multa.estado = EstadoMulta.NOTIFICADA
    multa.notificada_por = usuario
    multa.fecha_notificacion = timezone.now()
    multa.save()

    canales = list(multa.entregas.filter(intento=1).values_list('canal', 'destino', 'estado'))
    registrar_historial(
        multa, estado_anterior, multa.estado, usuario,
        'Notificacion despachada. El plazo de apelacion arranca al acusarse recibo.',
    )
    sellar_acto(multa, TipoActo.NOTIFICACION, usuario, extra={
        'correo_destino': multa.persona_infractor.correo_electronico,
        # Quien recibio copia queda sellado: si mañana se discute si el
        # copropietario fue notificado, el acta lo prueba.
        'copias_copropietario': sorted(copias),
        # Cada canal con su destino y resultado: si manana se discute si se
        # notifico, el acta muestra por donde se intento y como resulto.
        'entregas': sorted(f'{canal}:{destino}:{estado}' for canal, destino, estado in canales),
        'plazo_descargo_dias': multa.plazo_descargo_dias,
        'pdf_notificacion': multa.pdf_notificacion.name,
    })
    return multa


def motivo_para_confirmar(multa):
    """
    Devuelve por que este expediente no deberia cobrarse sin que alguien lo
    mire, o cadena vacia si puede quedar firme solo.

    No se revisan todas las multas sin apelar: eso devolveria al comite al
    papel de cuello de botella. Se detienen unicamente aquellas donde hay una
    señal concreta de que la persona pudo no haber podido defenderse.
    """
    from condominios.models import CondicionEspecial
    from .models import CanalNotificacion

    persona = multa.persona_infractor
    if persona and persona.condicion_especial:
        etiqueta = CondicionEspecial(persona.condicion_especial).label
        return f'{persona.nombre_completo} figura en el registro como: {etiqueta.lower()}.'

    # Que la notificacion se haya perfeccionado dejando un papel en el buzon
    # significa que nunca hubo confirmacion de la propia persona: pudo estar
    # de viaje, hospitalizada, o simplemente no verlo.
    if multa.canal_acuse == CanalNotificacion.BUZON:
        return (
            'La notificacion nunca fue confirmada por el residente: se perfecciono '
            'dejando la constancia en el buzon de la unidad.'
        )
    return ''


def actualizar_multas_vencidas(condominio=None):
    """
    Cierra las multas notificadas cuyo plazo vencio sin apelacion.

    La mayoria queda FIRME sola, sin que nadie intervenga. Las que traen una
    señal de indefension (ver motivo_para_confirmar) quedan POR_CONFIRMAR: no
    se estudian de nuevo, solo esperan que alguien confirme antes del cobro.

    Se ejecuta de forma perezosa (al listar) para no depender de un scheduler
    externo tipo Celery.
    """
    from .models import Multa

    qs = Multa.objects.filter(estado=EstadoMulta.NOTIFICADA, fecha_limite_descargo__lt=timezone.now())
    if condominio is not None:
        qs = qs.filter(condominio=condominio)

    for multa in qs:
        motivo = motivo_para_confirmar(multa)
        if multa.es_aviso_de_cortesia:
            # Un aviso sin cobro no necesita confirmarse antes de cobrar: no
            # hay nada que cobrar. Cierra como cortesia y queda en el registro.
            destino = EstadoMulta.CORTESIA
        elif motivo:
            destino = EstadoMulta.POR_CONFIRMAR
        else:
            destino = EstadoMulta.FIRME

        multa.estado = destino
        if destino == EstadoMulta.FIRME:
            multa.fecha_firme = timezone.now()
        multa.save(update_fields=['estado', 'fecha_firme'])

        if destino == EstadoMulta.CORTESIA:
            comentario = (
                'Cerrado como aviso de cortesia: vencio el plazo sin objecion y no hay cobro.'
            )
        elif motivo:
            comentario = f'Vencio el plazo sin apelacion, pero el cobro se detiene para confirmacion. {motivo}'
        else:
            comentario = 'Firme automaticamente: vencio el plazo de descargo sin presentacion.'
        registrar_historial(multa, EstadoMulta.NOTIFICADA, destino, None, comentario)
        sellar_acto(multa, TipoActo.FIRMEZA_AUTOMATICA, None, auth_metodo='sistema', extra={
            'fecha_limite_vencida': multa.fecha_limite_descargo.isoformat(),
            'estado_resultante': destino,
            'motivo_confirmacion': motivo,
        })


def confirmar_antes_del_cobro(multa, usuario, dar_cortesia=False, comentario=''):
    """
    Resuelve un expediente detenido antes del cobro. Solo dos salidas: confirmar
    que se cobra, o convertirlo en parte de cortesia.

    Es a proposito una confirmacion y no una revision de fondo: el caso ya
    quedo sin apelacion en plazo. Lo unico que se pregunta es si corresponde
    cobrarle a alguien que quiza nunca pudo defenderse.
    """
    from .models import EstadoMulta, TipoActo

    estado_anterior = multa.estado
    monto_condonado = multa.monto

    if dar_cortesia:
        multa.monto = Decimal('0.00')
        multa.estado = EstadoMulta.CORTESIA
        detalle = (
            f'Confirmado como parte de cortesia por la condicion del residente: la falta '
            f'queda en el registro y se condonan {monto_condonado}.'
        )
    else:
        multa.estado = EstadoMulta.FIRME
        detalle = 'Confirmado el cobro pese a la alerta: el expediente queda firme.'

    multa.fecha_firme = timezone.now()
    multa.save(update_fields=['estado', 'monto', 'fecha_firme'])

    registrar_historial(multa, estado_anterior, multa.estado, usuario, f'{detalle} {comentario}'.strip())
    sellar_acto(multa, TipoActo.CONFIRMACION_PREVIA_COBRO, usuario, extra={
        'dio_cortesia': dar_cortesia,
        'monto_condonado': str(monto_condonado) if dar_cortesia else None,
        'motivo_de_la_alerta': motivo_para_confirmar(multa),
        'comentario': comentario,
    })
    return multa


def proponer_resoluciones(multa):
    """
    Sugiere al Comite como podria resolver la apelacion, con el fundamento de
    cada opcion.

    Propone, no decide: son opciones ordenadas con su razon a la vista, para
    que el Comite resuelva sabiendo que hay detras y no tenga que reconstruir
    a mano el historial de la unidad. Quien firma sigue siendo el Comite.
    """
    from .models import EstadoMulta, Multa, ResolucionDescargo

    opciones = []
    if multa.infraccion is None or multa.unidad is None:
        return opciones

    antecedentes = (
        Multa.objects
        .filter(unidad=multa.unidad, infraccion=multa.infraccion)
        .exclude(id=multa.id)
        .exclude(estado__in=[EstadoMulta.RECHAZADA, EstadoMulta.ANULADA, EstadoMulta.EN_REVISION])
        .count()
    )

    if antecedentes == 0:
        opciones.append({
            'resolucion': ResolucionDescargo.CORTESIA,
            'etiqueta': 'Parte de cortesia (sin cobro)',
            'fundamento': (
                f'Es la primera vez que esta unidad incurre en "{multa.infraccion.codigo}". '
                'La falta queda acreditada y en el registro, pero no se cobra. Una nueva '
                'falta igual ya no admitira cortesia.'
            ),
        })
        opciones.append({
            'resolucion': ResolucionDescargo.DESCUENTO,
            'porcentaje_descuento': 50,
            'etiqueta': 'Rebajar el monto a la mitad',
            'fundamento': 'Sin antecedentes previos por esta infraccion, una rebaja es proporcional.',
        })
    else:
        opciones.append({
            'resolucion': ResolucionDescargo.RECHAZADO,
            'etiqueta': 'Mantener la multa',
            'fundamento': (
                f'La unidad ya registra {antecedentes} caso(s) por "{multa.infraccion.codigo}". '
                'No corresponde cortesia sobre una falta reiterada.'
            ),
        })
        opciones.append({
            'resolucion': ResolucionDescargo.DESCUENTO,
            'porcentaje_descuento': 30,
            'etiqueta': 'Rebajar el monto un 30%',
            'fundamento': 'Si los descargos aportan algo atendible, una rebaja menor deja el precedente.',
        })

    opciones.append({
        'resolucion': ResolucionDescargo.ACEPTADO,
        'etiqueta': 'Anular la multa',
        'fundamento': 'Si los descargos desvirtuan el hecho, la falta se cae completa.',
    })
    return opciones


def convocar_reunion(descargo, usuario, modalidad, fecha, lugar_o_enlace):
    """
    Cita al residente a exponer su caso, en linea o presencialmente.

    Convocar extiende el plazo que tiene el Comite para resolver hasta despues
    de la reunion: de otro modo, citar a alguien cerca del vencimiento seria
    imposible, o quedaria contado como incumplimiento del propio organo que
    esta tratando de escuchar mejor.
    """
    from .models import EstadoReunion, ReunionApelacion, TipoActo

    reunion = ReunionApelacion.objects.create(
        descargo=descargo, modalidad=modalidad, fecha_propuesta=fecha,
        lugar_o_enlace=lugar_o_enlace, convocada_por=usuario,
        estado=EstadoReunion.PROPUESTA,
    )

    margen = fecha + timedelta(days=descargo.multa.condominio.plazo_resolucion_dias)
    if descargo.fecha_limite_resolucion is None or descargo.fecha_limite_resolucion < margen:
        descargo.fecha_limite_resolucion = margen
        descargo.save(update_fields=['fecha_limite_resolucion'])

    multa = descargo.multa
    registrar_historial(
        multa, multa.estado, multa.estado, usuario,
        f'Se cito al residente a una reunion {modalidad.lower()} el '
        f'{fecha:%d-%m-%Y a las %H:%M}.',
    )
    sellar_acto(multa, TipoActo.REUNION_CONVOCADA, usuario, extra={
        'modalidad': modalidad,
        'fecha_propuesta': fecha.isoformat(),
        'lugar_o_enlace': lugar_o_enlace,
        'nueva_fecha_limite_resolucion': descargo.fecha_limite_resolucion.isoformat(),
    })
    return reunion


def registrar_acta_reunion(reunion, usuario, acta, antecedentes=()):
    """
    Cierra la reunion dejando por escrito lo que se expuso.

    Lo que el residente aporte ahi entra al expediente como antecedente de
    origen REUNION: una explicacion dada de viva voz que no queda escrita es,
    para efectos del expediente, una explicacion que no existio.
    """
    from .models import AntecedenteDescargo, EstadoReunion, OrigenAntecedente, TipoActo

    reunion.estado = EstadoReunion.REALIZADA
    reunion.acta = acta
    reunion.save(update_fields=['estado', 'acta'])

    for texto in antecedentes:
        if texto and texto.strip():
            AntecedenteDescargo.objects.create(
                descargo=reunion.descargo, texto=texto.strip(),
                origen=OrigenAntecedente.REUNION, aportado_por=usuario,
            )

    multa = reunion.descargo.multa
    registrar_historial(
        multa, multa.estado, multa.estado, usuario,
        f'Reunion {reunion.modalidad.lower()} realizada y acta registrada.',
    )
    sellar_acto(multa, TipoActo.REUNION_REALIZADA, usuario, extra={
        'modalidad': reunion.modalidad,
        'acta': acta,
        'antecedentes_sumados': len([a for a in antecedentes if a and a.strip()]),
    })
    return reunion


def registrar_voto_resolucion(descargo, usuario, resolucion, porcentaje_descuento=None, comentario=''):
    """
    Registra el voto de un miembro del Comite y devuelve (voto, alcanzo_quorum).

    Solo cuentan como acuerdo los votos por la MISMA salida: tres personas que
    votan cosas distintas no resolvieron nada. Un mismo actor no vota dos veces.
    """
    from .models import TipoActo, VotoResolucion

    voto, creado = VotoResolucion.objects.get_or_create(
        descargo=descargo, actor=usuario,
        defaults={
            'resolucion': resolucion,
            'porcentaje_descuento': porcentaje_descuento,
            'comentario': comentario,
        },
    )
    if not creado:
        return voto, False

    quorum = descargo.multa.condominio.quorum_resolucion_apelacion
    coincidentes = descargo.votos.filter(
        resolucion=resolucion, porcentaje_descuento=porcentaje_descuento,
    ).count()

    multa = descargo.multa
    sellar_acto(multa, TipoActo.VOTO_RESOLUCION, usuario, extra={
        'resolucion': resolucion,
        'porcentaje_descuento': porcentaje_descuento,
        'votos_coincidentes': coincidentes,
        'quorum_requerido': quorum,
    })
    return voto, coincidentes >= quorum


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
    elif resolucion == ResolucionDescargo.CORTESIA:
        # La falta se dio por acreditada pero no se cobra. Se conserva el monto
        # original en el descargo: sin ese dato no se podria explicar despues
        # de cuanto fue la cortesia que se otorgo.
        descargo.monto_original = multa.monto
        monto_final = Decimal('0.00')
        multa.monto = monto_final
        multa.estado = EstadoMulta.CORTESIA
        multa.fecha_firme = timezone.now()
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
        # Mantener un aviso de cortesia no lo convierte en cobro: sigue sin monto.
        multa.estado = EstadoMulta.CORTESIA if multa.es_aviso_de_cortesia else EstadoMulta.FIRME
        multa.fecha_firme = timezone.now()

    descargo.save()
    multa.save()

    detalle = f'Descargo resuelto: {resolucion}.'
    if resolucion == ResolucionDescargo.DESCUENTO:
        detalle = f'Descargo resuelto: DESCUENTO {porcentaje_descuento}% (monto {descargo.monto_original} -> {monto_final}).'
    elif resolucion == ResolucionDescargo.CORTESIA:
        detalle = (
            f'Descargo resuelto: PARTE DE CORTESIA. La falta queda acreditada y en el '
            f'registro, sin cobro (se condonaron {descargo.monto_original}). '
            f'Una nueva falta igual ya no admite cortesia.'
        )
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
