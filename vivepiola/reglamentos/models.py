from decimal import Decimal

from django.conf import settings
from django.db import models

# La base normativa transversal de Chile vive en su propio modulo porque no
# pertenece a ningun condominio: la mantiene la plataforma.
from .normativa import (  # noqa: F401  (se reexporta para que Django registre los modelos)
    FragmentoNormativo, FuenteNormativa, TipoFuente, buscar_normativa,
    contexto_normativo, estado_del_corpus, indexar_fuente,
)


class TipoNorma(models.TextChoices):
    """
    Que clase de documento es. Una comunidad no se rige por un solo texto: al
    reglamento de copropiedad se suman los instructivos de estacionamientos y
    espacios comunes, las normas de seguridad, la normativa ambiental y los
    acuerdos de asamblea, que obligan igual que el reglamento.

    Importa mas alla de la etiqueta: el acta se lee distinto que el reglamento
    (tiene acuerdos, no articulos), y la infraccion que salga de ella debe
    citar el acuerdo y su fecha, no un articulo inexistente.
    """

    REGLAMENTO_COPROPIEDAD = 'REGLAMENTO_COPROPIEDAD', 'Reglamento de copropiedad'
    ESTACIONAMIENTOS = 'ESTACIONAMIENTOS', 'Normas de uso de estacionamientos'
    ESPACIOS_COMUNES = 'ESPACIOS_COMUNES', 'Normas de uso de espacios comunes'
    SEGURIDAD = 'SEGURIDAD', 'Normas de seguridad'
    AMBIENTAL = 'AMBIENTAL', 'Normativa ambiental'
    ACTA_ASAMBLEA = 'ACTA_ASAMBLEA', 'Acta o acuerdo de asamblea'
    OTRO = 'OTRO', 'Otro cuerpo normativo'


class Reglamento(models.Model):
    """
    Un cuerpo normativo de la comunidad, en PDF: base legal del catalogo.

    Se sigue llamando Reglamento porque asi lo referencia el resto del sistema,
    pero ya no es solo el reglamento de copropiedad: ver TipoNorma.
    """

    condominio = models.ForeignKey(
        'condominios.Condominio', on_delete=models.CASCADE, related_name='reglamentos'
    )
    tipo = models.CharField(
        max_length=30, choices=TipoNorma.choices, default=TipoNorma.REGLAMENTO_COPROPIEDAD,
    )
    titulo = models.CharField(
        max_length=200, blank=True,
        help_text='Como lo conoce la comunidad. Ej: "Instructivo de estacionamientos 2026".',
    )
    # Fecha del documento, no de la carga: en un acta de asamblea es lo que
    # identifica el acuerdo y lo que se cita al sancionar.
    fecha_documento = models.DateField(null=True, blank=True)
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
        etiqueta = self.titulo or TipoNorma(self.tipo).label
        return f'{etiqueta} - {self.condominio.nombre}'

    @property
    def referencia_citable(self):
        """Como se nombra este documento al fundar una sancion."""
        if self.tipo == TipoNorma.ACTA_ASAMBLEA:
            fecha = self.fecha_documento.strftime('%d-%m-%Y') if self.fecha_documento else 's/f'
            return f'Acuerdo de asamblea del {fecha}'
        return self.titulo or TipoNorma(self.tipo).label


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
    # Multiplicador aplicado automaticamente al monto cuando la unidad reincide
    # en esta infraccion dentro de la ventana legal (Ley 21.442). 1.00 = sin
    # agravante automatico (el Comite decide); 2.00 = doble, etc.
    factor_reincidencia = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal('1.00'))
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
