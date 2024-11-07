# Generated by Django 4.2.3 on 2024-11-07 21:00

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("plan_de_estudio", "0007_alter_silabo_descripcion_estrategia_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="PlanTematico",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("nombre_dela_unidad", models.CharField(max_length=255)),
                ("clases_teoricas_semanales", models.CharField(max_length=255)),
                ("clases_teoricas_continuas", models.CharField(max_length=255)),
                (
                    "tct",
                    models.IntegerField(
                        validators=[
                            django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(12),
                        ]
                    ),
                ),
                ("clases_practicas_laboratorio", models.CharField(max_length=255)),
                ("clases_practicas_campo_trabajo", models.CharField(max_length=255)),
                ("clases_practicas_teoria", models.CharField(max_length=255)),
                ("clases_practicas_visitas_tc", models.CharField(max_length=255)),
                (
                    "tcp",
                    models.IntegerField(
                        validators=[
                            django.core.validators.MinValueValidator(2),
                            django.core.validators.MaxValueValidator(8),
                        ]
                    ),
                ),
                (
                    "evaluacion_final_examen",
                    models.IntegerField(
                        validators=[
                            django.core.validators.MinValueValidator(0),
                            django.core.validators.MaxValueValidator(100),
                        ]
                    ),
                ),
                (
                    "evaluacion_final_trabajo_clase",
                    models.IntegerField(
                        validators=[
                            django.core.validators.MinValueValidator(0),
                            django.core.validators.MaxValueValidator(100),
                        ]
                    ),
                ),
                (
                    "evaluacion_final_participacion_clase",
                    models.IntegerField(
                        validators=[
                            django.core.validators.MinValueValidator(0),
                            django.core.validators.MaxValueValidator(100),
                        ]
                    ),
                ),
                ("te", models.IntegerField()),
                ("thp", models.IntegerField()),
                ("ti", models.IntegerField()),
                ("th", models.IntegerField()),
            ],
        ),
    ]
