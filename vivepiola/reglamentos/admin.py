from django.contrib import admin

from .models import NormaTransversal, InfraccionCatalogo, Reglamento


@admin.register(Reglamento)
class ReglamentoAdmin(admin.ModelAdmin):
    list_display = ('condominio', 'version', 'vigente', 'procesado_ia', 'fecha_carga')
    list_filter = ('condominio', 'vigente')


@admin.register(InfraccionCatalogo)
class InfraccionCatalogoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'descripcion', 'condominio', 'monto', 'unidad_monto', 'estado', 'generado_por_ia')
    list_filter = ('condominio', 'estado', 'gravedad', 'generado_por_ia')
    search_fields = ('codigo', 'descripcion')


@admin.register(NormaTransversal)
class NormaTransversalAdmin(admin.ModelAdmin):
    """
    La base normativa la mantiene la plataforma, no los condominios. Se
    administra desde aqui o con el comando cargar_normativa.
    """

    list_display = ('identificador', 'tipo', 'vigente', 'cargada', 'actualizada_en')
    list_filter = ('tipo', 'vigente')
    search_fields = ('identificador', 'titulo', 'texto')
    readonly_fields = ('actualizada_en',)

    @admin.display(boolean=True, description='Con texto')
    def cargada(self, obj):
        return obj.cargada
