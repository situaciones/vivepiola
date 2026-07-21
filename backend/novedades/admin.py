from django.contrib import admin

from .models import NovedadLibro


@admin.register(NovedadLibro)
class NovedadLibroAdmin(admin.ModelAdmin):
    list_display = ('id', 'condominio', 'unidad', 'tipo', 'estado', 'fecha_limite_respuesta', 'fecha_creacion')
    list_filter = ('condominio', 'tipo', 'estado')
