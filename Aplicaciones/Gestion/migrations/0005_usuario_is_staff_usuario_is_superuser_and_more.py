# Generated by Django 5.0.6 on 2024-07-28 22:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Gestion', '0004_remove_vehiculo_chasis_veh'),
    ]

    operations = [
        migrations.AddField(
            model_name='usuario',
            name='is_staff',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='usuario',
            name='is_superuser',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='usuario',
            name='last_login',
            field=models.DateTimeField(blank=True, null=True, verbose_name='last login'),
        ),
    ]
