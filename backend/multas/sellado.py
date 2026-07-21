"""
Sellado criptografico de actos de decision (V2).

Principios de diseño acordados:
- El manifiesto EMBEBE el contenido normativo mostrado (texto, articulo,
  monto), no lo referencia: el catalogo es mutable y un FK no prueba que
  version vio el decisor.
- La lista de evidencias del manifiesto es cerrada: lo que se suba despues
  queda en el expediente pero FUERA del sello, y su ausencia del manifiesto
  es prueba positiva de que no existia al decidir.
- Toda transicion del verificador es de deteccion, no de prevencion: la
  prevencion a nivel de fila la dan los triggers de base de datos y, en
  produccion, un usuario de conexion sin UPDATE/DELETE sobre la tabla.
- Sin backfill de garantias: expedientes sin actas son legacy V1.
"""

import hashlib
import json

from django.db import transaction
from django.utils import timezone

from .models import ActaSellada, Multa


# ---------------------------------------------------------------------------
# Canonicalizacion y hashes
# ---------------------------------------------------------------------------

def canonico(datos):
    """JSON canonico: claves ordenadas, sin espacios, ASCII escapado.

    Solo tipos deterministas (str/int/bool/None/list/dict). Los montos van
    como string y las fechas como ISO-8601, nunca como float.
    """
    return json.dumps(datos, sort_keys=True, ensure_ascii=True, separators=(',', ':'))


def sha256_texto(texto):
    return hashlib.sha256(texto.encode('utf-8')).hexdigest()


def sha256_archivo(archivo):
    """Hash de contenido de un archivo subido o abierto, por chunks."""
    h = hashlib.sha256()
    for chunk in archivo.chunks() if hasattr(archivo, 'chunks') else iter(lambda: archivo.read(65536), b''):
        h.update(chunk)
    if hasattr(archivo, 'seek'):
        archivo.seek(0)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Ingesta de evidencia: hash + metadatos de origen (EXIF)
# ---------------------------------------------------------------------------

TAG_DATETIME_ORIGINAL = 36867
TAG_GPS = 34853


def procesar_evidencia(archivo):
    """Devuelve (sha256, metadatos_origen, anclaje_fisico) para un upload.

    anclaje_fisico = la imagen trae fecha de captura Y datos GPS en su EXIF.
    La falta de anclaje se marca, no se rechaza (politica configurable por
    vertical; en condominios las fotos reenviadas rara vez conservan EXIF).
    """
    digest = sha256_archivo(archivo)

    metadatos = {}
    tiene_gps = False
    fecha_captura = None
    try:
        from PIL import Image

        with Image.open(archivo) as img:
            exif = img.getexif()
            if exif:
                fecha_captura = exif.get(TAG_DATETIME_ORIGINAL) or exif.get(306)  # 306 = DateTime
                gps = exif.get_ifd(TAG_GPS) if hasattr(exif, 'get_ifd') else None
                tiene_gps = bool(gps)
        archivo.seek(0)
    except Exception:
        # Un EXIF corrupto no invalida la evidencia; solo queda sin anclaje.
        pass

    metadatos = {
        'fecha_captura_exif': str(fecha_captura) if fecha_captura else None,
        'tiene_gps': tiene_gps,
    }
    return digest, metadatos, bool(fecha_captura and tiene_gps)


# ---------------------------------------------------------------------------
# Construccion del manifiesto y sellado
# ---------------------------------------------------------------------------

def _manifiesto_evidencias(multa):
    return [
        {
            'id': ev.id,
            'sha256': ev.sha256 or None,  # None = ingresada antes de la epoca de sellado
            'archivo': ev.imagen.name,
            'subida_en': ev.subida_en.isoformat(),
            'anclaje_fisico': ev.anclaje_fisico,
            'metadatos_origen': ev.metadatos_origen or {},
        }
        for ev in multa.ticket.evidencias.all().order_by('id')
    ]


