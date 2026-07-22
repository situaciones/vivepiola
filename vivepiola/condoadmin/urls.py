from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('accounts.urls')),
    path('api/', include('condominios.urls')),
    path('api/', include('reglamentos.urls')),
    path('api/', include('multas.urls')),
    path('api/', include('novedades.urls')),
    path('api/', include('gastos_comunes.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
