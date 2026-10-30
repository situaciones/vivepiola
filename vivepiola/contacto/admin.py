from django.contrib import admin

from .models import SolicitudDemo


@admin.register(SolicitudDemo)
class SolicitudDemoAdmin(admin.ModelAdmin):
    list_display = ('creada_en', 'nombre', 'correo', 'empresa', 'atendida')
    list_filter = ('atendida',)
    list_editable = ('atendida',)
    search_fields = ('nombre', 'correo', 'empresa')
    readonly_fields = ('nombre', 'correo', 'empresa', 'creada_en')
