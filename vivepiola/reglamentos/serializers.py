from rest_framework import serializers

from .models import InfraccionCatalogo, Reglamento
from .utils import ReglamentoIlegible, extraer_texto_pdf


class ReglamentoSerializer(serializers.ModelSerializer):
    # En multipart un booleano ausente se interpreta como "casilla desmarcada",
    # asi que sin este default todo reglamento subido desde la app quedaba
    # marcado como no vigente.
    vigente = serializers.BooleanField(required=False, default=True)

    def validate_archivo_pdf(self, archivo):
        """
        El texto se extrae ANTES de guardar: si el PDF no sirve, el
        administrador se entera al subirlo y no queda un reglamento
        inservible ocupando el lugar del vigente.
        """
        try:
            self._texto_extraido = extraer_texto_pdf(archivo)
        except ReglamentoIlegible as exc:
            raise serializers.ValidationError(str(exc))
        finally:
            archivo.seek(0)
        return archivo

    def create(self, validated_data):
        validated_data['texto_extraido'] = self._texto_extraido
        return super().create(validated_data)

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
