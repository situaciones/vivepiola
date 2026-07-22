from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import Rol
from accounts.permissions import EsAdministrador, EsComiteOAdministrador

from .models import EstadoInfraccion, InfraccionCatalogo, Reglamento
from .serializers import InfraccionCatalogoSerializer, ReglamentoSerializer
from .utils import extraer_texto_pdf, sugerir_infracciones_desde_texto


class ReglamentoViewSet(viewsets.ModelViewSet):
    serializer_class = ReglamentoSerializer
    permission_classes = [EsAdministrador]

    def get_queryset(self):
        user = self.request.user
        qs = Reglamento.objects.all()
        if user.rol == Rol.SUPERADMIN:
            return qs
        return qs.filter(condominio_id=user.condominio_id)

    def perform_create(self, serializer):
        reglamento = serializer.save(condominio=self.request.user.condominio, cargado_por=self.request.user)
        try:
            texto = extraer_texto_pdf(reglamento.archivo_pdf)
            reglamento.texto_extraido = texto
            reglamento.save(update_fields=['texto_extraido'])
        except Exception:
            pass

    @action(detail=True, methods=['post'], url_path='generar-borradores-ia')
    def generar_borradores_ia(self, request, pk=None):
        """
        Genera sugerencias de infracciones con IA a partir del texto del PDF.
        Todas quedan en estado BORRADOR: ninguna es utilizable por el Comite
        hasta que un humano las confirme (ver InfraccionCatalogoViewSet.confirmar).
        """
        reglamento = self.get_object()
        if not reglamento.texto_extraido:
            return Response({'detail': 'No se pudo extraer texto del PDF de este reglamento.'}, status=400)

        try:
            sugerencias = sugerir_infracciones_desde_texto(reglamento.texto_extraido)
        except Exception as exc:
            return Response({'detail': f'Error consultando el modelo de IA: {exc}'}, status=502)

        creadas = []
        omitidas = []
        for item in sugerencias:
            codigo = str(item.get('codigo') or '').strip()
            if not codigo:
                continue

            existente = InfraccionCatalogo.objects.filter(
                condominio=reglamento.condominio, codigo=codigo,
            ).first()
            if existente and existente.estado != EstadoInfraccion.BORRADOR:
                # Nunca degradar una infraccion ya confirmada (o descartada) por
                # un humano: las multas cursadas dependen de su validez.
                omitidas.append(codigo)
                continue

            infraccion, _ = InfraccionCatalogo.objects.update_or_create(
                condominio=reglamento.condominio,
                codigo=codigo,
                defaults={
                    'reglamento': reglamento,
                    'descripcion': item.get('descripcion', '')[:500],
                    'articulo_referencia': item.get('articulo_referencia', '')[:100],
                    'monto': item.get('monto') or 0,
                    'unidad_monto': item.get('unidad_monto', 'UF'),
                    'gravedad': item.get('gravedad', 'LEVE'),
                    'estado': EstadoInfraccion.BORRADOR,
                    'generado_por_ia': True,
                    'texto_fuente': item.get('texto_fuente', ''),
                    'creado_por': request.user,
                },
            )
            creadas.append(infraccion)

        reglamento.procesado_ia = True
        reglamento.save(update_fields=['procesado_ia'])

        return Response(
            {
                'borradores': InfraccionCatalogoSerializer(creadas, many=True).data,
                'omitidas': omitidas,
            },
            status=status.HTTP_201_CREATED,
        )


class InfraccionCatalogoViewSet(viewsets.ModelViewSet):
    serializer_class = InfraccionCatalogoSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['estado', 'gravedad', 'generado_por_ia']

    def get_queryset(self):
        user = self.request.user
        qs = InfraccionCatalogo.objects.all()
        if user.rol != Rol.SUPERADMIN:
            qs = qs.filter(condominio_id=user.condominio_id)
        if user.rol in (Rol.COMITE, Rol.RESIDENTE):
            # El Comite (al aprobar multas) y el residente solo deben ver el catalogo vigente.
            qs = qs.filter(estado=EstadoInfraccion.ACTIVA)
        return qs

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy', 'confirmar', 'rechazar'):
            return [EsComiteOAdministrador()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(condominio=self.request.user.condominio, creado_por=self.request.user)

    @action(detail=True, methods=['post'])
    def confirmar(self, request, pk=None):
        """
        Activa una infraccion (sea manual o borrador de IA) en el catalogo oficial.
        Este es el punto de control humano obligatorio antes de que una infraccion
        pueda ser usada como fundamento de una multa.
        """
        infraccion = self.get_object()
        infraccion.estado = EstadoInfraccion.ACTIVA
        infraccion.confirmado_por = request.user
        infraccion.fecha_confirmacion = timezone.now()
        infraccion.save(update_fields=['estado', 'confirmado_por', 'fecha_confirmacion'])
        return Response(InfraccionCatalogoSerializer(infraccion).data)

    @action(detail=True, methods=['post'])
    def rechazar(self, request, pk=None):
        infraccion = self.get_object()
        infraccion.estado = EstadoInfraccion.INACTIVA
        infraccion.save(update_fields=['estado'])
        return Response(InfraccionCatalogoSerializer(infraccion).data)
