from django.urls import path

from .views import AsistenteView

urlpatterns = [
    path('asistente/', AsistenteView.as_view(), name='asistente'),
]
