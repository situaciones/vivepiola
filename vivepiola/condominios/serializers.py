from rest_framework import serializers

from .models import Condominio, Persona, RegistroImportacion, Unidad


class CondominioSerializer(serializers.ModelSerializer):
    codigo_comunidad = serializers.SerializerMethodField()

    class Meta:
        model = Condominio
        fields = ('id', 'nombre', 'direccion', 'rut', 'plazo_descargo_dias', 'codigo_comunidad')

    def get_codigo_comunidad(self, obj):
        """El Codigo Unico de Comunidad solo lo ve quien puede repartirlo."""
        request = self.context.get('request')
        if request and getattr(request.user, 'rol', None) in ('ADMINISTRADOR', 'SUPERADMIN'):
            return obj.codigo_comunidad
        return None


class UnidadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Unidad
        fields = ('id', 'condominio', 'identificador', 'alicuota')
        read_only_fields = ('condominio',)


class PersonaSerializer(serializers.ModelSerializer):
    unidad_identificador = serializers.CharField(source='unidad.identificador', read_only=True)

    class Meta:
        model = Persona
        fields = (
            'id', 'condominio', 'unidad', 'unidad_identificador', 'rol_ocupacion',
            'nombre_completo', 'cedula_identidad', 'domicilio', 'correo_electronico',
            'telefono', 'activo', 'creado_en', 'actualizado_en',
        )
        read_only_fields = ('condominio', 'creado_en', 'actualizado_en')


class RegistroImportacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = RegistroImportacion
        fields = (
            'id', 'condominio', 'archivo', 'cargado_por', 'fecha_carga',
            'filas_totales', 'filas_ok', 'filas_error', 'detalle_errores', 'estado',
        )
        read_only_fields = fields
