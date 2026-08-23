# Feature 041 keep-awake-geocerca (T024): toggle global del baseline keep-awake.
# AddField aditivo; default True (ON por omisión, decisión de producto ronda 3).
# Encadena sobre 0065 para no dejar dos hojas de migración en core.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0065_coresettings_geo_geofence_interval_min'),
    ]

    operations = [
        migrations.AddField(
            model_name='coresettings',
            name='keep_awake_baseline_enabled',
            field=models.BooleanField(default=True),
        ),
    ]
