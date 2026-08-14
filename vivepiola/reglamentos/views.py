from django.db import transaction
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from accounts.permissions import UsuarioAsignado
from rest_framework.response import Response

from accounts.models import Rol
from accounts.permissions import EsAdministrador, EsComiteOAdministrador

from .models import EstadoInfraccion, InfraccionCatalogo, Reglamento
from .serializers import InfraccionCatalogoSerializer, ReglamentoSerializer
from .utils import normalizar_sugerencia, sugerir_infracciones_desde_texto


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
        # El texto ya se extrajo y valido en el serializer: si el PDF no era
        # legible, aqui no se llega y no queda nada guardado.
        serializer.save(condominio=self.request.user.condominio, cargado_por=self.request.user)

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

        if not isinstance(sugerencias, list):
            return Response(
                {'detail': 'El modelo de IA no devolvio una lista de infracciones.'}, status=502,
            )

        creadas = []
        omitidas = []
        # Todo o nada: si algo falla a mitad del lote, el catalogo no queda a medias.
        with transaction.atomic():
            for item in sugerencias:
                datos = normalizar_sugerencia(item)
                if datos is None:
                    continue

                existente = InfraccionCatalogo.objects.filter(
                    condominio=reglamento.condominio, codigo=datos['codigo'],
                ).first()
                if existente and existente.estado != EstadoInfraccion.BORRADOR:
                    # Nunca degradar una infraccion ya confirmada (o descartada) por
                    # un humano: las multas cursadas dependen de su validez.
                    omitidas.append(datos['codigo'])
                    continue

                infraccion, _ = InfraccionCatalogo.objects.update_or_create(
                    condominio=reglamento.condominio,
                    codigo=datos['codigo'],
                    defaults={
                        **datos,
                        'reglamento': reglamento,
                        'estado': EstadoInfraccion.BORRADOR,
                        'generado_por_ia': True,
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
    permission_classes = [UsuarioAsignado]
    filterset_fields = ['estado', 'gravedad', 'generado_por_ia']

    def get_queryset(self):
        user = self.request.user
        qs = InfraccionCatalogo.objects.all()
        if user.rol != Rol.SUPERADMIN:
            qs = qs.filter(condominio_id=user.condominio_id)
        if user.rol == Rol.RESIDENTE:
            # El residente solo ve el catalogo vigente.
            qs = qs.filter(estado=EstadoInfraccion.ACTIVA)
        # El Comite ve TODO el catalogo, incluidos los borradores: confirmarlos
        # es su trabajo. Que solo pueda fundar una multa en una infraccion
        # ACTIVA se garantiza al aprobar (MultaViewSet.aprobar), no escondiendole
        # aqui los borradores que debe revisar.
        return qs

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy', 'confirmar', 'rechazar'):
            return [EsComiteOAdministrador()]
        return [UsuarioAsignado()]

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
