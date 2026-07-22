from django.contrib import admin

from .models import Descargo, EvidenciaFoto, HistorialMulta, Multa, Ticket


class EvidenciaFotoInline(admin.TabularInline):
    model = EvidenciaFoto
    extra = 0


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('id', 'unidad', 'creado_por', 'estado', 'fecha_hecho', 'fecha_creacion')
    list_filter = ('condominio', 'estado')
    inlines = [EvidenciaFotoInline]


class HistorialMultaInline(admin.TabularInline):
    model = HistorialMulta
    extra = 0
    readonly_fields = ('estado_anterior', 'estado_nuevo', 'usuario', 'comentario', 'fecha')


@admin.register(Multa)
class MultaAdmin(admin.ModelAdmin):
    list_display = ('id', 'unidad', 'infraccion', 'monto', 'estado', 'es_reincidencia', 'fecha_creacion')
    list_filter = ('condominio', 'estado', 'es_reincidencia')
    inlines = [HistorialMultaInline]


@admin.register(Descargo)
class DescargoAdmin(admin.ModelAdmin):
    list_display = ('multa', 'presentado_por', 'resolucion', 'fecha_presentacion')
    list_filter = ('resolucion',)
