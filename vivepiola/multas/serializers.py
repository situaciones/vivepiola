from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from .models import (
    CausalLevantamiento, Delegacion, Descargo, EvidenciaFoto, HistorialMulta,
    MedidaInmediata, Multa, Ticket,
)


class EvidenciaFotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = EvidenciaFoto
        fields = ('id', 'ticket', 'imagen', 'descripcion', 'subida_en', 'sha256', 'anclaje_fisico')
        read_only_fields = ('subida_en', 'sha256', 'anclaje_fisico')


class TicketSerializer(serializers.ModelSerializer):
    evidencias = EvidenciaFotoSerializer(many=True, read_only=True)
    unidad_identificador = serializers.CharField(source='unidad.identificador', read_only=True)
    creado_por_nombre = serializers.SerializerMethodField()

    class Meta:
        model = Ticket
        fields = (
            'id', 'condominio', 'unidad', 'unidad_identificador', 'persona_reportada', 'creado_por',
            'creado_por_nombre', 'descripcion', 'fecha_hecho', 'ubicacion', 'estado', 'fecha_creacion', 'evidencias',
        )
        read_only_fields = ('condominio', 'creado_por', 'estado', 'fecha_creacion')

    def validate_fecha_hecho(self, value):
        if value > timezone.now():
            raise serializers.ValidationError('La fecha del hecho no puede estar en el futuro.')
        return value

    def get_creado_por_nombre(self, obj):
        if not obj.creado_por:
            return ''
        return obj.creado_por.get_full_name() or obj.creado_por.username


class HistorialMultaSerializer(serializers.ModelSerializer):
    usuario_nombre = serializers.CharField(source='usuario.get_full_name', read_only=True)

    class Meta:
        model = HistorialMulta
        fields = ('id', 'estado_anterior', 'estado_nuevo', 'usuario', 'usuario_nombre', 'comentario', 'fecha')


class DescargoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Descargo
        fields = (
            'id', 'multa', 'presentado_por', 'texto', 'archivo_adjunto', 'fecha_presentacion',
            'resolucion', 'resuelto_por', 'comentario_resolucion', 'fecha_resolucion',
        )
        read_only_fields = (
            'presentado_por', 'fecha_presentacion', 'resolucion', 'resuelto_por',
            'comentario_resolucion', 'fecha_resolucion',
        )


class MultaSerializer(serializers.ModelSerializer):
    ticket_detalle = TicketSerializer(source='ticket', read_only=True)
    infraccion_descripcion = serializers.CharField(source='infraccion.descripcion', read_only=True)
    infraccion_codigo = serializers.CharField(source='infraccion.codigo', read_only=True)
    infraccion_articulo = serializers.CharField(source='infraccion.articulo_referencia', read_only=True)
    infraccion_texto_fuente = serializers.CharField(source='infraccion.texto_fuente', read_only=True)
    unidad_identificador = serializers.CharField(source='unidad.identificador', read_only=True)
    persona_nombre = serializers.CharField(source='persona_infractor.nombre_completo', read_only=True)
    historial = HistorialMultaSerializer(many=True, read_only=True)
    descargo = DescargoSerializer(read_only=True)

    class Meta:
        model = Multa
        fields = (
            'id', 'condominio', 'ticket', 'ticket_detalle', 'unidad', 'unidad_identificador',
            'persona_infractor', 'persona_nombre', 'infraccion', 'infraccion_descripcion',
            'infraccion_codigo', 'infraccion_articulo', 'infraccion_texto_fuente', 'monto', 'estado',
            'aprobada_por', 'fecha_aprobacion', 'motivo_rechazo',
            'notificada_por', 'fecha_notificacion', 'pdf_notificacion',
            'plazo_descargo_dias', 'fecha_limite_descargo',
            'es_reincidencia', 'multa_primera_sancion', 'agravante_sugerido',
            'fecha_creacion', 'fecha_firme', 'historial', 'descargo',
        )
        read_only_fields = (
            'condominio', 'unidad', 'persona_infractor', 'estado', 'aprobada_por', 'fecha_aprobacion',
            'notificada_por', 'fecha_notificacion', 'pdf_notificacion', 'fecha_limite_descargo',
            'es_reincidencia', 'multa_primera_sancion', 'agravante_sugerido', 'fecha_creacion', 'fecha_firme',
        )


class AprobarMultaSerializer(serializers.Serializer):
    infraccion_id = serializers.IntegerField()
    monto = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, min_value=Decimal('0.01'))


class RechazarMultaSerializer(serializers.Serializer):
    motivo = serializers.CharField()


