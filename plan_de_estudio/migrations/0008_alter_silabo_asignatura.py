# Generated by Django 4.2.3 on 2023-09-08 23:13

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('plan_de_estudio', '0007_alter_silabo_eje_transversal_alter_silabo_fecha_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='silabo',
            name='asignatura',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='plan_de_estudio.plan_de_estudio', verbose_name='Pla de estudio'),
        ),
    ]
