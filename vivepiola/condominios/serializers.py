from rest_framework import serializers

from .models import Condominio, Persona, RegistroImportacion, Unidad


class CondominioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Condominio
        fields = ('id', 'nombre', 'direccion', 'rut', 'plazo_descargo_dias')


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