class PresentarDescargoSerializer(serializers.Serializer):
    texto = serializers.CharField()
    archivo_adjunto = serializers.FileField(required=False)


class ResolverDescargoSerializer(serializers.Serializer):
    resolucion = serializers.ChoiceField(choices=['ACEPTADO', 'RECHAZADO'])
    comentario = serializers.CharField(required=False, allow_blank=True)


class VotoRatificacionSerializer(serializers.ModelSerializer):
    actor_nombre = serializers.CharField(source='actor.username', read_only=True)
    delegante_nombre = serializers.SerializerMethodField()

    class Meta:
        from .models import VotoRatificacion as _VR
        model = _VR
        fields = ('id', 'actor', 'actor_nombre', 'en_calidad_de', 'delegacion', 'delegante_nombre', 'ts')

    def get_delegante_nombre(self, obj):
        return obj.delegacion.delegante.username if obj.delegacion_id else None


class MedidaInmediataSerializer(serializers.ModelSerializer):
    hallazgo_codigo = serializers.CharField(source='hallazgo.codigo', read_only=True)
    hallazgo_descripcion = serializers.CharField(source='hallazgo.descripcion', read_only=True)
    hallazgo_gravedad = serializers.CharField(source='hallazgo.gravedad', read_only=True)
    unidad_identificador = serializers.CharField(source='multa.unidad.identificador', read_only=True)
    ejecutada_por_nombre = serializers.CharField(source='ejecutada_por.username', read_only=True)
    evidencias = EvidenciaFotoSerializer(many=True, read_only=True)
    votos = VotoRatificacionSerializer(many=True, read_only=True)
    votos_emitidos = serializers.SerializerMethodField()
    ya_vote = serializers.SerializerMethodField()

    class Meta:
        model = MedidaInmediata
        fields = (
            'id', 'multa', 'unidad_identificador', 'hallazgo', 'hallazgo_codigo',
            'hallazgo_descripcion', 'hallazgo_gravedad', 'descripcion', 'estado', 'activa',
            'ejecutada_por', 'ejecutada_por_nombre', 'auth_metodo_ejecucion', 'ejecutada_en',
            'plazo_ratificacion_horas', 'proxima_revision', 'nivel_escalamiento',
            'quorum_requerido', 'votos', 'votos_emitidos', 'ya_vote',
            'ratificada_por', 'ratificada_en',
            'levantada_por', 'levantada_en', 'causal_levantamiento', 'fundamento_levantamiento',
            'evidencias',
        )
        read_only_fields = fields

    def get_votos_emitidos(self, obj):
        return obj.votos.count()

    def get_ya_vote(self, obj):
        user = self.context.get('request').user if self.context.get('request') else None
        if not user or not user.is_authenticated:
            return False
        return obj.votos.filter(actor=user).exists()


class EjecutarMedidaSerializer(serializers.Serializer):
    """Contrato minimalista de primera linea: el operario reporta, el backend califica."""

    expediente_id = serializers.IntegerField()
    hallazgo_codigo = serializers.CharField(max_length=30)
    evidencia_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)
    descripcion = serializers.CharField(max_length=500, required=False, allow_blank=True, default='')
    auth_metodo = serializers.CharField(max_length=40, required=False, default='jwt_password_session')


class LevantarMedidaSerializer(serializers.Serializer):
    causal = serializers.ChoiceField(choices=CausalLevantamiento.choices)
    fundamento = serializers.CharField()


class DelegacionSerializer(serializers.ModelSerializer):
    delegante_nombre = serializers.CharField(source='delegante.username', read_only=True)
    delegado_nombre = serializers.CharField(source='delegado.username', read_only=True)

    class Meta:
        model = Delegacion
        fields = (
            'id', 'condominio', 'delegante', 'delegante_nombre', 'delegado', 'delegado_nombre',
            'version', 'acciones', 'tope_gravedad', 'vigencia_desde', 'vigencia_hasta',
            'estado', 'motivo', 'otorgamiento_hash', 'revocada_en', 'creada_en',
        )
        read_only_fields = fields


class OtorgarDelegacionSerializer(serializers.Serializer):
    delegado_id = serializers.IntegerField()
    acciones = serializers.ListField(child=serializers.ChoiceField(choices=['RATIFICAR_CONTENCION']), default=['RATIFICAR_CONTENCION'])
    tope_gravedad = serializers.ChoiceField(choices=['LEVE', 'GRAVE', 'GRAVISIMA'], default='GRAVE')
    vigencia_desde = serializers.DateTimeField()
    vigencia_hasta = serializers.DateTimeField()
    motivo = serializers.CharField(required=False, allow_blank=True, default='')
