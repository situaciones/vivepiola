from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import VivePiolaTokenObtainPairView, MeView

urlpatterns = [
    path('auth/login/', VivePiolaTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/me/', MeView.as_view(), name='me'),
]
