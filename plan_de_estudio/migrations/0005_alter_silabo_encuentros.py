# Generated by Django 4.2.3 on 2024-10-19 17:02

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("plan_de_estudio", "0004_alter_silabo_encuentros"),
    ]

    operations = [
        migrations.AlterField(
            model_name="silabo",
            name="encuentros",
            field=models.IntegerField(
                validators=[
                    django.core.validators.MinValueValidator(1),
                    django.core.validators.MaxValueValidator(12),
                ]
            ),
        ),
    ]
