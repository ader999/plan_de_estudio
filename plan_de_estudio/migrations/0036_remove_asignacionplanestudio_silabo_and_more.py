# Generated by Django 4.2.3 on 2024-10-10 00:32

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("plan_de_estudio", "0035_silabo_completado"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="asignacionplanestudio",
            name="silabo",
        ),
        migrations.RemoveField(
            model_name="silabo",
            name="completado",
        ),
        migrations.AddField(
            model_name="asignacionplanestudio",
            name="completado",
            field=models.BooleanField(default=False),
        ),
    ]
