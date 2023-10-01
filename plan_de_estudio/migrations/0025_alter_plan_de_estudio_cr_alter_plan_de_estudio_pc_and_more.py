# Generated by Django 4.2.3 on 2023-09-21 02:24

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('plan_de_estudio', '0024_remove_asignatura_plan_de_estudios'),
    ]

    operations = [
        migrations.AlterField(
            model_name='plan_de_estudio',
            name='cr',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='cr_set', to='plan_de_estudio.asignatura'),
        ),
        migrations.AlterField(
            model_name='plan_de_estudio',
            name='pc',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='pc_set', to='plan_de_estudio.asignatura'),
        ),
        migrations.AlterField(
            model_name='plan_de_estudio',
            name='pr',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='pr_set', to='plan_de_estudio.asignatura'),
        ),
    ]
