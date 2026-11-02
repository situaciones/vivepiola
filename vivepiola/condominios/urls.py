from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views_comite import (
    DesignarComiteView, ElegiblesComiteView, EstadoComiteView, ReenviarAccesoComiteView,
)
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
    path('comite/', EstadoComiteView.as_view(), name='estado_comite'),
    path('comite/elegibles/', ElegiblesComiteView.as_view(), name='elegibles_comite'),
    path('comite/designar/', DesignarComiteView.as_view(), name='designar_comite'),
    path('comite/miembros/<int:pk>/reenviar/', ReenviarAccesoComiteView.as_view(), name='reenviar_acceso_comite'),
    path('', include(router.urls)),
]
