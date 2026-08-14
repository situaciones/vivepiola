"""
El buzon del residente: su expediente, accesible SIN iniciar sesion.

Es deliberado que no pida cuenta. Quien mas necesita esta puerta es justamente
quien no tiene la app instalada ni recuerda una contraseña, y el derecho a
defenderse no puede depender de saber usar un software.

Aqui aterriza el residente venga de donde venga —del correo, del WhatsApp o de
la app— porque los tres canales llevan el mismo enlace firmado. Desde esta
pagina puede:

- ver de que se le acusa, con que norma y que evidencia;
- confirmar que recibio la notificacion (lo que hace correr el plazo);
- volver a descargar el PDF cuantas veces quiera;
- presentar su apelacion.

El enlace va firmado, asi que identifica el expediente sin exponer nada, y las
acciones son POST explicitos para que ningun escaner de correo que sigue
enlaces pueda dar por notificado o por apelado a alguien que no hizo nada.
"""

from django.http import HttpResponse
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import CanalNotificacion, Descargo, EstadoMulta, ResolucionDescargo, TipoActo
from .sellado import sellar_acto
from .services import multa_desde_token_acuse, registrar_acuse, registrar_historial

# Que puede hacer el residente en cada estado. Se envia al frontend para que la
# pagina no tenga que replicar las reglas del backend y arriesgar decir una cosa
# distinta de la que el servidor va a aceptar.
def _acciones(multa):
    return {
        'puede_acusar': multa.estado == EstadoMulta.NOTIFICADA and not multa.fecha_acuse,
        'puede_apelar': (
            multa.estado == EstadoMulta.NOTIFICADA
            and not hasattr(multa, 'descargo')
        ),
        'tiene_documento': bool(multa.pdf_notificacion),
    }


def _expediente(multa):
    """
    Lo que el residente tiene derecho a saber de su propio caso.

    No se expone quien reporto: el anonimato del denunciante es parte del
    diseño, y aqui es donde mas tentador seria filtrarlo.
    """
    infraccion = multa.infraccion
    descargo = getattr(multa, 'descargo', None)

    return {
        'multa_id': multa.id,
        'organizacion': multa.condominio.nombre,
        'unidad': multa.unidad.identificador if multa.unidad else '',
        'estado': multa.estado,
        'es_aviso_de_cortesia': multa.es_aviso_de_cortesia,
        'infraccion': infraccion.descripcion if infraccion else '',
        'articulo': infraccion.articulo_referencia if infraccion else '',
        'texto_norma': infraccion.texto_fuente if infraccion else '',
        'monto': str(multa.monto or ''),
        'monto_sin_cortesia': str(multa.monto_sin_cortesia) if multa.monto_sin_cortesia else '',
        'unidad_monto': infraccion.unidad_monto if infraccion else '',
        'hecho': multa.ticket.descripcion if multa.ticket_id else '',
        'fecha_hecho': multa.ticket.fecha_hecho if multa.ticket_id else None,
        'evidencias': [
            {'es_video': ev.es_video, 'descripcion': ev.descripcion}
            for ev in (multa.ticket.evidencias.all() if multa.ticket_id else [])
        ],
        'plazo_dias': multa.plazo_descargo_dias or multa.condominio.plazo_descargo_dias,
        'ya_acusada': bool(multa.fecha_acuse),
        'fecha_acuse': multa.fecha_acuse,
        'fecha_limite_descargo': multa.fecha_limite_descargo,
        'apelacion': {
            'texto': descargo.texto,
            'fecha': descargo.fecha_presentacion,
            'resolucion': descargo.resolucion,
            'comentario': descargo.comentario_resolucion,
        } if descargo else None,
        'acciones': _acciones(multa),
    }


