from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import FileResponse, Http404
from django.urls import include, path, re_path


def app_web(request):
    """
    Entrega la app web (React) para cualquier ruta que no sea de la API.

    En la nube Django sirve tambien el frontend: los archivos con nombre
    (/assets/..., /sw.js) los entrega whitenoise, y las rutas del navegador
    (/app, /login, /acuse/...) caen aqui y reciben index.html para que React
    las resuelva.
    """
    index = settings.FRONTEND_DIST / 'index.html'
    if not index.exists():
        raise Http404('La app web no esta empaquetada en esta instalacion.')
    return FileResponse(open(index, 'rb'), content_type='text/html')

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

# Al final: todo lo que no sea API, admin, estaticos ni media es una ruta de la app web.
urlpatterns += [re_path(r'^(?!api/|admin/|static/|media/).*$', app_web)]
