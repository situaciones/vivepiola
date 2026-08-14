from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DelegacionViewSet, MedidaInmediataViewSet, MultaViewSet, TicketViewSet
from .views_acuse import AcuseNotificacionView, ApelarView, DocumentoNotificacionView

router = DefaultRouter()
router.register('tickets', TicketViewSet, basename='ticket')
router.register('multas', MultaViewSet, basename='multa')
router.register('medidas-inmediatas', MedidaInmediataViewSet, basename='medida_inmediata')
router.register('delegaciones', DelegacionViewSet, basename='delegacion')

urlpatterns = [
    # Publicas a proposito: el buzon del residente tiene que funcionar sin
    # cuenta. Los tres canales (app, correo, WhatsApp) llevan a este enlace.
    path('notificaciones/acuse/<str:token>/', AcuseNotificacionView.as_view(), name='acuse_notificacion'),
    path('notificaciones/documento/<str:token>/', DocumentoNotificacionView.as_view(), name='documento_notificacion'),
    path('notificaciones/apelar/<str:token>/', ApelarView.as_view(), name='apelar_notificacion'),
    path('', include(router.urls)),
]
