from django.contrib import admin
from .models import Archivo
# Register your models here.

class ArchivoAdmin(admin.ModelAdmin):
    # Configurar las columnas que se mostrarán en la lista del admin
    list_display = ('nombre', 'usuario', 'descripcion_corta', 'fecha_subida')  # Muestra estas columnas
    list_filter = ('usuario', 'fecha_subida')  # Filtrar por usuario y fecha
    search_fields = ('nombre', 'descripcion', 'usuario__username')  # Campos de búsqueda
    date_hierarchy = 'fecha_subida'  # Añade navegación jerárquica por fecha
    ordering = ('-fecha_subida',)  # Orden descendente por fecha de subida

    # Método para mostrar una versión corta de la descripción
    def descripcion_corta(self, obj):
        return (obj.descripcion[:50] + '...') if len(obj.descripcion) > 50 else obj.descripcion
    descripcion_corta.short_description = 'Descripción'

# Registra el modelo en el administrador
admin.site.register(Archivo, ArchivoAdmin)