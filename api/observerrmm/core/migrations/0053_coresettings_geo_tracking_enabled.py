# Feature 023 (geolocalización de activos): interruptor GLOBAL de la flota.
# Migración ADITIVA (solo AddField con default) — no toca columnas existentes,
# por lo que no puede romper el INSERT/UPDATE por SQL raw de natsapi (DT-002).
# Apagado por defecto: activar la geolocalización es una decisión explícita.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0052_alter_coresettings_mesh_device_group'),
    ]

    operations = [
        migrations.AddField(
            model_name='coresettings',
            name='geo_tracking_enabled',
            field=models.BooleanField(default=False),
        ),
    ]