class _VistaConToken(APIView):
    """Base de las vistas publicas: resuelven la multa desde el token firmado."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def _multa(self, token):
        return multa_desde_token_acuse(token)

    def _invalido(self):
        return Response({'detail': 'El enlace no es valido o ya vencio.'}, status=404)


class AcuseNotificacionView(_VistaConToken):
    """GET muestra el expediente completo; POST deja constancia de la recepcion."""

    def get(self, request, token):
        multa = self._multa(token)
        if multa is None:
            return self._invalido()
        return Response(_expediente(multa))

    def post(self, request, token):
        multa = self._multa(token)
        if multa is None:
            return self._invalido()

        registrar_acuse(
            multa, CanalNotificacion.EMAIL,
            destino=multa.persona_infractor.correo_electronico if multa.persona_infractor else '',
            detalle='Confirmado por el destinatario desde el enlace de la notificacion.',
        )
        multa.refresh_from_db()
        return Response(_expediente(multa))


class DocumentoNotificacionView(_VistaConToken):
    """
    Entrega el PDF de la notificacion, cuantas veces haga falta.

    Se sirve a traves del token y no como enlace directo al archivo: asi el
    documento sigue siendo privado tanto si el almacenamiento es local como si
    es un bucket, y el residente no depende de haber guardado el correo.
    """

    def get(self, request, token):
        multa = self._multa(token)
        if multa is None:
            return self._invalido()
        if not multa.pdf_notificacion:
            return Response({'detail': 'Este expediente todavia no tiene documento.'}, status=404)

        try:
            multa.pdf_notificacion.open('rb')
            contenido = multa.pdf_notificacion.read()
        finally:
            try:
                multa.pdf_notificacion.close()
            except Exception:
                pass

        respuesta = HttpResponse(contenido, content_type='application/pdf')
        respuesta['Content-Disposition'] = f'inline; filename="notificacion_{multa.id}.pdf"'
        return respuesta


class ApelarView(_VistaConToken):
    """
    Presenta la apelacion sin necesidad de cuenta.

    Apelar prueba que se entero, asi que si todavia no habia acusado recibo se
    registra el acuse en el mismo acto: seria absurdo rechazarle la defensa a
    quien la esta ejerciendo por no haber apretado antes otro boton.
    """

    def post(self, request, token):
        multa = self._multa(token)
        if multa is None:
            return self._invalido()

        texto = str(request.data.get('texto', '')).strip()
        if not texto:
            return Response({'detail': 'Escribe tu apelacion antes de enviarla.'}, status=400)

        # Se revisa primero si ya apelo: es la razon mas comun de que llegue
        # aqui de nuevo, y "ya no admite apelacion" no le explica nada a quien
        # solo quiere saber si su escrito entro.
        if hasattr(multa, 'descargo'):
            return Response({'detail': 'Ya presentaste una apelacion en este caso.'}, status=400)
        if multa.estado != EstadoMulta.NOTIFICADA:
            return Response(
                {'detail': 'Este expediente ya no admite apelacion.'}, status=400,
            )

        if not multa.fecha_acuse:
            registrar_acuse(
                multa, CanalNotificacion.EMAIL,
                detalle='El residente apelo desde el enlace de la notificacion.',
            )
            multa.refresh_from_db()

        if not multa.descargo_vigente:
            return Response({'detail': 'El plazo para apelar ya vencio.'}, status=400)

        from datetime import timedelta

        from django.utils import timezone

        dias = multa.condominio.plazo_resolucion_dias
        descargo = Descargo.objects.create(
            multa=multa,
            presentado_por=None,  # llego por el enlace, sin sesion
            texto=texto[:5000],
            fecha_limite_resolucion=timezone.now() + timedelta(days=dias),
        )

        estado_anterior = multa.estado
        multa.estado = EstadoMulta.CON_DESCARGO
        multa.save(update_fields=['estado'])

        registrar_historial(
            multa, estado_anterior, multa.estado, None,
            'Apelacion presentada por el residente desde el enlace de la notificacion.',
        )
        sellar_acto(multa, TipoActo.DESCARGO_PRESENTADO, None, auth_metodo='enlace_firmado', extra={
            'texto': descargo.texto,
            'via': 'enlace_de_notificacion',
            'archivo_adjunto': None,
        })

        multa.refresh_from_db()
        return Response(_expediente(multa), status=201)
