import os
import time
import resend
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from .models import AsignacionPlanEstudio

# Configurar API Key de Resend
resend.api_key = os.environ.get("RESEND")

def enviar_correos_plan_incompleto():
    """
    Envía correos electrónicos a los usuarios que tienen menos de 11 sílabos o guías creadas
    usando la API de Resend.
    """
    if not resend.api_key:
        print("Error: La variable de entorno RESEND no está configurada.")
        return 0

    # Filtrar asignaciones con planes incompletos
    asignaciones_incompletas = AsignacionPlanEstudio.objects.filter(
        silabos_creados__lt=11
    ) | AsignacionPlanEstudio.objects.filter(
        guias_creadas__lt=11
    )
    
    # Eliminar duplicados
    asignaciones_incompletas = asignaciones_incompletas.distinct()

    correos_enviados = 0

    for asignacion in asignaciones_incompletas:
        usuario = asignacion.usuario
        email_usuario = usuario.email

        if not email_usuario:
            continue

        context = {
            'nombre_usuario': usuario.get_full_name() or usuario.username,
            'asignatura': asignacion.plan_de_estudio.asignatura.nombre,
            'silabos_creados': asignacion.silabos_creados,
            'guias_creadas': asignacion.guias_creadas,
        }

        html_message = render_to_string('emails/recordatorio_plan.html', context)
        subject = 'Recordatorio: Plan de Estudio Incompleto'

        try:
            r = resend.Emails.send({
                "from": "planeauml@codeader.com",
                "to": email_usuario,
                "subject": subject,
                "html": html_message
            })
            print(f"Correo enviado a {email_usuario}. ID: {r.get('id')}")
            correos_enviados += 1
            # Esperar 1 segundo para respetar el límite de velocidad de Resend (2 req/s)
            time.sleep(1)
        except Exception as e:
            print(f"Error al enviar correo a {email_usuario}: {e}")

    return correos_enviados


