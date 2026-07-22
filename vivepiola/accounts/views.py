from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import DebidoTokenObtainPairSerializer, UsuarioSerializer


class VivePiolaTokenObtainPairView(TokenObtainPairView):
    serializer_class = DebidoTokenObtainPairSerializer


class MeView(RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UsuarioSerializer
    http_method_names = ['get', 'patch']

    def get_object(self):
        return self.request.user
