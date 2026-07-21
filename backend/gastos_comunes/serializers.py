from rest_framework import serializers

from .models import CargoGastoComun, LoteExportacion


class CargoGastoComunSerializer(serializers.ModelSerializer):
    unidad_identificador = serializers.CharField(source='unidad.identificador', read_only=True)

    class Meta:
        model = CargoGastoComun
        fields = ('id', 'lote', 'multa', 'unidad', 'unidad_identificador', 'monto', 'descripcion')


class LoteExportacionSerializer(serializers.ModelSerializer):
    cargos = CargoGastoComunSerializer(many=True, read_only=True)

    class Meta:
        model = LoteExportacion
        fields = (
            'id', 'condominio', 'periodo', 'generado_por', 'archivo_csv',
            'fecha_generacion', 'total_monto', 'cargos',
        )
        read_only_fields = fields


class GenerarLoteSerializer(serializers.Serializer):
    periodo = serializers.RegexField(regex=r'^\d{4}-\d{2}$', help_text='Formato AAAA-MM')
