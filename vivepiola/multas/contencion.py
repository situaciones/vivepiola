"""
Carril de contencion (MedidaInmediata) — logica de negocio.

Invariantes no negociables:
- FAIL-CLOSED: ninguna funcion de este modulo transiciona a LEVANTADA salvo
  levantar_contencion(), que exige actor humano, causal y fundamento.
- La omision escala y queda sellada como acto atribuible; jamas libera.
- Toda mutacion de la medida se hace bajo candado (select_for_update sobre
  la medida, y sobre el expediente al sellar): si el gerente y el job chocan,
  el segundo relee la realidad y se aborta a si mismo.
"""

from datetime import timedelta

from django.core.mail import send_mail
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from accounts.models import Rol, Usuario

from .models import (
    ESTADOS_MEDIDA_ACTIVOS, AccionDelegable, Delegacion, EnCalidadDe, EstadoDelegacion,
    EstadoMedida, MedidaInmediata, TipoActo, VotoRatificacion,
)
from .sellado import canonico, sellar_acto_contencion, sha256_texto


class TransicionInvalida(Exception):
    """La medida no admite la transicion pedida en su estado actual."""


class SinAutoridad(Exception):
    """El actor no tiene autoridad (por cargo ni por delegacion vigente) para el voto."""


# ---------------------------------------------------------------------------
# Delegacion (otorgamiento sellado por su hash de contenido)
# ---------------------------------------------------------------------------

def otorgar_delegacion(condominio, delegante, delegado, acciones, tope_gravedad,
                       vigencia_desde, vigencia_hasta, motivo=''):
    """
    Crea una delegacion tactica. Restricciones duras: vencimiento obligatorio,
    profundidad 1 (el delegado no puede a su vez delegar), y sin auto-delegacion.
    Nace con su hash de contenido, para que el snapshot embebido en cada voto
    sea cotejable por el verificador.
    """
    if vigencia_hasta <= vigencia_desde:
        raise TransicionInvalida('La vigencia de la delegacion debe tener fin posterior al inicio.')
    if delegante == delegado:
        raise TransicionInvalida('No se puede delegar en si mismo.')

    delegacion = Delegacion.objects.create(
        condominio=condominio, delegante=delegante, delegado=delegado,
        acciones=list(acciones), tope_gravedad=tope_gravedad,
        vigencia_desde=vigencia_desde, vigencia_hasta=vigencia_hasta, motivo=motivo,
    )
    contenido = canonico({
        'delegacion_id': delegacion.id, 'condominio': condominio.id,
        'delegante': delegante.id, 'delegado': delegado.id,
        'acciones': list(acciones), 'tope_gravedad': tope_gravedad,
        'vigencia_desde': vigencia_desde.isoformat(), 'vigencia_hasta': vigencia_hasta.isoformat(),
        'version': delegacion.version,
    })
    delegacion.otorgamiento_hash = sha256_texto(contenido)
    delegacion.save(update_fields=['otorgamiento_hash'])
    return delegacion


def revocar_delegacion(delegacion):
    delegacion.estado = EstadoDelegacion.REVOCADA
    delegacion.revocada_en = timezone.now()
    delegacion.save(update_fields=['estado', 'revocada_en'])
    return delegacion


def _resolver_autoridad(medida, actor, momento):
    """
    Devuelve (en_calidad_de, delegacion) para el voto de `actor` sobre `medida`
    en `momento`. Titular (COMITE del condominio) vota por cargo; si no, busca
    una delegacion VIGENTE que cubra RATIFICAR_CONTENCION con techo >= gravedad.
    Lanza SinAutoridad si nada lo respalda.
    """
    if actor.rol in (Rol.COMITE, Rol.SUPERADMIN) and actor.condominio_id == medida.multa.condominio_id:
        return EnCalidadDe.TITULAR, None

    gravedad = medida.hallazgo.gravedad
    delegaciones = Delegacion.objects.select_for_update().filter(
        condominio=medida.multa.condominio, delegado=actor, estado=EstadoDelegacion.VIGENTE,
    ).order_by('-creada_en')
    for d in delegaciones:
        if d.vigente_para(AccionDelegable.RATIFICAR_CONTENCION, gravedad, momento):
            return EnCalidadDe.DELEGADO, d
    raise SinAutoridad(
        'No tiene autoridad para ratificar: ni por cargo, ni por una delegacion vigente '
        'que cubra esta accion y gravedad en este momento.'
    )


