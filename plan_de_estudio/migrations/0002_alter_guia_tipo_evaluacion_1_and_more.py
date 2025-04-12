# Generated by Django 4.2.3 on 2025-04-11 14:40

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("plan_de_estudio", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="guia",
            name="tipo_evaluacion_1",
            field=models.CharField(
                choices=[
                    ("Diagnóstica", "Diagnóstica"),
                    ("Formativa", "Formativa"),
                    ("Sumativa", "Sumativa"),
                ],
                max_length=100,
                verbose_name="Tipo evaluación 1",
            ),
        ),
        migrations.AlterField(
            model_name="guia",
            name="tipo_evaluacion_2",
            field=models.CharField(
                choices=[
                    ("Diagnóstica", "Diagnóstica"),
                    ("Formativa", "Formativa"),
                    ("Sumativa", "Sumativa"),
                ],
                max_length=100,
                verbose_name="Tipo evaluación 2",
            ),
        ),
        migrations.AlterField(
            model_name="guia",
            name="tipo_evaluacion_3",
            field=models.CharField(
                choices=[
                    ("Diagnóstica", "Diagnóstica"),
                    ("Formativa", "Formativa"),
                    ("Sumativa", "Sumativa"),
                ],
                max_length=100,
                verbose_name="Tipo evaluación 3",
            ),
        ),
        migrations.AlterField(
            model_name="guia",
            name="tipo_evaluacion_4",
            field=models.CharField(
                choices=[
                    ("Diagnóstica", "Diagnóstica"),
                    ("Formativa", "Formativa"),
                    ("Sumativa", "Sumativa"),
                ],
                max_length=200,
                verbose_name="Tipo evaluación 4",
            ),
        ),
    ]
