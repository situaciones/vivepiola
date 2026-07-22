from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import GenerarLoteExportacionView, LoteExportacionViewSet

router = DefaultRouter()
router.register('gastos-comunes/lotes', LoteExportacionViewSet, basename='lote_gasto_comun')

urlpatterns = [
    path('gastos-comunes/exportar/', GenerarLoteExportacionView.as_view(), name='exportar_gastos_comunes'),
    path('', include(router.urls)),
]
