from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import Rol
from accounts.permissions import EsAdministrador

from .models import EstadoNovedad, NovedadLibro
from .serializers import NovedadLibroSerializer, ResponderNovedadSerializer


def _marcar_vencidas(condominio):
    NovedadLibro.objects.filter(
        condominio=condominio, estado=EstadoNovedad.PENDIENTE, fecha_limite_respuesta__lt=timezone.now(),
    ).update(estado=EstadoNovedad.VENCIDA)


class NovedadLibroViewSet(viewsets.ModelViewSet):
    """
    Libro de Novedades Digital: cualquier residente puede registrar un
    reclamo o solicitud; la administracion debe responder dentro del plazo
    legal (por defecto 20 dias corridos, art. settings.NOVEDADES_PLAZO_RESPUESTA_DIAS).
    """

    serializer_class = NovedadLibroSerializer
    http_method_names = ['get', 'post', 'head', 'options']

    def get_permissions(self):
        if self.action == 'responder':
            return [EsAdministrador()]
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        qs = NovedadLibro.objects.all()
        if user.rol != Rol.SUPERADMIN:
            qs = qs.filter(condominio_id=user.condominio_id)
            _marcar_vencidas(user.condominio)
        if user.rol == Rol.RESIDENTE:
            qs = qs.filter(solicitante=user)
        return qs

    def perform_create(self, serializer):
        user = self.request.user
        plazo = serializer.validated_data.get('plazo_respuesta_dias') or settings.NOVEDADES_PLAZO_RESPUESTA_DIAS

        unidad = serializer.validated_data.get('unidad')
        if unidad and unidad.condominio_id != user.condominio_id:
            raise ValidationError({'unidad': 'La unidad no pertenece a su condominio.'})
        if unidad is None and user.persona_id:
            unidad = user.persona.unidad

        serializer.save(
            condominio=user.condominio,
            solicitante=user,
            unidad=unidad,
            plazo_respuesta_dias=plazo,
            fecha_limite_respuesta=timezone.now() + timedelta(days=plazo),
        )

    @action(detail=True, methods=['post'])
    def responder(self, request, pk=None):
        novedad = self.get_object()
        datos = ResponderNovedadSerializer(data=request.data)
        datos.is_valid(raise_exception=True)

        novedad.respuesta_texto = datos.validated_data['respuesta_texto']
        novedad.respondida_por = request.user
        novedad.fecha_respuesta = timezone.now()
        novedad.estado = EstadoNovedad.RESPONDIDA
        novedad.save()
        return Response(NovedadLibroSerializer(novedad).data)
