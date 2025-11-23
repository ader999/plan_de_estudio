from django.core.management.base import BaseCommand
from plan_de_estudio.email_utils import enviar_correos_plan_incompleto

class Command(BaseCommand):
    help = 'Envía correos electrónicos a los usuarios con planes de estudio incompletos.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Iniciando el envío de recordatorios...'))
        
        try:
            cantidad = enviar_correos_plan_incompleto()
            if cantidad > 0:
                self.stdout.write(self.style.SUCCESS(f'Se enviaron {cantidad} correos exitosamente.'))
            else:
                self.stdout.write(self.style.WARNING('No se encontraron usuarios con planes incompletos o no se pudo enviar ningún correo.'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Ocurrió un error al ejecutar el comando: {str(e)}'))