def _cadena_activa(condominio):
    from condominios.models import CadenaEscalamiento

    return (
        CadenaEscalamiento.objects.filter(condominio=condominio, activa=True)
        .order_by('-version')
        .prefetch_related('niveles__usuarios')
        .first()
    )


def _destinatarios_segun_cadena(medida):
    """
    Resuelve a quien notificar segun la cadena versionada de la organizacion.

    Notificacion ACUMULATIVA: al ejecutarse (nivel 0) se notifica el nivel 1;
    cada omision N notifica los niveles 1..N+1, subiendo un peldano cada vez.
    Si el escalamiento supera el largo de la cadena, se notifica a toda la
    cadena y se marca tope_alcanzado (el acta lo deja escrito).
    Fallback sin cadena configurada: Comite + Administrador de la organizacion.
    """
    cadena = _cadena_activa(medida.multa.condominio)
    if cadena is None:
        usuarios = list(
            Usuario.objects.filter(
                condominio=medida.multa.condominio,
                rol__in=[Rol.COMITE, Rol.ADMINISTRADOR],
                is_active=True,
            )
        )
        tope = medida.nivel_escalamiento >= 1
        return usuarios, {'cadena_version': None, 'tope_alcanzado': tope}

    niveles = list(cadena.niveles.all())
    hasta = min(medida.nivel_escalamiento + 1, len(niveles))
    tope = (medida.nivel_escalamiento + 1) > len(niveles)

    usuarios, vistos = [], set()
    for nivel in niveles[:hasta]:
        for u in nivel.usuarios.all():
            if u.is_active and u.id not in vistos:
                vistos.add(u.id)
                usuarios.append(u)
    return usuarios, {
        'cadena_version': cadena.version,
        'nivel_notificado_hasta': hasta,
        'tope_alcanzado': tope,
    }


def _notificar_adjudicadores(medida, motivo):
    """
    Notifica segun la cadena de escalamiento (o el fallback) y devuelve el
    detalle para el acta: quien fue avisado, con que version de cadena y si
    se alcanzo el tope. El registro de la omision es la presion ejecutiva.
    """
    destinatarios, detalle_cadena = _destinatarios_segun_cadena(medida)

    asuntos = {
        'ejecutada': f'[CONTENCION ACTIVA] Medida inmediata #{medida.id} requiere ratificacion',
        'omision': f'[ESCALAMIENTO N{medida.nivel_escalamiento}] Medida #{medida.id} sin ratificar — la contencion SIGUE ACTIVA',
    }
    cuerpo = (
        f'Medida inmediata #{medida.id} sobre la unidad {medida.multa.unidad.identificador} '
        f'(hallazgo {medida.hallazgo.codigo}: {medida.hallazgo.descripcion}).\n'
        f'Estado: {medida.get_estado_display()}.\n'
        f'Plazo de ratificacion: {medida.plazo_ratificacion_horas} horas. '
        f'Proxima revision: {medida.proxima_revision:%d-%m-%Y %H:%M}.\n\n'
        'La contencion permanece activa hasta que un facultado la ratifique o la levante '
        'con causal fundada. Esta notificacion queda registrada en el expediente sellado.'
    )
    correos = [u.email for u in destinatarios if u.email]
    if correos:
        try:
            send_mail(asuntos[motivo], cuerpo, settings.DEFAULT_FROM_EMAIL, correos, fail_silently=True)
        except Exception:
            pass

    return {
        'notificados': [u.username for u in destinatarios],
        **detalle_cadena,
    }


