from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import Usuario


class UsuarioSerializer(serializers.ModelSerializer):
    vocabulario = serializers.SerializerMethodField()

    class Meta:
        model = Usuario
        fields = (
            'id', 'username', 'email', 'first_name', 'last_name',
            'rol', 'condominio', 'persona', 'telefono', 'is_active', 'vocabulario',
        )
        read_only_fields = ('id', 'rol', 'condominio', 'persona', 'vocabulario')

    def get_vocabulario(self, obj):
        """Diccionario de etiquetas del vertical de la organizacion (la 'piel'
        multi-nicho). Vacio = vocabulario por defecto (copropiedad)."""
        if obj.condominio_id and obj.condominio.vertical_id:
            return obj.condominio.vertical.vocabulario or {}
        return {}


class VivePiolaTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Incluye el rol y el condominio en el JWT para que el frontend rutee el dashboard correcto."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['rol'] = user.rol
        token['condominio_id'] = user.condominio_id
        token['nombre'] = user.get_full_name() or user.username
        return token
