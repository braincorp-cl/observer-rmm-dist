# Feature 041 keep-awake-geocerca (T005): estado "fuera de geocerca" per-agente.
# AddField aditivo; el default False cubre todas las filas existentes (sin backfill).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('agents', '0067_lostmodestate_cascade_alarm_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='agent',
            name='outside_geofence',
            field=models.BooleanField(default=False),
        ),
    ]
