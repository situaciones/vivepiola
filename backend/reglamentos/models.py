from django.conf import settings
from django.db import models


class Reglamento(models.Model):
    """PDF del reglamento de copropiedad vigente, base legal del catalogo de infracciones."""

    condominio = models.ForeignKey(
        'condominios.Condominio', on_delete=models.CASCADE, related_name='reglamentos'
    )
    archivo_pdf = models.FileField(upload_to='reglamentos/%Y/%m/')
    version = models.CharField(max_length=50, blank=True)
    vigente = models.BooleanField(default=True)
    cargado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    fecha_carga = models.DateTimeField(auto_now_add=True)
    texto_extraido = models.TextField(blank=True, help_text='Texto plano extraido del PDF (para la IA y busqueda).')
    procesado_ia = models.BooleanField(default=False)

    class Meta:
        ordering = ['-fecha_carga']

    def __str__(self):
        return f'Reglamento {self.condominio.nombre} v{self.version or self.id}'


class EstadoInfraccion(models.TextChoices):
    BORRADOR = 'BORRADOR', 'Borrador (sugerido por IA, sin confirmar)'
    ACTIVA = 'ACTIVA', 'Activa'
    INACTIVA = 'INACTIVA', 'Inactiva'


class Gravedad(models.TextChoices):
    LEVE = 'LEVE', 'Leve'
    GRAVE = 'GRAVE', 'Grave'
    GRAVISIMA = 'GRAVISIMA', 'Gravisima'


class InfraccionCatalogo(models.Model):
    """
    Catalogo de infracciones del reglamento local. Solo las infracciones en
    estado ACTIVA (revisadas y confirmadas por un humano) pueden ser
    seleccionadas por el Comite al aprobar una multa: una sancion nunca
    puede fundarse en un borrador generado por IA sin revision.
    """

    condominio = models.ForeignKey(
        'condominios.Condominio', on_delete=models.CASCADE, related_name='infracciones'
    )
    reglamento = models.ForeignKey(
        Reglamento, on_delete=models.SET_NULL, null=True, blank=True, related_name='infracciones'
    )
    codigo = models.CharField(max_length=30)
    descripcion = models.CharField(max_length=500)
    articulo_referencia = models.CharField(max_length=100, blank=True)
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    unidad_monto = models.CharField(
        max_length=10,
        choices=[('CLP', 'Pesos chilenos'), ('UF', 'UF'), ('UTM', 'UTM')],
        default='UF',
    )
    gravedad = models.CharField(max_length=20, choices=Gravedad.choices, default=Gravedad.LEVE)
    estado = models.CharField(max_length=20, choices=EstadoInfraccion.choices, default=EstadoInfraccion.BORRADOR)
    # Contencion: la calificacion juridica se hace EN FRIO al configurar el
    # catalogo, nunca en terreno. Si conlleva_contencion=True, reportar este
    # hallazgo detona una MedidaInmediata cuyo plazo de ratificacion es este.
    conlleva_contencion = models.BooleanField(default=False)
    plazo_ratificacion_horas = models.PositiveSmallIntegerField(default=24)
    # Quorum K-de-N fijo por politica de riesgo (no por disponibilidad del
    # personal): "si es GRAVE, firman 2, sin excusas". 1 = ratificacion simple.
    quorum_ratificacion = models.PositiveSmallIntegerField(default=1)
    generado_por_ia = models.BooleanField(default=False)
    texto_fuente = models.TextField(
        blank=True, help_text='Fragmento del reglamento usado por la IA para sugerir esta infraccion (trazabilidad).'
    )
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    confirmado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='infracciones_confirmadas',
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_confirmacion = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['codigo']
        unique_together = ('condominio', 'codigo')

    def __str__(self):
        return f'{self.codigo} - {self.descripcion[:60]}'
