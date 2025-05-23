# Generated by Django 5.1.7 on 2025-04-09 04:15

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0025_alter_car_license_plate_alter_car_model'),
    ]

    operations = [
        migrations.AddField(
            model_name='dealer',
            name='user',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='user',
            name='role',
            field=models.CharField(blank=True, choices=[('customer', 'Customer'), ('concierge', 'Concierge'), ('dealer', 'Dealer'), ('owner', 'Owner')], max_length=20, null=True),
        ),
    ]
