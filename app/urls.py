from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('login/', views.index, name='login'),
    path('register/', views.register, name='register'),
    path('verify-2fa/', views.verify_2fa, name='verify_2fa'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('nosotros/', views.nosotros, name='nosotros'),
    path('logout/', views.logout_view, name='logout'),
    # Módulo de Modelos ML
    path('modelos/', views.modelos_lista, name='modelos_lista'),
    path('modelos/crear/', views.modelo_crear, name='modelo_crear'),
    path('modelos/<int:pk>/', views.modelo_detalle, name='modelo_detalle'),
    path('modelos/<int:pk>/ejecutar/', views.modelo_ejecutar, name='modelo_ejecutar'),
]