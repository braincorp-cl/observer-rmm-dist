# Alerta de desinstalación manual del agente: nuevo valor en AlertType.
#
# Sólo cambia `choices`, que Django valida en Python y no toca el esquema de
# Postgres. Es una AlterField no-op a nivel de BD, pero tiene que existir para
# que `makemigrations --check` no quede sucio.
#
# ⚠️ Va sobre la 0015 (geofence, feature 026), que existe SÓLO en dist. En el hub
# esta misma alteración es la 0015: el número difiere entre repos a propósito
# (divergencia dist > hub, ADR-015). Los nombres de archivo sí coinciden para
# que se reconozcan como la misma alteración.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("alerts", "0015_alter_alert_alert_type"),
    ]

    operations = [
        migrations.AlterField(
            model_name="alert",
            name="alert_type",
            field=models.CharField(
                choices=[
                    ("availability", "Availability"),
                    ("check", "Check"),
                    ("task", "Task"),
                    ("custom", "Custom"),
                    ("geofence", "Geofence"),
                    ("agent_uninstall", "Agent Uninstall"),
                ],
                default="availability",
                max_length=20,
            ),
        ),
    ]
