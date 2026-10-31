from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    AsignarRolView, DenunciantesView, EliminarCuentaView, GoogleLoginView, InvitacionViewSet, MeView,
    PermisoDenunciaView,
    UsuariosPendientesView, SinConflictoTokenObtainPairView,
)

router = DefaultRouter()
router.register('invitaciones', InvitacionViewSet, basename='invitacion')

urlpatterns = [
    path('auth/login/', SinConflictoTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/google/', GoogleLoginView.as_view(), name='google_login'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/me/', MeView.as_view(), name='me'),
    path('auth/me/eliminar/', EliminarCuentaView.as_view(), name='eliminar_cuenta'),
    path('usuarios/pendientes/', UsuariosPendientesView.as_view(), name='usuarios_pendientes'),
    path('usuarios/<int:pk>/asignar-rol/', AsignarRolView.as_view(), name='asignar_rol'),
    path('usuarios/denunciantes/', DenunciantesView.as_view(), name='denunciantes'),
    path(
        'usuarios/<int:pk>/permiso-denuncia/', PermisoDenunciaView.as_view(),
        name='permiso_denuncia',
    ),
    path('', include(router.urls)),
]
