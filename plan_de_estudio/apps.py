from django.apps import AppConfig

class PlanDeEstudioConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'plan_de_estudio'

    def ready(self):
        import plan_de_estudio.signals
