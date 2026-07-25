from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import ROLES_ASIGNABLES, Invitacion, Usuario


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


class InvitacionSerializer(serializers.ModelSerializer):
    unidad_identificador = serializers.CharField(source='unidad.identificador', read_only=True)
    vigente = serializers.BooleanField(read_only=True)

    class Meta:
        model = Invitacion
        fields = (
            'id', 'condominio', 'correo', 'unidad', 'unidad_identificador', 'rol_sugerido',
            'codigo', 'estado', 'vigente', 'creada_por', 'creada_en', 'expira_en',
            'aceptada_por', 'aceptada_en',
        )
        read_only_fields = (
            'condominio', 'codigo', 'estado', 'creada_por', 'creada_en', 'expira_en',
            'aceptada_por', 'aceptada_en',
        )

    def validate_rol_sugerido(self, value):
        if value not in ROLES_ASIGNABLES:
            raise serializers.ValidationError(
                f'El Administrador solo puede invitar con rol: {", ".join(ROLES_ASIGNABLES)}.'
            )
        return value


class UsuarioPendienteSerializer(serializers.ModelSerializer):
    nombre = serializers.SerializerMethodField()

    class Meta:
        model = Usuario
        fields = ('id', 'username', 'email', 'nombre', 'condominio', 'date_joined')

    def get_nombre(self, obj):
        return obj.get_full_name() or obj.username


class AsignarRolSerializer(serializers.Serializer):
    rol = serializers.ChoiceField(choices=[(r, r) for r in ROLES_ASIGNABLES])
    persona_id = serializers.IntegerField(required=False)


class GoogleLoginSerializer(serializers.Serializer):
    credential = serializers.CharField()
    codigo = serializers.CharField(required=False, allow_blank=True, default='')


class VivePiolaTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Incluye el rol y el condominio en el JWT para que el frontend rutee el dashboard correcto."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['rol'] = user.rol
        token['condominio_id'] = user.condominio_id
        token['nombre'] = user.get_full_name() or user.username
        return token
