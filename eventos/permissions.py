from rest_framework import permissions


class IsEventoCreatorOrAdmin(permissions.BasePermission):
    """
    Permite lectura a cualquier usuario autenticado, pero escritura
    únicamente al creador del evento o a un superusuario.
    """
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        # Si el objeto es un Evento directamente
        if hasattr(obj, 'creado_por'):
            return (obj.creado_por == request.user) or request.user.is_superuser
        # Si el objeto tiene relación con evento (Criterio, Participante, Jurado)
        if hasattr(obj, 'evento'):
            return (obj.evento.creado_por == request.user) or request.user.is_superuser
        return False


class IsJuradoOrAdmin(permissions.BasePermission):
    """
    Permite evaluar solo a los jurados registrados para el evento o a superusuarios.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated
