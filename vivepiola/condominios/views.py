from django.http import HttpResponse
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Rol
from accounts.permissions import EsAdministrador, EsSuperadmin

from .models import Condominio, Persona, RegistroImportacion, Unidad
from .serializers import (
    CondominioSerializer, PersonaSerializer, RegistroImportacionSerializer, UnidadSerializer,
)
from .utils import generar_plantilla_excel, importar_registro_copropietarios


class CondominioViewSet(viewsets.ModelViewSet):
    """
    Alta y consulta de organizaciones (comunidades). Crear/editar/eliminar
    queda reservado al administrador del sistema (SUPERADMIN), que provisiona
    la comunidad nueva; el resto de los roles solo consulta la suya.
    """

    serializer_class = CondominioSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [EsSuperadmin()]
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        if user.rol == Rol.SUPERADMIN:
            return Condominio.objects.all()
        return Condominio.objects.filter(id=user.condominio_id)


class _CondominioScopedMixin:
    """
    Lectura para cualquier usuario autenticado del condominio; escritura solo
    para el Administrador, que es quien mantiene el registro exigido por la ley.
    """

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [EsAdministrador()]
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        qs = self.queryset_model.objects.all()
        if user.rol == Rol.SUPERADMIN:
            return qs
        return qs.filter(condominio_id=user.condominio_id)

    def perform_create(self, serializer):
        serializer.save(condominio=self.request.user.condominio)


class UnidadViewSet(_CondominioScopedMixin, viewsets.ModelViewSet):
    serializer_class = UnidadSerializer
    queryset_model = Unidad


class PersonaViewSet(_CondominioScopedMixin, viewsets.ModelViewSet):
    serializer_class = PersonaSerializer
    queryset_model = Persona
    filterset_fields = ['unidad', 'rol_ocupacion', 'activo']

    def perform_create(self, serializer):
        condominio = self.request.user.condominio
        unidad = serializer.validated_data.get('unidad')
        if unidad and unidad.condominio_id != condominio.id:
            raise ValidationError({'unidad': 'La unidad no pertenece a su condominio.'})
        serializer.save(condominio=condominio)


class PlantillaRegistroView(APIView):
    """Descarga la plantilla Excel obligatoria para la carga del registro de copropietarios."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        buffer = generar_plantilla_excel()
        response = HttpResponse(
            buffer.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = 'attachment; filename="plantilla_registro_copropietarios.xlsx"'
        return response


class ImportarRegistroView(APIView):
    """
    Carga masiva del registro de copropietarios. Reservado al Administrador:
    es quien mantiene actualizado el registro exigido por la ley.
    """

    permission_classes = [EsAdministrador]
    parser_classes = [MultiPartParser]

    def post(self, request):
        archivo = request.FILES.get('archivo')
        if not archivo:
            return Response({'detail': 'Debe adjuntar un archivo .xlsx o .csv.'}, status=400)

        condominio = request.user.condominio
        if condominio is None:
            return Response({'detail': 'Su cuenta no esta asociada a un condominio.'}, status=400)
        totales, ok, con_error, detalle = importar_registro_copropietarios(condominio, archivo)

        estado = RegistroImportacion.Estado.PROCESADO
        if con_error and ok:
            estado = RegistroImportacion.Estado.CON_ERRORES
        elif con_error and not ok:
            estado = RegistroImportacion.Estado.FALLIDO

        registro = RegistroImportacion.objects.create(
            condominio=condominio,
            archivo=archivo,
            cargado_por=request.user,
            filas_totales=totales,
            filas_ok=ok,
            filas_error=con_error,
            detalle_errores=detalle,
            estado=estado,
        )
        return Response(RegistroImportacionSerializer(registro).data, status=201)
