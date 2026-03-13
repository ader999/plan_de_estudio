from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import AsignacionPlanEstudio
import threading
from .services.google_classroom import crear_clase_e_invitar_maestro

@receiver(post_save, sender=AsignacionPlanEstudio)
def asegurar_curso_classroom(sender, instance, created, **kwargs):
    """
    Señal que intercepta el guardado de una AsignacionPlanEstudio.
    Si se acaba de crear la asignación y no tiene `curso_classroom_id`,
    se invoca a la API de Classroom de forma asíncrona para no bloquear.
    """
    if created and not instance.curso_classroom_id:
        # Se ejecuta asincrónicamente para no demorar el response del request
        thread = threading.Thread(target=crear_clase_e_invitar_maestro, args=(instance,))
        thread.start()
