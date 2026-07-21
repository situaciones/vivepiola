from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Rol
from accounts.permissions import EsAdministrador

from .models import LoteExportacion
from .serializers import GenerarLoteSerializer, LoteExportacionSerializer
from .utils import exportar_multas_firmes


class LoteExportacionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = LoteExportacionSerializer
    permission_classes = [EsAdministrador]

    def get_queryset(self):
        user = self.request.user
        qs = LoteExportacion.objects.all()
        if user.rol == Rol.SUPERADMIN:
            return qs
        return qs.filter(condominio_id=user.condominio_id)


class GenerarLoteExportacionView(APIView):
    """
    Exporta las multas FIRME (sin descargos/apelaciones pendientes) del
    condominio como cargos del aviso de cobro mensual de gastos comunes.
    """

    permission_classes = [EsAdministrador]

    def post(self, request):
        datos = GenerarLoteSerializer(data=request.data)
        datos.is_valid(raise_exception=True)

        lote = exportar_multas_firmes(request.user.condominio, datos.validated_data['periodo'], request.user)
        if lote is None:
            return Response({'detail': 'No hay multas firmes pendientes de exportar para este periodo.'}, status=400)
        return Response(LoteExportacionSerializer(lote).data, status=201)
