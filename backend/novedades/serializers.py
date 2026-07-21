from rest_framework import serializers

from .models import NovedadLibro


class NovedadLibroSerializer(serializers.ModelSerializer):
    solicitante_nombre = serializers.CharField(source='solicitante.get_full_name', read_only=True)
    dias_restantes = serializers.IntegerField(read_only=True)

    class Meta:
        model = NovedadLibro
        fields = (
            'id', 'condominio', 'unidad', 'solicitante', 'solicitante_nombre', 'tipo', 'texto',
            'plazo_respuesta_dias', 'fecha_limite_respuesta', 'estado', 'respondida_por',
            'respuesta_texto', 'fecha_respuesta', 'fecha_creacion', 'dias_restantes',
        )
        read_only_fields = (
            'condominio', 'solicitante', 'fecha_limite_respuesta', 'estado',
            'respondida_por', 'respuesta_texto', 'fecha_respuesta', 'fecha_creacion',
        )


class ResponderNovedadSerializer(serializers.Serializer):
    respuesta_texto = serializers.CharField()
