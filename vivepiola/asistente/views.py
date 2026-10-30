from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from accounts.permissions import UsuarioAsignado

from .servicio import AsistenteNoConfigurado, AsistenteNoDisponible, responder


class AsistenteView(APIView):
    """
    POST {"mensajes": [{"rol": "usuario"|"asistente", "texto": "..."}]}
    -> {"respuesta": "...", "casos": [12, 15]}

    Sin estado en el servidor: el cliente manda la conversacion completa en
    cada pregunta. El limite por hora protege la cuenta de Anthropic de un
    usuario (o un script) que no para de preguntar.
    """

    permission_classes = [IsAuthenticated, UsuarioAsignado]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'asistente'

    def post(self, request):
        try:
            return Response(responder(request.user, request.data.get('mensajes')))
        except ValueError as e:
            return Response({'detail': str(e)}, status=400)
        except AsistenteNoConfigurado:
            return Response(
                {'detail': 'El asistente todavia no esta activado en esta instalacion.'},
                status=503,
            )
        except AsistenteNoDisponible:
            return Response(
                {'detail': 'El asistente no esta disponible en este momento. Intenta en unos minutos.'},
                status=503,
            )
