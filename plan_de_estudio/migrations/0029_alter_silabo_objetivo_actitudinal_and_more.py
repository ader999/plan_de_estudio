# Generated by Django 4.2.3 on 2023-09-21 20:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('plan_de_estudio', '0028_remove_silabo_objetivos_silabo_objetivo_actitudinal_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='silabo',
            name='objetivo_actitudinal',
            field=models.TextField(verbose_name='Objetivo Actitudinal'),
        ),
        migrations.AlterField(
            model_name='silabo',
            name='objetivo_conceptual',
            field=models.TextField(verbose_name='Objetivo Conceptual'),
        ),
        migrations.AlterField(
            model_name='silabo',
            name='objetivo_procedimental',
            field=models.TextField(verbose_name='Objetivo Procedimental'),
        ),
    ]
