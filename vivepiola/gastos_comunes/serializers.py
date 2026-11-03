from rest_framework import serializers

from .models import CargoGastoComun, LoteExportacion


class CargoGastoComunSerializer(serializers.ModelSerializer):
    unidad_identificador = serializers.CharField(source='unidad.identificador', read_only=True)

    class Meta:
        model = CargoGastoComun
        fields = ('id', 'lote', 'multa', 'unidad', 'unidad_identificador', 'monto', 'unidad_monto', 'descripcion')


class LoteExportacionSerializer(serializers.ModelSerializer):
    cargos = CargoGastoComunSerializer(many=True, read_only=True)
    # El total por unidad de monto, ya legible ("2.50 UF + 30000.00 CLP").
    total_texto = serializers.SerializerMethodField()

    class Meta:
        model = LoteExportacion
        fields = (
            'id', 'condominio', 'periodo', 'generado_por', 'archivo_csv',
            'fecha_generacion', 'total_monto', 'total_texto', 'cargos',
        )
        read_only_fields = fields

    def get_total_texto(self, obj):
        totales = obj.totales_por_unidad()
        return ' + '.join(f'{monto} {unidad}' for unidad, monto in sorted(totales.items())) or '0'


class GenerarLoteSerializer(serializers.Serializer):
    periodo = serializers.RegexField(regex=r'^\d{4}-\d{2}$', help_text='Formato AAAA-MM')
