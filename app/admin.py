from django.contrib import admin
from .models import Archivo, ModeloML

class ArchivoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'usuario', 'descripcion_corta', 'fecha_subida')
    list_filter = ('usuario', 'fecha_subida')
    search_fields = ('nombre', 'descripcion', 'usuario__username')
    date_hierarchy = 'fecha_subida'
    ordering = ('-fecha_subida',)

    def descripcion_corta(self, obj):
        return (obj.descripcion[:50] + '...') if len(obj.descripcion) > 50 else obj.descripcion
    descripcion_corta.short_description = 'Descripción'

admin.site.register(Archivo, ArchivoAdmin)

class ModeloMLAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'categoria', 'estado', 'precision', 'usuario', 'fecha_creacion')
    list_filter = ('categoria', 'estado', 'usuario')
    search_fields = ('nombre', 'nombre_estudio', 'descripcion')
    ordering = ('-fecha_creacion',)
    readonly_fields = ('fecha_creacion', 'fecha_actualizacion')

admin.site.register(ModeloML, ModeloMLAdmin)