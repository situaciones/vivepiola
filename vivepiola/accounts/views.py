from django.conf import settings
from django.core.mail import EmailMessage
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .google import GoogleAuthError, verificar_credencial_google
from .models import EstadoInvitacion, Invitacion, Rol, Usuario
from .permissions import EsAdministrador
from .serializers import (
    AsignarRolSerializer, GoogleLoginSerializer, InvitacionSerializer,
    UsuarioPendienteSerializer, UsuarioSerializer, VivePiolaTokenObtainPairSerializer,
)


class VivePiolaTokenObtainPairView(TokenObtainPairView):
    serializer_class = VivePiolaTokenObtainPairSerializer


class MeView(RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]  # accesible tambien para cuentas PENDIENTE
    serializer_class = UsuarioSerializer
    http_method_names = ['get', 'patch']

    def get_object(self):
        return self.request.user


def _username_desde_email(email):
    base = email.split('@')[0][:140] or 'usuario'
    username = base
    sufijo = 1
    while Usuario.objects.filter(username=username).exists():
        sufijo += 1
        username = f'{base}{sufijo}'
    return username


def _tokens_para(usuario):
    token = VivePiolaTokenObtainPairSerializer.get_token(usuario)
    return {'access': str(token.access_token), 'refresh': str(token)}


