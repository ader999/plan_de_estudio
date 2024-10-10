# Generated by Django 4.2.3 on 2024-10-07 21:01

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("plan_de_estudio", "0032_estudio_independiente_enlace"),
    ]

    operations = [
        migrations.CreateModel(
            name="AsignacionPlanEstudio",
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
                (
                    "plan_tematico",
                    models.FileField(
                        blank=True, null=True, upload_to="planes_tematicos/"
                    ),
                ),
                ("fecha_asignacion", models.DateTimeField(auto_now_add=True)),
                (
                    "plan_de_estudio",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="plan_de_estudio.plan_de_estudio",
                    ),
                ),
                (
                    "usuario",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "unique_together": {("usuario", "plan_de_estudio")},
            },
        ),
    ]