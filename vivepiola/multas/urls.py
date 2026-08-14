from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DelegacionViewSet, MedidaInmediataViewSet, MultaViewSet, TicketViewSet
from .views_acuse import AcuseNotificacionView

router = DefaultRouter()
router.register('tickets', TicketViewSet, basename='ticket')
router.register('multas', MultaViewSet, basename='multa')
router.register('medidas-inmediatas', MedidaInmediataViewSet, basename='medida_inmediata')
router.register('delegaciones', DelegacionViewSet, basename='delegacion')

urlpatterns = [
    # Publica a proposito: el acuse tiene que funcionar sin cuenta.
    path('notificaciones/acuse/<str:token>/', AcuseNotificacionView.as_view(), name='acuse_notificacion'),
    path('', include(router.urls)),
]
