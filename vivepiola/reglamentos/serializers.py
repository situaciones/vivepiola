from rest_framework import serializers

from .models import EstadoInfraccion, InfraccionCatalogo, Reglamento
from .utils import ReglamentoIlegible, extraer_texto_pdf


class ReglamentoSerializer(serializers.ModelSerializer):
    referencia_citable = serializers.CharField(read_only=True)
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
            'id', 'condominio', 'tipo', 'titulo', 'fecha_documento', 'archivo_pdf',
            'version', 'vigente', 'cargado_por', 'fecha_carga', 'procesado_ia',
            'referencia_citable',
        )
        read_only_fields = ('condominio', 'cargado_por', 'fecha_carga', 'procesado_ia', 'referencia_citable')


class InfraccionCatalogoSerializer(serializers.ModelSerializer):
    class Meta:
        model = InfraccionCatalogo
        fields = (
            'id', 'condominio', 'reglamento', 'codigo', 'descripcion', 'articulo_referencia',
            'monto', 'monto_minimo', 'monto_maximo', 'unidad_monto', 'gravedad', 'factor_reincidencia',
            'estado', 'generado_por_ia', 'texto_fuente',
            'conlleva_contencion', 'plazo_ratificacion_horas', 'quorum_ratificacion',
            'creado_por', 'confirmado_por', 'fecha_creacion', 'fecha_confirmacion',
        )
        read_only_fields = (
            'condominio', 'generado_por_ia', 'creado_por', 'confirmado_por', 'fecha_creacion', 'fecha_confirmacion',
        )

    def validate(self, datos):
        monto = datos.get('monto', getattr(self.instance, 'monto', None))
        minimo = datos.get('monto_minimo', getattr(self.instance, 'monto_minimo', None))
        maximo = datos.get('monto_maximo', getattr(self.instance, 'monto_maximo', None))
        if monto is not None:
            if minimo is not None and minimo > monto:
                raise serializers.ValidationError({'monto_minimo': 'El minimo no puede ser mayor que el monto.'})
            if maximo is not None and maximo < monto:
                raise serializers.ValidationError({'monto_maximo': 'El maximo no puede ser menor que el monto.'})
        # Una falta activa tiene que fundarse en el reglamento de copropiedad o la ley.
        estado = datos.get('estado', getattr(self.instance, 'estado', None))
        if estado == EstadoInfraccion.ACTIVA:
            borrador = InfraccionCatalogo(
                articulo_referencia=datos.get('articulo_referencia', getattr(self.instance, 'articulo_referencia', '')),
                reglamento=datos.get('reglamento', getattr(self.instance, 'reglamento', None)),
            )
            motivo = borrador.motivo_sin_base_legal()
            if motivo:
                raise serializers.ValidationError({'articulo_referencia': motivo})
        return datos
