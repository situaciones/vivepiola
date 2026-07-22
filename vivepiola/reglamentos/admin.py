from django.contrib import admin

from .models import InfraccionCatalogo, Reglamento


@admin.register(Reglamento)
class ReglamentoAdmin(admin.ModelAdmin):
    list_display = ('condominio', 'version', 'vigente', 'procesado_ia', 'fecha_carga')
    list_filter = ('condominio', 'vigente')


@admin.register(InfraccionCatalogo)
class InfraccionCatalogoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'descripcion', 'condominio', 'monto', 'unidad_monto', 'estado', 'generado_por_ia')
    list_filter = ('condominio', 'estado', 'gravedad', 'generado_por_ia')
    search_fields = ('codigo', 'descripcion')
