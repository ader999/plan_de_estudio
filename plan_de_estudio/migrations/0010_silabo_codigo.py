# Generated by Django 4.2.3 on 2023-09-10 07:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('plan_de_estudio', '0009_alter_silabo_asignatura'),
    ]

    operations = [
        migrations.AddField(
            model_name='silabo',
            name='codigo',
            field=models.CharField(default=2020, max_length=10),
            preserve_default=False,
        ),
    ]
