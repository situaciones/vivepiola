"""
Acuse de recibo de la notificacion, accesible SIN iniciar sesion.

Es deliberado que no pida cuenta: quien mas necesita esta puerta es
justamente quien no tiene la app instalada ni recuerda una contraseña. El
enlace va firmado, asi que identifica el expediente sin exponer nada, y la
confirmacion es un POST explicito para que ningun escaner de correo que
sigue enlaces pueda dar por notificado a alguien que no abrio nada.
"""

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import CanalNotificacion
from .services import multa_desde_token_acuse, registrar_acuse


def _resumen(multa):
    """Lo justo para que la persona reconozca de que se trata, sin exponer de mas."""
    infraccion = multa.infraccion
    return {
        'multa_id': multa.id,
        'organizacion': multa.condominio.nombre,
        'unidad': multa.unidad.identificador if multa.unidad else '',
        'infraccion': infraccion.descripcion if infraccion else '',
        'articulo': infraccion.articulo_referencia if infraccion else '',
        'monto': str(multa.monto or ''),
        'unidad_monto': infraccion.unidad_monto if infraccion else '',
        'plazo_dias': multa.plazo_descargo_dias or multa.condominio.plazo_descargo_dias,
        'ya_acusada': bool(multa.fecha_acuse),
        'fecha_limite_descargo': multa.fecha_limite_descargo,
    }


class AcuseNotificacionView(APIView):
    """GET muestra de que multa se trata; POST deja constancia de la recepcion."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, token):
        multa = multa_desde_token_acuse(token)
        if multa is None:
            return Response({'detail': 'El enlace no es valido o ya vencio.'}, status=404)
        return Response(_resumen(multa))

    def post(self, request, token):
        multa = multa_desde_token_acuse(token)
        if multa is None:
            return Response({'detail': 'El enlace no es valido o ya vencio.'}, status=404)

        registrar_acuse(
            multa, CanalNotificacion.EMAIL,
            destino=multa.persona_infractor.correo_electronico if multa.persona_infractor else '',
            detalle='Confirmado por el destinatario desde el enlace de la notificacion.',
        )
        multa.refresh_from_db()
        return Response(_resumen(multa))