def ejecutar_contencion(multa, hallazgo, actor, evidencias=None, descripcion='',
                        auth_metodo='jwt_password_session'):
    """Crea la medida (contencion activa desde el segundo cero) y sella el acto."""
    ahora = timezone.now()
    medida = MedidaInmediata.objects.create(
        multa=multa,
        hallazgo=hallazgo,
        descripcion=descripcion,
        estado=EstadoMedida.EJECUTADA,
        ejecutada_por=actor,
        auth_metodo_ejecucion=auth_metodo,
        ejecutada_en=ahora,
        plazo_ratificacion_horas=hallazgo.plazo_ratificacion_horas,
        proxima_revision=ahora + timedelta(hours=hallazgo.plazo_ratificacion_horas),
        quorum_requerido=hallazgo.quorum_ratificacion or 1,
    )
    if evidencias:
        medida.evidencias.set(evidencias)

    detalle_notificacion = _notificar_adjudicadores(medida, 'ejecutada')
    sellar_acto_contencion(
        medida, TipoActo.CONTENCION_EJECUTADA, actor, auth_metodo=auth_metodo,
        extra=detalle_notificacion,
    )
    return medida


def ratificar_contencion(medida, actor, auth_metodo='jwt_password_session'):
    """
    Emite el voto de `actor` hacia el quorum de la medida. Si con este voto se
    alcanza el quorum requerido, sella ademas CONTENCION_RATIFICADA. Todo bajo
    el candado del expediente: si el job de escalamiento choca con el voto que
    completa el quorum, el motor los encola y el que llega segundo relee la
    realidad.

    Idempotencia: un mismo actor no incrementa el quorum dos veces (unique
    (medida, actor) + candado). Un segundo intento del mismo actor es no-op.
    """
    with transaction.atomic():
        m = MedidaInmediata.objects.select_for_update().get(pk=medida.pk)
        if m.estado not in (EstadoMedida.EJECUTADA, EstadoMedida.EN_ESCALAMIENTO):
            raise TransicionInvalida(
                f'No se puede ratificar una medida en estado {m.get_estado_display()}.'
            )

        momento = timezone.now()
        # Autoridad (bajo candado: una revocacion de delegacion no puede colarse
        # entre el chequeo y el sello).
        en_calidad, delegacion = _resolver_autoridad(m, actor, momento)

        # Idempotencia: si el actor ya voto, no cuenta de nuevo.
        if VotoRatificacion.objects.filter(medida=m, actor=actor).exists():
            medida.refresh_from_db()
            return medida

        try:
            VotoRatificacion.objects.create(
                medida=m, actor=actor, en_calidad_de=en_calidad, delegacion=delegacion, ts=momento,
            )
        except IntegrityError:
            # Carrera perdida contra otro voto del MISMO actor: idempotente.
            medida.refresh_from_db()
            return medida

        votos_actuales = VotoRatificacion.objects.filter(medida=m).count()

        # Con quorum=1 (ratificacion simple) el acto CONTENCION_RATIFICADA ES el
        # voto: no se sella un VOTO_RATIFICACION redundante. El ledger de votos
        # individuales solo tiene sentido cuando hay que reunir K firmas.
        if m.quorum_requerido > 1:
            extra_voto = {
                'en_calidad_de': en_calidad,
                'quorum': {
                    'requerido': m.quorum_requerido,
                    'voto_ordinal': votos_actuales,
                    'gravedad_hallazgo': m.hallazgo.gravedad,
                },
                'autoridad': delegacion.snapshot() if delegacion else None,
            }
            sellar_acto_contencion(
                m, TipoActo.VOTO_RATIFICACION, actor, auth_metodo=auth_metodo, extra=extra_voto,
            )

        # ¿Se completo el quorum con este voto?
        if votos_actuales >= m.quorum_requerido:
            tardia = m.estado == EstadoMedida.EN_ESCALAMIENTO
            m.estado = EstadoMedida.RATIFICADA
            m.ratificada_por = actor
            m.ratificada_en = momento
            m.save(update_fields=['estado', 'ratificada_por', 'ratificada_en'])
            sellar_acto_contencion(
                m, TipoActo.CONTENCION_RATIFICADA, actor, auth_metodo=auth_metodo,
                extra={
                    'ratificacion_tardia': tardia,
                    'nivel_escalamiento_al_ratificar': m.nivel_escalamiento,
                    'quorum_completado': f'{votos_actuales}/{m.quorum_requerido}',
                },
            )
    medida.refresh_from_db()
    return medida