def _manifiesto_norma(multa):
    if not multa.infraccion_id:
        return None
    inf = multa.infraccion
    return {
        'codigo': inf.codigo,
        'descripcion': inf.descripcion,
        'articulo_referencia': inf.articulo_referencia,
        'monto_base': str(inf.monto),
        'unidad_monto': inf.unidad_monto,
        'gravedad': inf.gravedad,
        'texto_fuente': inf.texto_fuente,
    }


def construir_manifiesto(multa, tipo_acto, actor, ts, auth_metodo, extra=None):
    ticket = multa.ticket
    return {
        'version_sellado': 2,
        'tipo_manifiesto': 'SANCION',
        'acto': tipo_acto,
        'ts': ts.isoformat(),
        'actor': (
            {
                'id': actor.id,
                'username': actor.username,
                'rol': actor.rol,
            }
            if actor
            else None
        ),
        'auth_metodo': auth_metodo,
        'expediente': {
            'multa_id': multa.id,
            'estado': multa.estado,
            'monto': str(multa.monto) if multa.monto is not None else None,
            'es_reincidencia': multa.es_reincidencia,
            'condominio_id': multa.condominio_id,
            'unidad': multa.unidad.identificador,
            'persona_infractor': (
                {
                    'id': multa.persona_infractor.id,
                    'nombre': multa.persona_infractor.nombre_completo,
                    'cedula': multa.persona_infractor.cedula_identidad,
                }
                if multa.persona_infractor_id
                else None
            ),
        },
        'reporte': {
            'ticket_id': ticket.id,
            'descripcion': ticket.descripcion,
            'ubicacion': ticket.ubicacion,
            'fecha_hecho': ticket.fecha_hecho.isoformat(),
            'reportado_por': ticket.creado_por.username if ticket.creado_por_id else None,
        },
        'evidencias_visibles': _manifiesto_evidencias(multa),
        'norma_aplicada': _manifiesto_norma(multa),
        'extra': extra or {},
    }


def _sellar(multa, tipo_acto, actor, auth_metodo, construir):
    """
    Nucleo del sellado con candado pesimista sobre la fila del expediente.

    Flujo: inicia transaccion -> SELECT ... FOR UPDATE sobre la Multa ->
    lee hash_previo -> construye el manifiesto (leyendo el estado YA
    comprometido bajo el candado) -> inserta el acta -> libera. Si dos
    actores (ej. el gerente ratificando y el job escalando) chocan, el motor
    los encola: el segundo ve la realidad que dejo el primero.
    """
    with transaction.atomic():
        multa_bloqueada = Multa.objects.select_for_update().get(pk=multa.pk)

        previa = (
            ActaSellada.objects.filter(multa=multa_bloqueada).order_by('-indice').first()
        )
        hash_previo = previa.hash_acto if previa else ActaSellada.GENESIS
        indice = (previa.indice + 1) if previa else 1

        ts = timezone.now()
        manifiesto = construir(multa_bloqueada, ts)
        m_sha = sha256_texto(canonico(manifiesto))
        hash_acto = sha256_texto(hash_previo + m_sha)

        return ActaSellada.objects.create(
            multa=multa_bloqueada,
            indice=indice,
            tipo_acto=tipo_acto,
            actor=actor,
            auth_metodo=auth_metodo,
            ts=ts,
            manifiesto=manifiesto,
            manifiesto_sha256=m_sha,
            hash_previo=hash_previo,
            hash_acto=hash_acto,
        )


def sellar_acto(multa, tipo_acto, actor, extra=None, auth_metodo='jwt_password_session'):
    """Acta sellada de un acto del carril sancionatorio (manifiesto SANCION)."""
    return _sellar(
        multa, tipo_acto, actor, auth_metodo,
        lambda m, ts: construir_manifiesto(m, tipo_acto, actor, ts, auth_metodo, extra),
    )


