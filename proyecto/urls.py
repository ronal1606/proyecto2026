
from django.contrib import admin
from django.urls import path, include

# Handler personalizado para páginas no encontradas (404)
# Se activa cuando DEBUG=False en settings.py
handler404 = 'app.views.pagina_404'

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('app.urls')),
]
