# Feature 049-B: resumen diario de actividad por agente (lo sube el agente 2.17.4+).
# CreateModel aditivo; no toca tablas existentes.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("agents", "0068_agent_outside_geofence"),
    ]

    operations = [
        migrations.CreateModel(
            name="AgentActivityDaily",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("date", models.DateField()),
                ("data", models.JSONField(default=dict)),
                ("partial", models.BooleanField(default=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                (
                    "agent",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="activity_days",
                        to="agents.agent",
                    ),
                ),
            ],
        ),
        migrations.AlterUniqueTogether(
            name="agentactivitydaily",
            unique_together={("agent", "date")},
        ),
    ]
