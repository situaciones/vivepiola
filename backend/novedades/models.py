from django.conf import settings
from django.db import models
from django.utils import timezone


class TipoNovedad(models.TextChoices):
    RECLAMO = 'RECLAMO', 'Reclamo'
    SOLICITUD = 'SOLICITUD', 'Solicitud'
    OBSERVACION = 'OBSERVACION', 'Observacion'


class EstadoNovedad(models.TextChoices):
    PENDIENTE = 'PENDIENTE', 'Pendiente'
    RESPONDIDA = 'RESPONDIDA', 'Respondida'
    VENCIDA = 'VENCIDA', 'Vencida (fuera de plazo legal)'


class NovedadLibro(models.Model):
    """
    Libro de Novedades Digital exigido por la ley: reclamos y solicitudes
    dirigidas a la administracion deben responderse en un plazo maximo de
    20 dias corridos (configurable por condominio).
    """

    condominio = models.ForeignKey('condominios.Condominio', on_delete=models.CASCADE, related_name='novedades')
    unidad = models.ForeignKey(
        'condominios.Unidad', on_delete=models.SET_NULL, null=True, blank=True, related_name='novedades'
    )
    solicitante = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    tipo = models.CharField(max_length=20, choices=TipoNovedad.choices)
    texto = models.TextField()
    plazo_respuesta_dias = models.PositiveSmallIntegerField(default=20)
    fecha_limite_respuesta = models.DateTimeField()
    estado = models.CharField(max_length=20, choices=EstadoNovedad.choices, default=EstadoNovedad.PENDIENTE)
    respondida_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='novedades_respondidas'
    )
    respuesta_texto = models.TextField(blank=True)
    fecha_respuesta = models.DateTimeField(null=True, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha_creacion']

    def __str__(self):
        return f'Novedad #{self.id} - {self.get_tipo_display()} ({self.condominio.nombre})'

    @property
    def dias_restantes(self):
        delta = self.fecha_limite_respuesta - timezone.now()
        return delta.days

    @property
    def esta_vencida(self):
        return self.estado == EstadoNovedad.PENDIENTE and timezone.now() > self.fecha_limite_respuesta
