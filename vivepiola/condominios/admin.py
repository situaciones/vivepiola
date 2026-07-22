from django.contrib import admin

from .models import (
    CadenaEscalamiento, Condominio, NivelEscalamiento, Persona,
    RegistroImportacion, Unidad, Vertical,
)


@admin.register(Vertical)
class VerticalAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'slug', 'marco_legal_nombre', 'plazo_descargo_dias_default', 'plazo_ratificacion_horas_default')
    prepopulated_fields = {'slug': ('nombre',)}


class NivelEscalamientoInline(admin.TabularInline):
    model = NivelEscalamiento
    extra = 1
    filter_horizontal = ('usuarios',)


@admin.register(CadenaEscalamiento)
class CadenaEscalamientoAdmin(admin.ModelAdmin):
    list_display = ('condominio', 'version', 'activa', 'descripcion', 'creada_en')
    list_filter = ('condominio', 'activa')
    inlines = [NivelEscalamientoInline]


@admin.register(Condominio)
class CondominioAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'rut', 'vertical', 'plazo_descargo_dias')


@admin.register(Unidad)
class UnidadAdmin(admin.ModelAdmin):
    list_display = ('identificador', 'condominio', 'alicuota')
    list_filter = ('condominio',)


@admin.register(Persona)
class PersonaAdmin(admin.ModelAdmin):
    list_display = ('nombre_completo', 'cedula_identidad', 'rol_ocupacion', 'unidad', 'correo_electronico', 'activo')
    list_filter = ('condominio', 'rol_ocupacion', 'activo')
    search_fields = ('nombre_completo', 'cedula_identidad', 'correo_electronico')


@admin.register(RegistroImportacion)
class RegistroImportacionAdmin(admin.ModelAdmin):
    list_display = ('id', 'condominio', 'fecha_carga', 'estado', 'filas_ok', 'filas_error')
    list_filter = ('condominio', 'estado')
