from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import api_views

router = DefaultRouter()
router.register(r'eventos', api_views.EventoViewSet, basename='api_evento')

app_name = 'eventos_api'

urlpatterns = [
    # Autenticación y Perfil
    path('auth/login/', api_views.api_login, name='api_login'),
    path('auth/logout/', api_views.api_logout, name='api_logout'),
    path('auth/me/', api_views.api_me, name='api_me'),
    path('auth/usuarios/', api_views.api_usuarios_disponibles, name='api_usuarios'),
    path('auth/usuarios-disponibles/<int:evento_id>/', api_views.api_usuarios_disponibles, name='api_usuarios_disponibles'),

    # Criterios individuales
    path('criterios/<int:criterio_id>/', api_views.api_criterio_detail, name='api_criterio_detail'),

    # Participantes individuales
    path('participantes/<int:participante_id>/', api_views.api_participante_detail, name='api_participante_detail'),

    # Jurados individuales
    path('jurados/<int:jurado_id>/', api_views.api_jurado_detail, name='api_jurado_detail'),

    # Rutas del Router (Eventos CRUD + acciones anidadas)
    path('', include(router.urls)),
]