class GoogleLoginView(APIView):
    """
    Ingreso universal via Google (ID token de Google Identity Services).

    Reglas de primera vez:
      1. Invitacion vigente para el correo (o cuyo codigo se adjunta) ->
         la cuenta nace en la comunidad con el rol sugerido por el Administrador.
      2. Codigo Unico de Comunidad valido -> la cuenta nace asociada a la
         comunidad en estado PENDIENTE (el Administrador confirma el rol).
      3. Sin invitacion ni codigo -> cuenta PENDIENTE sin comunidad.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        datos = GoogleLoginSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        codigo = (datos.validated_data.get('codigo') or '').strip()

        try:
            perfil = verificar_credencial_google(datos.validated_data['credential'])
        except GoogleAuthError as exc:
            return Response({'detail': str(exc)}, status=400)

        email = perfil['email']
        usuario = Usuario.objects.filter(email__iexact=email).first()

        if usuario is None:
            usuario = self._crear_usuario(perfil, codigo)
        elif usuario.rol == Rol.PENDIENTE and codigo:
            # Cuenta pendiente que ahora aporta un codigo: intentar asociarla.
            self._asociar_por_codigo(usuario, codigo)

        if not usuario.is_active:
            return Response({'detail': 'Su cuenta esta deshabilitada.'}, status=403)

        respuesta = _tokens_para(usuario)
        respuesta.update({'rol': usuario.rol, 'condominio_id': usuario.condominio_id})
        return Response(respuesta)

    def _crear_usuario(self, perfil, codigo):
        from condominios.models import Condominio, Persona

        email = perfil['email']
        invitacion = (
            Invitacion.objects.filter(correo__iexact=email, estado=EstadoInvitacion.PENDIENTE)
            .order_by('-creada_en').first()
        )
        if (invitacion is None or not invitacion.vigente) and codigo:
            candidata = Invitacion.objects.filter(codigo=codigo, estado=EstadoInvitacion.PENDIENTE).first()
            if candidata and candidata.vigente:
                invitacion = candidata

        rol, condominio = Rol.PENDIENTE, None
        if invitacion and invitacion.vigente:
            rol, condominio = invitacion.rol_sugerido, invitacion.condominio
        elif codigo:
            condominio = Condominio.objects.filter(codigo_comunidad=codigo.upper()).first()

        usuario = Usuario(
            username=_username_desde_email(email),
            email=email,
            first_name=perfil['nombre'][:150],
            last_name=perfil['apellido'][:150],
            rol=rol,
            condominio=condominio,
        )
        usuario.set_unusable_password()  # el acceso es exclusivamente via Google
        usuario.save()

        if invitacion and invitacion.vigente:
            invitacion.estado = EstadoInvitacion.ACEPTADA
            invitacion.aceptada_por = usuario
            invitacion.aceptada_en = timezone.now()
            invitacion.save(update_fields=['estado', 'aceptada_por', 'aceptada_en'])
            # Vinculo automatico a su ficha del registro si el correo coincide.
            persona = Persona.objects.filter(
                condominio=invitacion.condominio, correo_electronico__iexact=email,
            ).first()
            if persona:
                usuario.persona = persona
                usuario.save(update_fields=['persona'])
        return usuario

    def _asociar_por_codigo(self, usuario, codigo):
        from condominios.models import Condominio

        invitacion = Invitacion.objects.filter(codigo=codigo, estado=EstadoInvitacion.PENDIENTE).first()
        if invitacion and invitacion.vigente:
            usuario.rol = invitacion.rol_sugerido
            usuario.condominio = invitacion.condominio
            usuario.save(update_fields=['rol', 'condominio'])
            invitacion.estado = EstadoInvitacion.ACEPTADA
            invitacion.aceptada_por = usuario
            invitacion.aceptada_en = timezone.now()
            invitacion.save(update_fields=['estado', 'aceptada_por', 'aceptada_en'])
            return
        condominio = Condominio.objects.filter(codigo_comunidad=codigo.upper()).first()
        if condominio and usuario.condominio_id is None:
            usuario.condominio = condominio
            usuario.save(update_fields=['condominio'])


def _enviar_correo_invitacion(invitacion):
    """Best-effort: en dev el backend de consola lo imprime; nunca bloquea la creacion."""
    enlace = f'{settings.FRONTEND_URL}/login?codigo={invitacion.codigo}'
    cuerpo = (
        f'Le han invitado a {invitacion.condominio.nombre} en VIVEPIOLA '
        f'con el rol {invitacion.get_rol_sugerido_display()}.\n\n'
        f'Para aceptar, ingrese con su cuenta de Google desde:\n{enlace}\n\n'
        f'O use este codigo de invitacion al iniciar sesion: {invitacion.codigo}\n'
        f'La invitacion vence el {invitacion.expira_en:%d-%m-%Y}.'
    )
    try:
        EmailMessage(
            subject=f'Invitacion a {invitacion.condominio.nombre} - VIVEPIOLA',
            body=cuerpo,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[invitacion.correo],
        ).send(fail_silently=True)
    except Exception:
        pass


class InvitacionViewSet(viewsets.ModelViewSet):
    """
    Modulo delegado: el Administrador del condominio invita y gestiona sus
    invitaciones. Sin update: una invitacion se revoca y se emite otra.
    """

    serializer_class = InvitacionSerializer
    permission_classes = [EsAdministrador]
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        user = self.request.user
        qs = Invitacion.objects.all()
        if user.rol != Rol.SUPERADMIN:
            qs = qs.filter(condominio_id=user.condominio_id)
        return qs

    def perform_create(self, serializer):
        condominio = self.request.user.condominio
        if condominio is None:
            raise ValidationError({'detail': 'Su cuenta no esta asociada a una comunidad.'})
        unidad = serializer.validated_data.get('unidad')
        if unidad and unidad.condominio_id != condominio.id:
            raise ValidationError({'unidad': 'La unidad no pertenece a su comunidad.'})
        invitacion = serializer.save(condominio=condominio, creada_por=self.request.user)
        _enviar_correo_invitacion(invitacion)

    @action(detail=True, methods=['post'])
    def revocar(self, request, pk=None):
        invitacion = self.get_object()
        if invitacion.estado != EstadoInvitacion.PENDIENTE:
            return Response({'detail': 'Solo se pueden revocar invitaciones pendientes.'}, status=400)
        invitacion.estado = EstadoInvitacion.REVOCADA
        invitacion.save(update_fields=['estado'])
        return Response(InvitacionSerializer(invitacion).data)


class UsuariosPendientesView(APIView):
    """Cuentas Google en espera de rol, visibles para el Administrador de su comunidad."""

    permission_classes = [EsAdministrador]

    def get(self, request):
        qs = Usuario.objects.filter(rol=Rol.PENDIENTE, is_active=True)
        if request.user.rol != Rol.SUPERADMIN:
            qs = qs.filter(condominio_id=request.user.condominio_id)
        return Response(UsuarioPendienteSerializer(qs.order_by('date_joined'), many=True).data)


class AsignarRolView(APIView):
    """El Administrador confirma el rol final de una cuenta pendiente de su comunidad."""

    permission_classes = [EsAdministrador]

    def post(self, request, pk):
        datos = AsignarRolSerializer(data=request.data)
        datos.is_valid(raise_exception=True)

        try:
            objetivo = Usuario.objects.get(pk=pk, rol=Rol.PENDIENTE)
        except Usuario.DoesNotExist:
            return Response({'detail': 'La cuenta no existe o ya tiene rol asignado.'}, status=404)

        if request.user.rol != Rol.SUPERADMIN:
            if objetivo.condominio_id not in (None, request.user.condominio_id):
                return Response({'detail': 'La cuenta pertenece a otra comunidad.'}, status=403)

        objetivo.rol = datos.validated_data['rol']
        if objetivo.condominio_id is None:
            objetivo.condominio = request.user.condominio

        persona_id = datos.validated_data.get('persona_id')
        if persona_id:
            from condominios.models import Persona
            try:
                persona = Persona.objects.get(id=persona_id, condominio=objetivo.condominio)
            except Persona.DoesNotExist:
                return Response({'detail': 'La ficha de persona no existe en la comunidad.'}, status=400)
            objetivo.persona = persona

        objetivo.save()
        return Response(UsuarioSerializer(objetivo).data)