def construir_manifiesto_contencion(medida, multa, tipo_acto, actor, ts, auth_metodo, extra=None):
    """Manifiesto polimorfico del carril de contencion (tipo CONTENCION).

    Claves obligatorias del contrato: criticidad, plazo_ratificacion_horas y
    estado_contencion. La criticidad EMBEBE el hallazgo del catalogo (que es
    mutable) igual que el manifiesto sancionatorio embebe la norma.
    """
    hallazgo = medida.hallazgo
    return {
        'version_sellado': 2,
        'tipo_manifiesto': 'CONTENCION',
        'acto': tipo_acto,
        'ts': ts.isoformat(),
        'actor': (
            {'id': actor.id, 'username': actor.username, 'rol': actor.rol} if actor else None
        ),
        'auth_metodo': auth_metodo,
        'expediente': {
            'multa_id': multa.id,
            'estado': multa.estado,
            'condominio_id': multa.condominio_id,
            'unidad': multa.unidad.identificador,
        },
        'medida': {
            'id': medida.id,
            'ejecutada_en': medida.ejecutada_en.isoformat(),
            'ejecutada_por': medida.ejecutada_por.username if medida.ejecutada_por_id else None,
            'nivel_escalamiento': medida.nivel_escalamiento,
            'proxima_revision': medida.proxima_revision.isoformat(),
            'descripcion': medida.descripcion,
        },
        'criticidad': {
            'codigo': hallazgo.codigo,
            'descripcion': hallazgo.descripcion,
            'gravedad': hallazgo.gravedad,
            'articulo_referencia': hallazgo.articulo_referencia,
            'conlleva_contencion': hallazgo.conlleva_contencion,
            'texto_fuente': hallazgo.texto_fuente,
        },
        'plazo_ratificacion_horas': medida.plazo_ratificacion_horas,
        'estado_contencion': medida.estado,
        'evidencias_citadas': [
            {
                'id': ev.id,
                'sha256': ev.sha256 or None,
                'archivo': ev.imagen.name,
                'subida_en': ev.subida_en.isoformat(),
                'anclaje_fisico': ev.anclaje_fisico,
            }
            for ev in medida.evidencias.all().order_by('id')
        ],
        'extra': extra or {},
    }


def sellar_acto_contencion(medida, tipo_acto, actor, extra=None, auth_metodo='jwt_password_session'):
    """Acta sellada de un acto del carril de contencion, en la MISMA cadena del expediente."""
    def construir(multa_bloqueada, ts):
        medida.refresh_from_db()  # sella el estado real bajo el candado
        return construir_manifiesto_contencion(
            medida, multa_bloqueada, tipo_acto, actor, ts, auth_metodo, extra,
        )

    return _sellar(medida.multa, tipo_acto, actor, auth_metodo, construir)


# ---------------------------------------------------------------------------
# Verificador de integridad
# ---------------------------------------------------------------------------

_ORDEN_GRAVEDAD = {'LEVE': 0, 'GRAVE': 1, 'GRAVISIMA': 2}


def _auditar_autoridad_voto(manifiesto):
    """
    Auditoria aritmetica de un voto por delegacion, desde el manifiesto sellado.

    Devuelve (ok, detalle). detalle=None cuando el acta no es un voto delegado
    (no aplica auditoria de autoridad). Cuando aplica, comprueba SOLO contra el
    contenido sellado: ventana temporal, alcance de accion y techo de gravedad.
    """
    if manifiesto.get('acto') != 'VOTO_RATIFICACION':
        return True, None
    extra = manifiesto.get('extra') or {}
    if extra.get('en_calidad_de') != 'DELEGADO':
        return True, None

    aut = extra.get('autoridad') or {}
    quorum = extra.get('quorum') or {}
    ts = manifiesto.get('ts', '')
    desde = aut.get('vigencia_desde', '')
    hasta = aut.get('vigencia_hasta', '')
    gravedad = quorum.get('gravedad_hallazgo', '')

    # Comparacion de instantes por ISO-8601 lexicografico (mismo offset Z): el
    # ts sellado debe caer dentro de la ventana sellada — "ese milisegundo".
    ventana_ok = bool(desde) and bool(hasta) and (desde <= ts <= hasta)
    accion_ok = 'RATIFICAR_CONTENCION' in (aut.get('acciones') or [])
    techo_ok = _ORDEN_GRAVEDAD.get(gravedad, 99) <= _ORDEN_GRAVEDAD.get(aut.get('tope_gravedad'), -1)

    ok = ventana_ok and accion_ok and techo_ok
    detalle = {
        'delegacion_id': aut.get('delegacion_id'),
        'delegante': (aut.get('delegante') or {}).get('username'),
        'ventana_cubre_ts': ventana_ok,
        'accion_cubierta': accion_ok,
        'techo_gravedad_ok': techo_ok,
    }
    return ok, detalle


