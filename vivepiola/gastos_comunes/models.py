from django.conf import settings
from django.db import models


class LoteExportacion(models.Model):
    """
    Agrupa las multas firmes exportadas en un periodo, para sumarlas al
    aviso de cobro mensual de gastos comunes (obligacion economica, Ley 21.442).
    """

    condominio = models.ForeignKey('condominios.Condominio', on_delete=models.CASCADE, related_name='lotes_exportacion')
    periodo = models.CharField(max_length=7, help_text='Formato AAAA-MM')
    generado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    archivo_csv = models.FileField(upload_to='gastos_comunes/%Y/%m/', null=True, blank=True)
    fecha_generacion = models.DateTimeField(auto_now_add=True)
    total_monto = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        ordering = ['-fecha_generacion']
        unique_together = ('condominio', 'periodo')

    def __str__(self):
        return f'Lote {self.periodo} - {self.condominio.nombre}'


class CargoGastoComun(models.Model):
    """Linea individual: una multa firme exportada como cargo de gastos comunes."""

    lote = models.ForeignKey(LoteExportacion, on_delete=models.CASCADE, related_name='cargos')
    multa = models.OneToOneField('multas.Multa', on_delete=models.CASCADE, related_name='cargo_gasto_comun')
    unidad = models.ForeignKey('condominios.Unidad', on_delete=models.CASCADE, related_name='cargos_gastos_comunes')
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    descripcion = models.CharField(max_length=255)

    def __str__(self):
        return f'Cargo multa #{self.multa_id} - {self.unidad.identificador}'
