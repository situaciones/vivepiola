from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import NovedadLibroViewSet

router = DefaultRouter()
router.register('novedades', NovedadLibroViewSet, basename='novedad')

urlpatterns = [
    path('', include(router.urls)),
]