def levantar_contencion(medida, actor, causal, fundamento, auth_metodo='jwt_password_session'):
    """
    UNICO camino a LEVANTADA. Exige causal (CORREGIDA/DESESTIMADA) y
    fundamento escrito: alguien firma con su nombre que el riesgo ya no
    existe o que nunca existio.
    """
    if not fundamento or not fundamento.strip():
        raise TransicionInvalida('Levantar una contencion exige fundamento escrito.')

    with transaction.atomic():
        m = MedidaInmediata.objects.select_for_update().get(pk=medida.pk)
        if m.estado not in ESTADOS_MEDIDA_ACTIVOS:
            raise TransicionInvalida(
                f'No se puede levantar una medida en estado {m.get_estado_display()}.'
            )
        m.estado = EstadoMedida.LEVANTADA
        m.levantada_por = actor
        m.levantada_en = timezone.now()
        m.causal_levantamiento = causal
        m.fundamento_levantamiento = fundamento
        m.save(update_fields=[
            'estado', 'levantada_por', 'levantada_en',
            'causal_levantamiento', 'fundamento_levantamiento',
        ])

        sellar_acto_contencion(
            m, TipoActo.CONTENCION_LEVANTADA, actor, auth_metodo=auth_metodo,
            extra={'causal': causal, 'fundamento': fundamento},
        )
    medida.refresh_from_db()
    return medida


def escalar_medidas_vencidas(condominio=None):
    """
    El job: barre medidas activas sin ratificar con revision vencida y sella
    la OMISION, subiendo el nivel de escalamiento. La contencion NUNCA se
    toca. Si al releer bajo candado otro actor ya resolvio (ratifico o
    levanto), el job se aborta a si mismo para esa medida.
    """
    ahora = timezone.now()
    candidatas = MedidaInmediata.objects.filter(
        estado__in=[EstadoMedida.EJECUTADA, EstadoMedida.EN_ESCALAMIENTO],
        proxima_revision__lt=ahora,
    )
    if condominio is not None:
        candidatas = candidatas.filter(multa__condominio=condominio)

    escaladas = 0
    for candidata in candidatas:
        with transaction.atomic():
            m = MedidaInmediata.objects.select_for_update().get(pk=candidata.pk)
            # Releer la realidad bajo candado: el gerente pudo ganar la carrera.
            if m.estado not in (EstadoMedida.EJECUTADA, EstadoMedida.EN_ESCALAMIENTO):
                continue
            if m.proxima_revision >= timezone.now():
                continue

            m.estado = EstadoMedida.EN_ESCALAMIENTO
            m.nivel_escalamiento += 1
            plazo_vencido = m.proxima_revision
            m.proxima_revision = timezone.now() + timedelta(hours=m.plazo_ratificacion_horas)
            m.save(update_fields=['estado', 'nivel_escalamiento', 'proxima_revision'])

            detalle_notificacion = _notificar_adjudicadores(m, 'omision')
            sellar_acto_contencion(
                m, TipoActo.ESCALAMIENTO_POR_OMISION, None, auth_metodo='sistema',
                extra={
                    'nivel': m.nivel_escalamiento,
                    'plazo_vencido': plazo_vencido.isoformat(),
                    **detalle_notificacion,
                },
            )
            escaladas += 1
    return escaladas
