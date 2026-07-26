# Feature 026 (geocerca por sitio): interruptor global + radio de la geocerca.
# Migración ADITIVA (solo AddField con default) — no toca columnas existentes, no
# puede romper el SQL raw de natsapi (DT-002). Apagado por defecto: encenderlo en una
# flota que ya reporta ubicación puede levantar un lote de alertas de golpe (sitios
# asignados de forma nominal), así que es una decisión explícita del operador.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0054_coresettings_geo_force_location_on"),
    ]

    operations = [
        migrations.AddField(
            model_name="coresettings",
            name="geo_geofence_enabled",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="coresettings",
            name="geo_geofence_radius_m",
            field=models.PositiveIntegerField(default=1000),
        ),
    ]
