"""
urls.py — Enrutador principal de la aplicación 'app'
=====================================================
Define TODAS las rutas (URLs) que la aplicación maneja.
Cada path() mapea una URL a una función definida en views.py.

Estructura general:
  - Autenticación:  index, register, verify-2fa, logout
  - Dashboard:      dashboard, nosotros
  - Módulo ML:      modelos/ (lista, crear, detalle, ejecutar)
"""

"""
urls.py (App) — Mapa de Rutas de la Aplicación
=============================================
Define los enlaces (endpoints) disponibles para el usuario final.
Se organiza en:
  1. Sesión y Acceso: Dashboard, Nosotros, Login.
  2. Gestión de Modelos: Listado y Detalle.
  3. Operaciones Admin: Crear, Editar y Eliminar modelos.
  4. Inferencia: Interfaz para ejecutar predicciones ONNX.
"""
from django.urls import path, re_path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # ── Autenticación ────────────────────────────────────────────────────────
    # Página principal/Login — redirige al dashboard si ya está autenticado
    path('', views.index, name='index'),
    # Alias para la URL /login/ (apunta a la misma vista que la raíz)
    path('login/', views.index, name='login'),
    # Formulario de registro de nuevos usuarios
    path('register/', views.register, name='register'),
    # Verificación del código OTP enviado por e-mail (2FA)
    path('verify-2fa/', views.verify_2fa, name='verify_2fa'),

    # ── Recuperación de Contraseña (Auth Views nativas) ─────────────────────
    path('password_reset/', auth_views.PasswordResetView.as_view(
        template_name='auth_recover/password_reset_form.html',
        email_template_name='auth_recover/password_reset_email.html'
    ), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='auth_recover/password_reset_done.html'), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='auth_recover/password_reset_confirm.html'), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name='auth_recover/password_reset_complete.html'), name='password_reset_complete'),

    # ── Secciones principales ────────────────────────────────────────────────
    # Panel principal del usuario (requiere login)
    path('dashboard/', views.dashboard, name='dashboard'),
    # Página "Nosotros" / información del semillero (requiere login)
    path('nosotros/', views.nosotros, name='nosotros'),
    # Cierra la sesión activa y redirige al login
    path('logout/', views.logout_view, name='logout'),

    # ── Módulo de Modelos ML ─────────────────────────────────────────────────
    # Lista/catálogo de todos los modelos registrados (con búsqueda y filtros)
    path('modelos/', views.modelos_lista, name='modelos_lista'),
    # Formulario para registrar un nuevo modelo ML
    path('modelos/crear/', views.modelo_crear, name='modelo_crear'),
    # Vista de detalle de un modelo específico, identificado por su PK (ID)
    path('modelos/<int:pk>/', views.modelo_detalle, name='modelo_detalle'),
    # Página de inferencia: sube imagen → obtiene predicción del modelo ONNX
    path('modelos/<int:pk>/ejecutar/', views.modelo_ejecutar, name='modelo_ejecutar'),
    # Editar datos de un modelo existente (solo admin)
    path('modelos/<int:pk>/editar/', views.modelo_editar, name='modelo_editar'),
    # Eliminar un modelo del catálogo (solo admin, acepta solo POST)
    path('modelos/<int:pk>/eliminar/', views.modelo_eliminar, name='modelo_eliminar'),

    # ── Historial de Ejecuciones ─────────────────────────────────────────────
    path('historial/', views.historial_lista, name='historial_lista'),
    path('historial/<int:pk>/', views.historial_detalle, name='historial_detalle'),
    path('historial/<int:pk>/eliminar/', views.historial_eliminar, name='historial_eliminar'),

    # Catch-all route to protect against invalid URLs
    re_path(r'^.*$', views.ruta_no_encontrada),
]
