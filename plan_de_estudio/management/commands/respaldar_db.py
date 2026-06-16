from django.core.management.base import BaseCommand
from plan_de_estudio.utils.db_backup import run_backup

class Command(BaseCommand):
    help = 'Genera una copia de seguridad de la base de datos (PostgreSQL dump con fallback a JSON) y la sube a MinIO.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Iniciando copia de seguridad...'))
        try:
            filepath, filename, _ = run_backup(send_email=False)
            self.stdout.write(self.style.SUCCESS(f'Copia de seguridad creada exitosamente en: {filepath}'))
            self.stdout.write(self.style.SUCCESS('Copia guardada exitosamente en MinIO (carpeta copias_db/).'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error al ejecutar la copia de seguridad: {str(e)}'))
