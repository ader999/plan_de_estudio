from .models import CredencialesGoogle, ConfiguracionSistema


def google_classroom_context(request):
    """
    Agrega variables globales de contexto relacionadas con la cuenta de Google vinculada
    y parámetros globales del sistema.
    """
    is_google_linked = False
    google_profile_picture = None

    if request.user.is_authenticated:
        try:
            credenciales = Creden…
