from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import VivePiolaTokenObtainPairSerializer, UsuarioSerializer


class VivePiolaTokenObtainPairView(TokenObtainPairView):
    serializer_class = VivePiolaTokenObtainPairSerializer


class MeView(RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UsuarioSerializer
    http_method_names = ['get', 'patch']

    def get_object(self):
        return self.request.user
