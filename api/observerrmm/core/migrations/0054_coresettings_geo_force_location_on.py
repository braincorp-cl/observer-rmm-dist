# Feature 023 (geolocalización de activos) · gap 3: force-on del sensor de
# ubicación/radio WiFi en el endpoint. Migración ADITIVA (solo AddField con
# default) — no toca columnas existentes, no puede romper el SQL raw de natsapi
# (DT-002). Apagado por defecto: forzar el endpoint es una decisión explícita.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0053_coresettings_geo_tracking_enabled'),
    ]

    operations = [
        migrations.AddField(
            model_name='coresettings',
            name='geo_force_location_on',
            field=models.BooleanField(default=False),
        ),
    ]
