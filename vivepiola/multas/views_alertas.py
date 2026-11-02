"""Alerta inmediata: la crea cualquiera de la comunidad, la atienden los guardias."""

from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from accounts.models import Rol
from accounts.permissions import UsuarioAsignado, permiso_por_rol

from .alertas import atender_alerta, crear_alerta
from .models import AlertaInmediata, TipoAlerta

# Atiende quien esta en terreno o la administracion.
PuedeAtender = permiso_por_rol(Rol.FISCALIZADOR, Rol.ADMINISTRADOR)


class AlertaSerializer(serializers.ModelSerializer):
    tipo_nombre = serializers.CharField(source='get_tipo_display', read_only=True)
    estado_nombre = serializers.CharField(source='get_estado_display', read_only=True)
    creada_por_nombre = serializers.SerializerMethodField()
    unidad_afectada_identificador = serializers.CharField(source='unidad_afectada.identificador', read_only=True, default=None)
    unidad_vehiculo_identificador = serializers.CharField(source='unidad_vehiculo.identificador', read_only=True, default=None)
    atendida_por_nombre = serializers.SerializerMethodField()
    avisos_enviados = serializers.SerializerMethodField()

    class Meta:
        model = AlertaInmediata
        fields = (
            'id', 'tipo', 'tipo_nombre', 'estado', 'estado_nombre', 'patente', 'descripcion', 'foto',
            'creada_por_nombre', 'unidad_afectada_identificador', 'unidad_vehiculo_identificador',
            'atendida_por_nombre', 'atendida_en', 'nota_atencion', 'creada_en', 'ticket', 'avisos_enviados',
        )

    def get_creada_por_nombre(self, obj):
        u = obj.creada_por
        return (u.get_full_name() or u.username) if u else None

    def get_atendida_por_nombre(self, obj):
        u = obj.atendida_por
        return (u.get_full_name() or u.username) if u else None

    def get_avisos_enviados(self, obj):
        """Cuantos avisos salieron, sin exponer a quienes (lo ve el equipo en el detalle)."""
        return sum(1 for a in obj.avisados or [] if a.get('canales'))


class AlertaViewSet(viewsets.ModelViewSet):
    serializer_class = AlertaSerializer
    http_method_names = ['get', 'post', 'head', 'options']
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filterset_fields = ['estado']

    def get_permissions(self):
        if self.action == 'atender':
            return [PuedeAtender()]
        return [UsuarioAsignado()]

    def get_throttles(self):
        # Un boton de alerta invita al abuso: limite por usuario al crear.
        if self.action == 'create':
            self.throttle_scope = 'alerta'
            return [ScopedRateThrottle()]
        return []

    def get_queryset(self):
        user = self.request.user
        qs = AlertaInmediata.objects.filter(condominio_id=user.condominio_id).select_related(
            'creada_por', 'unidad_afectada', 'unidad_vehiculo', 'atendida_por',
        )
        if user.rol == Rol.RESIDENTE:
            qs = qs.filter(creada_por=user)
        return qs

    def create(self, request, *args, **kwargs):
        if not request.user.condominio_id:
            raise ValidationError({'detail': 'Su cuenta no esta asociada a una comunidad.'})
        tipo = request.data.get('tipo') or TipoAlerta.SALIDA_BLOQUEADA
        if tipo not in TipoAlerta.values:
            raise ValidationError({'tipo': 'Tipo de alerta invalido.'})
        patente = request.data.get('patente') or ''
        descripcion = request.data.get('descripcion') or ''
        if tipo != TipoAlerta.OTRA and not patente and not request.FILES.get('foto'):
            raise ValidationError({'patente': 'Indica la patente o adjunta una foto del vehiculo.'})
        if tipo == TipoAlerta.OTRA and not descripcion.strip():
            raise ValidationError({'descripcion': 'Cuenta brevemente que pasa.'})
        alerta = crear_alerta(
            request.user, tipo=tipo, patente=patente, descripcion=descripcion, foto=request.FILES.get('foto'),
        )
        return Response(self.get_serializer(alerta).data, status=201)

    @action(detail=True, methods=['post'])
    def atender(self, request, pk=None):
        alerta = self.get_object()
        try:
            atender_alerta(alerta, request.user, request.data.get('nota', ''))
        except ValueError as exc:
            raise ValidationError({'detail': str(exc)})
        return Response(self.get_serializer(alerta).data)