def verificar_expediente(multa):
    """Recalcula toda la cadena y los hashes de archivos de evidencia.

    Devuelve un informe apto para mostrar a un auditor. Un expediente sin
    actas es legacy V1: no se le afirma ni niega integridad criptografica.
    """
    actas = list(multa.actas_selladas.order_by('indice'))

    if not actas:
        return {
            'multa_id': multa.id,
            'version': 1,
            'sellado': False,
            'integra': None,
            'detalle': 'Expediente sin actos de decision sellados: anterior a la epoca de sellado (legacy V1) o aun sin decisiones.',
            'actas': [],
            'evidencias': [],
        }

    resultados_actas = []
    hash_esperado_previo = ActaSellada.GENESIS
    cadena_integra = True

    for acta in actas:
        m_sha_recalculado = sha256_texto(canonico(acta.manifiesto))
        hash_recalculado = sha256_texto(acta.hash_previo + m_sha_recalculado)

        manifiesto_ok = m_sha_recalculado == acta.manifiesto_sha256
        eslabon_ok = acta.hash_previo == hash_esperado_previo
        hash_ok = hash_recalculado == acta.hash_acto

        # Auditoria de autoridad: si el acta es un voto por delegacion, la
        # ventana embebida debe cubrir el ts sellado, cubrir la accion y el
        # techo de gravedad. 100% aritmetico y offline: no se consulta el
        # estado vivo de la delegacion, solo el snapshot congelado en el sello.
        autoridad_ok, autoridad_detalle = _auditar_autoridad_voto(acta.manifiesto)

        acta_ok = manifiesto_ok and eslabon_ok and hash_ok and autoridad_ok
        cadena_integra = cadena_integra and acta_ok

        fila = {
            'indice': acta.indice,
            'tipo_acto': acta.tipo_acto,
            'ts': acta.ts.isoformat(),
            'actor': acta.actor.username if acta.actor_id else 'sistema',
            'manifiesto_integro': manifiesto_ok,
            'eslabon_integro': eslabon_ok,
            'hash_integro': hash_ok,
            'integra': acta_ok,
        }
        if autoridad_detalle is not None:
            fila['autoridad_integra'] = autoridad_ok
            fila['autoridad_detalle'] = autoridad_detalle
        resultados_actas.append(fila)
        hash_esperado_previo = acta.hash_acto

    resultados_evidencias = []
    evidencias_integras = True
    for ev in multa.ticket.evidencias.all().order_by('id'):
        if not ev.sha256:
            resultados_evidencias.append({
                'id': ev.id, 'archivo': ev.imagen.name, 'integra': None,
                'detalle': 'Sin hash de ingesta (anterior a la epoca de sellado).',
            })
            continue
        try:
            with ev.imagen.open('rb') as f:
                digest_actual = sha256_archivo(f)
            ok = digest_actual == ev.sha256
        except Exception:
            ok = False
        evidencias_integras = evidencias_integras and ok
        resultados_evidencias.append({'id': ev.id, 'archivo': ev.imagen.name, 'integra': ok})

    return {
        'multa_id': multa.id,
        'version': 2,
        'sellado': True,
        'integra': cadena_integra and evidencias_integras,
        'total_actas': len(actas),
        'actas': resultados_actas,
        'evidencias': resultados_evidencias,
    }
