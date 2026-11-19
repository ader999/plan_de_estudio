from django.db import migrations, models
from django.utils import timezone
import plan_de_estudio.trimestre_utils


def _codigo_desde_fecha(fecha):
    if fecha is None:
        ref = timezone.localdate()
    else:
        ref = timezone.localtime(fecha).date() if timezone.is_aware(fecha) else fecha.date()
    mes = ref.month
    year = ref.year
    if 3 <= mes <= 5:
        return f"{year}-I"
    if 6 <= mes <= 8:
        return f"{year}-II"
    if 9 <= mes <= 11:
        return f"{year}-III"
    if mes == 12:
        return f"{year}-IV"
    return f"{year - 1}-IV"


def poblar_trimestre_lectivo_existente(apps, schema_editor):
    AsignacionPlanEstudio = apps.get_model('plan_de_estudio', 'AsignacionPlanEstudio')
    actualizaciones = []
    for asignacion in AsignacionPlanEstudio.objects.all().only('id', 'fecha_asignacion', 'trimestre_lectivo'):
        if not asignacion.trimestre_lectivo:
            asignacion.trimestre_lectivo = _codigo_desde_fecha(asignacion.fecha_asignacion)
            actualizaciones.append(asignacion)
    if actualizaciones:
        AsignacionPlanEstudio.objects.bulk_update(actualizaciones, ['trimestre_lectivo'], batch_size=500)


class Migration(migrations.Migration):

    dependencies = [
        ('plan_de_estudio', '0022_configuracionsistema_mostrar_ranking_docentes'),
    ]

    operations = [
        migrations.AddField(
            model_name='asignacionplanestudio',
            name='trimestre_lectivo',
            field=models.CharField(
                blank=True,
                help_text='Trimestre y año lectivo exacto al que pertenece esta asignación.',
                max_length=20,
                null=True,
                validators=[plan_de_estudio.trimestre_utils.validar_trimestre_lectivo],
                verbose_name='Trimestre lectivo',
            ),
        ),
        migrations.RunPython(
            poblar_trimestre_lectivo_existente,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name='asignacionplanestudio',
            name='trimestre_lectivo',
            field=models.CharField(
                help_text='Trimestre y año lectivo exacto al que pertenece esta asignación.',
                max_length=20,
                validators=[plan_de_estudio.trimestre_utils.validar_trimestre_lectivo],
                verbose_name='Trimestre lectivo',
            ),
        ),
    ]
