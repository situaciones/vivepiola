from django.contrib import admin

from .models import CargoGastoComun, LoteExportacion


class CargoGastoComunInline(admin.TabularInline):
    model = CargoGastoComun
    extra = 0


@admin.register(LoteExportacion)
class LoteExportacionAdmin(admin.ModelAdmin):
    list_display = ('periodo', 'condominio', 'total_monto', 'fecha_generacion')
    list_filter = ('condominio',)
    inlines = [CargoGastoComunInline]
