from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CondominioViewSet, ImportarRegistroView, PersonaViewSet, PlantillaRegistroView, UnidadViewSet,
)

router = DefaultRouter()
router.register('condominios', CondominioViewSet, basename='condominio')
router.register('unidades', UnidadViewSet, basename='unidad')
router.register('personas', PersonaViewSet, basename='persona')

urlpatterns = [
    path('registro/plantilla/', PlantillaRegistroView.as_view(), name='plantilla_registro'),
    path('registro/importar/', ImportarRegistroView.as_view(), name='importar_registro'),
    path('', include(router.urls)),
]
