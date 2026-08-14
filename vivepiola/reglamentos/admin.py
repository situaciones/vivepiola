from django.contrib import admin, messages

from .models import (
    FragmentoNormativo, FuenteNormativa, InfraccionCatalogo, Reglamento,
)


@admin.register(Reglamento)
class ReglamentoAdmin(admin.ModelAdmin):
    list_display = ('condominio', 'version', 'vigente', 'procesado_ia', 'fecha_carga')
    list_filter = ('condominio', 'vigente')


@admin.register(InfraccionCatalogo)
class InfraccionCatalogoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'descripcion', 'condominio', 'monto', 'unidad_monto', 'estado', 'generado_por_ia')
    list_filter = ('condominio', 'estado', 'gravedad', 'generado_por_ia')
    search_fields = ('codigo', 'descripcion')


@admin.register(FuenteNormativa)
class FuenteNormativaAdmin(admin.ModelAdmin):
    """
    El panel del superadministrador de la plataforma.

    Aqui un abogado con experiencia en copropiedad decide que entra al corpus.
    No es una funcion de ningun condominio: es mantencion de la plataforma, y
    por eso vive en el admin de Django y no en la app de las comunidades.
    """

    list_display = ('identificador', 'tipo', 'vigente', 'indexada', 'total_fragmentos', 'fecha_carga')
    list_filter = ('tipo', 'vigente')
    search_fields = ('identificador', 'titulo', 'texto')
    readonly_fields = ('texto', 'fecha_carga', 'indexada_en', 'cargada_por')
    actions = ('reindexar',)

    fieldsets = (
        ('Identificacion', {
            'fields': ('tipo', 'identificador', 'titulo', 'fecha_documento'),
            'description': (
                'El identificador es lo que se cita en el fundamento de una sancion. '
                'Escribelo como se cita: "Ley 21.442", "Circular MINVU 15/2026".'
            ),
        }),
        ('Fuente', {
            'fields': ('archivo', 'url_fuente'),
            'description': 'Sube el PDF o Word, o pega la URL. Se admite uno de los dos.',
        }),
        ('Vigencia', {'fields': ('vigente', 'nota_version')}),
        ('Estado', {'fields': ('texto', 'indexada_en', 'cargada_por', 'fecha_carga')}),
    )

    @admin.display(boolean=True, description='Indexada')
    def indexada(self, obj):
        return obj.indexada

    @admin.display(description='Fragmentos')
    def total_fragmentos(self, obj):
        return obj.total_fragmentos

    def save_model(self, request, obj, form, change):
        """Al guardar se extrae el texto y se indexa: sin eso la fuente no se consulta."""
        from .fuentes import FuenteIlegible, extraer_texto
        from .normativa import indexar_fuente

        if obj.cargada_por_id is None:
            obj.cargada_por = request.user
        super().save_model(request, obj, form, change)

        cambio_la_fuente = 'archivo' in form.changed_data or 'url_fuente' in form.changed_data
        if not (cambio_la_fuente or not obj.texto):
            return

        try:
            if obj.archivo:
                obj.archivo.open('rb')
                texto = extraer_texto(archivo=obj.archivo, nombre=obj.archivo.name)
                obj.archivo.close()
            elif obj.url_fuente:
                texto = extraer_texto(url=obj.url_fuente)
            else:
                messages.warning(request, 'Sin archivo ni URL: no hay nada que indexar.')
                return
        except FuenteIlegible as exc:
            messages.error(request, f'No se pudo leer la fuente: {exc}')
            return

        cuantos = indexar_fuente(obj, texto=texto)
        messages.success(request, f'Fuente indexada en {cuantos} fragmento(s) citables.')

    @admin.action(description='Volver a indexar las fuentes seleccionadas')
    def reindexar(self, request, queryset):
        from .normativa import indexar_fuente

        total = sum(indexar_fuente(f) for f in queryset.exclude(texto=''))
        messages.success(request, f'Reindexados {total} fragmento(s).')


@admin.register(FragmentoNormativo)
class FragmentoNormativoAdmin(admin.ModelAdmin):
    """Solo lectura: sirve para revisar como quedo troceada una fuente."""

    list_display = ('fuente', 'referencia', 'largo', 'buscable')
    list_filter = ('fuente__tipo', 'fuente')
    search_fields = ('referencia', 'texto')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description='Caracteres')
    def largo(self, obj):
        return len(obj.texto)

    @admin.display(boolean=True, description='Buscable')
    def buscable(self, obj):
        return obj.vector is not None
