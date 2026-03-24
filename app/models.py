"""
models.py — Definición de la Base de Datos (Modelos)
===================================================
Este archivo define la estructura de datos de BIGDATALAB usando el ORM de Django.
Se divide en tres pilares:
  1. Perfiles de Usuario: Extensión del modelo User de Django para roles y 2FA.
  2. Gestión de Archivos: Almacenamiento genérico de documentos.
  3. Catálogo de Modelos ML: Modelos ONNX/PKL, metadatos técnicos y telemetría.

Además, contiene 'Signals' (señales) para la limpieza automática de archivos
físicos cuando se eliminan o actualizan registros en la BD.
"""
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver


# ============================================================
# 0. CATÁLOGO DE CATEGORÍAS (dinámico)
# ============================================================

# Lista de categorías predefinidas para sembrar la BD al inicio
CATEGORIAS_PREDEFINIDAS = [
    'fresa', 'cacao', 'manzana', 'tomate', 'café', 'plátano', 'palma'
]

class Categoria(models.Model):
    """Categoría de un modelo ML. El administrador puede agregar nuevas al subir un modelo."""
    nombre = models.CharField(max_length=100, unique=True, verbose_name='Nombre')

    class Meta:
        ordering = ['nombre']
        verbose_name = 'Categoría'
        verbose_name_plural = 'Categorías'

    def __str__(self):
        return self.nombre.capitalize()


# ============================================================
# 1. PERFILES Y ROLES DE USUARIO
# ============================================================

class UserProfile(models.Model):
    # Roles disponibles en la plataforma
    ROL_CHOICES = [
        ('admin', 'Administrador'),  # Puede crear, editar y eliminar modelos
        ('user',  'Usuario'),        # Solo puede ver y ejecutar (consumir) modelos
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    otp_code = models.CharField(max_length=6, blank=True, null=True)
    otp_created_at = models.DateTimeField(blank=True, null=True)

    # Rol del usuario dentro de la plataforma (independiente del sistema de permisos de Django)
    rol = models.CharField(max_length=10, choices=ROL_CHOICES, default='user',
                           verbose_name='Rol')

    def __str__(self):
        return f"Perfil de {self.user.username} ({self.get_rol_display()})"

    def es_admin(self):
        """Devuelve True si el usuario tiene rol de administrador o es superusuario de Django."""
        return self.rol == 'admin' or self.user.is_superuser


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        # Los superusuarios de Django obtienen rol admin automáticamente
        rol_inicial = 'admin' if instance.is_superuser else 'user'
        UserProfile.objects.create(user=instance, rol=rol_inicial)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if not hasattr(instance, 'profile'):
        UserProfile.objects.create(user=instance)
    instance.profile.save()

# Modelo de Archivos Genéricos (Datasets, Papers Sueltos, etc)
class Archivo(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    nombre = models.CharField(max_length=255)
    descripcion = models.TextField()
    archivo = models.FileField(upload_to='archivos/')
    fecha_subida = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nombre

# Catálogo de Modelos Machine Learning
class ModeloML(models.Model):
    ESTADO_CHOICES = [
        ('activo', 'Activo'),
        ('inactivo', 'Inactivo'),
        ('entrenamiento', 'En Entrenamiento'),
    ]

    nombre = models.CharField(max_length=255)
    nombre_estudio = models.CharField(max_length=255, verbose_name='Nombre del Estudio')
    descripcion = models.TextField()
    # Categoría libre (sin choices fijos) — se relaciona con el modelo Categoria
    categoria = models.CharField(max_length=100)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='activo')

    archivo_modelo = models.FileField(
        upload_to='modelos_ml/',
        verbose_name='Archivo del Modelo (.onnx, .pkl)',
        help_text='Sube el archivo de tu modelo entrenado (formatos aceptados: .onnx, .pkl)'
    )
    documento_estudio = models.FileField(
        upload_to='estudios_pdf/',
        verbose_name='Documento del Estudio (PDF)',
        blank=True,
        null=True,
        help_text='Documento PDF con la investigación o estudio relacionado'
    )

    precision = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name='Precisión (%)',
        help_text='Precisión del modelo en porcentaje (ej: 95.87)'
    )

    # Campos de Configuración de Inferencia Dinámica
    img_width = models.IntegerField(
        default=28,
        verbose_name='Ancho de Entrada (px)',
        help_text='Ancho esperado de la imagen por el modelo ONNX (ej: 28, 224).'
    )

    img_height = models.IntegerField(
        default=28,
        verbose_name='Alto de Entrada (px)',
        help_text='Alto esperado de la imagen por el modelo ONNX (ej: 28, 224).'
    )

    es_rgb = models.BooleanField(
        default=False,
        verbose_name='¿Es RGB (A color)?',
        help_text='Marca esta opción si el modelo fue entrenado con imágenes a color. Déjalo vacío si es en escala de grises.'
    )

    invertir_colores = models.BooleanField(
        default=False,
        verbose_name='¿Invertir Colores?',
        help_text='Ideal para modelos como MNIST que esperan trazos blancos sobre fondo negro.'
    )

    nombres_clases = models.TextField(
        blank=True,
        null=True,
        verbose_name='Nombres de las Clases',
        help_text='Nombres separados por comas. Ej: "Manzana Sana,Manzana Enferma". Convierte el resultado numérico en texto legible.'
    )

    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='modelos_ml')
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-fecha_creacion']
        verbose_name = 'Modelo ML'
        verbose_name_plural = 'Modelos ML'

    def __str__(self):
        return self.nombre


from django.db.models.signals import post_delete, pre_save

# Señal para eliminar el archivo del almacenamiento al eliminar la instancia (Archivo)
@receiver(post_delete, sender=Archivo)
def eliminar_archivo(sender, instance, **kwargs):
    if instance.archivo:
        instance.archivo.delete(False)

# Señal para eliminar el archivo anterior antes de actualizar (Archivo)
@receiver(pre_save, sender=Archivo)
def actualizar_archivo(sender, instance, **kwargs):
    if not instance.pk:
        return
    try:
        old_instance = Archivo.objects.get(pk=instance.pk)
        if old_instance.archivo and old_instance.archivo != instance.archivo:
            old_instance.archivo.delete(save=False)
    except Archivo.DoesNotExist:
        pass


# Señales para eliminar los archivos de ModeloML (ONNX y PDF)
@receiver(post_delete, sender=ModeloML)
def eliminar_archivos_modeloml(sender, instance, **kwargs):
    if instance.archivo_modelo:
        instance.archivo_modelo.delete(False)
    if instance.documento_estudio:
        instance.documento_estudio.delete(False)

@receiver(pre_save, sender=ModeloML)
def actualizar_archivos_modeloml(sender, instance, **kwargs):
    if not instance.pk:
        return
    try:
        old_instance = ModeloML.objects.get(pk=instance.pk)
        if old_instance.archivo_modelo and old_instance.archivo_modelo != instance.archivo_modelo:
            old_instance.archivo_modelo.delete(save=False)
        if old_instance.documento_estudio and old_instance.documento_estudio != instance.documento_estudio:
            old_instance.documento_estudio.delete(save=False)
    except ModeloML.DoesNotExist:
        pass