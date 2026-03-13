from .models import CredencialesGoogle

def google_classroom_context(request):
    """
    Agrega variables globales de contexto relacionadas con la cuenta de Google vinculada.
    """
    is_google_linked = False
    google_profile_picture = None

    if request.user.is_authenticated:
        try:
            credenciales = CredencialesGoogle.objects.get(usuario=request.user)
            is_google_linked = True
            google_profile_picture = credenciales.foto_perfil
        except CredencialesGoogle.DoesNotExist:
            pass

    return {
        'is_google_linked': is_google_linked,
        'google_profile_picture': google_profile_picture
    }
