# Feature 049-B2: monitoreo de actividad por equipo (tri-estado, nulo = hereda).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("agents", "0069_agentactivitydaily"),
    ]

    operations = [
        migrations.AddField(
            model_name="agent",
            name="activity_monitoring",
            field=models.BooleanField(blank=True, default=None, null=True),
        ),
    ]
