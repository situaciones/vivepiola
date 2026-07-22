from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import InfraccionCatalogoViewSet, ReglamentoViewSet

router = DefaultRouter()
router.register('reglamentos', ReglamentoViewSet, basename='reglamento')
router.register('infracciones', InfraccionCatalogoViewSet, basename='infraccion')

urlpatterns = [
    path('', include(router.urls)),
]
