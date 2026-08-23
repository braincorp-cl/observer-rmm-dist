# Feature 041 keep-awake-geocerca (T006): cadencia geo apretada fuera de la cerca.
# AddField aditivo; default 5 (minutos). El agente aplica piso de 300 s.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0064_coresettings_lost_mode_alarm_enabled_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='coresettings',
            name='geo_geofence_interval_min',
            field=models.PositiveIntegerField(default=5),
        ),
    ]
