# Feature 030 · modo perdido/robado (ADR-025).
#
# Dos permisos separados: operar el caso y ver la evidencia. El default es False
# en los dos, mismo criterio que la 0042: encender de golpe una capacidad nueva
# para todos los roles existentes sería un cambio de postura de seguridad
# silencioso, y acá además hay material personal de por medio.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0042_role_endpoint_response_perms"),
    ]

    operations = [
        migrations.AddField(
            model_name="role",
            name="can_manage_lost_mode",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="role",
            name="can_view_lost_evidence",
            field=models.BooleanField(default=False),
        ),
    ]
