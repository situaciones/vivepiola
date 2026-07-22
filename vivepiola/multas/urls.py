from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DelegacionViewSet, MedidaInmediataViewSet, MultaViewSet, TicketViewSet

router = DefaultRouter()
router.register('tickets', TicketViewSet, basename='ticket')
router.register('multas', MultaViewSet, basename='multa')
router.register('medidas-inmediatas', MedidaInmediataViewSet, basename='medida_inmediata')
router.register('delegaciones', DelegacionViewSet, basename='delegacion')

urlpatterns = [
    path('', include(router.urls)),
]
