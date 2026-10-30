from django.urls import path

from .views import SolicitudDemoView

urlpatterns = [
    path('contacto/demo/', SolicitudDemoView.as_view(), name='solicitud_demo'),
]
