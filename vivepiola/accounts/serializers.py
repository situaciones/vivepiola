from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import ROLES_ASIGNABLES, Invitacion, PermisoDenuncia, Usuario


class UsuarioSerializer(serializers.ModelSerializer):
    vocabulario = serializers.SerializerMethodField()
    permiso_denuncia = serializers.SerializerMethodField()

    class Meta:
        model = Usuario
        fields = (
            'id', 'username', 'email', 'first_name', 'last_name',
            'rol', 'condominio', 'persona', 'telefono', 'is_active', 'vocabulario',
            'permiso_denuncia',
        )
        read_only_fields = ('id', 'rol', 'condominio', 'persona', 'vocabulario')

    def get_permiso_denuncia(self, obj):
        """Los limites que el Denunciante tiene, para que los vea en su panel."""
        try:
            return PermisoDenunciaSerializer(obj.permiso_denuncia).data
        except PermisoDenuncia.DoesNotExist:
            return None

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


class SinConflictoTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Incluye el rol y el condominio en el JWT para que el frontend rutee el dashboard correcto."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['rol'] = user.rol
        token['condominio_id'] = user.condominio_id
        token['nombre'] = user.get_full_name() or user.username
        return token


class PermisoDenunciaSerializer(serializers.ModelSerializer):
    unidades_identificadores = serializers.SerializerMethodField()

    class Meta:
        model = PermisoDenuncia
        fields = (
            'suspendido', 'vigente_desde', 'vigente_hasta', 'dias', 'hora_desde', 'hora_hasta',
            'unidades', 'unidades_identificadores', 'notas', 'actualizado_en',
        )
        read_only_fields = ('actualizado_en',)

    def get_unidades_identificadores(self, obj):
        return [u.identificador for u in obj.unidades.all()]

    def validate_dias(self, value):
        if not isinstance(value, list) or any(not isinstance(d, int) or not 0 <= d <= 6 for d in value):
            raise serializers.ValidationError('Los dias van de 0 (lunes) a 6 (domingo).')
        return sorted(set(value))

    def validate_unidades(self, value):
        condominio_id = self.context['condominio_id']
        if any(u.condominio_id != condominio_id for u in value):
            raise serializers.ValidationError('Alguna unidad no pertenece a su comunidad.')
        return value

    def validate(self, attrs):
        desde, hasta = attrs.get('vigente_desde'), attrs.get('vigente_hasta')
        if desde and hasta and hasta < desde:
            raise serializers.ValidationError({'vigente_hasta': 'El termino no puede ser antes del inicio.'})
        if bool(attrs.get('hora_desde')) != bool(attrs.get('hora_hasta')):
            raise serializers.ValidationError({'hora_hasta': 'Indique la hora de inicio y la de termino, o ninguna.'})
        return attrs


class DenuncianteSerializer(serializers.ModelSerializer):
    nombre = serializers.SerializerMethodField()
    permiso = serializers.SerializerMethodField()

    class Meta:
        model = Usuario
        fields = ('id', 'nombre', 'email', 'is_active', 'permiso')

    def get_nombre(self, obj):
        return obj.get_full_name() or obj.username

    def get_permiso(self, obj):
        try:
            return PermisoDenunciaSerializer(obj.permiso_denuncia).data
        except PermisoDenuncia.DoesNotExist:
            return None
