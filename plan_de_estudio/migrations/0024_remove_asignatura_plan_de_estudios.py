# Generated by Django 4.2.3 on 2023-09-17 16:08

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('plan_de_estudio', '0023_alter_plan_de_estudio_cr_alter_plan_de_estudio_pc_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='asignatura',
            name='plan_de_estudios',
        ),
    ]
