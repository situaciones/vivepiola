from rest_framework import serializers

from .models import InfraccionCatalogo, Reglamento


class ReglamentoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reglamento
        fields = (
            'id', 'condominio', 'archivo_pdf', 'version', 'vigente',
            'cargado_por', 'fecha_carga', 'procesado_ia',
        )
        read_only_fields = ('condominio', 'cargado_por', 'fecha_carga', 'procesado_ia')


class InfraccionCatalogoSerializer(serializers.ModelSerializer):
    class Meta:
        model = InfraccionCatalogo
        fields = (
            'id', 'condominio', 'reglamento', 'codigo', 'descripcion', 'articulo_referencia',
            'monto', 'unidad_monto', 'gravedad', 'factor_reincidencia', 'estado', 'generado_por_ia', 'texto_fuente',
            'conlleva_contencion', 'plazo_ratificacion_horas', 'quorum_ratificacion',
            'creado_por', 'confirmado_por', 'fecha_creacion', 'fecha_confirmacion',
        )
        read_only_fields = (
            'condominio', 'generado_por_ia', 'creado_por', 'confirmado_por', 'fecha_creacion', 'fecha_confirmacion',
        )
