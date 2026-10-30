import logging

from django.conf import settings
from django.core.mail import send_mail
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .models import SolicitudDemo

logger = logging.getLogger(__name__)


class SolicitudDemoSerializer(serializers.ModelSerializer):
    # Campo trampa: invisible para una persona, los robots lo llenan.
    sitio_web = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = SolicitudDemo
        fields = ('nombre', 'correo', 'empresa', 'sitio_web')


class SolicitudDemoView(APIView):
    """
    POST publico del formulario "Solicitar demo" de la portada.

    Sin autenticacion a proposito: lo llena gente que todavia no tiene cuenta.
    Sin authentication_classes, ademas, un token vencido guardado en el
    navegador no convierte el envio en un 401.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'demo'

    def post(self, request):
        datos = SolicitudDemoSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        if datos.validated_data.pop('sitio_web', ''):
            # Al robot se le responde igual que a una persona: si supiera que
            # lo descubrimos, cambiaria de estrategia.
            return Response({'ok': True}, status=201)

        solicitud = datos.save()
        try:
            send_mail(
                f'Nueva solicitud de demo: {solicitud.nombre}',
                f'Nombre: {solicitud.nombre}\n'
                f'Correo: {solicitud.correo}\n'
                f'Condominio o administradora: {solicitud.empresa or "(no indico)"}\n\n'
                'Queda registrada en el panel de administracion, en "Solicitudes de demo".',
                settings.DEFAULT_FROM_EMAIL,
                [settings.CONTACTO_CORREO],
                fail_silently=False,
            )
        except Exception:
            logger.exception('No se pudo avisar por correo la solicitud de demo %s', solicitud.id)
        return Response({'ok': True}, status=201)
